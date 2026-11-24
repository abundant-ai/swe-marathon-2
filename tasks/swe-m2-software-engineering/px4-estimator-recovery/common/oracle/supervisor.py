"""Qualify independent estimator epochs before allowing closed-loop handover."""

from math import dist
from typing import Any

from .estimator import Estimate, Record, series


class Source:
    """Own one estimator boot epoch, frame tracker and integrity streak."""

    def __init__(self) -> None:
        """Start with no aligned source or qualifying evidence."""
        self.epoch=-1
        self.tracker=Estimate()
        self.aligned=False
        self.count=0

    def sample(self, report: Record | None, now: int, age: int,
               predicted: tuple[list,list] | None, settings: Record) -> tuple[list,list] | None:
        """Update calibration and qualification from one current source envelope."""
        if report is None or report["epoch"]<self.epoch:
            self.count=0
            return None
        if report["epoch"]>self.epoch:
            self.epoch=report["epoch"]
            self.tracker=Estimate()
            self.aligned=False
            self.count=0
        local=report["local"]
        if (not report["healthy"] or local is None or local["timestamp_sample"]>now):
            self.count=0
            return None
        fresh=self.tracker.ingest(local)
        active=fresh and now-local["timestamp_sample"]<=age and None not in self.tracker.position
        anchor=local.get("anchor",[None]*3)
        complete_anchor=active and None not in anchor
        if complete_anchor:
            self.aligned=True
        p,v=self.tracker.position.copy(),self.tracker.velocity.copy()
        if not active or not self.aligned:
            self.count=0
            return None
        if predicted is None:
            consistent=complete_anchor
        else:
            consistent=(dist(p,predicted[0])<=settings["max_position_innovation_m"]
                        and dist(v,predicted[1])<=settings["max_velocity_innovation_mps"])
        if not consistent:
            self.count=0
            return None
        self.count+=1
        return (p,v) if self.count>=settings["qualification_samples"] else None


class Supervisor:
    """Select live estimator authority and reuse the mission controller."""

    def __init__(self, mission: Any) -> None:
        """Attach source ledgers to the earlier mission implementation."""
        self.mission=mission
        self.spec=mission.spec
        self.settings=self.spec["supervisor"]
        self.sources={name:Source() for name in self.settings["sources"]}
        self.incumbent=None
        self.switched=-1

    def prediction(self, event: Record) -> tuple[list,list] | None:
        """Construct a one-interval physical innovation witness."""
        imu=event.get("imu")
        mission=self.mission
        if (mission.state is None or mission.inertial>=self.spec["max_inertial_ticks"]
                or imu is None or imu["from_tick"]!=event["tick"]-1):
            return None
        dt=self.spec["dt"]
        p,v=mission.state
        a=series(imu["accel"],3)
        return ([x+vel*dt+0.5*accel*dt*dt for x,vel,accel in zip(p,v,a,strict=True)],
                [vel+accel*dt for vel,accel in zip(v,a,strict=True)])

    def observe(self,event: Record) -> Record:
        """Choose a source from simultaneous integrity checks and act in the common frame."""
        if self.mission.terminal is not None:
            return self.mission.response(self.mission.terminal)|{"source":None}
        tick,now=event["tick"],event["now_us"]
        predicted=self.prediction(event)
        eligible={}
        for name,source in self.sources.items():
            ready=source.sample(event["reports"].get(name),now,self.spec["max_age_us"],predicted,self.settings)
            if ready is not None:
                eligible[name]=ready
        top=next(iter(eligible),None)
        chosen=self.incumbent
        if chosen not in eligible or tick-self.switched>=self.settings["switch_delay_ticks"]:
            chosen=top
        if chosen!=self.incumbent:
            self.incumbent,self.switched=chosen,tick
        local=None
        if chosen is not None:
            p,v=eligible[chosen]
            local={"timestamp":now,"timestamp_sample":now,"position":p,"velocity":v,"xy_valid":True,
                   "z_valid":True,"xy_reset_counter":0,"z_reset_counter":0,"delta_xy":[0,0],"delta_z":0}
        response=self.mission.observe(event|{"local":local})
        return response|{"source":chosen if response["mode"] in ("track","complete") else None}


def guarded_acceleration(x: float,v: float,u: float,dt: float,cap: float,
                         lower: float,upper: float) -> float:
    """Clamp an axis command into the interval that permits a full stop."""
    def brake_extent(command: float,direction: float) -> float:
        """Predict the stopping extremity of one signed axis after this command."""
        speed=max(0.0,direction*(v+command*dt))
        return direction*(x+v*dt+0.5*command*dt*dt)+speed*speed/(2*cap)
    if brake_extent(u,1)>upper:
        lo,hi=-cap,u
        for _ in range(38):
            mid=(lo+hi)/2
            if brake_extent(mid,1)<=upper:lo=mid
            else:hi=mid
        u=lo
    if brake_extent(u,-1)>-lower:
        lo,hi=u,cap
        for _ in range(38):
            mid=(lo+hi)/2
            if brake_extent(mid,-1)<=-lower:hi=mid
            else:lo=mid
        u=hi
    return u
