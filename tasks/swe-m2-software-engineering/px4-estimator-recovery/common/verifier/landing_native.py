"""Independent optical landing missions driven by native MuJoCo forces and contacts."""

from collections import Counter
import json
from math import acos, cos, sin
from pathlib import Path

import mujoco
import numpy as np

from commission_checks import make_kit
from flight_native import (CONTROL_STEPS, DT, G, IMU_ARM, STEP_US, Environment, Plant, angle_error,
                           commissioned, describe, matrix, quaternion, yaw)
from transport import Driver, require


LANDING_CASES=(
    {"name":"slant-flow-and-thrust-derating-to-emergency-pad","kind":"land","variant":0,"direction":1,"fault":"voltage"},
    {"name":"range-obstruction-holds-until-clear","kind":"land","variant":2,"direction":-1,"fault":"obstruction"},
    {"name":"reacquired-vision-does-not-divert-committed-pad","kind":"rejoin","variant":1,"direction":1,"fault":"outliers"},
    {"name":"reversed-narrow-pad-with-slow-torque-response","kind":"land","variant":0,"direction":-1,"fault":"heavy"},
)


def landing_config(kit,case):
    """Publish instrument geometry, flight envelope and certified pad choices."""
    cfg=describe(kit,case)
    code=("voltage","obstruction","outliers","heavy").index(case["fault"])
    direction=case["direction"]
    cfg["initial"]["position_m"]=[0.0,0.0,-1.24]
    cfg["initial"]["q_wxyz"]=quaternion(yaw([2.74,-2.45,.72,-.98][code])).tolist()
    cfg["waypoints"]=[{"position_m":[1.79*direction,.07,-1.17],"yaw_rad":[-2.36,2.97,2.14,.56][code]}]
    arm=[.099,-.059,.015]
    rolling=.094+.015*code
    roll=matrix(np.array([cos(rolling),sin(rolling),0,0]))
    pitch=matrix(np.array([cos(.073),0,sin(.073),0]))
    frame=yaw([.68,-1.1,.37,1.13][code])@roll@pitch
    targets=[[1.07*direction,-.39],[.36*direction,.56]]
    names=(f"registered-{79-code*11}",f"registered-{36+code*13}")
    cfg.update({"max_body_rate_rad_s":2.65 if case["fault"]!="heavy" else 2.25,
                "period_s":CONTROL_STEPS*DT,"cruise_mps":.70,"track_age_us":225_000,
                "ground_support_age_us":218_000,
                "deadline_us":cfg["initial"]["timestamp_us"]+16_800_000,
                "min_ned":[-2.00,-.98,-1.91],"max_ned":[2.00,.93,0.0],
                "pads":[{"id":name,"center_ne_m":xy,"half_extent_ne_m":[.22 if code==3 else .27,.23]}
                        for name,xy in zip(names,targets,strict=True)],
                "ground_sensor":{"body_from_flow_wxyz":quaternion(frame).tolist(),"lever_arm_m":arm,
                         "floor_z_m":0.0,"min_quality":61,"min_range_m":.043,"max_range_m":2.35,
                         "range_innovation_m":.16,"velocity_innovation_mps":.36}})
    return cfg


class VariedPlant(Plant):
    """Use force saturation and real actuator lag windows across held-out vehicles."""

    def __init__(self,initial,case):
        self.case=case
        self.elapsed_after_loss=0
        self.thrust_scale=1.0
        fault=case["fault"]
        self.derating={"voltage":.138,"obstruction":.039,"outliers":.055,"heavy":.105}[fault]
        self.thrust_response={"voltage":.062,"obstruction":.086,"outliers":.079,"heavy":.043}[fault]
        mass={"voltage":1.19,"obstruction":.93,"outliers":.99,"heavy":1.53}[fault]
        super().__init__(initial,mass)

    def step(self, rates, collective, wind, loss):
        _,v,r,w=self.motion()
        previous_imu_velocity=v+r@np.cross(w,IMU_ARM)
        if loss:
            self.elapsed_after_loss+=1
        k=self.elapsed_after_loss*DT
        kind=self.case["fault"]
        self.thrust_scale=1-self.derating*min(k/1.25,1.0)
        target_thrust=self.thrust_scale*collective*self.max_thrust
        self.thrust+=self.thrust_response*(target_thrust-self.thrust)
        torque_response=.165 if kind=="heavy" else .215
        wanted=np.clip((rates-w)*[.168,.17,.137],-.21,.21)
        self.torque+=torque_response*(wanted-self.torque)
        drift=np.array([.049,-.135 if kind=="obstruction" else .095,.041])*min(k/.45,1.0)
        self.data.xfrc_applied[self.id,:3]=r@[0.0,0.0,-self.thrust]-.215*v+wind+drift
        self.data.xfrc_applied[self.id,3:]=r@self.torque
        mujoco.mj_step(self.model,self.data)
        mujoco.mj_forward(self.model,self.data)
        _,next_v,next_r,next_w=self.motion()
        imu_velocity=next_v+next_r@np.cross(next_w,IMU_ARM)
        residual=np.array([.044,-.032,.017])*min(k/.65,1.0)
        specific=.5*(r+next_r).T@((imu_velocity-previous_imu_velocity)/DT-G)+residual
        return (w+next_w)*.5,specific


class LandingEnvironment(Environment):
    """Publish delayed measurements from independently measured body motion."""

    def __init__(self,cfg,kit,case):
        super().__init__(cfg,kit,case)
        instrument=cfg["ground_sensor"]
        self.flow_mount=matrix(instrument["body_from_flow_wxyz"])
        self.flow_arm=np.array(instrument["lever_arm_m"])
        self.native=VariedPlant(cfg["initial"],case)
        self.pending_ground=[]
        self.flow_seq=0
        self.range_occlusion=None
        self.impact=None
        self.flight_max_tilt=0

    def flow(self):
        """Generate integrated angular image velocity and slant distance at the sensor."""
        p,v,orientation,w=self.native.motion()
        step=self.step_id
        self.flow_seq+=1
        q_sensor=orientation@self.flow_mount
        offset=orientation@self.flow_arm
        camera_velocity=v+orientation@np.cross(w,self.flow_arm)
        local_velocity=q_sensor.T@camera_velocity
        local_rate=self.flow_mount.T@w
        distance=(-p[2]-offset[2])/q_sensor[2,2]
        duration=.044 if self.flow_seq%2 else .057
        gyro=duration*local_rate[:2]
        integrated=gyro+duration*np.array([-local_velocity[1],local_velocity[0]])/distance
        event={"id":f"g-{self.flow_seq}","capture_us":self.start+step*STEP_US,
               "interval_us":round(duration*1e6),"integrated_flow_rad":integrated.tolist(),
               "integrated_gyro_rad":gyro.tolist(),"omega_body_rad_s":w.tolist(),
               "slant_range_m":distance,"quality":93}
        fault=self.case["fault"]
        if fault=="obstruction" and self.outage is not None and self.range_occlusion is None and p[2]>-.80:
            self.range_occlusion=step
        outcome="accepted"
        if self.range_occlusion is not None and step-self.range_occlusion<145:
            event["slant_range_m"]*=.43
            outcome="range"
        elif fault=="outliers" and self.outage is not None:
            if self.flow_seq in (31,43,51,68):
                event["integrated_flow_rad"][0]+=duration*.9/distance
                outcome="innovation"
            elif self.flow_seq in (23,28,35,42):
                event["quality"]=20
                outcome="quality"
        if not self.cfg["ground_sensor"]["min_range_m"]<=event["slant_range_m"]<=self.cfg["ground_sensor"]["max_range_m"]:
            outcome="range" if outcome=="accepted" else outcome
        lag=(18,12,33,16,17)[self.flow_seq%5]
        self.pending_ground.append((step+lag,event,outcome))
        if self.flow_seq%16==7:
            self.pending_ground.append((step+lag+142,event|{"id":event["id"]+"-late"},"time"))
            self.pending_ground.append((step+lag+11,event,"duplicate"))

    def advance(self,rates,collective):
        """Measure physical clearance before applying the next candidate packet."""
        direction=self.case["direction"]
        for _ in range(CONTROL_STEPS):
            self.step_id+=1
            step=self.step_id
            prior=self.native.data.qvel[:3].copy()
            touching=self.native.data.ncon>0
            wind=np.array([.058*sin(2.2*DT*step),.061*cos(1.37*DT*step),.019*sin(3*DT*step)])
            gyro,accel=self.native.step(rates,collective,wind,self.outage is not None)
            self.accumulated+=DT*np.stack((gyro,accel))
            self.accum_steps+=1
            if self.accum_steps==(2,4,3,3,2)[self.seq%5]:
                self.imu()
            p,v,r,_=self.native.motion()
            self.flight_max_tilt=max(self.flight_max_tilt,acos(float(np.clip(r[2,2],-1,1))))
            if self.outage is None and direction*p[0]>.44 and direction*v[0]>.43:
                self.outage=step
                self.outage_speed=float(direction*v[0])
            if self.native.data.ncon>0 and not touching and self.impact is None:
                self.impact=(p.copy(),prior)
            if step%19==0:
                self.vision()
            if step%17==0:
                self.flow()
            require(all(low<=pos<=high for low,pos,high in zip(self.cfg["min_ned"],p,self.cfg["max_ned"],strict=True))
                    and self.flight_max_tilt<.65,"aircraft left its physical clearance envelope")

    def packet(self,tick):
        event,vision=super().packet(tick)
        ready=[row for row in self.pending_ground if row[0]<=self.step_id]
        self.pending_ground=[row for row in self.pending_ground if row[0]>self.step_id]
        ready.sort(key=lambda item:(item[1]["capture_us"],item[1]["id"]))
        event["ground_aid"]=[item[1] for item in ready]
        # Ground aid can be lost. A direct simulated altitude would bypass the instrument.
        del event["height_m"]
        return event,vision,ready


def check_landing(app: Path,root: Path,case: dict):
    """Verify the submitted metrology, sensible fallback and native touchdown."""
    kit=make_kit(root/"bench",case["variant"])
    cfg=landing_config(kit,case)
    spec=root/"landing.json"
    spec.write_text(json.dumps(cfg))
    work=root/"candidate"
    work.mkdir()
    work.chmod(0o777)
    calibration=work/"flight-commissioning.json"
    commissioned(app,kit,calibration)
    plant=LandingEnvironment(cfg,kit,case)
    pilot=Driver(app,spec,work,command=["land-assured","--spec",str(spec),"--calibration",str(calibration)])
    modes,ground_checks=Counter(),Counter()
    latest_ground=None
    latest_position=plant.start
    blackout_position=None
    committed=None
    pad=None
    touchdown_contact=0
    braking_speed=None
    first_descend=None
    max_errors=[0.0,0.0,0.0]
    max_degraded_v_error=0.
    try:
        for tick in range(421):
            packet,vision,ground=plant.packet(tick)
            reply=pilot.exchange(packet)
            expected_optical=[]
            for _,row,outcome in ground:
                expected_optical.append({"id":row["id"],"status":outcome})
                ground_checks[outcome]+=1
                if outcome=="accepted":
                    latest_ground=row["capture_us"] if latest_ground is None else max(latest_ground,row["capture_us"])
            require(reply.get("ground_aiding")==expected_optical and reply.get("last_ground_us")==latest_ground,
                    f"incorrect ground capture decision at tick {tick}: {reply.get('ground_aiding')} expected {expected_optical}")
            for _,row,outcome in vision:
                if outcome=="accepted" and row["position_m"] is not None:
                    latest_position=max(latest_position,row["capture_us"])
            require(reply.get("aiding")==[{"id":row["id"],"status":outcome} for _,row,outcome in vision]
                    and reply.get("accepted_position_us")==latest_position,
                    "horizontal position authority used arrival or ground flow time")
            p,v,orientation,_=plant.native.motion()
            attitude=quaternion(orientation)
            estimate=reply["estimate"]
            measured_p=np.asarray(estimate["position_m"])
            measured_v=np.asarray(estimate["velocity_mps"])
            q=np.asarray(estimate["q_wxyz"])
            require(measured_p.shape==(3,) and measured_v.shape==(3,) and q.shape==(4,)
                    and abs(np.linalg.norm(q)-1)<1e-4,"invalid estimated dimensions or quaternion")
            ep=float(np.linalg.norm(measured_p-p))
            ev=float(np.linalg.norm(measured_v-v))
            er=angle_error(q,attitude)
            max_errors=[max(a,b) for a,b in zip(max_errors,(ep,ev,er),strict=True)]
            mode=reply.get("mode")
            modes[mode]+=1
            if plant.outage is not None and blackout_position is None:
                blackout_position=p.copy()
            if committed is None and packet["now_us"]-latest_position>cfg["track_age_us"]:
                committed=latest_position
                braking_speed=float(np.linalg.norm(v[:2]))
                pad=next((item for item in cfg["pads"] if item["id"]==reply["pad"]),None)
                require(pad is not None and mode=="brake","lost primary aiding must enter a registered-pad braking approach")
            if committed is None:
                require(mode=="track" and reply["pad"] is None,"landing committed while primary position was recent")
            else:
                max_degraded_v_error=max(max_degraded_v_error,ev)
                require(reply["pad"]==pad["id"] and mode in ("brake","hold","approach","descend","disarmed"),
                        "committed degraded landing revoked its selected pad")
                fresh=latest_ground is not None and packet["now_us"]-latest_ground<=cfg["ground_support_age_us"]
                if mode in ("approach","descend"):
                    require(fresh,"approach or descent lacked current ground velocity and range support")
                if mode=="descend":
                    if first_descend is None:
                        first_descend=tick
                        require(np.linalg.norm(v[:2])<.24,"descent began before physical horizontal braking")
                if p[2]>-.44:
                    require(np.all(np.abs(p[:2]-pad["center_ne_m"])<=np.array(pad["half_extent_ne_m"])),
                            "vehicle entered the low pad approach outside its surveyed pad")
            require(ep<.105 and ev<.127 and er<.065,
                    f"current state missed native motion at tick {tick} ({ep:.3f} m, {ev:.3f} m/s, {er:.3f} rad)")
            rates=np.asarray(reply["body_rates_rad_s"],dtype=float)
            thrust=reply["collective"]
            require(rates.shape==(3,) and np.isfinite(rates).all() and np.max(np.abs(rates))<=cfg["max_body_rate_rad_s"]+1e-9
                    and type(thrust) in (float,int) and 0<=thrust<=1,"incorrect rotor interface bounds")
            if packet["contact"]:
                touchdown_contact+=1
            if mode=="disarmed":
                require(touchdown_contact>=3 and plant.impact is not None and thrust==0 and np.linalg.norm(rates)==0
                        and first_descend is not None,"disarm without a measured pad touchdown")
                impact_p,impact_v=plant.impact
                require(np.all(np.abs(impact_p[:2]-pad["center_ne_m"])<=pad["half_extent_ne_m"])
                        and abs(impact_v[2])<.37 and np.linalg.norm(impact_v[:2])<.19,
                        "physical first touchdown did not fit the low-energy pad envelope")
                require(plant.outage is not None and plant.outage_speed>.43 and modes["brake"]>=3
                        and np.linalg.norm(impact_p[:2]-blackout_position[:2])>.28,
                        "landing did not require genuine movement, braking and pad approach")
                if case["fault"]=="obstruction":
                    require(ground_checks["range"]>=4 and modes["hold"]>=5,
                            "intermittent real-world range obstruction did not exercise a hold and recovery")
                if case["fault"]=="outliers":
                    require(ground_checks["quality"]>=3 and ground_checks["innovation"]>=2
                            and latest_position>committed,"late vision or known corrupt ground aiding was not exercised")
                return {"terminal_tick":tick,"pad":pad["id"],"outage_speed_mps":plant.outage_speed,
                        "braking_entry_speed_mps":braking_speed,"first_descent_tick":first_descend,
                        "touchdown_ne_m":impact_p[:2].tolist(),"impact_velocity_ned":impact_v.tolist(),
                        "native_mass_kg":plant.native.mass,"thrust_ceiling_fraction_at_touchdown":plant.native.thrust_scale,
                        "rotor_thrust_update_fraction":plant.native.thrust_response,
                        "peak_native_tilt_rad":plant.flight_max_tilt,"max_estimator_errors":max_errors,
                        "max_degraded_velocity_error_mps":max_degraded_v_error,
                        "ground_aiding":dict(ground_checks),"modes":dict(modes)}
            plant.advance(rates,thrust)
        require(False,f"pad landing did not finish before the deadline; modes={dict(modes)}")
    finally:
        pilot.close()
