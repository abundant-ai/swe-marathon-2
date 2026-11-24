"""Native moving-deck contact from independent raw onboard aiding in a local gauge."""

import json
import math

import mujoco
import numpy as np

from flight_native import quaternion
from transport import Driver, require


DT = .004
G = np.array([0.,0.,9.81])
DECK_CENTER_DOWN = -.36
AIRFRAME_RADIUS = .069
CAMERA_ARM = np.array([.064,-.034,.012])
MAX_CAPTURE_AGE = .43
MAX_VISION_GAP = 1.45
DEADLINE = 16.
CASE_NAMES = ("relative-east", "relative-west-reacquire", "bearing-loss-abort", "floor-flow-reacquire")
EAST_CASES = {"relative-east","floor-flow-reacquire"}
BEARING_LOSS_CASES = {"relative-west-reacquire","bearing-loss-abort"}


def rotation(yaw):
    return np.array([[math.cos(yaw),-math.sin(yaw),0.],
                     [math.sin(yaw),math.cos(yaw),0.],
                     [0.,0.,1.]])


ROLL = .162
MOUNT = rotation(-.43) @ np.array([[1.,0.,0.],[0.,math.cos(ROLL),-math.sin(ROLL)],
                                  [0.,math.sin(ROLL),math.cos(ROLL)]])


def cart_state(t, case):
    direction = 1 if case in EAST_CASES else -1
    return (np.array([direction*(.52+.345*t+.17*math.sin(.8*t)),
                      .16+.34*math.sin(.7*t+.15), .04*math.sin(.91*t) + (DECK_CENTER_DOWN if direction>0 else -.43)]),
            np.array([direction*(.345+.136*math.cos(.8*t)),
                      .238*math.cos(.7*t+.15), .0364*math.cos(.91*t)]),
            direction*(.28+.31*math.sin(.65*t)),
            direction*.2015*math.cos(.65*t))


class CartPlant:
    def __init__(self, case):
        self.case = case
        self.mass = 1.18 if case in EAST_CASES else 1.31
        xml = f"""
        <mujoco model="commissioning enclosure">
          <compiler angle="radian"/>
          <option timestep="{DT}" gravity="0 0 9.81" integrator="implicitfast"/>
          <worldbody>
            <geom name="floor" type="plane" size="15 8 .1" euler="{math.pi} 0 0"/>
            <body name="airframe">
              <freejoint/>
              <inertial pos="0 0 0" mass="{self.mass}" diaginertia=".012 .013 .021"/>
              <geom name="shoe" type="sphere" size="{AIRFRAME_RADIUS}" friction=".9 .004 .0002"/>
            </body>
            <body name="cart" pos="0 0 .036">
              <joint name="cart_x" type="slide" axis="1 0 0"/>
              <joint name="cart_y" type="slide" axis="0 1 0"/>
              <joint name="cart_z" type="slide" axis="0 0 1"/>
              <joint name="cart_yaw" type="hinge" axis="0 0 1"/>
              <geom name="deck" type="box" size=".245 .205 .036" mass="45" friction=".9 .004 .0002"/>
            </body>
          </worldbody>
        </mujoco>"""
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)
        self.body = self.model.body("airframe").id
        self.foot = self.model.geom("shoe").id
        self.deck = self.model.geom("deck").id
        self.data.qpos[:7] = [0.,-.36,-1.34,math.cos(.9),0.,0.,math.sin(.9)]
        self.thrust = self.mass*9.81
        self.torque = np.zeros(3)
        self.update_cart(0.)
        mujoco.mj_forward(self.model,self.data)

    def update_cart(self, t):
        p,v,heading,yaw_rate = cart_state(t,self.case)
        self.data.qpos[7:] = [p[0],p[1],p[2],heading]
        self.data.qvel[6:] = [v[0],v[1],v[2],yaw_rate]

    def state(self):
        return (self.data.qpos[:3].copy(),self.data.qvel[:3].copy(),
                self.data.xmat[self.body].reshape(3,3).copy())

    def deck_contact(self):
        return any({contact.geom1,contact.geom2} == {self.foot,self.deck}
                   for contact in self.data.contact)

    def step(self, rates, collective):
        t = self.data.time
        _,v,r = self.state()
        local = np.empty(6)
        mujoco.mj_objectVelocity(self.model,self.data,mujoco.mjtObj.mjOBJ_BODY,self.body,local,1)
        self.thrust += .094*(self.mass*9.81*collective/.49-self.thrust)
        wanted = np.clip((rates-local[:3])*[.18,.18,.16],-.23,.23)
        self.torque += .21*(wanted-self.torque)
        wind = np.array([.047*math.sin(1.6*t),.059*math.cos(t),.023*math.sin(2*t)])
        self.data.xfrc_applied[self.body,:3] = r@[0.,0.,-self.thrust]-.22*v+wind
        self.data.xfrc_applied[self.body,3:] = r@self.torque
        self.update_cart(t)
        mujoco.mj_step(self.model,self.data)
        mujoco.mj_forward(self.model,self.data)




RANGE_ARM = np.array([-.051,.038,-.018])
FLOW_ARM = np.array([.07,.082,.014])
FLOW_MOUNT = rotation(.25)@np.array([[1.,0.,0.],[0.,.9838437,-.1790296],[0.,.1790296,.9838437]])
MAX_FLOW_AGE = .22



IMU_STEP_US = 4000
CONTROL_STEP_US = 40000

class Sensors:
    def __init__(self, seed):
        self.rng=np.random.default_rng(seed)
        self.pending=[]

    def imu(self, step, before, after, native):
        _,v0,r0=before
        _,v1,r1=after
        result=np.empty(6)
        mujoco.mj_objectVelocity(native.model,native.data,mujoco.mjtObj.mjOBJ_BODY,native.body,result,1)
        w=result[:3].copy()
        force=.5*(r0+r1).T@((v1-v0)/DT-G)+np.array([.091,-.056,.048])
        noisy_omega=w+np.array([.00038,-.00021,.00083])+self.rng.normal(0.,.00024,3)
        return w,{"capture_us":step*IMU_STEP_US,"gyro_rad_s":noisy_omega.tolist(),
                  "specific_force_mps2":(force+self.rng.normal(0.,.004,3)).tolist()}

    def flow(self, step, p,v,r,w, low_quality):
        orientation=r@FLOW_MOUNT
        camera_v=orientation.T@(v+r@np.cross(w,FLOW_ARM))
        change=FLOW_MOUNT.T@w
        slant=-(p+r@FLOW_ARM)[2]/orientation[2,2]
        interval=.042
        rotation_flow=interval*change[:2]
        optical=rotation_flow+interval*np.array([-camera_v[1],camera_v[0]])/slant
        packet={"stream":"flow","step":step,"quality":35 if low_quality else 92,
                "slant_m":slant+float(self.rng.normal(0.,.0015)),"interval_s":interval,
                "integrated_gyro_rad":rotation_flow.tolist(),
                "integrated_flow_rad":(optical+self.rng.normal(0.,.00013,2)).tolist()}
        delay=(14,24,17,9)[(step//16)%4]
        self.pending.append((step+delay,packet))

    def target(self, step, state, target_state, bearing_visible):
        p,_,r=state
        position=target_state[0]
        if step%21==4 and bearing_visible:
            vec=MOUNT.T@(r.T@(position-p)-CAMERA_ARM)
            uv=vec[:2]/max(.018,vec[2])+self.rng.normal(0.,.0015,2)
            seq=step//21
            quality=40 if seq%18==7 or vec[2]<.018 or np.linalg.norm(uv)>2.7 else 96
            if quality<70:
                uv += [.15,-.11]
            delay=(59,48,71,53,46)[seq%5]
            packet={"stream":"bearing","step":step,"bearing_xy":uv.tolist(),"quality":quality}
            self.pending.append((step+delay,packet))
            if seq%13==4:
                self.pending.append((step+delay+84,packet))
        if step%16==7:
            distance=float(np.linalg.norm(position-p-r@RANGE_ARM))
            seq=step//16
            delay=(19,35,22,27,17)[seq%5]
            self.pending.append((step+delay,{"stream":"range","step":step,
                         "range_m":distance+float(self.rng.normal(0.,.0035)),"quality":93}))

    def deliver(self, step):
        out=[row for arrival,row in self.pending if arrival<=step]
        self.pending=[item for item in self.pending if item[0]>step]
        return out


RELATIVE_CASES = [{"name":"sensor-only-"+case,"case":case} for case in CASE_NAMES]


def config():
    return {"imu_period_us":IMU_STEP_US,"period_us":CONTROL_STEP_US,"deadline_us":round(DEADLINE*1e6),
            "bearing_max_age_us":round(MAX_CAPTURE_AGE*1e6),"range_max_age_us":270_000,"flow_max_age_us":220_000,
            "abort_age_us":round(MAX_VISION_GAP*1e6),"hover_collective":.49,"max_body_rate_rad_s":2.65,
            "camera":{"lever_arm_m":CAMERA_ARM.tolist(),"body_from_sensor_wxyz":quaternion(MOUNT).tolist()},
            "flow":{"lever_arm_m":FLOW_ARM.tolist(),"body_from_sensor_wxyz":quaternion(FLOW_MOUNT).tolist()},
            "range":{"lever_arm_m":RANGE_ARM.tolist()}}


def finite_number(value):
    return type(value) in (float,int) and math.isfinite(value)


def vector(value):
    require(isinstance(value,list) and len(value)==3 and all(finite_number(x) for x in value),
            "invalid finite three-vector")
    return np.asarray(value,dtype=float)


def control(driver,step,imu,detections,cfg):
    reply = driver.exchange({"now_us":step*IMU_STEP_US,"imu":imu,
                             "detections":[{k:v for k,v in record.items() if k!="step"}|
                                           {"capture_us":record["step"]*IMU_STEP_US}
                                           for record in detections]})
    phase,rates,collective = reply["phase"],vector(reply["body_rates_rad_s"]),reply["collective"]
    require(phase in ("approach","descend","hold","abort"),"unknown flight phase")
    require(np.max(np.abs(rates))<=cfg["max_body_rate_rad_s"]+1e-7 and finite_number(collective)
            and 0.<=collective<=1.,"actuation left the commissioned limits")
    estimate=reply["relative"]
    if estimate is not None:
        require(isinstance(estimate,dict) and set(estimate)=={"position_m","velocity_mps"},
                "invalid relative estimate contract")
        estimate=vector(estimate["position_m"]),vector(estimate["velocity_mps"])
    return phase,rates,collective,estimate


def fly(driver,case,cfg):
    native=CartPlant(case)
    sensors=Sensors(8183+CASE_NAMES.index(case))
    phase,rates,collective="hold",np.zeros(3),.49
    imu=[]
    latest={}
    errors=[]
    velocity_errors=[]
    descent_witness=[]
    stale_ranging=[]
    flow_dropout=[]
    flow_loss_at=None
    hold_speeds=[]
    fresh_steps=0
    blackout,reopen,contact=None,None,None
    sortie_aborted=False
    fault=None
    for step in range(cfg["deadline_us"]//IMU_STEP_US):
        t = step*DT
        state = native.state()
        p,v,_ = state
        deck,deck_velocity,_,deck_yaw_rate=cart_state(t,case)
        clearance = deck[2]-p[2]
        if blackout is None and case in BEARING_LOSS_CASES and clearance<.755 and phase=="descend":
            blackout=t
            reopen=t+1.10 if case=="relative-west-reacquire" else None
        if flow_loss_at is None and case=="floor-flow-reacquire" and clearance<.755 and phase=="descend":
            flow_loss_at=t
        visible=blackout is None or (reopen is not None and t>=reopen)
        sensors.target(step,state,(deck,deck_velocity),visible)
        if step%(CONTROL_STEP_US//IMU_STEP_US)==0:
            detections=sensors.deliver(step)
            for observation in detections:
                stream=observation["stream"]
                cutoff=75 if stream=="flow" else 70
                if observation["quality"]>=cutoff:
                    latest[stream]=max(observation["step"],latest.get(stream,-1))
            ages={name:(step-latest[name])*IMU_STEP_US if name in latest else math.inf
                  for name in ("bearing","range","flow")}
            available=all(ages[name]<=cfg[f"{name}_max_age_us"] for name in ages)
            previous=phase
            phase,rates,collective,estimate=control(driver,step,imu,detections,cfg)
            imu=[]
            if phase=="descend" and previous!="descend":
                descent_witness.append({"time_s":t,"relative_speed_mps":float(np.linalg.norm(v[:2]-deck_velocity[:2])),
                                        "center_distance_m":float(np.linalg.norm(p[:2]-deck[:2]))})
            if sortie_aborted and phase!="abort":
                fault="land authority recovered after an abort"
                break
            sortie_aborted |= phase=="abort"
            if phase=="descend" and not available:
                fault="descent with stale bearing, range or floor velocity support"
                break
            if t>.8 and available and not sortie_aborted:
                fresh_steps+=1
                if estimate is not None:
                    frame=rotation(-1.8)
                    errors.append(float(np.linalg.norm(estimate[0]-frame@(deck-p))))
                    velocity_errors.append(float(np.linalg.norm(estimate[1]-frame@(deck_velocity-v))))
            if blackout is not None and ages["bearing"]>cfg["bearing_max_age_us"] and ages["range"]<=cfg["range_max_age_us"]:
                stale_ranging.append(float(clearance))
                if phase not in ("hold","abort"):
                    fault="continued approach with range only"
                    break
                if t>blackout+1.02:
                    hold_speeds.append(float(np.linalg.norm(v[:2])))
            if (case=="bearing-loss-abort" and blackout is not None
                    and ages["bearing"]>cfg["abort_age_us"]+CONTROL_STEP_US and phase!="abort"):
                fault="persistent bearing loss did not latch abort by its deadline"
                break
            if (flow_loss_at is not None and ages["flow"]>cfg["flow_max_age_us"]
                    and ages["bearing"]<=cfg["bearing_max_age_us"] and ages["range"]<=cfg["range_max_age_us"]):
                flow_dropout.append(float(clearance))
                if phase!="hold":
                    fault="missing ground-flow support did not trigger hold"
                    break
        native.step(rates,collective)
        after=native.state()
        omega,record=sensors.imu(step+1,state,after,native)
        imu.append(record)
        if (step+1)%16==3:
            invalid_floor_sampling=(case=="relative-west-reacquire" and 2.4<t<2.54
                                    or flow_loss_at is not None and t<flow_loss_at+.73)
            sensors.flow(step+1,*after,omega,invalid_floor_sampling)
        if native.data.ncon and not native.deck_contact():
            fault="unintended ground or enclosure contact"
            break
        if native.deck_contact():
            surface=deck_velocity+np.cross([0.,0.,deck_yaw_rate],p-deck)
            contact={"time_s":t,"center_error_m":float(np.linalg.norm(p[:2]-deck[:2])),
                     "closing_mps":float(v[2]-surface[2]),
                     "relative_slip_mps":float(np.linalg.norm(v[:2]-surface[:2])),
                     "phase":phase,"fresh_support":all(name in latest and
                                (step-latest[name])*IMU_STEP_US<=cfg[f"{name}_max_age_us"]
                                for name in ("bearing","range","flow"))}
            break
        if abs(p[0])>8.5 or abs(p[1])>1.6 or not -2.4<=p[2]<=-.05:
            fault="left the flight enclosure"
            break

    position_rmse=float(np.sqrt(np.mean(np.square(errors)))) if errors else None
    velocity_rmse=float(np.sqrt(np.mean(np.square(velocity_errors)))) if errors else None
    min_hold=min(stale_ranging,default=None)
    max_drift=max(hold_speeds,default=None)
    result={"case":case,"contact":contact,"descent_entries":descent_witness,
            "terminal_phase":phase,"bearing_blackout_at_s":blackout,"stale_bearing_live_range_ticks":len(stale_ranging),
            "minimum_stale_clearance_m":min_hold,"maximum_late_hold_ground_speed_mps":max_drift,
            "relative_position_rmse_m":position_rmse,"relative_velocity_rmse_mps":velocity_rmse,
            "relative_estimate_ticks":len(errors),"supported_sensor_ticks":fresh_steps,
            "stale_flow_ticks":len(flow_dropout),"floor_flow_blackout_at_s":flow_loss_at,
            "minimum_stale_flow_clearance_m":min(flow_dropout,default=None)}
    require(not fault,(fault or "")+": "+json.dumps(result))
    require(fresh_steps>=25 and len(errors)>=.75*fresh_steps and position_rmse is not None
            and position_rmse<=.075 and velocity_rmse<=.23,
            "relative estimation did not qualify: "+json.dumps(result))
    require(descent_witness and all(row["relative_speed_mps"]<=.21 and row["center_distance_m"]<=.14
                                   for row in descent_witness),
            "descent before relative position and velocity converged: "+json.dumps(result))
    if case in BEARING_LOSS_CASES:
        require(min_hold is not None and min_hold>=.43,
                "bearing outage did not yield a safe independent hold: "+json.dumps(result))
    if case=="floor-flow-reacquire":
        require(flow_dropout and min(flow_dropout)>=.43,
                "ground-flow outage did not yield a safe hold: "+json.dumps(result))
    if case=="bearing-loss-abort":
        require(contact is None and phase=="abort" and max_drift is not None and max_drift<=.22,
                "sustained bearing loss did not yield a stationary abort: "+json.dumps(result))
    else:
        require(contact is not None and contact["phase"]=="descend" and contact["fresh_support"]
                and contact["center_error_m"]<=.096 and 0<=contact["closing_mps"]<=.30
                and contact["relative_slip_mps"]<=.15,
                "qualified native moving-deck touchdown not reached: "+json.dumps(result))
    return result


def check_relative(app,root,case):
    commissioning = config()
    spec=root/"sensor-commissioning.json"
    spec.write_text(json.dumps(commissioning)+"\n")
    driver=Driver(app,spec,root,command=["land-relative","--spec",str(spec)])
    try:
        return fly(driver,case["case"],commissioning)
    finally:
        driver.close()
