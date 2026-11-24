"""Contact checks using native arm Jacobians and an independently generated plant."""

import cmath
from math import cos, sin

import mujoco
import numpy as np


ARM = {"lengths_m":[0.62,0.43],"world_from_base":{"xy":[-0.17,0.31],"yaw_rad":0.35},
       "pusher_offset_m":[0.062,-0.094]}
CAL = {"tool_from_sensor":{"xy":[0.145,-0.071],"yaw_rad":-1.147},"bias":[0.29,-0.43,0.088]}


def native_arm(arm):
    """Compile the commissioned arm from native hinge and site primitives."""
    first,second=arm["lengths_m"]
    x,y=arm["world_from_base"]["xy"]
    px,py=arm["pusher_offset_m"]
    yaw=arm["world_from_base"]["yaw_rad"]
    xml=f"""<mujoco><compiler angle="radian"/><worldbody>
      <body pos="{x} {y} 0" euler="0 0 {yaw}"><joint name="a" axis="0 0 1"/>
      <geom type="capsule" size=".02" fromto="0 0 0 {first} 0 0"/>
      <body pos="{first} 0 0"><joint name="b" axis="0 0 1"/>
      <geom type="capsule" size=".02" fromto="0 0 0 {second} 0 0"/>
      <site name="pusher" pos="{second+px} {py} 0"/></body></body></worldbody></mujoco>"""
    model=mujoco.MjModel.from_xml_string(xml)
    return model,mujoco.MjData(model)


def native_pose(native,q):
    """Return independently evaluated point, angle and full geometric Jacobian."""
    model,data=native
    data.qpos[:]=q
    mujoco.mj_forward(model,data)
    linear=np.zeros((3,2))
    angular=np.zeros((3,2))
    mujoco.mj_jacSite(model,data,linear,angular,0)
    heading=complex(data.site_xmat[0,0],data.site_xmat[0,3])
    return data.site_xpos[0,:2].copy(),heading,np.vstack((linear[:2],angular[2]))


def sensor_reading(tool_force, tool_torque, calibration):
    """Generate a biased raw observation from independently applied loads."""
    mount=calibration["tool_from_sensor"]
    true=tool_force / cmath.rect(1,mount["yaw_rad"])
    torque=tool_torque-(complex(*mount["xy"]).conjugate()*tool_force).imag
    return (np.array([true.real,true.imag,torque])+calibration["bias"]).tolist()


def same(value,wanted,tol=2e-7):
    """Compare a candidate numeric record at physical precision."""
    try:
        a,b=np.asarray(value),np.asarray(wanted)
        return a.dtype.kind in "fiu" and a.shape==b.shape and bool(np.allclose(a,b,atol=tol,rtol=tol))
    except (TypeError,ValueError,OverflowError):
        return False


def transform_case(run,arm,cal,seed):
    """Check world wrenches and virtual work using native and finite-difference geometry."""
    random=np.random.default_rng(seed)
    native=native_arm(arm)
    samples=[]
    expected=[]
    for index in range(14):
        q=random.uniform(-1.7,1.7,2)
        xyz,heading,J=native_pose(native,q)
        f=complex(*random.uniform(-5.,5.,2))
        torsion=float(random.uniform(-1,1))
        world=f*heading
        wrench=[world.real,world.imag,torsion-(complex(*arm["pusher_offset_m"]).conjugate()*f).imag]
        lab=np.asarray(wrench)
        key=f"w-{index:02}"
        samples.append({"id":key,"q":q.tolist(),"raw_wrench":sensor_reading(f,torsion,cal)})
        match = []
        for axis in range(2):
            change = np.eye(2)[axis]*1e-5
            nominal=native_pose(native,q+change)[0]-native_pose(native,q-change)[0]
            match.append(float(lab[:2]@nominal/2e-5+lab[2]))
        if not same(J.T@lab,match):
            raise RuntimeError("MuJoCo Jacobian and finite-difference geometry disagree")
        expected.append((key,xyz,lab,match))
    result=run("transform",{"arm":arm,"calibration":cal,"samples":samples})
    seen=result.get("samples")
    return isinstance(seen,list) and len(seen)==len(expected) and all(
        isinstance(row,dict) and row.get("id")==key and same(row.get("pusher_position_m"),xyz) and
        same(row.get("world_wrench"),wrench) and same(row.get("joint_torque_nm"),torques)
        for row,(key,xyz,wrench,torques) in zip(seen,expected,strict=True))


def calibration_input(cal,seed,degenerate=False):
    """Construct known applied loads with independent contaminated force channels."""
    random=np.random.default_rng(seed)
    observations=[]
    for index in range(34):
        f=complex(*random.uniform(-12,12,2)) if not degenerate else complex(index/5,0)
        moment=float(random.uniform(-1.8,1.8))
        raw=sensor_reading(f,moment,cal)
        if index in (4,11,18,27):
            raw=(np.array(raw)+random.normal(2.3,2,3)).tolist()
        observations.append({"id":str(index),"q":random.uniform(-2,2,2).tolist(),
            "reference_tool_wrench":[f.real,f.imag,moment],"raw_wrench":raw})
    return {"arm":ARM,"samples":observations}


def calibration_agrees(output,cal):
    """Check an estimated mount and all independently planted sensor biases."""
    result=output.get("calibration")
    if output.get("status")!="ok" or not isinstance(result,dict):
        return False
    mount=result.get("tool_from_sensor")
    return (isinstance(mount,dict) and same(mount.get("xy"),cal["tool_from_sensor"]["xy"],2e-5)
            and same(mount.get("yaw_rad"),cal["tool_from_sensor"]["yaw_rad"],2e-5)
            and same(result.get("bias"),cal["bias"],2e-5))


def make_contact(native,q,dq,point,velocity,params,body):
    """Generate force from independent native point Jacobian and unilateral material law."""
    xyz,heading,J=native_pose(native,q)
    relative=np.array(point)-xyz
    distance=np.linalg.norm(relative)
    overlap=body["radius_m"]+body["pusher_radius_m"]-distance
    if overlap<=0 or distance<=0:
        return np.zeros(2),heading
    direction=relative/distance
    speed=float(direction@(J[:2]@dq-velocity))
    compliance=max(0.,params[0]*overlap+params[1]*speed)
    return compliance*direction,heading


def pushing_case(index,cal):
    """Generate disjoint force and trajectory truth with held-out pusher controls."""
    random=np.random.default_rng(719+10*index)
    native=native_arm(ARM)
    gains=([67.,9.1,2.9,4.8],[96.,6.8,6.4,1.8])[index]
    body={"mass_kg":1.24+0.24*index,"radius_m":0.072,"pusher_radius_m":0.048}
    dt=0.024
    rows=[]
    for i in range(86):
        q=random.uniform(-1.3,1.3,2)
        dq=random.uniform(-0.5,0.5,2)
        vel=random.uniform(-0.36,0.36,2)
        pusher,heading,J=native_pose(native,q)
        theta=random.uniform(-3.,3.)
        normal=np.array([cos(theta),sin(theta)])
        point=pusher+normal*random.uniform(.075,.151)
        F,_=make_contact(native,q,dq,point,vel,gains,body)
        next_vel=vel+dt*(F-np.array(gains[2:])*vel)/body["mass_kg"]
        force=complex(*F)/heading
        moment=(complex(*ARM["pusher_offset_m"]).conjugate()*force).imag
        raw=np.array(sensor_reading(force,moment,cal))
        if i%19==7:
            raw+=random.normal(1.5,2.,3)
        rows.append({"q":q.tolist(),"dq":dq.tolist(),"position_m":point.tolist(),"velocity_m_s":vel.tolist(),
                     "next_velocity_m_s":next_vel.tolist(),"raw_wrench":raw.tolist()})
    cases,expected=[],[]
    for index_run,qpair in enumerate(([0.35,-0.52],[-0.96,0.47],[-0.44,-0.44])):
        q0=np.array(qpair)
        pusher,_,J=native_pose(native,q0)
        draft=np.array([0.22+0.1*index_run,-0.11])
        direction=J[:2]@draft
        position=pusher+0.111*direction/np.linalg.norm(direction)
        velocity=np.array([.024,-.019])
        spec={"id":f"verification-{index_run}","initial_position_m":position.tolist(),
              "initial_velocity_m_s":velocity.tolist(),"controls":[]}
        wanted=[]
        for j in range(51):
            t=j*dt
            q=q0+np.array([draft[0]*sin(t),draft[1]*sin(1.4*t)/1.4])
            dq=np.array([draft[0]*cos(t),draft[1]*cos(1.4*t)])
            force,_=make_contact(native,q,dq,position,velocity,gains,body)
            velocity=velocity+dt*(force-np.array(gains[2:])*velocity)/body["mass_kg"]
            position=position+dt*velocity
            spec["controls"].append({"q":q.tolist(),"dq":dq.tolist()})
            wanted.append({"force_n":force.tolist(),"position_m":position.tolist(),"velocity_m_s":velocity.tolist()})
        cases.append(spec)
        expected.append({"id":spec["id"],"steps":wanted})
    return {"arm":ARM,"calibration":cal,"object":body,"dt_s":dt,"fit":rows,"validation":cases},gains,expected


def qualification_agrees(output,gains,expected):
    """Check physical parameters and independent force and motion at every boundary."""
    if output.get("status")!="ok" or not isinstance(output.get("parameters"),dict):
        return False
    params=output["parameters"]
    if not (same(params.get("stiffness_n_m"),gains[0],2e-5) and same(params.get("damping_n_s_m"),gains[1],2e-5)
            and same(params.get("drag_n_s_m"),gains[2:],2e-5)):
        return False
    sample=output.get("runs")
    if not isinstance(sample,list) or len(sample)!=len(expected):
        return False
    for got,wanted in zip(sample,expected,strict=True):
        if not isinstance(got,dict) or got.get("id")!=wanted["id"] or not isinstance(got.get("steps"),list):
            return False
        if len(got["steps"])!=len(wanted["steps"]):
            return False
        for step,truth in zip(got["steps"],wanted["steps"],strict=True):
            if not isinstance(step,dict) or not all(same(step.get(field),value,2e-5) for field,value in truth.items()):
                return False
    return True


def checks(run,level,data):
    """Score cumulative native geometry, mounted sensor recovery and held-out pushes."""
    changed=ARM | {"world_from_base":{"xy":[0.41,-0.76],"yaw_rad":2.3},
                   "lengths_m":[0.45,0.56],"pusher_offset_m":[-0.061,0.075]}
    other={"tool_from_sensor":{"xy":[-0.091,0.116],"yaw_rad":1.41},"bias":[-0.19,0.82,-0.23]}
    poses=[transform_case(run,ARM,CAL,327),transform_case(run,changed,other,542)]
    result={"native_wrench_and_joint_torques":poses[0],"independent_base_and_tool_geometry":poses[1]}
    if level>=2:
        fit=run("calibrate",calibration_input(CAL,992))
        varied=run("calibrate",calibration_input(other,147))
        degenerate=run("calibrate",calibration_input(CAL,109,True))
        positive=calibration_agrees(fit,CAL) or calibration_agrees(varied,other)
        result.update(robust_sensor_pose_and_bias=calibration_agrees(fit,CAL),
                      alternate_sensor_mount=calibration_agrees(varied,other),
                      parallel_load_abstention=positive and degenerate.get("status")=="insufficient_excitation"
                      and "calibration" in degenerate and degenerate["calibration"] is None)
    if level>=3:
        designed=[pushing_case(0,CAL),pushing_case(1,other)]
        first=[run("qualify",spec) for spec,_,_ in designed]
        valid=[qualification_agrees(out,p,x) for out,(_,p,x) in zip(first,designed,strict=True)]
        known=designed[0][0]
        fitted=fit.get("calibration")
        cascade=run("qualify",known | {"calibration":fitted}) if isinstance(fitted,dict) else {}
        changed_validation=run("qualify",known | {"validation":[]})
        absent=run("qualify",known | {"fit":[]})
        result.update(
            independent_contact_force_and_motion=valid[0], second_plant_drag_and_compliance=valid[1],
            actual_calibration_flows_to_heldout_motion=qualification_agrees(cascade,*designed[0][1:]),
            fit_is_frozen_when_validation_changes=any(valid) and changed_validation.get("parameters")==first[0].get("parameters")
            and changed_validation.get("runs")==[],
            insufficient_push_excitation=any(valid) and absent=={"status":"insufficient_excitation","parameters":None,"runs":[]},
            malformed_preserves_existing=any(valid) and run("qualify",known|{"dt_s":True},invalid=True).get("atomic",False))
    return result
