"""Load a calibrated, namespaced pair of native six-axis models."""

from copy import deepcopy
from dataclasses import dataclass
from math import atan2
import xml.etree.ElementTree as XML

import mujoco
import numpy as np


ARMS = ('left', 'right')


def number(value, *, positive=False):
    if type(value) not in (int, float) or not np.isfinite(value) or (positive and value <= 0):
        raise ValueError('invalid dimension or nonfinite number')
    return float(value)


def vector(value, length, *, positive=False):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError('unexpected vector shape')
    return np.asarray([number(x, positive=positive) for x in value])


def positive_int(value, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError('expected an integer within the commissioned horizon')
    return value


def rotation(quaternion):
    q = np.asarray(quaternion, dtype=float)
    size = np.linalg.norm(q)
    if not size or not np.isfinite(size):
        raise ValueError('invalid quaternion')
    result = np.zeros(9)
    mujoco.mju_quat2Mat(result, q/size)
    return result.reshape(3, 3)


def quat(matrix):
    result = np.zeros(4)
    mujoco.mju_mat2Quat(result, np.ascontiguousarray(matrix).ravel())
    return result if result[0] >= 0 else -result


def transform(p, r):
    result = np.eye(4)
    result[:3, :3], result[:3, 3] = r, p
    return result


def pose(value):
    p = vector(value['translation_m'], 3)
    q = vector(value['quaternion_xyzw'], 4)
    return transform(p, rotation(q[[3,0,1,2]]))


def encoded(matrix):
    return {'translation_m': matrix[:3, 3].tolist(), 'quaternion_xyzw': quat(matrix[:3, :3])[[1,2,3,0]].tolist()}


def inverse(matrix):
    r = matrix[:3, :3].T
    return transform(-r @ matrix[:3, 3], r)


def angular_delta(target, current):
    q = quat(target @ current.T)
    axis = q[1:]
    radius = np.linalg.norm(axis)
    return axis * (2.*atan2(radius, q[0])/radius) if radius > 1e-14 else axis*2.


def as_text(values):
    return ' '.join(str(float(x)) for x in values)


def xml_pose(node):
    return transform(np.fromstring(node.get('pos', '0 0 0'), sep=' '),
                     rotation(np.fromstring(node.get('quat', '1 0 0 0'), sep=' ')))


def set_pose(node, value):
    node.set('pos', as_text(value[:3, 3]))
    node.set('quat', as_text(quat(value[:3, :3])))


@dataclass(frozen=True)
class Assembly:
    model: mujoco.MjModel
    geoms: tuple[int, ...]
    fixtures: tuple[int, ...]
    payload: int
    weld: dict
    sites: dict
    owner_sites: dict
    offsets: dict
    pairs: tuple
    ranges: np.ndarray


def assemble(robot_xml, frames, payload, fixtures):
    """Build a public calibrated model with two sites per physically grasped part."""
    root = XML.fromstring(robot_xml)
    world, actuators = root.find('worldbody'), root.find('actuator')
    source = world.find('body')
    motors = list(actuators)
    world.remove(source)
    actuators.clear()
    keyframe = root.find('keyframe')
    if keyframe is not None:
        root.remove(keyframe)
    root.find('option').set('timestep', '.005')
    offsets = {side: pose(payload['object_from_grasp'][side]) for side in ARMS}
    payload_dims = vector(payload['half_size_m'], 3, positive=True)
    mass = number(payload['mass_kg'], positive=True)
    if np.max(payload_dims)>.42 or any(np.linalg.norm(value[:3,3])>.48 for value in offsets.values()):
        raise ValueError('payload geometry exceeds the commissioned holder envelope')
    for side in ARMS:
        body = deepcopy(source)
        set_pose(body, pose(frames[side]['world_from_base']) @ xml_pose(source))
        for node in body.iter():
            if 'name' in node.attrib:
                node.set('name', side+'_'+node.get('name'))
        wrist = body.find(f".//body[@name='{side}_wrist_3_link']")
        flange = wrist.find(f"site[@name='{side}_attachment_site']")
        marker = XML.SubElement(wrist, 'site', name=f'{side}_grasp', size='.005')
        offset = pose(frames[side]['flange_from_marker'])
        if np.linalg.norm(offset[:3,3])>.30:
            raise ValueError('tool exceeds commissioned flange envelope')
        set_pose(marker, xml_pose(flange) @ offset)
        world.append(body)
        for motor in motors:
            drive = deepcopy(motor)
            for key in ('name', 'joint'):
                drive.set(key, side+'_'+drive.get(key))
            actuators.append(drive)
    part = XML.SubElement(world, 'body', name='payload')
    XML.SubElement(part, 'freejoint', name='payload_free')
    XML.SubElement(part, 'geom', name='payload_box', type='box', size=as_text(payload_dims), mass=str(mass))
    equality = XML.SubElement(root, 'equality')
    for side in ARMS:
        handle = XML.SubElement(part, 'site', name=f'payload_{side}', size='.005')
        set_pose(handle, offsets[side])
        XML.SubElement(equality, 'weld', name=f'hold_{side}', site1=f'{side}_grasp', site2=f'payload_{side}',
                       active='false', solref='.018 1', torquescale='.24')
    for index, fixture in enumerate(fixtures):
        node = XML.SubElement(world, 'geom', name=f'fixture_{index}', type='box',
                              size=as_text(vector(fixture['half_size_m'], 3, positive=True)))
        set_pose(node, pose(fixture['world_from_box']))
    model = mujoco.MjModel.from_xml_string(XML.tostring(root, encoding='unicode'))
    model.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_NATIVECCD)
    if model.nq != 19 or model.nu != 12:
        raise ValueError('expected two six-axis UR5e models and one free payload')
    geoms = tuple(idx for idx in range(model.ngeom) if model.geom(idx).name.startswith(('left_', 'right_')))
    boxes = tuple(model.geom(f'fixture_{i}').id for i in range(len(fixtures)))
    payload_id = model.geom('payload_box').id
    pairs = []
    for p, a in enumerate(geoms):
        for b in geoms[p+1:]:
            first, second = int(model.geom_bodyid[a]), int(model.geom_bodyid[b])
            if first != second and not (model.body_parentid[first] == second or model.body_parentid[second] == first):
                pairs.append((a,b))
        pairs.extend((a,b) for b in (*boxes,payload_id))
    pairs.extend((payload_id,b) for b in boxes)
    return Assembly(model, geoms, boxes, payload_id,
                    {side:model.equality(f'hold_{side}').id for side in ARMS},
                    {side:model.site(f'{side}_grasp').id for side in ARMS},
                    {side:model.site(f'payload_{side}').id for side in ARMS}, offsets, tuple(pairs),
                    model.jnt_range[:12].copy())


class Geometry:
    """Evaluate independent physical geometry for planning at calibrated coordinates."""

    def __init__(self, assembly):
        self.cell = assembly
        self.data = mujoco.MjData(assembly.model)
        self.closest = np.zeros(6)

    def sites(self, q):
        self.data.qpos[:12] = q
        self.data.qpos[12:] = [0,0,0,1,0,0,0]
        mujoco.mj_kinematics(self.cell.model, self.data)

    def location(self, side):
        idx = self.cell.sites[side]
        return transform(self.data.site_xpos[idx].copy(), self.data.site_xmat[idx].reshape(3, 3).copy())

    def payload_pose(self, side):
        return self.location(side) @ inverse(self.cell.offsets[side])

    def distance(self, q, owner, margin):
        self.sites(q)
        part = self.payload_pose(owner)
        self.data.qpos[12:15] = part[:3, 3]
        self.data.qpos[15:] = quat(part[:3, :3])
        mujoco.mj_kinematics(self.cell.model, self.data)
        # Geometric contact pairs are fixed by the declared collision model.
        minimum = .8
        for first,second in self.cell.pairs:
            distance = mujoco.mj_geomDistance(self.cell.model,self.data,first,second,.8,self.closest)
            minimum = min(minimum, distance)
            if minimum < margin:
                break
        return minimum

    def ik(self, arm, desired, guess):
        """Fit one end-effector in SE(3) with damped native world Jacobians."""
        active = slice(0, 6) if arm == 'left' else slice(6, 12)
        clip = self.cell.ranges[active]
        q = np.asarray(guess, dtype=float).copy()
        jacp, jacr = (np.zeros((3, self.cell.model.nv)) for _ in range(2))
        for _ in range(125):
            self.sites(q)
            current = self.location(arm)
            position = desired[:3, 3] - current[:3, 3]
            angle = angular_delta(desired[:3, :3], current[:3, :3])
            if np.linalg.norm(position) < 2.5e-4 and np.linalg.norm(angle) < .0025:
                return q[active].copy()
            mujoco.mj_comPos(self.cell.model, self.data)
            mujoco.mj_jacSite(self.cell.model, self.data, jacp, jacr, self.cell.sites[arm])
            jac = np.concatenate((jacp[:, active], .28*jacr[:, active]))
            residual = np.r_[position, .28*angle]
            update = jac.T @ np.linalg.solve(jac @ jac.T + .0012*np.eye(6), residual)
            q[active] = np.clip(q[active] + np.clip(update, -.2, .2), clip[:,0]+1e-5, clip[:,1]-1e-5)
        return None
