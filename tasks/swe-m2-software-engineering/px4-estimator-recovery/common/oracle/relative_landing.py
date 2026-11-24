"""Estimate safe moving-cart approach from relative rays, beacon distance and optical-inertial aiding."""

import json
import math
import sys

import numpy as np

from .moving_landing import basis, wrapped
from .landing import bounded
from .rigid_flight import G


def expmap(vector):
    a=np.linalg.norm(vector)
    if a<1e-12:
        return np.eye(3)
    x,y,z=vector/a
    c,s=math.cos(a),math.sin(a)
    skew=np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
    return np.eye(3)+s*skew+(1-c)*(skew@skew)


class Navigation:
    """Integrate raw IMU in a local gauge and apply ground-flow corrections at capture."""

    def __init__(self, config):
        self.dt = config["imu_period_us"]/1e6
        self.flow_mount = basis(config["flow"]["body_from_sensor_wxyz"])
        self.flow_arm = np.array(config["flow"]["lever_arm_m"],dtype=float)
        self.rotation={0:np.eye(3)}
        self.omega={0:np.zeros(3)}
        self.accel={0:np.zeros(3)}
        self.estimates={0:(np.zeros(3),np.zeros(3))}
        self.flows={}
        self.last_step=0

    def update_imu(self, step, gyro, force):
        previous=self.rotation[step-1]
        self.rotation[step]=previous@expmap(gyro*self.dt)
        self.omega[step]=gyro
        self.accel[step]=previous@expmap(gyro*self.dt/2)@force+G
        self.last_step=step

    def update_flow(self, record):
        if record["quality"]>=75 and record["slant_m"]>0.:
            self.flows[record["step"]]=record

    def flow_measurement(self, step, flow, vertical_velocity):
        orientation = self.rotation[step]
        sensor = orientation@self.flow_mount
        rate = self.omega[step]
        arm = orientation@self.flow_arm
        lever = orientation@np.cross(rate,self.flow_arm)
        xyz = np.array(flow["integrated_flow_rad"])-np.array(flow["integrated_gyro_rad"])
        apparent = np.array([xyz[1],-xyz[0]])*flow["slant_m"]/flow["interval_s"]
        sensor_down = (vertical_velocity+lever[2]-sensor[2,:2]@apparent)/sensor[2,2]
        velocity=(sensor@np.r_[apparent,sensor_down]-lever)[:2]
        down = -flow["slant_m"]*sensor[2,2]-arm[2]
        return float(down),velocity

    def rebuild(self):
        start=max(0,self.last_step-round(.92/self.dt))
        p,v=(state.copy() for state in self.estimates[start])
        previous=max((stamp for stamp in self.flows if stamp<=start),default=None)
        previous_altitude=(self.flow_measurement(previous,self.flows[previous],v[2])[0]
                           if previous is not None else None)
        for step in range(start+1,self.last_step+1):
            acc = self.accel[step]
            p += self.dt*v+.5*self.dt**2*acc
            v += self.dt*acc
            flow = self.flows.get(step)
            if flow is not None:
                measured_down,observed_xy = self.flow_measurement(step,flow,v[2])
                p[2] += (.74 if previous is not None else 1.)*(measured_down-p[2])
                v[:2] += .65*(observed_xy-v[:2])
                if previous is not None:
                    measured_v=(measured_down-previous_altitude)/((step-previous)*self.dt)
                    if abs(measured_v-v[2])<.7:
                        v[2]+=.28*(measured_v-v[2])
                previous,previous_altitude=step,measured_down
            self.estimates[step]=(p.copy(),v.copy())

    def state(self, step):
        position,velocity=self.estimates[step]
        return position,velocity,self.rotation[step]

    def last_flow_age(self, step):
        return (step-max(self.flows))*self.dt if self.flows else math.inf


class Target:
    """Fit target motion in the local gauge using separately timed rays and distances."""

    def __init__(self, nav, config):
        self.nav=nav
        self.config=config
        self.dt=nav.dt
        self.camera_mount=basis(config["camera"]["body_from_sensor_wxyz"])
        self.camera_arm=np.array(config["camera"]["lever_arm_m"],dtype=float)
        self.range_arm=np.array(config["range"]["lever_arm_m"],dtype=float)
        self.records={"bearing":{},"range":{}}
        self.solution=None

    def insert(self, packet, now):
        if packet["quality"]<70 or packet["step"]>now or (now-packet["step"])*self.dt>.50:
            return
        table=self.records[packet["stream"]]
        if packet["step"] not in table:
            table[packet["step"]]=packet

    def fit(self, now):
        rb=self.records["bearing"]
        rd=self.records["range"]
        ba=(now-max(rb))*self.dt if rb else math.inf
        ra=(now-max(rd))*self.dt if rd else math.inf
        if ba>self.config["bearing_max_age_us"]/1e6 or ra>self.config["range_max_age_us"]/1e6:
            self.solution=None
            return None,ba,ra
        bearings=[row for step,row in rb.items() if (now-step)*self.dt<.88]
        ranges=[row for step,row in rd.items() if (now-step)*self.dt<.82]
        if len(bearings)<3 or len(ranges)<4:
            return None,ba,ra
        rays=[]
        distances=[]
        for row in bearings:
            p,_,r=self.nav.state(row["step"])
            direction=r@self.camera_mount@np.array([*row["bearing_xy"],1.])
            direction/=np.linalg.norm(direction)
            t=(row["step"]-now)*self.dt
            rays.append((t,p+r@self.camera_arm,direction))
        for row in ranges:
            p,_,r=self.nav.state(row["step"])
            distances.append(((row["step"]-now)*self.dt,p+r@self.range_arm,row["range_m"]))
        coefficients=np.zeros(9)
        if self.solution is not None:
            former,state=self.solution
            dt=(now-former)*self.dt
            coefficients[:3]=state[:3]+dt*state[3:6]+.5*dt*dt*state[6:]
            coefficients[3:6]=state[3:6]+dt*state[6:]
            coefficients[6:]=state[6:]
        else:
            _,origin,ray=max(rays,key=lambda item:item[0])
            _,ranger,distance=max(distances,key=lambda item:item[0])
            delta=origin-ranger
            dot=ray@delta
            scale=-dot+math.sqrt(max(.03,dot**2+distance**2-delta@delta))
            coefficients[:3]=origin+scale*ray
        eye=np.eye(3)
        for _ in range(4):
            matrix,observed=[],[]
            for t,origin,d in rays:
                projector=eye-np.outer(d,d)
                h=np.column_stack((eye,t*eye,.5*t*t*eye))
                vector = projector@(origin-h@coefficients)
                weight=min(1.,.025/max(.005,np.linalg.norm(vector)))
                matrix.extend(weight*(projector@h))
                observed.extend(weight*vector)
            for t,origin,offset in distances:
                h=np.column_stack((eye,t*eye,.5*t*t*eye))
                vector=h@coefficients-origin
                magnitude=max(1e-5,np.linalg.norm(vector))
                residual=offset-magnitude
                weight=min(.85,.030/max(.006,abs(residual)))
                matrix.append(weight*(vector/magnitude@h))
                observed.append(weight*residual)
            ridge=np.zeros((3,9))
            ridge[:,6:]=eye*.29
            matrix.extend(ridge)
            observed.extend(-.29*coefficients[6:])
            improvement=np.linalg.lstsq(matrix,observed,rcond=None)[0]
            coefficients+=improvement
        self.solution=now,coefficients
        if not np.isfinite(coefficients).all() or np.linalg.norm(coefficients[3:6])>2.0:
            return None,ba,ra
        return (coefficients[:3],coefficients[3:6]),ba,ra


class Supervisor:
    def __init__(self, config):
        self.config=config
        self.dt=config["imu_period_us"]/1e6
        self.nav=Navigation(config)
        self.target=Target(self.nav,config)
        self.hold=None
        self.staging=None
        self.has_descended=False
        self.abort=False
        self.track_ticks=0

    def tick(self, step, arrivals):
        for packet in arrivals:
            if packet["stream"]=="flow":
                self.nav.update_flow(packet)
            else:
                self.target.insert(packet,step)
        self.nav.rebuild()
        p,v,attitude=self.nav.state(step)
        target, bearing_age,range_age=self.target.fit(step)
        flow_age=self.nav.last_flow_age(step)
        if self.staging is None and flow_age<=self.config["flow_max_age_us"]/1e6:
            self.staging=p[2]
        if self.staging is None:
            return np.zeros(3),self.config["hover_collective"],"hold",None
        if self.has_descended and max(bearing_age,range_age)>self.config["abort_age_us"]/1e6:
            self.abort=True
        valid=target is not None and flow_age<=self.config["flow_max_age_us"]/1e6 and not self.abort
        if not valid:
            self.track_ticks=0
            if self.hold is None:
                self.hold=(min(p[2]-.105,self.staging+.025) if self.has_descended
                           else self.staging)
            phase="abort" if self.abort else "hold"
            dz=min(self.hold,self.staging) if self.abort else self.hold
            velocity=np.zeros(2)
        else:
            self.hold=None
            target_position,target_velocity=target
            relative=target_position-p
            relative_v=target_velocity-v
            velocity=bounded(bounded(target_velocity[:2],.67)+2.65*relative[:2],.93)
            aligned=np.linalg.norm(relative[:2]) <= .105 and np.linalg.norm(relative_v[:2]) <= .165
            self.track_ticks=(self.track_ticks+1) if aligned else 0
            if self.track_ticks>=3 or (self.has_descended and self.track_ticks>0):
                phase="descend"
                dz=target_position[2]-.048
                self.has_descended=True
            else:
                phase="approach"
                dz=min(self.staging+.37,p[2]) if self.has_descended else self.staging
        down=np.clip(1.8*(dz-p[2]),-.48,.255 if phase=="descend" else .03)
        if phase=="descend":
            down=min(.27,down+np.clip(target_velocity[2],-.055,.055))
        desired=np.r_[bounded(4.6*(velocity-v[:2]),1.68),4.1*(down-v[2])]
        thrust=G-desired
        now_down=attitude[:,2]
        tilt=8.2*(attitude.T@np.cross(now_down,thrust/np.linalg.norm(thrust)))
        tilt[2]=2.4*wrapped(-math.atan2(attitude[1,0],attitude[0,0]))
        collective=float(np.clip(self.config["hover_collective"]*(thrust@now_down)/9.81,0.,1.))
        estimated=None if not valid else (target[0]-p,target[1]-v)
        cap=self.config["max_body_rate_rad_s"]
        return np.clip(tilt,-cap,cap),collective,phase,estimated


def require_grid(timestamp, period):
    if type(timestamp) is not int or timestamp<0 or timestamp%period:
        raise ValueError("capture is off the commissioned IMU grid")
    return timestamp//period


def sample(values,dimension):
    vector = np.asarray(values,dtype=float)
    if vector.shape!=(dimension,) or not np.all(np.isfinite(vector)):
        raise ValueError("invalid sensor vector")
    return vector


def arrive(packet,controller,period,step):
    for imu in packet["imu"]:
        i=require_grid(imu["capture_us"],period)
        if i!=controller.nav.last_step+1:
            raise ValueError("unexpected IMU acquisition order")
        controller.nav.update_imu(i,sample(imu["gyro_rad_s"],3),sample(imu["specific_force_mps2"],3))
    if controller.nav.last_step!=step:
        raise ValueError("IMU support does not reach the control tick")
    observations=[]
    for record in packet["detections"]:
        index=require_grid(record["capture_us"],period)
        if index>step:
            raise ValueError("future sensor acquisition")
        observations.append(record|{"step":index})
    rates,collective,phase,relative=controller.tick(step,observations)
    estimate=None if relative is None else {"position_m":relative[0].tolist(),
                                            "velocity_mps":relative[1].tolist()}
    return {"phase":phase,"body_rates_rad_s":rates.tolist(),"collective":collective,"relative":estimate}


def land_relative(spec_path):
    """Process sealed onboard records without any world-position input."""
    spec=json.loads(spec_path.read_text())
    period=spec["imu_period_us"]
    if type(period) is not int or period<1 or spec["period_us"]%period:
        raise ValueError("invalid commissioned sensor and control periods")
    controller=Supervisor(spec)
    previous=-spec["period_us"]
    for line in sys.stdin:
        packet=json.loads(line)
        now=packet["now_us"]
        if now!=previous+spec["period_us"] or now>spec["deadline_us"]:
            raise ValueError("control tick does not follow the commissioning schedule")
        reply=arrive(packet,controller,period,require_grid(now,period))
        print(json.dumps(reply,allow_nan=False),flush=True)
        previous=now
