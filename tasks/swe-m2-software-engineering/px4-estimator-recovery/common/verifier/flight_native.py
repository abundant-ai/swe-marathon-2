"""Independent pinned-headless rigid-body flight enclosure and sensor publisher."""

from collections import Counter
import json
from math import acos, atan2, cos, pi, sin
from pathlib import Path
from subprocess import DEVNULL, run
import sys

import mujoco
import numpy as np

from commission_checks import make_kit
from transport import Driver, candidate_environment, identity, require


DT = 0.004
CONTROL_STEPS = 10
STEP_US = 4000
CAMERA_ARM = np.array([0.14,-0.041,-0.067])
IMU_ARM = np.array([-0.082,0.036,0.043])
CAMERA_Q = np.array([0.9747941071,0.0,0.0,0.2231063621])
CAMERA_Q /= np.linalg.norm(CAMERA_Q)
G = np.array([0.,0.,9.81])
RADIUS = 0.075

FLIGHT_CASES = [
    {"name":"tilted-traverse-and-yaw-across-pi","kind":"nominal","variant":0,"direction":1},
    {"name":"older-attitude-and-newer-position-arrive-out-of-order","kind":"reorder","variant":1,"direction":-1},
    {"name":"new-vision-frame-needs-independent-link","kind":"frame","variant":2,"direction":1},
    {"name":"delayed-duplicate-and-inconsistent-vision","kind":"check","variant":0,"direction":-1},
    {"name":"moving-aiding-outage-brakes-then-resumes","kind":"recover","variant":1,"direction":1},
    {"name":"positive-speed-irrecoverable-aiding-loss-lands","kind":"land","variant":2,"direction":1},
    {"name":"late-aiding-cannot-cancel-opposite-heading-landing","kind":"rejoin","variant":0,"direction":-1},
]


def matrix(q):
    result=np.empty(9)
    mujoco.mju_quat2Mat(result,np.asarray(q,dtype=float))
    return result.reshape(3,3)


def quaternion(mat):
    result=np.empty(4)
    mujoco.mju_mat2Quat(result,np.ascontiguousarray(mat.flatten(),dtype=float))
    return result


def yaw(angle):
    return np.array([[cos(angle),-sin(angle),0.0],[sin(angle),cos(angle),0.0],[0.0,0.0,1.0]])


def angle_error(a,b):
    return 2.0*acos(min(1.0,abs(float(a@b)/(np.linalg.norm(a)*np.linalg.norm(b)))))


def yaw_of(rotation):
    return atan2(rotation[1,0],rotation[0,0])


class Plant:
    """Step gravity, finite-rate torque and collective thrust in one free body."""

    def __init__(self, initial, mass):
        self.mass=mass
        self.max_thrust=mass*9.81/0.49
        xml=f"""
        <mujoco model="flight-test-enclosure"><compiler angle="radian"/>
        <option timestep="{DT}" gravity="0 0 9.81" integrator="implicitfast"/>
        <worldbody>
          <geom type="plane" size="8 8 .1" euler="{pi} 0 0" friction=".75 .004 .0002"/>
          <body name="airframe">
            <freejoint/><inertial pos="0 0 0" mass="{mass}" diaginertia=".012 .013 .021"/>
            <geom type="sphere" size="{RADIUS}" rgba=".2 .3 .4 1"/>
          </body>
        </worldbody></mujoco>"""
        self.model=mujoco.MjModel.from_xml_string(xml)
        self.data=mujoco.MjData(self.model)
        self.id=self.model.body("airframe").id
        self.data.qpos[:3]=initial["position_m"]
        self.data.qpos[3:7]=initial["q_wxyz"]
        self.thrust=self.mass*9.81
        self.torque=np.zeros(3)
        mujoco.mj_forward(self.model,self.data)

    def motion(self):
        local=np.empty(6)
        mujoco.mj_objectVelocity(self.model,self.data,mujoco.mjtObj.mjOBJ_BODY,self.id,local,1)
        return self.data.qpos[:3].copy(), self.data.qvel[:3].copy(), self.data.xmat[self.id].reshape(3,3).copy(), local[:3]

    def step(self, rates, collective, wind):
        p,v,r,w=self.motion()
        prev_sensor_v=v+r@np.cross(w,IMU_ARM)
        self.thrust+=(collective*self.max_thrust-self.thrust)*0.105
        wanted=np.clip((rates-w)*[0.18,0.18,0.16],-.23,.23)
        self.torque+=(wanted-self.torque)*0.23
        self.data.xfrc_applied[self.id,:3]=r@[0,0,-self.thrust]-0.24*v+wind
        self.data.xfrc_applied[self.id,3:]=r@self.torque
        mujoco.mj_step(self.model,self.data)
        mujoco.mj_forward(self.model,self.data)
        p2,v2,r2,w2=self.motion()
        sensor_v=v2+r2@np.cross(w2,IMU_ARM)
        specific=0.5*(r+r2).T@((sensor_v-prev_sensor_v)/DT-G)
        return (w+w2)*0.5,specific


def describe(kit, case):
    variant,direction=case["variant"],case["direction"]
    device=("imu-port","imu-starboard")[variant%2]
    imu=kit["devices"][device]
    base=imu["clock_origin_us"]+61_370_000
    initial_yaw=[2.86,-2.59,0.83][variant]
    initial={"timestamp_us":base,"position_m":[0.0,0.0,-1.24],"velocity_mps":[0.0,0.0,0.0],
             "q_wxyz":quaternion(yaw(initial_yaw)).tolist()}
    goal_heading=[-2.66,2.81,-1.01][variant]
    targets=[{"position_m":[1.33*direction,0.15,-1.39],"yaw_rad":goal_heading},
             {"position_m":[0.57*direction,-0.64,-1.13],"yaw_rad":-0.49*direction}]
    return {"initial":initial,"imu":imu|{"device":device,"lever_arm_m":IMU_ARM.tolist()},
            "camera":{"body_from_camera_wxyz":CAMERA_Q.tolist(),"lever_arm_m":CAMERA_ARM.tolist()},
            "waypoints":targets,"hover_collective":0.49,"max_body_rate_rad_s":2.8,"history_us":420_000,
            "track_age_us":235_000,"brake_age_us":890_000,"innovation":{"position_m":0.28,
            "velocity_mps":0.46,"attitude_rad":0.32},"position_tolerance_m":0.16,
            "speed_tolerance_mps":0.15,"yaw_tolerance_rad":0.17,"dwell_ticks":7,
            "min_ned":[-1.93,-1.12,-1.83],"max_ned":[1.93,0.65,0.0],
            "landing_area":{"min_ne_m":[0.25 if direction>0 else -1.49,-0.40],
                            "max_ne_m":[1.49 if direction>0 else -0.25,0.52]},
            "deadline_us":base+15_800_000}


class Environment:
    """Generate rate intervals and partial position/yaw captures from simulated truth."""

    def __init__(self,cfg,kit,case):
        self.cfg,self.case=cfg,case
        self.calib=kit["parameters"][cfg["imu"]["device"]]
        self.mount=matrix(cfg["imu"]["body_from_imu_wxyz"])
        self.camera=matrix(CAMERA_Q)
        self.native=Plant(cfg["initial"],0.95+0.08*case["variant"])
        self.start=cfg["initial"]["timestamp_us"]
        self.step_id=0
        self.pending=[]
        self.seq=0
        self.capture=0
        self.last_record=None
        self.epoch=11
        self.frames={11:(self.start,np.array([0.52,-0.31,0.27]),yaw(-0.69))}
        self.links=[self.link(11)]
        self.accumulated=np.zeros((2,3))
        self.accum_steps=0
        self.batched=[]
        self.outage=None
        self.outage_speed=None
        self.outage_tilt=None
        self.contacts=0
        self.max_touchdown_speed=0.0
        self.rng=np.random.default_rng(79364+case["variant"])

    def link(self,epoch):
        start,translation,rotation=self.frames[epoch]
        return {"epoch":epoch,"start_us":start,"translation_m":translation.tolist(),
                "ned_from_vision_wxyz":quaternion(rotation).tolist()}

    def device_stamp(self,system):
        origin=self.cfg["imu"]["clock_origin_us"]
        return round(origin+(system-origin-self.calib["offset_us"])/(1+1e-6*self.calib["skew_ppm"]))

    def imu(self):
        stamp=self.start+self.step_id*STEP_US
        dt=DT*self.accum_steps
        end=self.device_stamp(stamp)
        temp=29+7*sin((stamp-self.start)/2_460_000+0.54*self.case["variant"])
        deltas=[]
        for increment,prefix in zip(self.accumulated,("gyro","accel"),strict=True):
            sensor=self.mount.T @ increment
            deltas.append(sensor*self.calib[prefix+"_gain"]+dt*(np.array(self.calib[prefix+"_bias"])
                          +(temp-25)*np.array(self.calib[prefix+"_temp_slope"])))
        row={"sequence":self.seq,"stamp_us":end,"interval_us":end-self.device_stamp(stamp-round(dt*1e6)),
             "temp_c":temp,"clipped":False,"delta_angle":deltas[0].tolist(),"delta_velocity":deltas[1].tolist()}
        if self.seq in (47,101,229):
            self.batched.append(row|{"clipped":True,"delta_angle":[0.35,0.2,0.18]})
        self.batched.append(row)
        if self.seq in (29,122,274):
            self.batched.append(row)
        self.seq+=1
        self.accumulated*=0
        self.accum_steps=0

    def vision(self):
        step=self.step_id
        stamp=self.start+step*STEP_US
        kind=self.case["kind"]
        p,v,r,w=self.native.motion()
        self.capture+=1
        frame=self.frames[self.epoch]
        t=frame[1]
        v_from_ned=frame[2].T
        small_turn=float(self.rng.normal(0.0,0.002))
        qt=quaternion(v_from_ned @ r @ self.camera @ yaw(small_turn))
        if self.capture%3==0:
            qt=-qt
        raw={"id":f"v-{self.capture}","capture_us":stamp,"epoch":self.epoch,
             "position_m":(v_from_ned @ (p+r@CAMERA_ARM-t)+self.rng.normal(0.0,0.0025,3)).tolist(),
             "velocity_mps":(v_from_ned @ (v+r@np.cross(w,CAMERA_ARM))+self.rng.normal(0.0,0.0045,3)).tolist(),
             "q_wxyz":qt.tolist(),"omega_body_rad_s":w.tolist()}
        losing=self.outage is not None and (kind=="land" or step-self.outage<(420 if kind=="rejoin" else 134))
        if losing:
            raw.update(position_m=None,velocity_mps=None)
        latency=(19,32,25,23,34)[self.capture%5]
        if kind=="reorder":
            expected="accepted"
            attitude=raw|{"id":raw["id"]+"-yaw","position_m":None,"velocity_mps":None}
            raw["q_wxyz"]=None
            self.pending.append((step+latency+24,attitude,expected))
        expected="frame" if kind=="frame" and self.epoch==12 and step+latency<305 else "accepted"
        self.pending.append((step+latency,raw,expected))
        if kind=="check" and self.capture in (7,17):
            bogus=raw|{"id":raw["id"]+"-outlier","position_m":[a+b for a,b in zip(raw["position_m"],[1.7,-0.8,.63])]}
            self.pending.append((step+latency+3,bogus,"innovation"))
            self.pending.append((step+latency+11,raw,"duplicate"))
            self.pending.append((step+158,raw|{"id":raw["id"]+"-stale"},"time"))

    def advance(self,rates,collective):
        kind,direction=self.case["kind"],self.case["direction"]
        for _ in range(CONTROL_STEPS):
            self.step_id+=1
            step=self.step_id
            window=step*DT
            wind=np.array([0.027*sin(2.2*window),0.041*cos(1.37*window),0.014*sin(window*3)])
            was_touching=self.native.data.ncon>0
            before=self.native.data.qvel[:3].copy()
            gyro,accel=self.native.step(rates,collective,wind)
            self.accumulated+=DT*np.stack((gyro,accel))
            self.accum_steps+=1
            if self.accum_steps==(2,4,3,3,2)[self.seq%5]:
                self.imu()
            p,v,r,_=self.native.motion()
            if self.native.data.ncon>0 and not was_touching:
                self.contacts+=1
                self.max_touchdown_speed=max(self.max_touchdown_speed,float(np.linalg.norm(before)))
                require(abs(before[2])<0.43 and np.linalg.norm(before[:2])<0.24,
                        "airframe exceeded the permitted velocity before ground contact")
            if (kind in ("recover","land","rejoin") and self.outage is None and
                direction*p[0]>0.30 and direction*v[0]>0.40):
                self.outage=step
                self.outage_speed=float(direction*v[0])
                self.outage_tilt=acos(np.clip(r[2,2],-1,1))
            if kind=="frame" and step==244:
                self.epoch=12
                rotation=yaw(1.22) @ matrix(np.array([cos(.075),sin(.075),0,0]))
                self.frames[12]=(self.start+step*STEP_US,np.array([-0.72,0.43,-0.18]),rotation)
            if kind=="frame" and step==305:
                self.links.append(self.link(12))
            if step%19==0:
                self.vision()
            low,high=np.array(self.cfg["min_ned"]),np.array(self.cfg["max_ned"])
            require(np.all(p[:2]-RADIUS>=low[:2]) and np.all(p[:2]+RADIUS<=high[:2])
                    and p[2]-RADIUS>=low[2] and p[2]<=0.005,
                    f"rigid aircraft left its measured enclosure (x={p[0]:.3f}, y={p[1]:.3f}, z={p[2]:.3f})")
            require(r[2,2]>cos(.65),"rigid aircraft exceeded the measured attitude envelope")

    def packet(self,tick):
        ready,waiting=[],[]
        for entry in self.pending:
            (ready if entry[0]<=self.step_id else waiting).append(entry)
        self.pending=waiting
        ready.sort(key=lambda item:(item[1]["capture_us"],item[1]["id"]))
        imu,self.batched=self.batched,[]
        links,self.links=self.links,[]
        return {"tick":tick,"now_us":self.start+self.step_id*STEP_US,"imu":imu,
                "vision":[row for _,row,_ in ready],"frame_links":links,
                "height_m":float(-self.native.data.qpos[2]),"contact":self.native.data.ncon>0}, ready


def commissioned(app, kit, output):
    """Run the shipped commissioning command before each held-out flight."""
    work = run([sys.executable,"-B","-m","px4_recovery","commission","--spec",str(kit["spec"]),
                "--output",str(output)],cwd=app,stderr=DEVNULL,stdout=DEVNULL,timeout=18,
               env=candidate_environment(output.parent),**identity())
    require(work.returncode==0 and output.is_file() and not output.is_symlink() and output.stat().st_size<64_000,
            "held-out flight could not obtain a bounded candidate commissioning result")
    report=json.loads(output.read_text())
    require(isinstance(report, dict) and report.get("status")=="ok",
            "candidate rejected an observable commissioning kit")


def check_flight(app: Path, root: Path, case: dict):
    """Inspect actual safety, causal sensor decisions, and physical terminal liveness."""
    kit=make_kit(root/"bench",case["variant"])
    cfg=describe(kit,case)
    spec=root/"flight.json"
    spec.write_text(json.dumps(cfg))
    scratch=root/"candidate"
    scratch.mkdir(mode=0o777)
    scratch.chmod(0o777)
    calibration=scratch/"imu-tuning.json"
    commissioned(app,kit,calibration)
    environment=Environment(cfg,kit,case)
    pilot=Driver(app,spec,scratch,command=["fly","--spec",str(spec),"--calibration",str(calibration)])
    modes,decisions=Counter(),Counter()
    next_goal=goal_dwell=0
    maximum=[0.0,0.0,0.0]
    latest=environment.start
    prior_capture=environment.start
    reordered=False
    ground_contacts=0
    delayed_positions=0
    committed=False
    latest_at_commit=None
    try:
        for tick in range(396):
            packet,ready=environment.packet(tick)
            reply=pilot.exchange(packet)
            modes[reply.get("mode")]+=1
            expected_decisions=[]
            for _,row,want in ready:
                if want=="frame" and any(link["epoch"]==row["epoch"] for link in packet["frame_links"]):
                    want="accepted"
                expected_decisions.append({"id":row["id"],"status":want})
                decisions[want]+=1
                if want=="accepted":
                    reordered|=row["capture_us"]<prior_capture
                    prior_capture=max(prior_capture,row["capture_us"])
                    if row["position_m"] is not None:
                        latest=max(latest,row["capture_us"])
                        delayed_positions+=1
            require(reply.get("aiding")==expected_decisions,
                    f"capture/frame decisions incorrect at tick {tick}: expected {expected_decisions}, got {reply.get('aiding')}")
            require(reply.get("accepted_position_us")==latest,"position eligibility used arrival time or applied a duplicate")
            p,v,r,_=environment.native.motion()
            estimate=reply["estimate"]
            q=np.asarray(estimate["q_wxyz"])
            require(q.shape==(4,) and abs(np.linalg.norm(q)-1)<1e-4,"attitude output is not a unit quaternion")
            measured_p=np.array(estimate["position_m"])
            measured_v=np.array(estimate["velocity_mps"])
            require(measured_p.shape==(3,) and measured_v.shape==(3,),"position and velocity must contain three axes")
            ep=float(np.linalg.norm(measured_p-p))
            ev=float(np.linalg.norm(measured_v-v))
            eq=angle_error(q,quaternion(r))
            maximum=[max(a,b) for a,b in zip(maximum,[ep,ev,eq])]
            mode=reply.get("mode")
            age=packet["now_us"]-latest
            if not committed and age>cfg["brake_age_us"]:
                committed=True
                latest_at_commit=latest
                require(np.linalg.norm(v[:2])<0.22,"fallback began before horizontal braking took effect")
            want="land" if committed else "brake" if age>cfg["track_age_us"] else "track"
            require((mode==want or mode=="complete" and want=="track" or mode=="disarmed" and want=="land"),
                    f"unsupported flight authority mode at tick {tick}, age {age}: {mode!r}")
            require(ep<(0.12 if committed else 0.040) and ev<(0.17 if committed else 0.066) and eq<0.055,
                    f"current-time estimate outside held-out tolerance at tick {tick}: {ep:.3f} m, {ev:.3f} m/s, {eq:.3f} rad")
            rates=np.array(reply["body_rates_rad_s"],dtype=float)
            thrust=reply["collective"]
            require(rates.shape==(3,) and np.isfinite(rates).all() and np.max(abs(rates))<=cfg["max_body_rate_rad_s"]+1e-9
                    and type(thrust) in (int,float) and 0<=thrust<=1,"invalid body-rate or collective command")
            if next_goal<len(cfg["waypoints"]):
                goal=cfg["waypoints"][next_goal]
                yaw_error=abs(atan2(sin(yaw_of(r)-goal["yaw_rad"]),cos(yaw_of(r)-goal["yaw_rad"])))
                if (want=="track" and np.linalg.norm(p-goal["position_m"])<=cfg["position_tolerance_m"]+0.018
                    and np.linalg.norm(v)<=cfg["speed_tolerance_mps"]+0.021 and yaw_error<=cfg["yaw_tolerance_rad"]+0.022):
                    goal_dwell+=1
                    if goal_dwell>=cfg["dwell_ticks"]:
                        next_goal+=1
                        goal_dwell=0
                else:
                    goal_dwell=0
            if packet["contact"]:
                ground_contacts+=1
                require(want=="land" and abs(v[2])<0.43 and np.linalg.norm(v[:2])<0.24,
                        "airframe touched down without a controlled low-velocity descent")
                pads=cfg["landing_area"]
                require(np.all(p[:2]>=pads["min_ne_m"]) and np.all(p[:2]<=pads["max_ne_m"]),
                        "airframe touched down outside the independently measured landing area")
            if mode in ("complete","disarmed"):
                if case["kind"] in ("land","rejoin"):
                    require(mode=="disarmed" and ground_contacts>=3 and thrust==0 and np.linalg.norm(rates)==0
                            and modes["brake"]>=4 and modes["land"]>=20,"failed to physically brake, descend, and disarm")
                else:
                    require(mode=="complete" and next_goal==len(cfg["waypoints"]) and reply.get("waypoint")==next_goal,
                            "reported completion without both physical pose dwells")
                if case["kind"] in ("land","rejoin","recover"):
                    require(environment.outage is not None and environment.outage_speed>0.40 and modes["brake"]>=4,
                            "moving blackout or its braking branch was not exercised")
                    if case["kind"]=="recover":
                        require(modes["land"]==0,"a recoverable blackout caused a landing")
                    if case["kind"]=="rejoin":
                        require(latest>latest_at_commit,"the intended late horizontal reacquisition was not exercised")
                if case["kind"]=="reorder":
                    require(reordered and delayed_positions>=8,"out-of-order partial aiding was not exercised")
                if case["kind"]=="frame":
                    require(decisions["frame"]>=1,"missing link did not exercise frame rejection")
                if case["kind"]=="check":
                    require(all(decisions[key]>=2 for key in ("duplicate","innovation","time")),
                            "all three bad-capture categories must be exercised")
                return {"terminal":mode,"tick":tick,"peak_estimate_error":maximum,"mode_counts":dict(modes),
                        "aiding":dict(decisions),"land_contacts":environment.contacts,
                        "max_touchdown_speed_mps":environment.max_touchdown_speed,
                        "outage_speed_mps":environment.outage_speed,"outage_tilt_rad":environment.outage_tilt}
            environment.advance(rates,thrust)
        require(False,"simulated route neither completed nor landed inside its time horizon")
    finally:
        pilot.close()
