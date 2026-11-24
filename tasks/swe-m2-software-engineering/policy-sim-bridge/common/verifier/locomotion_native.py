"""Drive the submitted policy bridge against instrumented, free-base MuJoCo missions."""

from collections import Counter
from hashlib import sha256
import json
from math import acos, atan2
from pathlib import Path
from random import Random
import shutil
from xml.etree import ElementTree as ET

import mujoco
import numpy as np
import onnxruntime as ort

from transport import Stream, require


FEET = ("FL", "FR", "RL", "RR")
ASSETS = Path(__file__).with_name("locomotion-assets")
CASES = [
    {"name":"split-friction-slip-limit-and-recover","seed":61,"terrain":"split","fault":"push"},
    {"name":"walking-contact-loss-retires-lease-through-crash","seed":104,"terrain":"split","fault":"blackout"},
    {"name":"lease-expiry-and-reacquire-during-heading-change","seed":439,"terrain":"flat","fault":"expire"},
]


def fixture_assets():
    """Allow local source testing and the separate frozen verifier context."""
    if ASSETS.is_dir():
        return ASSETS
    return Path(__file__).parents[2]/"environment"/"example"/"locomotion"


def make_manifest(case, assets):
    """Create separately signed sensors and a permuted target wire."""
    template=json.loads((assets/"manifest.json").read_text())
    random=Random(case["seed"])
    names=template["policy_joints"]
    order=random.sample(names,len(names))
    template["joint_sensors"]=[{"joint":name,"sign":random.choice([-1,1]),
                                "zero_rad":random.uniform(-0.24,0.24)} for name in order]
    template["actuator_order"]=random.sample(names,len(names))
    template["actor"]=str(assets/"policy.onnx")
    template["slip_limit_mps"]=0.41
    template["recovery_ticks"]=6
    return template


def native_model(manifest, case, assets):
    """Load the real free joint, rigid links, masses, and collision shapes."""
    model=ET.parse(assets/"go2-headless.xml").getroot()
    ET.SubElement(model,"option",timestep="0.005",integrator="implicitfast",solver="Newton",
                  iterations="100",ls_iterations="50")
    actuators=model.find("actuator")
    by_joint={child.get("joint"):child for child in actuators}
    actuators[:]=[by_joint[name] for name in manifest["actuator_order"]]
    world=model.find("worldbody")
    if case["terrain"]=="split":
        for i,value in enumerate((.95,.58)):
            ET.SubElement(world,"geom",name=f"floor-{i}",type="box",size="12 5 .09",
                          pos=f"0 {5-10*i} -.09",priority="2",friction=f"{value} .005 .0001")
    else:
        ET.SubElement(world,"geom",name="floor-0",type="plane",size="0 0 .05")
    return mujoco.MjModel.from_xml_string(ET.tostring(model,encoding="unicode"))


def rotation(quaternion):
    """Convert native wxyz quaternion to a rotation matrix."""
    values=np.empty(9)
    mujoco.mju_quat2Mat(values,quaternion)
    return values.reshape(3,3)


class Plant:
    """Measure forces and step the actual actuator target of each issued reply."""

    def __init__(self, spec, config, assets, *, model=None):
        self.spec,self.config=spec,config
        self.model=native_model(spec,config,assets) if model is None else model
        self.data=mujoco.MjData(self.model)
        ids=[self.model.joint(name).id for name in spec["policy_joints"]]
        self.qp,self.qv=self.model.jnt_qposadr[ids],self.model.jnt_dofadr[ids]
        self.home=np.array(spec["default_positions_rad"])
        self.data.qpos[self.qp]=self.home
        self.base=self.model.body("base").id
        self.feet={self.model.geom(foot+"_foot_collision").id:foot for foot in FEET}
        self.floors={self.model.geom(name).id:name for name in ("floor-0","floor-1")
                     if name=="floor-0" or config["terrain"]=="split"}
        self.indices=[spec["policy_joints"].index(name) for name in spec["actuator_order"]]
        self.physical_friction={}
        self.touches=Counter()
        self.force=np.empty(6)
        self.twist=np.empty(6)
        self.pressure={foot:[0.,0.] for foot in FEET}
        self.peak_tilt=0.0
        self.peak_motor=0.0
        self.low_base=1.0
        self.nonfoot=0
        self.push_remaining=0
        self.push_tick=None
        self.slip_speeds=[]
        self.progress_at_stop=None
        mujoco.mj_forward(self.model,self.data)

    def contacts(self, tick):
        """Publish the four measured foot support aggregates for one sampling interval."""
        return [{"foot":foot,"capture_tick":tick,"normal_force_n":integral/4,
                 "tangent_speed_mps":speed/integral if integral>0 else 0.0}
                for foot,(integral,speed) in self.pressure.items()]

    def observe(self,tick,contacts,request):
        """Encode native proprioception through the manifest's independent sensor wire."""
        canonical=self.spec["policy_joints"]
        order=[canonical.index(datum["joint"]) for datum in self.spec["joint_sensors"]]
        p,v=self.data.qpos[self.qp][order], self.data.qvel[self.qv][order]
        q=self.data.qpos[3:7].copy()*(-1 if tick%2 else 1)
        return {"tick":tick,
                "joint_position_rad":[float((a-s["zero_rad"])*s["sign"]) for a,s in zip(p,self.spec["joint_sensors"])],
                "joint_velocity_rad_s":[float(a*s["sign"]) for a,s in zip(v,self.spec["joint_sensors"])],
                "q_xyzw":q[[1,2,3,0]].tolist(),
                "gyro_world_rad_s":(rotation(q)@self.data.qvel[3:6]).tolist(),
                "contacts":contacts,"request":request}

    def measure(self):
        """Accumulate true foot normal load and loaded tangent speeds."""
        for index in range(self.data.ncon):
            item=self.data.contact[index]
            floor,robot=item.geom1,item.geom2
            if floor not in self.floors:
                floor,robot=robot,floor
            if floor not in self.floors:
                continue
            mujoco.mj_contactForce(self.model,self.data,index,self.force)
            normal=float(self.force[0])
            if normal<2.0:
                continue
            if robot not in self.feet:
                self.nonfoot+=1
                continue
            tag=self.feet[robot]
            material=self.floors[floor]
            self.physical_friction[material]=float(item.friction[0])
            self.touches[f"{material}:{tag}"]+=1
            mujoco.mj_objectVelocity(self.model,self.data,mujoco.mjtObj.mjOBJ_GEOM,robot,self.twist,0)
            contact=self.twist[3:]+np.cross(self.twist[:3],item.pos-self.data.geom_xpos[robot])
            slip=float(np.linalg.norm(contact[:2]))
            self.pressure[tag][0]+=normal
            self.pressure[tag][1]+=normal*slip
            self.slip_speeds.append(slip)

    def advance(self,target,tick,can_disturb):
        """Use canonical local PD, directional torque limits and true native contacts."""
        target=np.asarray(target)
        self.pressure={foot:[0.0,0.0] for foot in FEET}
        for _ in range(4):
            p,v=self.data.qpos[self.qp][self.indices],self.data.qvel[self.qv][self.indices]
            effort=25*(target-p)-.5*v
            vehicle_limit=np.where(effort*v>0,20.2,23.4)*np.clip((30-np.abs(v))/16.5,0.0,1.0)
            self.data.ctrl[:]=np.clip(effort,-vehicle_limit,vehicle_limit)
            self.data.xfrc_applied[self.base]=0
            if (self.config["fault"]=="push" and self.push_tick is None and can_disturb and self.data.qpos[0]>.9
                and self.data.qvel[0]>.38):
                self.push_tick=tick
                self.push_remaining=26
            if self.push_remaining:
                self.data.xfrc_applied[self.base,:3]=[0,-75.0,0]
                self.push_remaining-=1
            mujoco.mj_step(self.model,self.data)
            self.measure()
            self.low_base=min(self.low_base,float(self.data.qpos[2]))
            tilt=acos(float(np.clip(rotation(self.data.qpos[3:7])[2,2],-1,1)))
            self.peak_tilt=max(self.peak_tilt,tilt)
            self.peak_motor=max(self.peak_motor,float(np.max(np.abs(self.data.actuator_force))))
            require(self.low_base>.16 and self.peak_tilt<.68 and self.nonfoot==0,
                    f"free-base airframe lost physical clearance at tick {tick}; height {self.low_base:.3f}, tilt {self.peak_tilt:.3f}, nonfoot {self.nonfoot}")


class Expected:
    """Independently derive authority from delivered evidence and the exact actor."""

    def __init__(self,spec):
        self.spec=spec
        actor=Path(spec["actor"])
        require(sha256(actor.read_bytes()).hexdigest()==spec["actor_sha256"],"frozen ONNX bytes changed")
        options=ort.SessionOptions()
        options.intra_op_num_threads=1
        options.inter_op_num_threads=1
        options.log_severity_level=3
        self.actor=ort.InferenceSession(str(actor),sess_options=options,providers=["CPUExecutionProvider"])
        self.known={}
        self.command=None
        self.retired=-1
        self.ready_run=0
        self.slip_recovery=0
        self.state="stop"
        self.terms=[np.zeros((10,width),dtype=np.float32) for width in (3,3,3,12,12,12)]
        self.last=np.zeros(12,dtype=np.float32)

    def read_contact(self,packet):
        """Accepted samples form four independent capture-time windows."""
        tick=packet["tick"]
        earliest=tick-self.spec["max_contact_age_ticks"]
        for row in packet["contacts"]:
            known=self.known.get(row["foot"])
            if earliest<=row["capture_tick"]<=tick and (known is None or known["capture_tick"]<row["capture_tick"]):
                self.known[row["foot"]]=row
        fresh={key:value for key,value in self.known.items() if value["capture_tick"]>=earliest}
        loaded={key for key,row in fresh.items() if row["normal_force_n"]>=self.spec["normal_min_n"]}
        slip=any(fresh[key]["tangent_speed_mps"]>self.spec["slip_limit_mps"] for key in loaded)
        return fresh,loaded,slip

    def reply(self,packet,p,v,r,omega):
        tick=packet["tick"]
        spec=self.spec
        fresh,loaded,slip=self.read_contact(packet)
        healthy=len(fresh)>=3 and r[2,2]>=np.cos(spec["max_tilt_rad"])
        stable=healthy and len(loaded)>=spec["min_support_feet"] and not slip
        self.ready_run=(self.ready_run+1) if stable else 0
        row=packet["request"]
        if row and (not self.command or row["sequence"]>self.command["sequence"]):
            if (tick<=row["valid_until_tick"]<=tick+spec["max_lease_ticks"]
                and np.all(np.abs(row["velocity"])<=spec["max_command_abs"])):
                self.command=row
        expired=self.command is not None and self.command["valid_until_tick"]<tick
        if expired or not healthy and self.state!="stop":
            self.retired=self.command["sequence"]
        if expired or not healthy or self.command is None:
            self.state="stop"
        elif self.state=="stop" and self.command["sequence"]>self.retired and self.ready_run>=spec["rearm_ticks"]:
            self.state="track"
        if self.state!="stop":
            if slip:
                self.state="limited"
                self.slip_recovery=0
            elif self.state=="limited":
                self.slip_recovery=self.slip_recovery+1 if stable else 0
                if self.slip_recovery>=spec["recovery_ticks"]:
                    self.state="track"
        else:
            self.slip_recovery=0
        authority=self.command["sequence"] if self.state!="stop" else None
        twist=np.zeros(3) if authority is None else np.array(self.command["velocity"],dtype=float)
        if self.state=="limited":
            twist*=spec["limit_factor"]
        entries=(omega*.25,-r[2],twist*spec["command_scale"],p-spec["default_positions_rad"],v*.05,self.last)
        for term,value in zip(self.terms,entries,strict=True):
            term[:-1,:]=term[1:,:]
            term[-1,:]=value
        history=np.concatenate([block.ravel() for block in self.terms]).reshape(1,450)
        self.last=np.clip(self.actor.run(["actions"],{"obs":history})[0][0],-100,100)
        full_target=np.array(spec["default_positions_rad"])+.25*self.last
        transmit=[float(full_target[spec["policy_joints"].index(joint)]) for joint in spec["actuator_order"]]
        return {"tick":tick,"mode":self.state,"lease":authority,"support":sorted(loaded),
                "effective_twist":twist.tolist(),"action":self.last.tolist(),"target_rad":transmit}


def request_for(tick,fault,blackout,finish):
    """Issue hard-expiring commands, including observable stale renewals."""
    if tick==finish:
        return {"sequence":900,"valid_until_tick":finish+21,"velocity":[0,0,0]}
    if tick>finish:
        return None
    if blackout is not None and blackout<=tick<blackout+32:
        if tick-blackout in (11,24):
            return {"sequence":12,"valid_until_tick":tick+18,"velocity":[.72,.25,.6]}
        return None
    if fault=="expire" and 104<=tick<149:
        if tick==119:
            return {"sequence":12,"valid_until_tick":tick+18,"velocity":[.84,.22,.7]}
        return None
    if tick%12==0 or blackout is not None and tick==blackout+32 or fault=="expire" and tick==149:
        yaw=-.24 if fault=="expire" and 149<=tick<237 else .15 if 196<=tick<242 else 0.0
        return {"sequence":4+tick//4,"valid_until_tick":tick+18,"velocity":[.61,0,yaw]}
    return None


def numeric_fields(reply, expected):
    """Check frame history and actuation with cross-platform float tolerance."""
    for key in ("tick","mode","lease","support"):
        require(reply.get(key)==expected[key],f"wrong {key} at tick {expected['tick']}: expected {expected[key]!r}, got {reply.get(key)!r}")
    for field,limit in (("effective_twist",1e-10),("action",3e-4),("target_rad",7.6e-5)):
        actual=np.array(reply.get(field),dtype=float)
        comparison=np.array(expected[field])
        require(actual.shape==comparison.shape and np.isfinite(actual).all()
                and np.max(np.abs(actual-comparison))<=limit,
                f"wrong {field} at tick {expected['tick']}")
    require(set(reply)==set(expected),"stream response fields differ from contract")


def run_locomotion(app,root,**condition):
    """Verify causal commands, durable retries and native terminal progress together."""
    assets=fixture_assets()
    spec=make_manifest(condition,assets)
    actor=root/"frozen-policy.onnx"
    shutil.copy2(spec["actor"],actor)
    actor.chmod(0o644)
    spec["actor"]=str(actor)
    plant=Plant(spec,condition,assets)
    expected=Expected(spec)
    fault=condition["fault"]
    finish=384 if fault=="blackout" else 348
    states=Counter()
    after_event=False
    boundaries=[]
    push_slip=0.0
    blackout=None
    pre_loss_velocity=0.0
    expired_before_rearm=0
    stopped_speed=None
    lost_replayed=False
    trace=[]
    with Stream(app,root/"wire",spec,command="locomote") as process:
        for tick in range(finish+53):
            contact=plant.contacts(tick)
            if (fault=="blackout" and blackout is None and tick>=95 and plant.data.qpos[0]>.58
                and plant.data.qvel[0]>.40):
                blackout=tick
                pre_loss_velocity=float(plant.data.qvel[0])
            if plant.push_tick is not None and plant.push_tick<tick<=plant.push_tick+10:
                peak=max((row["tangent_speed_mps"] for row in contact if row["normal_force_n"]>=spec["normal_min_n"]),default=0)
                push_slip=max(peak,push_slip)
            if tick%9==2:
                # A reordered stale or future packet must neither grant support nor plant a slip.
                contact.insert(0,{"foot":"FL","capture_tick":tick-3,"normal_force_n":90.0,"tangent_speed_mps":1.8})
                contact.append({"foot":"RR","capture_tick":tick+1,"normal_force_n":70.0,"tangent_speed_mps":1.7})
            if blackout is not None and blackout<=tick<blackout+22:
                contact=[dict(row,capture_tick=tick-5) for row in contact]
            packet=plant.observe(tick,contact,request_for(tick,fault,blackout,finish))
            r=rotation(plant.data.qpos[3:7])
            verified=expected.reply(packet,plant.data.qpos[plant.qp],plant.data.qvel[plant.qv],r,plant.data.qvel[3:6])
            answer=process.push(packet)
            numeric_fields(answer,verified)
            states[answer["mode"]]+=1
            if tick>=3 and (not trace or answer["mode"]!=trace[-1][1]):
                trace.append([tick,answer["mode"]])
            if blackout is not None and tick==blackout+7:
                process.restart()
                forged=packet|{"request":{"sequence":417,"valid_until_tick":tick+20,"velocity":[.86,.38,.82]}}
                for recovery_packet in (forged,packet|{"tick":tick-1},packet|{"tick":tick+2}):
                    rejected=process.push(recovery_packet)
                    require(rejected=={"tick":recovery_packet["tick"],"mode":"rejected","lease":None,"support":[],
                                      "effective_twist":None,"action":None,"target_rad":None},
                            "altered or noncontiguous replay changed authority")
                require(process.push(packet)==answer,"lost-response retry after process death changed exact output")
                lost_replayed=True
            if blackout is not None and blackout+3<=tick<blackout+32:
                require(answer["mode"]=="stop","unsafe motion authority survived telemetry loss")
                expired_before_rearm+=1
            if fault=="expire" and 115<=tick<149:
                require(answer["mode"]=="stop","unsafe motion authority survived lease expiry")
                expired_before_rearm+=1
            if fault=="push" and plant.push_tick is not None:
                if answer["mode"]=="limited" and plant.push_tick<tick<=plant.push_tick+10:
                    after_event=True
                if after_event and tick>=plant.push_tick+7 and answer["mode"]=="track":
                    boundaries.append(tick)
            plant.advance(answer["target_rad"],tick,answer["mode"]=="track")
            if (blackout is not None and tick==blackout+31) or (fault=="expire" and tick==148):
                stopped_speed=float(np.linalg.norm(plant.data.qvel[:2]))
    final=plant.data.qpos[:2].copy()
    closing_speed=float(np.linalg.norm(plant.data.qvel[:2]))
    require(final[0]>2.35 and abs(final[1])<.85 and closing_speed<.12,
            f"safe posture alone could not complete commanded travel and stop: x={final[0]:.3f}, y={final[1]:.3f}, speed={closing_speed:.3f}")
    if fault=="push":
        require(plant.push_tick is not None and push_slip>spec["slip_limit_mps"] and after_event and len(boundaries)>=12,
                f"native loaded slip did not exercise speed limiting and recovery; push={plant.push_tick}, slip={push_slip:.3f}, modes={trace}")
    if fault=="blackout":
        require(lost_replayed and pre_loss_velocity>.40 and expired_before_rearm>=25 and stopped_speed<.27,
                f"authority-loss route did not start while moving and then physically brake; before={pre_loss_velocity}, stopped={stopped_speed}")
    r=rotation(plant.data.qpos[3:7])
    heading=atan2(r[1,0],r[0,0])
    if fault=="expire":
        require(expired_before_rearm>=30 and stopped_speed<.24 and states["track"]>=100 and heading<-.15,
                f"lease-expiry route did not physically stop and then resume; stopped={stopped_speed}")
    if condition["terrain"]=="split":
        require(set(plant.physical_friction)=={"floor-0","floor-1"} and min(plant.physical_friction.values())<.60,
                "native split-friction contact did not occur")
    return {"forward_m":float(final[0]),"lateral_m":float(final[1]),"terminal_speed_mps":closing_speed,
            "final_heading_rad":heading,"peak_tilt_rad":plant.peak_tilt,
            "min_base_height_m":plant.low_base,"peak_motor_torque_nm":plant.peak_motor,
            "contact_friction":plant.physical_friction,"loaded_foot_samples":dict(plant.touches),
            "stance_slip_p95_mps":float(np.percentile(plant.slip_speeds,95)),"modes":dict(states),
            "mode_transitions":trace,"push_tick":plant.push_tick,"recovered_track_ticks":len(boundaries),
            "peak_early_disturbance_slip_mps":push_slip,"blackout_tick":blackout,
            "first_recovered_tick":boundaries[0] if boundaries else None,
            "unread_reply_replayed":lost_replayed,"pre_loss_speed_mps":pre_loss_velocity,
            "interruption_stop_speed_mps":stopped_speed}
