"""Measure navigation and frozen-actor ownership on a live native Go2 course."""

from collections import Counter, deque
from math import atan2, hypot
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET

import mujoco
import numpy as np

from locomotion_native import Expected, Plant, fixture_assets, make_manifest, numeric_fields, rotation
from transport import Stream, require


COURSES = (
    {'name':'switch-to-south-after-closure','side':1,'dark':False,'seed':506},
    {'name':'reflected-closure-with-retired-map','side':-1,'dark':False,'seed':814},
    {'name':'map-authority-loss-and-worker-restart','side':1,'dark':True,'seed':920},
)
BARRIER = (1.31,1.59,-.52,.52)


def lane_gate(side):
    return (1.31,1.63,side*1.36-.44,side*1.36+.44)


def course_model(spec, case, assets):
    """Create measured collision geometry around the frozen articulated robot."""
    model=ET.parse(assets/'go2-headless.xml').getroot()
    ET.SubElement(model,'option',timestep='0.005',integrator='implicitfast',solver='Newton',iterations='100')
    actuators=model.find('actuator')
    motors={child.get('joint'):child for child in actuators}
    actuators[:]=[motors[name] for name in spec['actuator_order']]
    world=model.find('worldbody')
    ET.SubElement(world,'geom',name='floor-0',type='plane',size='0 0 .05',friction='.95 .005 .0001')
    ET.SubElement(world,'geom',name='divider',type='box',size='.14 .52 .25',pos='1.45 0 .25')
    gate=ET.SubElement(world,'body',name='gate',mocap='true',pos=f"1.47 {-case['side']*1.36} .28")
    ET.SubElement(gate,'geom',name='lane_gate',type='box',size='.16 .44 .28')
    return mujoco.MjModel.from_xml_string(ET.tostring(model,encoding='unicode'))


class CoursePlant(Plant):
    """Observe collisions and clearance at the native integration rate."""

    def __init__(self,spec,case,assets):
        super().__init__(spec,case,assets,model=course_model(spec,case,assets))
        self.side=case['side']
        self.gate_id=self.model.body('gate').mocapid[0]
        self.barriers={self.model.geom('divider').id,self.model.geom('lane_gate').id}
        self.boxes=[BARRIER,lane_gate(-self.side)]
        self.extent=spec['course']['extent']
        self.clearance=float('inf')
        self.contacts_with_barriers=0

    def move_gate(self):
        self.boxes[1]=lane_gate(self.side)
        self.data.mocap_pos[self.gate_id]=[1.47,self.side*1.36,.28]
        mujoco.mj_forward(self.model,self.data)

    def measure(self):
        super().measure()
        x,y=self.data.qpos[:2]
        xmin,xmax,ymin,ymax=self.extent
        self.clearance=min(self.clearance,x-xmin,xmax-x,y-ymin,ymax-y)
        for lo,hi,bottom,top in self.boxes:
            self.clearance=min(self.clearance,hypot(max(lo-x,x-hi,0),max(bottom-y,y-top,0)))
        for index in range(self.data.ncon):
            report=self.data.contact[index]
            if self.barriers.intersection((report.geom1,report.geom2)):
                self.contacts_with_barriers+=1

    def observe_localization(self, tick):
        state=rotation(self.data.qpos[3:7])
        return {'capture_tick':tick,'position':self.data.qpos[:2].tolist(),
                'heading_rad':atan2(state[1,0],state[0,0]),'velocity':self.data.qvel[:2].tolist()}


def snapshot(revision,tick,boxes):
    return {'revision':revision,'capture_tick':tick,'valid_until_tick':tick+9,
            'obstacles':[list(rectangle) for rectangle in boxes]}


def run_course(app: Path, root: Path, **case):
    """Replay late map updates and measure whether the released actor completes the course."""
    assets=fixture_assets()
    config=make_manifest({**case,'terrain':'flat','fault':'route'},assets)
    actor=root/'frozen-policy.onnx'
    shutil.copy2(config['actor'],actor)
    actor.chmod(0o644)
    config['actor']=str(actor)
    config['course']={'extent':[-1.,5.,-2.15,2.15], 'goal':[3.93,case['side']*.19,case['side']*.28],
                      'footprint_radius_m':.46,'max_speed_mps':.56,'max_pose_age_ticks':7,
                      'max_map_age_ticks':12,'max_map_lease_ticks':11,'completion_tick':1449}
    plant=CoursePlant(config,{**case,'terrain':'flat','fault':'route'},assets)
    actor_check=Expected(config)
    target=np.array(config['course']['goal'])
    revision=41
    retired=None
    capture_queue=deque(maxlen=4)
    event_pose=None
    crossing=None
    modes=Counter()
    count_stopped=0
    restarted=False
    early_speed=None
    safe_speed=None
    accepted_revision=None
    blackout_begin=None
    dark=case['dark']
    with Stream(app,root/'wire',config,command='navigate') as process:
        for tick in range(config['course']['completion_tick']+1):
            if tick==94:
                x,y=plant.data.qpos[:2]
                speed=float(np.linalg.norm(plant.data.qvel[:2]))
                event_pose=[float(x),float(y),speed]
                retired=snapshot(revision,tick,plant.boxes)
                plant.move_gate()
                revision+=1
            if dark and blackout_begin is None and tick<94 and plant.data.qpos[0]>.25:
                physical_speed=float(np.linalg.norm(plant.data.qvel[:2]))
                if physical_speed>.27:
                    early_speed=physical_speed
                    blackout_begin=tick
            blackout=blackout_begin is not None and blackout_begin <= tick < blackout_begin+38
            current_map=None
            if not blackout:
                current_map=snapshot(revision,tick,plant.boxes)
                if retired and tick in (126,132):
                    current_map=retired|{'capture_tick':tick,'valid_until_tick':tick+8}
                else:
                    accepted_revision=revision
            capture_queue.append(plant.observe_localization(tick))
            localization=capture_queue[0]
            sensor=plant.observe(tick,plant.contacts(tick),None)
            sensor.pop('request')
            observation={**sensor,'localization':localization,'map':current_map}
            answer=process.push(observation)
            intent=answer['intent']
            require(answer.get('map_revision')==accepted_revision,'map epoch regressed or was not applied')
            require(intent['sequence']==tick and intent['valid_until_tick']==tick+1,'invalid navigation lease')
            twist=intent['velocity']
            require(isinstance(twist,list) and len(twist)==3 and all(np.isfinite(twist))
                    and hypot(*twist[:2]) <= .560001, 'navigation intent exceeded its speed envelope')
            require(answer['navigation'] in ('arrived','navigate','hold'),'invalid navigation status')
            if answer['navigation'] in ('arrived','hold'):
                require(twist==[0,0,0],'a stopped planner emitted motion')
            states=actor_check.reply({**sensor,'request':intent},plant.data.qpos[plant.qp],
                                     plant.data.qvel[plant.qv],rotation(plant.data.qpos[3:7]),
                                     plant.data.qvel[3:6])
            require(set(answer)==(set(states)|{'navigation','map_revision','intent'}),
                    'navigation reply has missing or undeclared fields')
            numeric_fields({key:answer[key] for key in states},states)
            if blackout and tick >= blackout_begin+10:
                require(answer['navigation']=='hold' and twist==[0,0,0],'an expired map granted motion')
            if blackout and tick==blackout_begin+19:
                process.restart()
                altered=observation|{'map':snapshot(revision+12,tick,plant.boxes)}
                rejected=process.push(altered)
                require(rejected=={'tick':tick,'mode':'rejected','lease':None,'support':[],
                                  'effective_twist':None,'action':None,'target_rad':None},
                        'an altered retry changed planning authority')
                require(process.push(observation)==answer,'navigation and actor receipt changed after worker death')
                restarted=True
            modes[answer['navigation']]+=1
            plant.advance(answer['target_rad'],tick,False)
            require(plant.contacts_with_barriers==0 and plant.clearance>=config['course']['footprint_radius_m'],
                    f'physical obstacle clearance failed at tick {tick}, minimum {plant.clearance:.3f} m')
            xy=plant.data.qpos[:2]
            if crossing is None and xy[0]>=1.52:
                crossing=float(xy[1])
            current=plant.observe_localization(tick)
            yaw_error=abs((current['heading_rad']-target[2]+np.pi)%(2*np.pi)-np.pi)
            error=float(np.linalg.norm(xy-target[:2]))
            speed=float(np.linalg.norm(plant.data.qvel[:2]))
            if blackout and tick==blackout_begin+31:
                safe_speed=speed
            if answer['navigation']=='arrived' and error<=.17 and yaw_error<=.16 and speed<.085:
                count_stopped+=1
            else:
                count_stopped=0
            if count_stopped>=22:
                break
    require(count_stopped>=22,
            f'robot did not complete the inspection dwell: pose {list(xy)}, error {error:.3f}, yaw {yaw_error:.3f}, '
            f'speed {speed:.3f}, modes {dict(modes)}, crossing {crossing}, clearance {plant.clearance:.3f}')
    require(crossing is not None and crossing*case['side']<-.90,'the inspected mission crossed the closed side')
    if dark:
        require(restarted and early_speed>.25 and safe_speed<.18,
                f'authority loss was not exercised while moving and followed by a stop: {early_speed}, {safe_speed}')
    return {'goal_error_m':error,'final_speed_mps':speed,'heading_error_rad':float(yaw_error),
            'stepped_ticks':tick+1,'settled_ticks':count_stopped,'minimum_base_clearance_m':plant.clearance,
            'observed_barrier_contacts':plant.contacts_with_barriers,'pose_at_gate_change':event_pose,
            'crossing_y_m':crossing,'modes':dict(modes),'replayed_after_restart':restarted,
            'pre_map_loss_speed_mps':early_speed,'map_hold_speed_mps':safe_speed,'blackout_start_tick':blackout_begin}
