"""Lead a coupled multicopter onto an emergency pad with degraded visual aiding."""

import json
from pathlib import Path
import sys

import numpy as np

from .rigid_flight import Estimator, G, azimuth_error, heading, inverse, qmul, rotate, unit


def bounded(vector, maximum):
    """Limit Euclidean speed or acceleration while preserving direction."""
    norm=np.linalg.norm(vector)
    return vector if norm<=maximum else vector*(maximum/norm)


class FlowEstimator(Estimator):
    """Fuse motion and height from a displaced, tilted downward sensor."""

    def __init__(self, spec, calibration):
        super().__init__(spec,calibration)
        self.flow_config=spec["ground_sensor"]
        self.flow_arm=np.array(self.flow_config["lever_arm_m"])
        self.flow_mount=unit(np.array(self.flow_config["body_from_flow_wxyz"]))
        self.ground_seen=set()
        self.last_ground=None
        self.range_positions={}

    def range_rate(self, stamp, corrected_height, predicted_speed):
        """Use the prior consistent capture to arrest vertical inertial drift."""
        self.range_positions={time: height for time,height in self.range_positions.items()
                              if time>=stamp-self.cfg["history_us"]}
        supported=[time for time in self.range_positions if 35_000<=stamp-time<=210_000]
        if not supported:
            return predicted_speed
        earlier=max(supported)
        observed=(corrected_height-self.range_positions[earlier])/((stamp-earlier)/1e6)
        # The derivative averages physical motion between range captures.
        if abs(observed-predicted_speed)>.28:
            return predicted_speed
        return .72*observed+.28*predicted_speed

    def optical(self, event):
        """Recover optical translation in the attitude at the capture instant."""
        now=event["now_us"]
        observations=[]
        for row in sorted(event["ground_aid"],key=lambda row:(row["capture_us"],row["id"])):
            stamp,identifier=row["capture_us"],row["id"]
            result="accepted"
            if identifier in self.ground_seen:
                result="duplicate"
            elif stamp<self.time or not 0<=now-stamp<=self.cfg["history_us"]:
                result="time"
            elif row["quality"]<self.flow_config["min_quality"]:
                result="quality"
            else:
                p,v,q=self.predict(stamp)
                plane=self.flow_config["floor_z_m"]
                offset=rotate(q,self.flow_arm)
                frame=qmul(q,self.flow_mount)
                beam=rotate(frame,[0,0,1])[2]
                if beam<=0.45:
                    result="range"
                else:
                    predicted_range=(plane-p[2]-offset[2])/beam
                    distance=row["slant_range_m"]
                    if (not self.flow_config["min_range_m"]<=distance<=self.flow_config["max_range_m"] or
                        abs(distance-predicted_range)>self.flow_config["range_innovation_m"]):
                        result="range"
                    else:
                        seconds=row["interval_us"]/1e6
                        fx,fy=np.subtract(row["integrated_flow_rad"],row["integrated_gyro_rad"])
                        sensor_velocity=np.array([fy*distance/seconds,-fx*distance/seconds,0.0])
                        ground_tangent=rotate(frame,sensor_velocity)
                        turn=rotate(q,np.cross(row["omega_body_rad_s"],self.flow_arm))
                        down=plane-distance*beam-offset[2]
                        vertical=self.range_rate(stamp,down,v[2])
                        # Flow observes two coordinates. Use independently supported vertical motion for the third.
                        axis_speed=(vertical+turn[2]-ground_tangent[2])/beam
                        fixed_velocity=ground_tangent+rotate(frame,[0,0,axis_speed])-turn
                        if np.linalg.norm(fixed_velocity[:2]-v[:2])>self.flow_config["velocity_innovation_mps"]:
                            result="innovation"
                        else:
                            fixed_position=p.copy()
                            fixed_position[2]=down
                            self.updates.append((stamp,identifier,(fixed_position,fixed_velocity,None)))
                            self.range_positions[stamp]=down
                            self.last_ground=stamp if self.last_ground is None else max(stamp,self.last_ground)
            self.ground_seen.add(identifier)
            observations.append({"id":identifier,"status":result})
        return observations

    def track(self,event):
        """Keep visual and ground evidence at the clocks where they were captured."""
        _, vision=super().observe(event)
        ground=self.optical(event)
        return self.predict(event["now_us"]), vision, ground


class Landing:
    """Survive the blind interval, fly a pad approach and control real touchdown."""

    def __init__(self,spec, calibration):
        self.spec=spec
        self.estimator=FlowEstimator(spec,calibration)
        self.pad=None
        self.hover_height=spec["initial"]["position_m"][2]
        self.lost_yaw=None
        self.braked=False
        self.descending=False
        self.contact_count=0
        self.vertical_trim=0.0

    def choose_pad(self, position, velocity):
        """Choose a nearby certified pad with respect to the projected braking endpoint."""
        predicted=position[:2]+.34*velocity[:2]
        return min(self.spec["pads"],key=lambda pad:(np.linalg.norm(np.array(pad["center_ne_m"])-predicted),pad["id"]))

    def command(self,q,acceleration,yaw):
        """Produce bounded rate and collective setpoints for the coupled native body."""
        thrust_vector=G-acceleration
        desired_down=unit(thrust_vector)
        current_down=rotate(q,[0.,0.,1.])
        small_rotation=rotate(inverse(q),np.cross(current_down,desired_down))
        requested=small_rotation*7.6
        requested[2]=2.45*azimuth_error(yaw,heading(q))
        cap=self.spec["max_body_rate_rad_s"]
        collective=self.spec["hover_collective"]*(thrust_vector@current_down)/9.81
        return np.clip(requested,-cap,cap).tolist(),float(np.clip(collective,0.0,1.0))

    def observe(self,event):
        (p,v,q),vision,ground=self.estimator.track(event)
        now=event["now_us"]
        vision_age=now-self.estimator.last_position
        support_age=np.inf if self.estimator.last_ground is None else now-self.estimator.last_ground
        supported=support_age<=self.spec["ground_support_age_us"]
        yaw=self.spec["waypoints"][0]["yaw_rad"]
        vertical_goal=self.hover_height
        if self.pad is None and vision_age<=self.spec["track_age_us"]:
            mode="track"
            waypoint=np.array(self.spec["waypoints"][0]["position_m"])
            planar=bounded(1.65*(waypoint[:2]-p[:2]),self.spec["cruise_mps"])
            vertical_goal=waypoint[2]
        else:
            if self.pad is None:
                self.pad=self.choose_pad(p,v)
                self.lost_yaw=heading(q)
                self.hover_height=p[2]
                vertical_goal=self.hover_height
            yaw=self.lost_yaw
            aim=np.array(self.pad["center_ne_m"])
            lateral_error=aim-p[:2]
            if not self.braked:
                self.braked=supported and np.linalg.norm(v[:2])<.17
            if not self.braked:
                mode,planar="brake",np.zeros(2)
            elif not supported:
                mode,planar="hold",np.zeros(2)
            elif not self.descending and (np.linalg.norm(lateral_error)>.105 or np.linalg.norm(v[:2])>.125):
                mode,planar="approach",bounded(1.46*lateral_error,.45)
            else:
                self.descending=True
                mode,planar="descend",bounded(1.38*lateral_error,.25)
        acceleration=np.zeros(3)
        acceleration[:2]=bounded((4.8 if mode in ("brake","hold") else 3.3)*(planar-v[:2]),2.9)
        if mode=="descend":
            height=self.spec["ground_sensor"]["floor_z_m"]-p[2]
            desired_down=min(.43,max(.10,.43*height))
        else:
            desired_down=np.clip(1.45*(vertical_goal-p[2]),-.29,.29)
        if not event["contact"]:
            self.vertical_trim=float(np.clip(self.vertical_trim+2.35*self.spec["period_s"]*(desired_down-v[2]),-2.3,2.3))
        acceleration[2]=np.clip(3.9*(desired_down-v[2])+self.vertical_trim,-3.1,2.1)
        self.contact_count=self.contact_count+1 if event["contact"] and self.descending else 0
        if self.contact_count>=3:
            mode,rates,collective="disarmed",[0.,0.,0.],0.
        else:
            if event["contact"] and self.descending:
                acceleration[:2]=0.
            rates,collective=self.command(q,acceleration,yaw)
        return {"mode":mode,"pad":None if self.pad is None else self.pad["id"],"aiding":vision,
                "ground_aiding":ground,"last_ground_us":self.estimator.last_ground,
                "accepted_position_us":self.estimator.last_position,
                "estimate":{"position_m":p.tolist(),"velocity_mps":v.tolist(),"q_wxyz":q.tolist()},
                "body_rates_rad_s":rates,"collective":collective}


def fly_assured(spec_path: Path, calibration_path: Path):
    """Run the bounded emergency-landing protocol."""
    spec=json.loads(spec_path.read_text())
    cal=json.loads(calibration_path.read_text())
    if cal["status"]!="ok":
        raise ValueError("landing requires commissioned inertial measurements")
    pilot=Landing(spec,cal)
    for line in sys.stdin:
        print(json.dumps(pilot.observe(json.loads(line)),allow_nan=False),flush=True)
