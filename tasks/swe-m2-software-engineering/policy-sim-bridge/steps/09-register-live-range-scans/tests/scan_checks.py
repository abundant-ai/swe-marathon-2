"""Exercise raw range sensing, native actuator behavior, and epoch recovery."""

from collections import Counter
from math import atan2, cos, pi, sin
from pathlib import Path
import shutil
from time import monotonic
from xml.etree import ElementTree as ET

import mujoco
import numpy as np

import locomotion_native as base
from transport import Stream, require


EXTENT=(-1.08,5.13,-2.18,2.18)
CLEARANCE=.46
CUT=4.5
BEAMS=180
MIN=-pi
STEP=2*pi/BEAMS
HISTORY_MIN=15
ANGLES = MIN+STEP*np.arange(BEAMS)
SCANNER_GROUP = np.array([0,0,0,0,1,0],dtype=np.uint8)


def heading(rotation):
    return atan2(rotation[1,0],rotation[0,0])


def wrap(angle):
    return (angle+pi)%(2*pi)-pi


def orient(v, angle):
    c,s = cos(angle),sin(angle)
    return np.asarray(v)@np.array([[c,s],[-s,c]])


def relative(previous, current):
    shifted = orient(current[:2]-previous[:2],-previous[2])
    return np.r_[shifted,wrap(current[2]-previous[2])]


def environment(spec,case,assets):
    """Put physical walls, asymmetrical survey columns and a relocatable shelf in the world."""
    model=ET.parse(assets/'go2-headless.xml').getroot()
    ET.SubElement(model,'option',timestep='0.005',integrator='implicitfast',solver='Newton',iterations='100')
    actuators=model.find('actuator')
    names={child.get('joint'):child for child in actuators}
    actuators[:]=[names[name] for name in spec['actuator_order']]
    world=model.find('worldbody')
    ET.SubElement(world,'geom',name='floor-0',type='plane',size='0 0 .05',friction='.95 .005 .0001')
    side = case['side']
    xmin,xmax,ymin,ymax = EXTENT

    def box(parent,tag,center,half,yaw=0):
        ET.SubElement(parent,'geom',name=tag,type='box',group='4',pos=' '.join(map(str,center)),
                      size=' '.join(map(str,half)),euler=f'0 0 {yaw}')

    for i,y in enumerate((ymin-.04,ymax+.04)):
        box(world,f'wall-horizontal-{i}',((xmin+xmax)/2,y,.40),((xmax-xmin)/2+.08,.04,.4))
    for i,x in enumerate((xmin-.04,xmax+.04)):
        box(world,f'wall-vertical-{i}',(x,0.,.40),(.04,(ymax-ymin)/2,.4))
    box(world,'divider', (1.48,side*.025,.29),(.16,.532,.29), yaw=side*.123)
    box(world,'corner-fiducial',(-.77,side*1.78,.32),(.18,.225,.32),yaw=side*.37)
    box(world,'small-wall-offset',(2.95,side*1.98,.30),(.24,.16,.30))
    shelf=ET.SubElement(world,'body',name='shelf',mocap='true',pos='7 4 .30')
    box(shelf,'movable-shelf',(0.,0.,0.),(.165,.439,.31),yaw=side*.052)
    return mujoco.MjModel.from_xml_string(ET.tostring(model,encoding='unicode'))


class NativeSite:
    """Raycast and measure the same native geometry that can make physical contact."""

    def __init__(self,base,spec,case,assets):
        self.base=base
        self.robot=base.Plant(spec,case,assets,model=environment(spec,case,assets))
        self.case=case
        self.side=case['side']
        self.shelf=int(self.robot.model.body('shelf').mocapid[0])
        self.geometry_ids=[idx for idx,group in enumerate(self.robot.model.geom_group) if group==4]
        self.rng=np.random.default_rng(case['seed'])
        sign=self.side
        self.mount=np.array([.168,-sign*.083,sign*.193])
        self.clearance=100.
        self.contacts=0
        self.lidar_ids=np.zeros(BEAMS,dtype=np.int32)
        self.depth=np.zeros(BEAMS)
        base_measure=self.robot.measure
        def measure():
            base_measure()
            origin=self.robot.data.qpos[:2]
            for idx in self.geometry_ids:
                local=self.robot.data.geom_xmat[idx].reshape(3,3)[:2,:2].T@(
                    origin-self.robot.data.geom_xpos[idx,:2])
                distance=np.linalg.norm(np.maximum(np.abs(local)-self.robot.model.geom_size[idx,:2],0.))
                self.clearance=min(self.clearance,float(distance))
            geometries=set(self.geometry_ids)
            for item in self.robot.data.contact:
                if geometries.intersection((item.geom1,item.geom2)):
                    self.contacts+=1
        self.robot.measure=measure

    def surface(self):
        state=self.robot.data.qpos
        return np.r_[state[:2],heading(self.base.rotation(state[3:7]))]

    def shelf_at(self,side):
        self.robot.data.mocap_pos[self.shelf]=[1.50,side*1.34,.30]
        mujoco.mj_forward(self.robot.model,self.robot.data)

    def scan(self,pose):
        xy=pose[:2]+orient(self.mount[:2],pose[2])
        pnt=np.r_[xy,.34]
        angle=ANGLES+pose[2]+self.mount[2]
        rays=np.c_[np.cos(angle),np.sin(angle),np.zeros(BEAMS)].ravel()
        mujoco.mj_multiRay(self.robot.model,self.robot.data,pnt,rays,SCANNER_GROUP,
                           True,-1,self.lidar_ids,self.depth,BEAMS,CUT)
        noise=self.rng.normal(0.,.0025,BEAMS)
        return [round(float(np.clip(distance+delta,.025,CUT)),5)
                if .023 < distance <= CUT else None for distance,delta in zip(self.depth,noise,strict=True)]

    def reset_location(self,change):
        state=self.robot.data.qpos
        position=self.surface()
        target=position+change
        state[:2]=target[:2]
        q=np.array([cos(change[2]/2),0,0,sin(change[2]/2)])
        result=np.empty(4)
        mujoco.mju_mulQuat(result,q,state[3:7].copy())
        state[3:7]=result
        self.robot.data.qvel[:]=0.
        mujoco.mj_forward(self.robot.model,self.robot.data)
        return target

    def proprioception(self,tick,epoch):
        sensed=self.robot.observe(tick,self.robot.contacts(tick),None)
        sensed.pop('request')
        angle=.72*self.side + (.91 if epoch>17 else 0.)
        q=np.asarray(sensed['q_xyzw'])[[3,0,1,2]]
        observed=np.empty(4)
        mujoco.mju_mulQuat(observed,np.array([cos(angle/2),0.,0.,sin(angle/2)]),q)
        sensed['q_xyzw']=observed[[1,2,3,0]].tolist()
        sensed['gyro_world_rad_s']=orient(sensed['gyro_world_rad_s'][:2],angle).tolist()+[sensed['gyro_world_rad_s'][2]]
        return sensed


def manifest_for(root,case):
    assets=base.fixture_assets()
    config=base.make_manifest({**case,'terrain':'flat','fault':'scan-course'},assets)
    plant=NativeSite(base,config,{**case,'terrain':'flat','fault':'scan-course'},assets)
    side=case['side']
    cursor=np.zeros(3)
    survey_side=1
    sample_path=np.array([[0.,0.,0.],[.50,survey_side*.40,.17],[.71,survey_side*1.34,.19],[2.20,survey_side*1.31,.04],
                          [3.69,survey_side*1.17,-.16],[4.23,survey_side*.23,-.23],[3.59,-survey_side*.82,.18],
                          [2.31,-survey_side*1.36,-.15],[.67,-survey_side*1.34,.18],[.15,-survey_side*.82,.14]])
    records=[]
    for pose in sample_path:
        delta=relative(cursor,pose)
        records.append({'delta':delta.tolist(),'ranges_m':plant.scan(pose)})
        cursor=pose
    config['teaching']=records
    config['scan_navigation']={'extent':EXTENT,'goal':[3.78,.23,.20],
        'footprint_radius_m':CLEARANCE,'max_speed_mps':.56,'max_scan_age_ticks':HISTORY_MIN,
        'resolution_m':.065,'body_from_lidar':plant.mount.tolist(),'angle_min_rad':MIN,
        'angle_step_rad':STEP,'beam_count':BEAMS,'range_max_m':CUT,'teach_anchor':[0.,0.,0.],
        'completion_tick':1499}
    policy=root/'frozen-policy.onnx'
    shutil.copy2(config['actor'],policy)
    policy.chmod(0o644)
    config['actor']=str(policy)
    return plant,config


MISSIONS = (
    {'name':'survey-repair-and-relocalize','side':1,'seed':6004,'reset':True},
    {'name':'reflected-shelf-survey','side':-1,'seed':11057,'reset':False},
)
REJECTED = {'mode':'rejected','lease':None,'support':[],'effective_twist':None,'action':None,'target_rad':None}


def run_scan_case(app, root, **case):
    """Drive native Go2 with one raw observation at a time and independent actor checks."""
    site,spec=manifest_for(root,case)
    robot=site.robot
    actor_check=base.Expected(spec)
    goal=np.asarray(spec['scan_navigation']['goal'])
    epoch=17
    pending={}
    proof_of_scan={}
    retired=None
    stats=Counter()
    start=monotonic()
    blackout, reset_tick, reset_before, after_recovery = None,None,None,None
    prior_motion, held_speed = None,None
    closing, crossing = None,None
    tracked, heading_errors = [], []
    settled=0
    restart=False
    accepted=None
    delayed_count=0
    reordered_count=0
    most_recent_delivery=-1
    site.shelf_at(-site.side)
    previous=site.surface()
    physical_speed=0.
    with Stream(app,root/'wire',spec,command='navigate-scans') as stream:
        for tick in range(spec['scan_navigation']['completion_tick']+1):
            current=site.surface()
            if case['reset'] and blackout is None and current[0]>.36:
                blackout=tick
                prior_motion=physical_speed
            dark=blackout is not None and blackout<=tick<blackout+63
            if blackout is not None and tick==blackout+39:
                held_speed=physical_speed
                require(held_speed<.14,f'scan authority loss did not produce a physical stop before relocation: {held_speed:.3f} m/s')
                retired={'epoch':epoch,'capture_tick':tick-1,'ranges_m':site.scan(current)}
                reset_before=current.tolist()
                current=site.reset_location(np.array([-.24,.52*site.side,.51*site.side]))
                previous=current
                epoch+=1
                reset_tick=tick
                accepted=None
            if closing is None and (current[0]>.38 or tick>=106):
                closing=current.tolist()
                site.shelf_at(site.side)
            if tick%5==0 and not dark:
                latency=(3,9,3,8,4)[(tick//5)%5]
                pending.setdefault(tick+latency,[]).append(
                    {'epoch':epoch,'capture_tick':tick,'ranges_m':site.scan(current)}
                )
            delivered=pending.pop(tick,[])
            if retired is not None and tick==reset_tick+3:
                delivered.append(retired)
            for row in delivered:
                stamp=row['capture_tick']
                delayed_count+=stamp<tick
                reordered_count+=stamp<most_recent_delivery
                most_recent_delivery=max(most_recent_delivery,stamp)
                if row['epoch']==epoch:
                    proof_of_scan[stamp]=epoch
            delta=relative(previous,current)
            delta[:2]=delta[:2]*[1.026,.966]+.00041*np.array([sin(tick*.27),cos(tick*.34)])
            delta[2]=wrap(delta[2]+.00034*sin(tick*.61)+.00014)
            if tick==0 or tick==reset_tick:
                delta=np.zeros(3)
            sensor=site.proprioception(tick,epoch)
            packet={**sensor,'odometry':{'epoch':epoch,'delta':delta.tolist()},'scans':delivered}
            answer=stream.push(packet)
            intent=answer['intent']
            twist=intent['velocity']
            report_stamp=answer['accepted_scan_tick']
            require(answer['localization_epoch']==epoch,'reported odometry epoch does not match the current source')
            if report_stamp!=accepted:
                require(type(report_stamp) is int and proof_of_scan.get(report_stamp)==epoch and
                        tick-HISTORY_MIN<=report_stamp<=tick and (accepted is None or report_stamp>accepted),
                        'accepted old, missing, or wrong-epoch scan evidence')
                accepted=report_stamp
            require(intent['sequence']==tick and intent['valid_until_tick']==tick+1,'invalid intent lease')
            require(isinstance(twist,list) and len(twist)==3 and all(np.isfinite(twist))
                    and np.linalg.norm(twist[:2])<=.560001,'unsafe locomotion speed limit')
            require(answer['navigation'] in ('arrived','navigate','hold'),'unrecognized navigation output')
            if answer['navigation'] in ('arrived','hold'):
                require(twist==[0.,0.,0.],'a stopped navigator issued a moving intent')
            authority=(accepted is not None and tick-accepted<=HISTORY_MIN)
            if not authority:
                require(answer['navigation']=='hold' and twist==[0.,0.,0.],
                        'a stale or missing scan granted navigation authority')
            if reset_tick is not None and reset_tick<=tick<blackout+63:
                require(accepted is None and answer['pose_map'] is None,
                        'a retired scan retained or restored localization after the odometry reset')
            if reset_tick is not None and tick==reset_tick+4:
                stream.restart()
                altered=packet|{'scans':[retired]}
                require(stream.push(altered)=={'tick':tick,**REJECTED},'changed retry modified the scan epoch')
                require(stream.push(packet)==answer,'map and actor reply changed after the worker died')
                restart=True
            estimate=answer['pose_map']
            if authority:
                require(isinstance(estimate,list) and len(estimate)==3 and all(np.isfinite(estimate)),
                        'a fresh registered scan did not produce a finite map pose')
                error=float(np.linalg.norm(np.asarray(estimate[:2])-current[:2]))
                direction=abs(wrap(estimate[2]-current[2]))
                if answer['navigation'] == 'navigate' and any(twist):
                    tracked.append(error)
                    heading_errors.append(direction)
                if reset_tick is not None and after_recovery is None:
                    after_recovery={'tick':tick,'error_m':error,'heading_error_rad':direction,
                                    'current_pose':current.tolist(),'estimated_pose':estimate}
            independent=actor_check.reply({**sensor,'request':intent},robot.data.qpos[robot.qp],
                robot.data.qvel[robot.qv],base.rotation(robot.data.qpos[3:7]),robot.data.qvel[3:6])
            require(set(answer)==set(independent)|{'navigation','intent','localization_epoch','accepted_scan_tick','pose_map'},
                    'scan response lacks declared state and actor fields')
            base.numeric_fields({key:answer[key] for key in independent},independent)
            stats[answer['navigation']]+=1
            previous=current
            robot.advance(answer['target_rad'],tick,False)
            require(site.contacts==0 and site.clearance>=CLEARANCE,
                    f'physical robot shell crossed an obstacle or boundary at tick {tick} (minimum {site.clearance:.3f} m)')
            physical_speed=float(np.linalg.norm(robot.data.qvel[:2]))
            after=site.surface()
            if crossing is None and after[0]>=1.51:
                crossing=float(after[1])
            error=float(np.linalg.norm(after[:2]-goal[:2]))
            yaw_error=abs(wrap(after[2]-goal[2]))
            if answer['navigation']=='arrived' and error<=.17 and yaw_error<=.16 and physical_speed<.085:
                settled+=1
            else:
                settled=0
            if settled>=22:
                break
    require(settled>=22,f'raw-scan route never settled at the goal: error {error:.3f}, modes {dict(stats)}')
    require(crossing is not None and crossing*site.side<-.83,'robot did not cross through the lane opened by the shelf')
    require(delayed_count>45 and reordered_count>10 and len(tracked)>=200,'a live delayed sensor path was not exercised')
    p95=float(np.quantile(tracked,.95))
    yaw95=float(np.quantile(heading_errors,.95))
    require(p95<=.14 and yaw95<=.18,f'raw-scan map frame disagreed with physical pose: {p95:.3f} m and {yaw95:.3f} rad')
    if case['reset']:
        require(restart and after_recovery is not None and after_recovery['error_m']<=.16
                and after_recovery['heading_error_rad']<=.18,
                'recovery did not establish an accurate new epoch after the restart')
    return {'goal_error_m':error,'goal_heading_error_rad':yaw_error,'settled_ticks':settled,
            'final_speed_mps':physical_speed,'crossing_y_m':crossing,'obstacle_contacts':site.contacts,
            'minimum_clearance_m':site.clearance,'stepped_ticks':tick+1,'shelf_move_pose':closing,
            'delayed_scans':delayed_count,'out_of_order_scans':reordered_count,'modes':dict(stats),
            'localization_p95_m':p95,'localization_yaw_p95_rad':yaw95,'scan_loss_tick':blackout,
            'odometry_epoch_reset_tick':reset_tick,'pre_loss_speed_mps':prior_motion,
            'pre_relocation_held_speed_mps':held_speed,'pose_before_relocation':reset_before,
            'first_recovered_pose':after_recovery,'durable_restart_exercised':restart,'wall_seconds':monotonic()-start}
