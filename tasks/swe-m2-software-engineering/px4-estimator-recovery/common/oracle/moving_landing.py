"""Track a delayed moving landing target separately from ownship navigation."""

import json
import math
import sys

import numpy as np

from .landing import bounded
from .rigid_flight import G, rotate, unit


def basis(quaternion):
    q = unit(np.array(quaternion,dtype=float))
    return np.column_stack([rotate(q, axis) for axis in np.eye(3)])


def wrapped(angle):
    return (angle+math.pi) % (2*math.pi)-math.pi


class Tracker:
    """Keep the ownship state independent and fit target motion on a capture-time window."""

    def __init__(self, spec):
        self.spec = spec
        self.history = {}
        self.max_age = spec["max_capture_age_us"]/1e6
        self.abort_age = spec["abort_age_us"]/1e6
        self.deck = spec["deck_down_m"]
        self.arm = np.array(spec["camera"]["lever_arm_m"],dtype=float)
        self.mount = basis(spec["camera"]["body_from_camera_wxyz"])
        self.hover_down = spec["staging_down_m"]
        self.samples = {}
        self.carried_altitude = None
        self.ever_descended = False
        self.aborted = False

    def tick(self, now, state, history, arrivals):
        p,v,body = state
        for packet in arrivals:
            capture = packet["capture"]
            if capture not in history or packet["quality"] < self.spec["minimum_quality"]:
                continue
            if not 0 <= now-capture <= self.max_age:
                continue
            if capture in self.samples:
                continue
            own_p,_,own_r = history[capture]
            target = own_p+own_r@(self.arm+self.mount@np.asarray(packet["position_camera_m"]))
            if abs(target[2]-self.deck) > .06:
                continue
            self.samples[capture] = target[:2]
        self.samples = {stamp:xy for stamp,xy in self.samples.items() if now-stamp <= 2.1}
        samples = sorted(self.samples.items())
        age = now-samples[-1][0] if samples else math.inf
        supported = len(samples) >= 4 and age <= self.max_age
        if age > self.abort_age and self.ever_descended:
            self.aborted = True
        forecast = None
        predicted_v = None
        if not supported or self.aborted:
            phase = "abort" if self.aborted else "hold"
            if self.carried_altitude is None:
                self.carried_altitude = min(p[2]-.07, -.86) if self.ever_descended else self.hover_down
            hz = self.carried_altitude
            goal_v = np.zeros(2)
        else:
            self.carried_altitude = None
            subset = [sample for sample in samples if samples[-1][0]-sample[0] < .64]
            tj = np.array([stamp-now for stamp,_ in subset])
            points = np.array([xy for _,xy in subset])
            degree = 2 if len(subset) >= 6 else 1
            design = np.column_stack([tj**exponent for exponent in range(degree+1)])
            coefficients = np.linalg.lstsq(design,points,rcond=None)[0]
            mask = np.linalg.norm(design@coefficients-points,axis=1) <= .027
            if sum(mask) >= degree+2 and not all(mask):
                coefficients = np.linalg.lstsq(design[mask],points[mask],rcond=None)[0]
            forecast = coefficients[0]
            predicted_v = bounded(coefficients[1],.65)
            correction = forecast-p[:2]
            goal_v = bounded(predicted_v+2.5*correction,.88)
            qualified = np.linalg.norm(correction) <= .11 and np.linalg.norm(v[:2]-predicted_v) <= .21
            if qualified or (self.ever_descended and np.linalg.norm(correction) <= .135):
                phase,hz = "descend", self.deck-.043
                self.ever_descended = True
            else:
                phase,hz = "approach",min(-.87,p[2]) if self.ever_descended else self.hover_down
        vertical_limit=.27 if phase=="descend" else .44
        desired_d = np.clip(1.8*(hz-p[2]),-.52,vertical_limit)
        accel = np.r_[bounded(4.6*(goal_v-v[:2]),1.6),4.1*(desired_d-v[2])]
        thrust = G-accel
        down = body[:,2]
        omega = 8.2*(body.T@np.cross(down,thrust/np.linalg.norm(thrust)))
        omega[2] = 2.7*wrapped(self.spec["hold_yaw_rad"]-math.atan2(body[1,0],body[0,0]))
        cap = self.spec["max_body_rate_rad_s"]
        collective = self.spec["hover_collective"]*(thrust@down)/9.81
        return np.clip(omega,-cap,cap),float(np.clip(collective,0.,1.)),phase,forecast,predicted_v,age


    def reply(self, packet):
        clock = packet["now_us"]
        now = clock/1e6
        for state in packet["navigation"]:
            stamp = state["at_us"]/1e6
            if not now-2.2 <= stamp <= now:
                continue
            self.history[stamp] = (np.array(state["position_ned_m"],dtype=float),
                                   np.array(state["velocity_ned_mps"],dtype=float),
                                   basis(state["q_ned_from_body_wxyz"]))
        self.history = {stamp:state for stamp,state in self.history.items() if now-stamp<=2.2}
        detections = [row|{"capture":row["capture_us"]/1e6} for row in packet["target_detections"]]
        omega,thrust,phase,point,velocity,age = self.tick(now,self.history[now],self.history,detections)
        target = None if point is None else {"at_us":clock,
                  "capture_us":round((now-age)*1e6),"position_ne_m":point.tolist(),
                  "velocity_ne_mps":velocity.tolist()}
        return {"phase":phase,"body_rates_rad_s":omega.tolist(),"collective":thrust,"target":target}


def land_moving(spec_path):
    tracker = Tracker(json.loads(spec_path.read_text()))
    for line in sys.stdin:
        response = tracker.reply(json.loads(line))
        print(json.dumps(response,allow_nan=False),flush=True)
