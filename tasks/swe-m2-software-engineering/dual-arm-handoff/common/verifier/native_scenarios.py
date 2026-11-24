"""Author measured native workcells and private full-pose transfer witnesses."""

from copy import deepcopy
from math import cos, sin
import xml.etree.ElementTree as ET

import mujoco
import numpy as np


SIDES = ('left','right')


def rotation_z(yaw):
    return np.array([[cos(yaw),-sin(yaw),0.],[sin(yaw),cos(yaw),0.],[0.,0.,1.]])


def xform(position, rotation):
    result = np.eye(4)
    result[:3,:3],result[:3,3] = rotation,position
    return result


def quaternion(matrix):
    target = np.zeros(4)
    mujoco.mju_mat2Quat(target, np.array(matrix,order='C').reshape(9))
    return target


def unroll(data):
    q = [data['quaternion_xyzw'][3], *data['quaternion_xyzw'][:3]]
    matrix = np.empty(9)
    mujoco.mju_quat2Mat(matrix, np.array(q)/np.linalg.norm(q))
    return xform(data['translation_m'], matrix.reshape(3,3))


def record(matrix):
    q=quaternion(matrix[:3,:3])
    return {'translation_m':matrix[:3,3].tolist(),'quaternion_xyzw':q[[1,2,3,0]].tolist()}


def site(data, index):
    return xform(data.site_xpos[index].copy(),data.site_xmat[index].reshape(3,3).copy())


def group(q):
    return dict(zip(SIDES,[q[:6].tolist(),q[6:].tolist()],strict=True))


def session(robot_xml, *, variant=0):
    """Plant calibration and useful task-space targets without supplying waypoint joints."""
    model=mujoco.MjModel.from_xml_string(robot_xml)
    data=mujoco.MjData(model)
    detector=model.site('attachment_site').id
    variations = [0., .077, -.062, .105]
    shift=variations[variant%4]
    bases={'left':xform([.014+shift,-.76,.005],rotation_z(.04+shift)),
           'right':xform([-.025,.79+shift,.03],rotation_z(np.pi-.062+shift))}
    markers={'left':xform([.006,-.012,.126],rotation_z(.16+shift)),
             'right':xform([-.014,.018,.119],rotation_z(-.12-shift))}

    def grip(side,q):
        data.qpos[:]=q
        mujoco.mj_kinematics(model,data)
        return bases[side] @ site(data,detector) @ markers[side]

    ql=np.array([-1.57+shift,-1.29,1.47,-1.60,-1.57,.20])
    qr=np.array([-1.57,-1.27+shift,1.46,-1.58,-1.50,-.20])
    left,right=grip('left',ql),grip('right',qr)
    x=right[:3,3]-left[:3,3]
    separation=np.linalg.norm(x)
    x/=separation
    y=np.cross([0.,0.,1.],x);y/=np.linalg.norm(y)
    z=np.cross(x,y)
    station=xform((left[:3,3]+right[:3,3])/2,np.column_stack((x,y,z)))
    offsets={'left':np.linalg.solve(station,left),'right':np.linalg.solve(station,right)}
    qstart=np.r_[ql+[-.32,.19,-.22,.16,.14,-.17],qr+[.23,.12,-.24,-.10,.16,.15]]
    qend=qr+[.37,-.14,.31,-.16,.14,.24]
    end=np.linalg.solve(offsets['right'].T,grip('right',qend).T).T
    payload={'mass_kg':.55+variant*.11,'half_size_m':[float(separation/2-.047),.026,.029],
             'object_from_grasp':{key:record(value) for key,value in offsets.items()}}
    fitted={'status':'ok','calibration':{arm:{'world_from_base':record(bases[arm]),
                                            'flange_from_marker':record(markers[arm]),'inliers':12} for arm in SIDES}}
    spec={'robot_xml':robot_xml,'calibration':fitted,'payload':payload,'fixtures':[],
          'handoff_object_poses':[record(station)],'destination':{'owner':'right','world_from_object':record(end)},
          'measured':{'tick':20+7*variant,'owner':'left','q':group(qstart),'dq':group(np.zeros(12))},
          'deadline_tick':2500+7*variant,'transfer_ticks':160,'clearance_m':.006,
          'speed_rad_s':[.65]*12,'acceleration_rad_s2':[1.8]*12}
    return spec,np.r_[ql,qr],np.r_[ql,qend]


def number_text(data):
    return ' '.join(map(str,data))


def applied_form(node,matrix):
    node.set('pos',number_text(matrix[:3,3]));node.set('quat',number_text(quaternion(matrix[:3,:3])))


def xml_transform(node):
    quaternion_raw=np.fromstring(node.get('quat','1 0 0 0'),sep=' ')
    reordered=quaternion_raw[[1,2,3,0]]
    return unroll({'translation_m':np.fromstring(node.get('pos','0 0 0'),sep=' '),'quaternion_xyzw':reordered})


class NativePlant:
    """Operate the actual native two-arm servo system and a free welded part."""

    def __init__(self, spec):
        root=ET.fromstring(spec['robot_xml'])
        root.find('option').set('timestep','.005')
        root.find('option').set('iterations','45')
        body=root.find('worldbody/body')
        world=root.find('worldbody');world.remove(body)
        root.remove(root.find('keyframe'))
        motor=root.find('actuator');mappings=list(motor);motor.clear()
        offsets=spec['payload']['object_from_grasp']
        part=ET.SubElement(world,'body',name='asset_payload')
        ET.SubElement(part,'freejoint',name='asset_free')
        ET.SubElement(part,'geom',name='asset_geom',type='box',size=number_text(spec['payload']['half_size_m']),
                      mass=str(spec['payload']['mass_kg']))
        equality=ET.SubElement(root,'equality');contact=ET.SubElement(root,'contact')
        for arm in SIDES:
            arm_calibration=spec['calibration']['calibration'][arm]
            chain=deepcopy(body)
            prefix=f'{arm}-native-'
            # Build each native body independently from the licensed single-arm tree.
            applied_form(chain,unroll(arm_calibration['world_from_base'])@xml_transform(body))
            for node in chain.iter():
                if 'name' in node.attrib:
                    node.set('name',prefix+node.get('name'))
            flange=chain.find(f".//site[@name='{prefix}attachment_site']")
            wrist=chain.find(f".//body[@name='{prefix}wrist_3_link']")
            hand=ET.SubElement(wrist,'site',name=f'hand_{arm}',size='.005')
            applied_form(hand,xml_transform(flange)@unroll(arm_calibration['flange_from_marker']))
            extension=ET.SubElement(part,'site',name=f'grasp_{arm}',size='.004')
            applied_form(extension,unroll(offsets[arm]))
            ET.SubElement(equality,'weld',name=f'lock_{arm}',site1=f'hand_{arm}',site2=f'grasp_{arm}',
                          active='false',solref='.010 1',solimp='.995 .999 .001',torquescale='1.5')
            world.append(chain)
            for old in mappings:
                item=deepcopy(old)
                item.set('joint',prefix+old.get('joint'))
                item.set('name',prefix+old.get('name'))
                motor.append(item)
        for i,fixture in enumerate(spec['fixtures']):
            obstacle=ET.SubElement(world,'geom',name=f'fixture_{i}',type='box',size=number_text(fixture['half_size_m']))
            applied_form(obstacle,unroll(fixture['world_from_box']))
        self.model=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
        self.model.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_NATIVECCD)
        self.data=mujoco.MjData(self.model)
        self.tick=spec['measured']['tick']
        self.model.opt.timestep=.005
        self.arm_names=tuple(name for arm in SIDES for name in [self.model.joint(k).name for k in range(self.model.njnt)]
                             if name.startswith(f'{arm}-native-'))
        self.joints=np.array([self.model.joint(name).qposadr[0] for name in self.arm_names])
        self.dofs=np.array([self.model.joint(name).dofadr[0] for name in self.arm_names])
        self.asset_idx=int(self.model.joint('asset_free').qposadr[0])
        self.asset_dof=int(self.model.joint('asset_free').dofadr[0])
        self.grippers={arm:self.model.site(f'hand_{arm}').id for arm in SIDES}
        self.payload_sites={arm:self.model.site(f'grasp_{arm}').id for arm in SIDES}
        self.weld={arm:self.model.equality(f'lock_{arm}').id for arm in SIDES}
        self.owner=spec['measured']['owner']
        self.allowed=set()
        self.status='valid'
        self.target=np.r_[*(spec['measured']['q'][arm] for arm in SIDES)].astype(float)
        self.data.qpos[self.joints]=self.target
        self.data.qvel[self.dofs]=np.r_[*(spec['measured']['dq'][arm] for arm in SIDES)]
        mujoco.mj_forward(self.model,self.data)
        start=site(self.data,self.grippers[self.owner])@np.linalg.inv(unroll(offsets[self.owner]))
        self.data.qpos[self.asset_idx:self.asset_idx+3]=start[:3,3]
        self.data.qpos[self.asset_idx+3:self.asset_idx+7]=quaternion(start[:3,:3])
        self.data.eq_active[self.weld[self.owner]]=True
        self.depth_limit=spec['clearance_m']
        mujoco.mj_forward(self.model,self.data)
        self.contact_peak=0
        self.max_tracking=0.
        self.max_speed=0.
        robot=[i for i in range(self.model.ngeom) if '-native-' in self.model.geom(i).name]
        payload=self.model.geom('asset_geom').id
        obstacles=[i for i in range(self.model.ngeom) if self.model.geom(i).name.startswith('fixture_')]
        pairs=[]
        for j,a in enumerate(robot):
            aa=int(self.model.geom_bodyid[a])
            for b in robot[j+1:]:
                bb=int(self.model.geom_bodyid[b])
                if aa!=bb and aa!=self.model.body_parentid[bb] and bb!=self.model.body_parentid[aa]:
                    pairs.append((a,b))
            pairs.extend((a,b) for b in [payload,*obstacles])
        self.distances=tuple(pairs+[(payload,b) for b in obstacles])
        self.clearance_seen=.8

    def object_pose(self):
        idx=self.model.body('asset_payload').id
        return xform(self.data.xpos[idx].copy(),self.data.xmat[idx].reshape(3,3).copy())

    def grasp_error(self,side):
        actual=site(self.data,self.grippers[side])
        target=site(self.data,self.payload_sites[side])
        q=quaternion(actual[:3,:3].T@target[:3,:3])
        return np.linalg.norm(actual[:3,3]-target[:3,3]),2*np.arctan2(np.linalg.norm(q[1:]),abs(q[0]))

    def readback(self):
        return {'tick':self.tick,'owner':self.owner,'q':group(self.data.qpos[self.joints]),
                'dq':group(self.data.qvel[self.dofs])}

    def step(self,position,velocity):
        """Use native servo torque with causal velocity and gravity feed-forward."""
        stiffness=self.model.actuator_gainprm[:,0]
        damp=-self.model.actuator_biasprm[:,2]
        self.data.ctrl[:]=np.clip(position+(damp*velocity+self.data.qfrc_bias[self.dofs])/stiffness,
                                  self.model.actuator_ctrlrange[:,0],self.model.actuator_ctrlrange[:,1])
        mujoco.mj_step(self.model,self.data)
        self.tick+=1
        self.max_tracking=max(self.max_tracking,float(np.max(abs(self.data.qpos[self.joints]-position))))
        self.max_speed=max(self.max_speed,float(np.max(abs(self.data.qvel[self.dofs]))))
        self.contact_peak=max(self.contact_peak,int(self.data.ncon))
        closest=min(mujoco.mj_geomDistance(self.model,self.data,a,b,.8,None) for a,b in self.distances)
        self.clearance_seen=min(self.clearance_seen,float(closest))
        return self.data.ncon==0 and closest>=self.depth_limit-1e-7 and np.all(np.isfinite(self.data.qpos))

    def exchange(self,new):
        """Switch physical possession only at an observed aligned resting grasp."""
        delta, angle=self.grasp_error(new)
        moving=max(abs(self.data.qvel[self.dofs]))
        if new==self.owner or max(moving,.0)>.17 or delta>.018 or angle>.055:
            return False
        self.data.eq_active[self.weld[self.owner]]=False
        self.data.eq_active[self.weld[new]]=True
        self.owner=new
        return True


def distance_pose(a,b):
    translation=float(np.linalg.norm(a[:3,3]-b[:3,3]))
    turn=quaternion(a[:3,:3].T@b[:3,:3])
    rotation=float(2*np.arctan2(np.linalg.norm(turn[1:]),abs(turn[0])))
    return translation,rotation


def within(a,b,linear=.018,rotation=.060):
    d,theta=distance_pose(a,b)
    return d<=linear and theta<=rotation


def animate(plant, command, spec, *, until=None):
    """Execute an issued motor primitive from current references without teleportation."""
    start,end=command.get('start'),command.get('end')
    if type(start) is not int or type(end) is not int or start!=plant.tick or not start<end<=spec['deadline_tick']:
        return False
    first=plant.target.copy()
    kind=command['kind']
    if kind=='transfer':
        if end-start!=spec['transfer_ticks'] or command.get('to')==plant.owner or until is not None:
            return False
        if command.get('to') not in SIDES:
            return False
        if not any(within(plant.object_pose(),unroll(pose),.036,.11) for pose in spec['handoff_object_poses']):
            return False
        for _ in range(end-start):
            if not plant.step(first,np.zeros(12)):
                return False
        return plant.exchange(command['to'])
    if kind not in ('move','brake'):
        return False
    dest=np.asarray([value for arm in SIDES for value in command['q'][arm]],dtype=float)
    if dest.shape!=(12,) or not np.isfinite(dest).all():
        return False
    actual=plant.data.qpos[plant.joints].copy()
    if np.max(abs(actual-first))>.035:
        return False
    bounds=np.array([plant.model.jnt_range[plant.model.joint(name).id] for name in plant.arm_names])
    if np.any(dest<bounds[:,0]) or np.any(dest>bounds[:,1]):
        return False
    seconds=(end-start)*plant.model.opt.timestep
    maxspeed=np.asarray(spec['speed_rad_s'])
    accel=np.asarray(spec['acceleration_rad_s2'])
    if kind=='brake':
        measured=plant.data.qvel[plant.dofs].copy()
        if not np.allclose(dest,actual+.5*seconds*measured,atol=.001,rtol=0) or np.any(abs(measured)/seconds>accel+1e-6):
            return False
        first=actual
        factor_v,factor_a=2,2
    else:
        factor_v,factor_a=1.5,6
    delta=dest-first
    if np.any(factor_v*np.abs(delta)/seconds>maxspeed+1e-7) or np.any(factor_a*np.abs(delta)/seconds**2>accel+1e-7):
        return False
    ticks=end-start if until is None else until-start
    if not 0<ticks<=end-start:
        return False
    for i in range(1,ticks+1):
        f=i/(end-start)
        phase=2*f-f*f if kind=='brake' else f*f*(3.-2.*f)
        slope=2.-2.*f if kind=='brake' else 6.*f*(1.-f)
        command_q=first+phase*delta
        if not plant.step(command_q,slope*delta/seconds):
            return False
        plant.target=command_q
    return True


def success(plant,spec):
    """Check native tool delivery and custody while preserving the actual continuous state."""
    endpoint=unroll(spec['destination']['world_from_object'])
    transforms=within(plant.object_pose(),endpoint,.027,.075)
    return (transforms and plant.owner==spec['destination']['owner'] and plant.tick<=spec['deadline_tick']
            and plant.contact_peak==0 and plant.max_tracking<.04 and plant.max_speed<.88)


def staging_case(robot_xml, *, variant=0, blocker=False, blocked=False):
    """Commission native authored station alternatives and hide their joint witnesses."""
    spec,station,_=session(robot_xml,variant=variant)
    first=unroll(spec['handoff_object_poses'][0])
    raised=first.copy()
    raised[:3,3]+=[.018,.018,.178]
    spec['handoff_object_poses'].append(record(raised))
    raised[:3,3]=first[:3,3]+[.04,.02,.14]
    spec['handoff_object_poses'][1]=record(raised)
    position=first[:3,3]-.75*spec['payload']['half_size_m'][0]*first[:3,0] if blocker else np.array([2.,1.8,.1])
    span=[.024,.026,.024]
    if blocked:
        spec['destination']['world_from_object']['translation_m'][0]=3.8
    spec['fixtures']=[{'half_size_m':span,'world_from_box':record(xform(position,np.eye(3)))}]
    return spec
