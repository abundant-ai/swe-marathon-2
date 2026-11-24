"""Native reference observations produced by a separately authored MJCF."""

from cmath import phase
from random import Random

import mujoco
import numpy as np

from fixtures import combine,rotate


def shadow(fixture,spec):
    """Run the physical command schedule and independently derive bridge observations."""
    dt=fixture["dt"]
    x,y,z,heading=fixture["base"]
    a,b,c,theta=fixture["box"]
    rsize=" ".join(str(n/2) for n in fixture["rover_size"])
    osize=" ".join(str(n/2) for n in fixture["box_size"])
    quat=rotate(theta/2)
    xml=f"""<mujoco model="shadow"><option timestep="{dt}" gravity="0 0 0" integrator="Euler"/>
    <worldbody><body name="chassis" pos="0 0 {z}">
    <joint name="x" type="slide" axis="1 0 0" damping="{spec['damping']}"/>
    <joint name="y" type="slide" axis="0 1 0" damping="{spec['damping']}"/>
    <joint name="heading" type="hinge" axis="0 0 1" damping="{spec['damping']}"/>
    <geom type="box" name="body" size="{rsize}" mass="{spec['mass_kg']}"/></body>
    <body name="block" mocap="true" pos="{a} {b} {c}" quat="{quat.real} 0 0 {quat.imag}">
    <geom type="box" name="box" size="{osize}"/></body>
    </worldbody><actuator><motor joint="x"/><motor joint="y"/><motor joint="heading"/></actuator></mujoco>"""
    model=mujoco.MjModel.from_xml_string(xml)
    data=mujoco.MjData(model)
    rand=Random(spec["seed"])
    epoch=epoch_tick=0
    output=[]
    direction=0
    for tick in range(spec["steps"]):
        if tick==0 or tick in spec["reset_steps"]:
            data=mujoco.MjData(model)
            data.qpos[:]=[x,y,heading]
            epoch+=int(tick>0)
            epoch_tick=0
        if direction+1<len(spec["commands"]) and spec["commands"][direction+1]["step"]==tick:
            direction+=1
        for event in spec["relocations"]:
            if event["step"]==tick:
                u,v,w,psi=event["pose"]
                jitter=event["jitter_m"]
                data.mocap_pos[:]=[u+(2*rand.random()-1)*jitter,v+(2*rand.random()-1)*jitter,w]
                q=rotate(psi/2)
                data.mocap_quat[0]=[q.real,0,0,q.imag]
        mujoco.mj_forward(model,data)
        px,py,pt=(float(data.joint(term).qpos[0]) for term in ("x","y","heading"))
        base=[px,py,z,phase(rotate(pt))]
        contacts=[fixture["load"]] if any(c.dist<=1e-8 for c in data.contact) else []
        messages=[]
        for topic,sensor in fixture["sensors"].items():
            if epoch_tick%sensor["period_steps"]:continue
            position=combine(base,sensor["relative"])
            if sensor["type"]=="imu":
                value=position[3]
            else:
                direction_ray=rotate(position[3])
                storage=np.zeros(1,dtype=np.int32)
                value=mujoco.mj_ray(model,data,np.asarray(position[:3]),
                                    np.asarray([direction_ray.real,direction_ray.imag,0.0]),None,1,
                                    model.body("chassis").id,storage)
                value=None if value<0 else float(value)
            messages.append({"topic":topic,"frame":sensor["frame"],"qos":spec["qos"][topic],
                             "pose":position,"value":value})
        output.append({"step":tick,"epoch":epoch,"time_ns":round(dt*1e9)*epoch_tick,
                       "base":base,"contacts":contacts,"messages":messages})
        cmd=spec["commands"][direction]
        motor=rotate(pt)*cmd["force_n"]
        data.ctrl[:]=[motor.real,motor.imag,cmd["torque_nm"]]
        mujoco.mj_step(model,data)
        epoch_tick+=1
    return {"steps":output}
