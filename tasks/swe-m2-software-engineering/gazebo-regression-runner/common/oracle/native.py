"""Construct and step the pinned headless dynamics backend."""

from math import cos,sin
from random import Random
from xml.etree import ElementTree as ET

import mujoco
import numpy as np

from .scene import Record, World, angle, relative, transform


def attributes(vector) -> str:
    """Encode numeric geometry into one MJCF attribute."""
    return " ".join(map(str,vector))


def quat(yaw: float) -> tuple[float,float,float,float]:
    """Return the backend's wxyz convention for a yaw-only rotation."""
    return cos(yaw/2),0.0,0.0,sin(yaw/2)


def engine(world: World, spec: Record) -> tuple:
    """Build uniquely named native joints, unit motors, planar robot, and obstacle bodies."""
    robo=spec["robot"]
    geometry=world.geometry()
    xyz=world.frames[robo]
    model=ET.Element("mujoco")
    ET.SubElement(model,"compiler",{"angle":"radian"})
    ET.SubElement(model,"option",{"timestep":str(world.dt),"gravity":"0 0 0","integrator":"Euler"})
    bodies=ET.SubElement(model,"worldbody")
    body=ET.SubElement(bodies,"body",{"name":"vehicle","pos":f"0 0 {xyz[2]}"})
    damping=str(spec["damping"])
    directions=[("east","slide","1 0 0"),("north","slide","0 1 0"),("turn","hinge","0 0 1")]
    for key,kind,axis in directions:
        ET.SubElement(body,"joint",{"name":key,"type":kind,"axis":axis,"damping":damping})
    ET.SubElement(body,"geom",{"type":"box","name":"vehicle-shape","size":attributes(geometry[robo]),
                              "mass":str(spec["mass_kg"])})
    native_models={}
    for i,(name,shape) in enumerate(geometry.items()):
        if name==robo: continue
        x,y,z,yaw=world.frames[name]
        mid=f"mocap-{i}"
        b=ET.SubElement(bodies,"body",{"name":mid,"mocap":"true","pos":attributes((x,y,z)),"quat":attributes(quat(yaw))})
        ET.SubElement(b,"geom",{"type":"box","name":f"surface-{i}","size":attributes(shape)})
        native_models[name]=(mid,f"surface-{i}")
    actuators=ET.SubElement(model,"actuator")
    for key,_,_ in directions:
        ET.SubElement(actuators,"motor",{"joint":key,"gear":"1"})
    mx=mujoco.MjModel.from_xml_string(ET.tostring(model,encoding="unicode"))
    return mx,native_models


def run(world: World,spec: Record) -> Record:
    """Execute seeded relocations and emit directly observed poses, contacts and sensors."""
    model,mocaps=engine(world,spec)
    data=mujoco.MjData(model)
    robot=spec["robot"]
    initial=world.frames[robot]
    sensors={t:entry for t,entry in world.sensors.items() if entry["frame"].split("::")[0]==robot}
    offsets={t:relative(initial,world.frames[entry["frame"]]) for t,entry in sensors.items()}
    cmd={item["step"]:item for item in spec["commands"]}
    resets=set(spec["reset_steps"])
    locations={}
    for event in spec["relocations"]: locations.setdefault(event["step"],[]).append(event)
    geom_by_name={model.geom(named).id:key for key,(_,named) in mocaps.items()}
    seed=Random(spec["seed"])
    rng_id=np.empty(1,dtype=np.int32)
    robot_shape=model.geom("vehicle-shape").id
    trace=[]
    epoch=origin=0
    for step in range(spec["steps"]):
        if step==0 or step in resets:
            if step:
                epoch+=1
                origin=step
            mujoco.mj_resetData(model,data)
            data.qpos[:]=initial[0],initial[1],initial[3]
        if step in cmd:
            command=cmd[step]
        for event in locations.get(step,[]):
            x,y,z,yaw=event["pose"]
            noise=event["jitter_m"]
            index=model.body(mocaps[event["model"]][0]).mocapid[0]
            data.mocap_pos[index]=x+seed.uniform(-noise,noise),y+seed.uniform(-noise,noise),z
            data.mocap_quat[index]=quat(yaw)
        mujoco.mj_forward(model,data)
        x,y,yaw=map(float,data.qpos)
        base=x,y,initial[2],angle(yaw)
        joints=[]
        for contact in data.contact[:data.ncon]:
            if contact.dist>1e-8: continue
            ids=(contact.geom1,contact.geom2)
            if robot_shape in ids:
                joints.extend(geom_by_name[i] for i in ids if i in geom_by_name)
        sensed=[]
        for topic,row in sorted(sensors.items()):
            if (step-origin)%row["period_steps"]: continue
            p=transform(base,offsets[topic])
            if row["type"]=="imu":
                reading=p[3]
            else:
                ray=np.array([cos(p[3]),sin(p[3]),0.0])
                hit=mujoco.mj_ray(model,data,np.array(p[:3]),ray,None,True,model.body("vehicle").id,rng_id)
                reading=float(hit) if hit>=0 else None
            sensed.append({"topic":topic,"frame":row["frame"],"qos":spec["qos"][topic],"pose":p,"value":reading})
        trace.append({"step":step,"epoch":epoch,"time_ns":(step-origin)*round(world.dt*1e9),
                      "base":base,"contacts":sorted(set(joints)),"messages":sensed})
        force=command["force_n"]
        data.ctrl[:]=force*cos(yaw),force*sin(yaw),command["torque_nm"]
        mujoco.mj_step(model,data)
    return {"steps":trace}
