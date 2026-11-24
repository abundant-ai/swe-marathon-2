"""Direct headless precision-landing qualification using a rigid body and a scripted cart."""

import json
import math

import mujoco
import numpy as np

from flight_native import quaternion
from transport import Driver, require


DT = .004
G = np.array([0.,0.,9.81])
DECK_Z = -.28
AIRFRAME_RADIUS = .069
ARM = np.array([.14,-.055,.021])
PERIOD = .04
MAX_CAPTURE_AGE = .46
DEADLINE = 14.
CASE_NAMES = ("curved-east", "curved-west-reacquire", "persistent-loss")


def rotation(yaw):
    return np.array([[math.cos(yaw),-math.sin(yaw),0.],
                     [math.sin(yaw),math.cos(yaw),0.],
                     [0.,0.,1.]])


ROLL = .162
MOUNT = rotation(-.43) @ np.array([[1.,0.,0.],[0.,math.cos(ROLL),-math.sin(ROLL)],
                                  [0.,math.sin(ROLL),math.cos(ROLL)]])


def local_estimate(t, position, velocity, attitude):
    """A separate navigation source supplies small, bounded tracking error."""
    delta = np.array([.003*math.sin(1.35*t),.004*math.cos(1.6*t),.002*math.sin(t)])
    rate = np.array([.00405*math.cos(1.35*t),-.0064*math.sin(1.6*t),.002*math.cos(t)])
    return position+delta, velocity+rate, rotation(.003*math.sin(1.3*t))@attitude


def cart_state(t, case):
    direction = 1 if case == "curved-east" else -1
    return (np.array([direction*(.52+.345*t+.17*math.sin(.8*t)),
                      .16+.34*math.sin(.7*t+.15), DECK_Z]),
            np.array([direction*(.345+.136*math.cos(.8*t)),
                      .238*math.cos(.7*t+.15), 0.]),
            direction*(.28+.31*math.sin(.65*t)),
            direction*.2015*math.cos(.65*t))


class CartPlant:
    def __init__(self, case):
        self.case = case
        self.mass = 1.18 if case == "curved-east" else 1.31
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
            <body name="cart" pos="0 0 {DECK_Z+.036}">
              <joint name="cart_x" type="slide" axis="1 0 0"/>
              <joint name="cart_y" type="slide" axis="0 1 0"/>
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
        self.data.qpos[7:] = [p[0],p[1],heading]
        self.data.qvel[6:] = [v[0],v[1],yaw_rate]

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




MOVING_CASES = [{"name": "cart-"+case, "case": case} for case in CASE_NAMES]


def spec():
    return {"period_us":40000,"deadline_us":14_000_000,"max_capture_age_us":460_000,
            "abort_age_us":1_450_000,"deck_down_m":DECK_Z,"staging_down_m":-1.34,
            "hold_yaw_rad":1.8,"hover_collective":.49,"max_body_rate_rad_s":2.65,
            "min_stale_clearance_m":.48,"minimum_quality":75,
            "camera":{"lever_arm_m":ARM.tolist(),"body_from_camera_wxyz":quaternion(MOUNT).tolist()}}


def finite_number(value):
    return type(value) in (float,int) and math.isfinite(value)


def check_motion(reply, cfg):
    phase, rates, throttle = (reply[key] for key in ("phase", "body_rates_rad_s", "collective"))
    require(phase in ("approach","descend","hold","abort"),"unknown moving landing phase")
    require(isinstance(rates,list) and len(rates)==3 and all(finite_number(x) for x in rates)
            and max(map(abs,rates))<=cfg["max_body_rate_rad_s"]+1e-7,
            "invalid body-rate authority")
    require(finite_number(throttle) and 0.<=throttle<=1.,"invalid collective authority")
    return phase, np.array(rates), throttle


def check_prediction(target, now, eligible, max_age):
    if target is None:
        return None
    require(isinstance(target,dict) and target.get("at_us")==now,"target estimate timestamp mismatch")
    captured = target.get("capture_us")
    require(type(captured) is int and captured in eligible and 0<=now-captured<=max_age,
            "target estimate has unsupported source timestamp")
    values = [target.get(key) for key in ("position_ne_m","velocity_ne_mps")]
    require(all(isinstance(row,list) and len(row)==2 and all(finite_number(x) for x in row)
                for row in values),"invalid target state estimate")
    return np.array(values[0])


def run_moving(driver, case, cfg):
    sim = CartPlant(case)
    rng = np.random.default_rng(7712+CASE_NAMES.index(case))
    navigation, pending, recent, forecasts = [], [], [], []
    eligible_captures = set()
    phase, rates, collective = "hold", np.zeros(3), .49
    blackout, release, impact = None, None, None
    previous_quality_capture = None
    available_ticks = 0
    violation = None
    step_us = round(DT*1e6)
    control_steps = cfg["period_us"]//step_us
    frame_count = 0
    abort_seen = False
    descent_seen = False
    for step in range(cfg["deadline_us"]//step_us):
        now = step*step_us
        t = now/1e6
        p,v,body = sim.state()
        xy,pad_v,pad_yaw,pad_yaw_rate = cart_state(t,case)
        if blackout is None and case!="curved-east" and p[2]>-.98 and phase=="descend":
            blackout = now
            release = now+1_030_000 if case=="curved-west-reacquire" else None
        visible = blackout is None or (release is not None and now>=release)

        own_p,own_v,own_body = local_estimate(t,p,v,body)
        navigation.append({"at_us":now,"position_ned_m":own_p.tolist(),"velocity_ned_mps":own_v.tolist(),
                           "q_ned_from_body_wxyz":quaternion(own_body).tolist()})
        if step%17==4 and visible:
            frame_count += 1
            delay = [241000,358000,267000,302000,216000][frame_count%5]
            cam_to_ned = body@MOUNT
            measured = np.linalg.solve(cam_to_ned,xy-p-body@ARM)+rng.normal(0.,.0016,3)
            quality = 91
            if frame_count%21==9:
                quality = 40
                measured += np.array([.17,-.13,.015])
            row = {"id":f"camera-{frame_count}","capture_us":now,
                   "position_camera_m":measured.tolist(),"quality":quality}
            pending.append((now+delay,row))
            if frame_count%14==2:
                pending.append((now+delay+530000,row))
        if step%control_steps==0:
            delivered = [packet for when,packet in pending if now>=when]
            pending = [row for row in pending if now<row[0]]
            eligible_captures.update(packet["capture_us"] for packet in delivered
                                     if packet["quality"]>=cfg["minimum_quality"])
            if eligible_captures:
                previous_quality_capture = max(eligible_captures)
            age = None if previous_quality_capture is None else now-previous_quality_capture
            stale = age is not None and age>cfg["max_capture_age_us"]
            reply = driver.exchange({"now_us":now,"navigation":navigation,"target_detections":delivered})
            navigation = []
            phase,rates,collective = check_motion(reply,cfg)
            abort_latched = not abort_seen or phase=="abort"
            abort_seen |= phase=="abort"
            descent_seen |= phase=="descend"
            if (descent_seen and age is not None and age>cfg["abort_age_us"]+cfg["period_us"]
                    and phase!="abort"):
                violation = "persistent target loss did not enter abort by the deadline"
                break
            point = check_prediction(reply["target"],now,eligible_captures,cfg["max_capture_age_us"])
            if stale:
                recent.append((phase,DECK_Z-p[2]))
                if phase not in ("hold","abort") or point is not None:
                    violation = "continued moving-target descent during stale evidence"
                    break
            if not abort_latched:
                violation = "abort phase did not latch"
                break
            if age is not None and not stale and t>1.0:
                available_ticks += 1
                if point is not None:
                    forecasts.append(float(np.linalg.norm(point-xy[:2])))
        sim.step(rates,collective)
        if sim.data.ncon and not sim.deck_contact():
            violation = "unintended native contact"
            break
        if sim.deck_contact():
            local = rotation(pad_yaw).T@(p-xy)
            surface_v = pad_v+np.cross([0.,0.,pad_yaw_rate],p-xy)
            impact = {"time_s":t,"radial_miss_m":float(np.linalg.norm(local[:2])),
                      "vertical_mps":float(v[2]),"slip_mps":float(np.linalg.norm(v[:2]-surface_v[:2])),
                      "source_age_us":None if previous_quality_capture is None else now-previous_quality_capture,
                      "phase":phase}
            break
        if abs(p[0])>7. or abs(p[1])>1.5 or not -2.0<=p[2]<=-.055:
            violation = "aircraft left the physical enclosure"
            break

    clearance = min((height for _,height in recent),default=None)
    rmse = float(np.sqrt(np.mean(np.square(forecasts)))) if forecasts else None
    summary = {"case":case,"deck_contact":impact,"terminal_phase":phase,"stale_ticks":len(recent),
               "minimum_stale_clearance_m":clearance,"target_forecast_rmse_m":rmse,
               "forecast_steps":len(forecasts),"fresh_observation_steps":available_ticks,
               "blackout_at_us":blackout,"target_return_at_us":release}
    require(not violation,(violation or "")+": "+json.dumps(summary))
    require(available_ticks>15 and len(forecasts)>=.75*available_ticks and rmse is not None and rmse<=.060,
            "insufficient target prediction accuracy or coverage: "+json.dumps(summary))
    if case!="curved-east":
        require(recent and clearance>=cfg["min_stale_clearance_m"],
                "blackout did not yield a physically safe hold: "+json.dumps(summary))
    if case=="persistent-loss":
        require(impact is None and phase=="abort","persistent loss did not latch abort: "+json.dumps(summary))
    else:
        require(impact is not None and impact["phase"]=="descend" and impact["source_age_us"] is not None
                and impact["source_age_us"]<=cfg["max_capture_age_us"] and impact["radial_miss_m"]<=.097
                and 0.<=impact["vertical_mps"]<=.30 and impact["slip_mps"]<=.15,
                "no safe native moving-deck touchdown by the deadline: "+json.dumps(summary))
    return summary


def check_moving(app, root, case):
    cfg = spec()
    path = root/"commissioned.json"
    path.write_text(json.dumps(cfg)+"\n")
    driver = Driver(app,path,root,command=["land-moving","--spec",str(path)])
    try:
        return run_moving(driver,case["case"],cfg)
    finally:
        driver.close()
