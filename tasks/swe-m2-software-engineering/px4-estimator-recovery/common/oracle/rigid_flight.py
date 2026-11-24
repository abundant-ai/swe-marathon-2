"""Predict two time domains and pilot an FRD rigid body from delayed aiding."""

from math import acos, atan2, cos, hypot, sin
from pathlib import Path
import json
import sys

import numpy as np


G = np.array([0.0, 0.0, 9.81])


def unit(vector):
    return vector / np.linalg.norm(vector)


def qmul(a, b):
    w, x, y, z = a
    v, i, j, k = b
    return np.array([w*v-x*i-y*j-z*k, w*i+x*v+y*k-z*j, w*j-x*k+y*v+z*i, w*k+x*j-y*i+z*v])


def inverse(q):
    return q * [1, -1, -1, -1]


def exp(rotation):
    angle = np.linalg.norm(rotation)
    if angle < 1e-10:
        return unit(np.r_[1.0, rotation/2])
    return np.r_[cos(angle/2), rotation*(sin(angle/2)/angle)]


def rotate(q, v):
    """Apply active quaternion rotation to one vector."""
    w, x, y, z = q
    a, b, c = v
    i, j, k = 2*(y*c-z*b), 2*(z*a-x*c), 2*(x*b-y*a)
    return np.array([a+w*i+y*k-z*j, b+w*j+z*i-x*k, c+w*k+x*j-y*i])


def heading(q):
    w, x, y, z = q
    return atan2(2*(w*z+x*y), 1-2*(y*y+z*z))


def geodesic(a, b):
    return 2 * acos(min(1.0, abs(float(a @ b))))


def azimuth_error(target, actual):
    return atan2(sin(target-actual), cos(target-actual))


class Estimator:
    """Retain a bounded IMU history with independent partial anchoring."""

    def __init__(self, cfg, calibration):
        self.cfg = cfg
        self.calibration = calibration
        self.device = cfg["imu"]["device"]
        self.imu = cfg["imu"]
        self.mount = unit(np.array(self.imu["body_from_imu_wxyz"]))
        self.lever = np.array(self.imu["lever_arm_m"])
        self.camera_q = unit(np.array(cfg["camera"]["body_from_camera_wxyz"]))
        self.camera_lever = np.array(cfg["camera"]["lever_arm_m"])
        self.time = cfg["initial"]["timestamp_us"]
        self.base = (np.array(cfg["initial"]["position_m"]), np.array(cfg["initial"]["velocity_mps"]),
                     unit(np.array(cfg["initial"]["q_wxyz"])))
        self.last_position = self.time
        self.last_attitude = self.time
        self.sequences = set()
        self.aid_ids = set()
        self.segments = []
        self.updates = []
        self.frames = {}
        self.rate = np.zeros(3)
        self.rate_stamp = self.time

    def map_time(self, stamp):
        coefficients = self.calibration["devices"][self.device]
        correction = coefficients["skew_ppm"] * (stamp-self.imu["clock_origin_us"]) / 1_000_000
        return round(stamp + coefficients["offset_us"] + correction)

    def observations(self, event):
        """Convert device increments to corrected body-origin rates."""
        params = self.calibration["devices"][self.device]
        for row in sorted(event["imu"], key=lambda row: row["stamp_us"]):
            if row["sequence"] in self.sequences or row["clipped"]:
                continue
            self.sequences.add(row["sequence"])
            end = self.map_time(row["stamp_us"])
            start = self.map_time(row["stamp_us"]-row["interval_us"])
            if start>=end or end<=self.rate_stamp:
                continue
            dt = (end-start)/1_000_000
            temp_delta = row["temp_c"] - 25.0
            values = []
            for kind, field in (("gyro","delta_angle"),("accel","delta_velocity")):
                raw = np.array(row[field])/dt
                values.append(rotate(self.mount, (raw-np.array(params[kind+"_bias"])
                    -temp_delta*np.array(params[kind+"_temp_slope"]))/np.array(params[kind+"_gain"])))
            omega, force = values
            if self.segments:
                previous_end, previous_rate, _ = self.segments[-1]
                midpoint_gap = max(dt, (end-previous_end)/1_000_000)
                alpha = (omega-previous_rate)/midpoint_gap
            else:
                alpha = np.zeros(3)
            corrected_force = force - np.cross(alpha,self.lever) - np.cross(omega,np.cross(omega,self.lever))
            self.segments.append((end, omega, corrected_force))
            self.rate_stamp, self.rate = end, omega

    @staticmethod
    def advance(state, omega, force, delta_us):
        """Integrate body axes with a midpoint attitude and NED gravity."""
        p, v, q = state
        dt = delta_us / 1_000_000
        half = exp(omega * (0.5*dt))
        acceleration = rotate(qmul(q,half), force) + G
        return p+dt*v+(0.5*dt*dt)*acceleration, v+dt*acceleration, unit(qmul(q,qmul(half,half)))

    def predict(self, end):
        """Replay retained IMU and accepted updates in capture order."""
        cursor, state = self.time, self.base
        updates = iter(sorted(self.updates, key=lambda item: (item[0],item[1])))
        update = next(updates,None)
        imu = [(t,w,f) for t,w,f in self.segments if t>cursor]
        if imu:
            last_rate, last_force = imu[-1][1:]
        else:
            last_rate, last_force = self.rate, np.array([0.0,0.0,-9.81])
        imu.append((end,last_rate,last_force))
        for stamp, omega, force in imu:
            stop = min(stamp,end)
            while update is not None and update[0]<=stop:
                t, _, fix = update
                if t>cursor:
                    state = self.advance(state,omega,force,t-cursor)
                state = tuple(p if revised is None else revised for p,revised in zip(state,fix,strict=True))
                cursor = t
                update = next(updates,None)
            if stop>cursor:
                state = self.advance(state,omega,force,stop-cursor)
                cursor = stop
            if cursor==end:
                return state
        return state

    def corrections(self, event):
        """Decide whether each camera observation can correct its capture state."""
        now = event["now_us"]
        for frame in event["frame_links"]:
            epoch = frame["epoch"]
            self.frames[epoch] = (frame["start_us"],np.array(frame["translation_m"]),
                                  unit(np.array(frame["ned_from_vision_wxyz"])))
        report=[]
        for vision in sorted(event["vision"],key=lambda row:(row["capture_us"],row["id"])):
            identifier, stamp = vision["id"], vision["capture_us"]
            reason = "accepted"
            if identifier in self.aid_ids:
                reason = "duplicate"
            self.aid_ids.add(identifier)
            frame = self.frames.get(vision["epoch"])
            if reason=="accepted":
                if stamp>now or stamp<self.time or now-stamp>self.cfg["history_us"]:
                    reason="time"
                elif frame is None or stamp<frame[0] or any(frame[0]<item[0]<=stamp for item in self.frames.values()):
                    reason="frame"
            if reason=="accepted":
                expected = self.predict(stamp)
                _, translation, rotation = frame
                q = None
                if vision["q_wxyz"] is not None:
                    q = unit(qmul(qmul(rotation,unit(np.array(vision["q_wxyz"]))), inverse(self.camera_q)))
                body_q = expected[2] if q is None else q
                pos = None if vision["position_m"] is None else (
                    translation+rotate(rotation,vision["position_m"])-rotate(body_q,self.camera_lever))
                vel = None if vision["velocity_mps"] is None else (
                    rotate(rotation,vision["velocity_mps"])
                    -rotate(body_q,np.cross(vision["omega_body_rad_s"],self.camera_lever)))
                if ((pos is not None and np.linalg.norm(pos-expected[0])>self.cfg["innovation"]["position_m"]) or
                    (vel is not None and np.linalg.norm(vel-expected[1])>self.cfg["innovation"]["velocity_mps"]) or
                    (q is not None and geodesic(q,expected[2])>self.cfg["innovation"]["attitude_rad"])):
                    reason="innovation"
                else:
                    self.updates.append((stamp,identifier,(pos,vel,q)))
                    if pos is not None:
                        self.last_position=max(stamp,self.last_position)
                    if q is not None:
                        self.last_attitude=max(stamp,self.last_attitude)
            report.append({"id":identifier,"status":reason})
        return report

    def observe(self,event):
        """Produce current-time pose and causal aiding decisions."""
        self.observations(event)
        decisions=self.corrections(event)
        now=event["now_us"]
        cutoff=now-self.cfg["history_us"]-20_000
        if cutoff>self.time:
            self.base=self.predict(cutoff)
            self.time=cutoff
            self.segments=[row for row in self.segments if row[0]>cutoff]
            self.updates=[row for row in self.updates if row[0]>cutoff]
        return self.predict(now), decisions


class Pilot:
    """Execute waypoints, brake and descend through the same physical interface."""

    def __init__(self, cfg, calibration):
        self.cfg = cfg
        self.estimator = Estimator(cfg,calibration)
        self.target = 0
        self.dwell = 0
        self.landing = False
        self.contact = 0
        self.complete = False

    def command(self, q, acceleration, yaw):
        """Map a desired NED acceleration to FRD body-rate and collective."""
        force = G-acceleration
        down = unit(force)
        current_down=rotate(q,[0.0,0.0,1.0])
        tilt_world=np.cross(current_down,down)
        leveling = rotate(inverse(q),tilt_world)*7.4
        leveling[2]=2.4*azimuth_error(yaw,heading(q))
        rates = np.clip(leveling,-self.cfg["max_body_rate_rad_s"],self.cfg["max_body_rate_rad_s"])
        thrust = np.clip(self.cfg["hover_collective"] * (force @ current_down)/9.81,0.0,1.0)
        return rates.tolist(),float(thrust)

    def observe(self,event):
        """Preserve a recoverable mission or finish a bounded fallback landing."""
        (p,v,q), decisions = self.estimator.observe(event)
        now=event["now_us"]
        age=now-self.estimator.last_position
        self.landing |= age>self.cfg["brake_age_us"]
        self.contact=self.contact+1 if self.landing and event["contact"] else 0
        desired=np.zeros(3)
        yaw=heading(q)
        if self.landing:
            mode="land"
            desired[2]=2.8*(min(0.29,0.09+0.36*event["height_m"])-v[2])
        elif age>self.cfg["track_age_us"]:
            mode="brake"
            self.dwell=0
            desired[:2]=np.clip(-3.8*v[:2],-2.5,2.5)
            desired[2]=np.clip(-3.0*v[2],-1.5,1.5)
        else:
            mode="track"
            goal=self.cfg["waypoints"][min(self.target,len(self.cfg["waypoints"])-1)]
            error=np.array(goal["position_m"])-p
            yaw=goal["yaw_rad"]
            if (np.linalg.norm(error)<self.cfg["position_tolerance_m"] and
                np.linalg.norm(v)<self.cfg["speed_tolerance_mps"] and
                abs(azimuth_error(yaw,heading(q)))<self.cfg["yaw_tolerance_rad"]):
                self.dwell+=1
                if self.dwell>=self.cfg["dwell_ticks"] and not self.complete:
                    self.target+=1
                    self.dwell=0
                    self.complete=self.target==len(self.cfg["waypoints"])
            else:
                self.dwell=0
            commanded_speed=np.clip(1.55*error,-0.68,0.68)
            commanded_speed[2]=np.clip(commanded_speed[2],-0.43,0.43)
            desired=np.clip(3.25*(commanded_speed-v),-2.3,2.3)
            if self.complete:
                mode="complete"
        # The independent range observation keeps descent observable without horizontal aiding.
        if mode=="land":
            height_error=-event["height_m"]-p[2]
            self.estimator.updates.append((now, f"range-{event['tick']}",(p+np.array([0,0,height_error]),None,None)))
        rates, collective = self.command(q,desired,yaw)
        if self.contact>=3:
            mode,rates,collective="disarmed",[0.0,0.0,0.0],0.0
        return {"mode":mode,"waypoint":self.target,
                "estimate":{"position_m":p.tolist(),"velocity_mps":v.tolist(),"q_wxyz":q.tolist()},
                "accepted_position_us":self.estimator.last_position,"aiding":decisions,
                "body_rates_rad_s":rates,"collective":collective}


def fly(spec_path: Path, calibration_path: Path) -> None:
    """Run the NDJSON flight interface with an earlier commissioning result."""
    spec=json.loads(spec_path.read_text())
    calibration=json.loads(calibration_path.read_text())
    if calibration["status"]!="ok":
        raise ValueError("flight requires an observable commissioned sensor")
    pilot=Pilot(spec,calibration)
    for line in sys.stdin:
        print(json.dumps(pilot.observe(json.loads(line)),allow_nan=False),flush=True)
