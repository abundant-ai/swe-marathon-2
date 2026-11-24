"""Resolve scoped planar world transforms from the authored SDF subset."""

from dataclasses import dataclass
from math import atan2, cos, isfinite, sin
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

Record=dict[str, Any]
Pose=tuple[float,float,float,float]
ZERO=(0.0,0.0,0.0,0.0)


def angle(yaw: float) -> float:
    """Wrap sensor angles consistently through full turns."""
    return atan2(sin(yaw),cos(yaw))


def transform(a: Pose, b: Pose) -> Pose:
    """Compose parent and relative poses in planar SE(2) plus height."""
    x,y,z,t=a
    u,v,w,s=b
    return x+cos(t)*u-sin(t)*v,y+sin(t)*u+cos(t)*v,z+w,angle(t+s)


def relative(a: Pose,b: Pose) -> Pose:
    """Express a world pose b in the local coordinates of a."""
    dx,dy=b[0]-a[0],b[1]-a[1]
    c,s=cos(a[3]),sin(a[3])
    return c*dx+s*dy,-s*dx+c*dy,b[2]-a[2],angle(b[3]-a[3])


def numbers(raw: str,width: int) -> tuple[float,...]:
    """Read a fixed-width finite XML numeric vector."""
    vals=tuple(map(float,raw.split()))
    if len(vals)!=width or not all(isfinite(v) for v in vals):
        raise ValueError("malformed pose or dimensions")
    return vals


def raw_pose(node: ET.Element) -> Pose:
    """Read an optional six-field pose with zero roll and pitch."""
    p=node.find("pose")
    if p is None:
        return ZERO
    x,y,z,r,pitch,s=numbers(p.text or "",6)
    if r or pitch: raise ValueError("world subset admits only yaw")
    return x,y,z,s


def label(node: ET.Element) -> str:
    """Read a nonempty local scoped name."""
    name=node.attrib.get("name","")
    if not name or "::" in name:
        raise ValueError("invalid component name")
    return name


@dataclass(frozen=True)
class World:
    """Resolved transforms, box model elements and one sensor schedule."""

    dt: float
    frames: dict[str,Pose]
    sensors: dict[str,Record]
    models: dict[str,ET.Element]

    def inspect(self) -> Record:
        """Return the portable frame manifest."""
        return {"dt_ns":round(self.dt*1e9),"frames":self.frames,"sensors":self.sensors}

    def geometry(self) -> dict[str,tuple[float,float,float]]:
        """Read the centered single-box native backend model declarations."""
        result={}
        for key, model in self.models.items():
            links=model.findall("link")
            if len(links)!=1 or raw_pose(links[0])!=ZERO:
                raise ValueError("model must have one centered link")
            items=links[0].findall("collision")
            if len(items)!=1 or raw_pose(items[0])!=ZERO:
                raise ValueError("model must have one centered collision")
            whole=numbers(items[0].findtext("geometry/box/size",""),3)
            if min(whole)<=0: raise ValueError("nonpositive box size")
            result[key]=tuple(v/2 for v in whole)
        return result


def read_world(file: Path) -> World:
    """Validate and resolve the world frame tree without accessing external resources."""
    sdf=ET.parse(file).getroot()
    worlds=sdf.findall("world")
    if sdf.tag!="sdf" or len(worlds)!=1:
        raise ValueError("one SDF world is required")
    world=worlds[0]
    dt,=numbers(world.findtext("physics/max_step_size",""),1)
    if dt<=0 or round(dt*1e9)<=0:
        raise ValueError("nonpositive physics step")
    specs={"world":(None,ZERO)}
    sensors,models={},{}
    def register(name: str,node: ET.Element,parent: str) -> None:
        """Record a scoped relative pose and defer parent resolution."""
        if name in specs:
            raise ValueError("duplicate frame name")
        element=node.find("pose")
        ref=element.get("relative_to",parent) if element is not None else parent
        specs[name]=(ref,raw_pose(node))
    for frame in world.findall("frame"):
        register(label(frame),frame,frame.get("attached_to","world"))
    for model in world.findall("model"):
        m=label(model)
        register(m,model,"world")
        models[m]=model
        for link in model.findall("link"):
            key=f"{m}::{label(link)}"
            register(key,link,m)
            for sensor in link.findall("sensor"):
                s=f"{key}::{label(sensor)}"
                kind=sensor.get("type")
                topic=sensor.findtext("topic","")
                rate,=numbers(sensor.findtext("update_rate",""),1)
                if (kind not in ("imu","gpu_lidar") or not topic.startswith("/") or topic in sensors or rate<=0):
                    raise ValueError("malformed sensor wiring")
                ratio=1/(rate*dt)
                steps=round(ratio)
                if steps<1 or abs(ratio-steps)>1e-8:
                    raise ValueError("nonintegral sensor schedule")
                register(s,sensor,key)
                sensors[topic]={"frame":s,"type":kind,"period_steps":steps}
    resolved={"world":ZERO}
    pending=set()
    def resolve(name: str) -> Pose:
        """Depth-first relative pose resolution with explicit loop detection."""
        if name in resolved:
            return resolved[name]
        if name in pending or name not in specs:
            raise ValueError("cyclic or missing frame reference")
        parent,local=specs[name]
        pending.add(name)
        result=transform(resolve(parent),local)
        pending.remove(name)
        resolved[name]=result
        return result
    for key in specs:
        resolve(key)
    return World(dt,resolved,sensors,models)
