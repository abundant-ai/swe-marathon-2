"""Prepare paired native checkpoints from authored scalar poses and world observations."""

from copy import deepcopy
import math

import mujoco
import numpy as np

from probes import STATE, identity, simulated, update


ROOT = mujoco.mjtObj.mjOBJ_XBODY
DT = .0007
SHAPE = np.array([.15,.10,.07])
PIVOT = ".043 -.039 .026"
BODY_FIXED = {
    "ram": '<body name="ram" pos="-.52 -.48 .17"><joint name="rail" type="slide" axis="1 0 0" damping=".4"/><geom type="box" size=".053 .043 .048"/></body>',
    "fence": '<body name="fence" mocap="true" pos=".31 .32 .16"><geom type="box" size=".04 .09 .08"/></body>',
}


def ids(name, kind):
    labels = ("tx","ty","tz") if kind=="slide" else ("a","b","c")
    return [name+"-"+label for label in labels]


def descriptor(name, kind):
    return ({"free_joint":name+"-float"} if kind=="free" else
            {"slides":ids(name,"slide"),"hinges":ids(name,"hinge")})


def body_text(name, kind, variant, dense):
    side = .49 if name == "second" else -.13
    zero_quat = ".9895059059 0 0 .1444924297" if dense else ".9817802074 .08365088997 -.012214092 .1438247389"
    fixed = (f'<inertial pos=".013 -.029 .019" mass="{1.63+.11*variant}" diaginertia=".009 .013 .017" '
             'quat=".995 0 .099875 0"/><geom type="box" size=".15 .10 .07" friction=".33 .005 .001"/>')
    if kind=="free":
        joints = f'<freejoint name="{name}-float"/>'
    else:
        slide = ("0 -1 0","0 0 1","1 0 0") if variant==0 else ("1 0 0","0 -1 0","0 0 1")
        hinge = ("0 0 1","0 1 0","1 0 0") if variant==0 else ("0 -1 0","0 0 1","1 0 0")
        joints = "".join(f'<joint name="{j}" type="slide" axis="{a}" ref="{r}"/>'
                         for j,a,r in zip(ids(name,"slide"),slide,(.031,.065,-.028),strict=True))
        joints += "".join(f'<joint name="{j}" type="hinge" axis="{a}" ref="{r}" pos="{PIVOT}"/>'
                          for j,a,r in zip(ids(name,"hinge"),hinge,(.22,-.32,.16),strict=True))
    return f'<body name="{name}" pos=".215 {side} .362" quat="{zero_quat}">{joints}{fixed}</body>'


def packet(layout, order, dense, changed_solver):
    payloads = {name:body_text(name,*properties,dense) for name,properties in layout.items()}
    bodies = "".join((BODY_FIXED|payloads)[body] for body in order)
    solver = 'solver="CG" iterations="1" tolerance="0"' if changed_solver else 'solver="Newton" iterations="30" tolerance="1e-11"'
    return {"assets":{},"xml":f"""
      <mujoco model="mixed coordinates native contact">
        <compiler angle="radian" alignfree="false"/>
        <size nuserdata="2"/>
        <option timestep="{DT}" gravity="0 0 -9.81" integrator="Euler" cone="elliptic" {solver}/>
        <worldbody><geom name="floor" type="plane" size="3 3 .1" friction=".33 .005 .001"/>{bodies}</worldbody>
        <actuator><general name="advance" joint="rail" dyntype="filterexact" dynprm=".06" gainprm="3"/></actuator>
        <equality><joint name="rail-stop" joint1="rail" polycoef=".13 0 0 0 0" active="false"/></equality>
      </mujoco>"""}


def pack(model,data,description,tick):
    values = np.empty(mujoco.mj_stateSize(model,STATE))
    mujoco.mj_getState(model,data,values,STATE)
    return {"model_id":identity(description),"tick":tick,"integration":values.tolist()}


def native(spec):
    return mujoco.MjModel.from_xml_string(spec["xml"])


def column_indices(model,name,kind):
    if kind=="free":
        begin=model.joint(name+"-float").dofadr[0]
        return np.arange(begin,begin+6)
    return np.array([model.joint(j).dofadr[0] for j in ids(name,"slide")+ids(name,"hinge")])


def jac(model,data,body,columns):
    jacp,jacr = np.empty((3,model.nv)),np.empty((3,model.nv))
    mujoco.mj_jacBody(model,data,jacp,jacr,body)
    return np.vstack((jacp,jacr))[:,columns]


def twist(model,data,body):
    raw = np.empty(6)
    mujoco.mj_objectVelocity(model,data,ROOT,body,raw,0)
    return np.r_[raw[3:],raw[:3]]


def bias(model,data,body):
    eps = 4e-6
    values = []
    for dt in (-eps,eps):
        moved = mujoco.MjData(model)
        moved.qpos[:] = data.qpos
        moved.qvel[:] = data.qvel
        mujoco.mj_integratePos(model,moved.qpos,data.qvel,dt)
        mujoco.mj_kinematics(model,moved)
        mujoco.mj_comPos(model,moved)
        mujoco.mj_comVel(model,moved)
        values.append(twist(model,moved,body))
    return (values[1]-values[0])/(2*eps)


def common_state(model,tick):
    data = mujoco.MjData(model)
    rail = model.joint("rail")
    data.qpos[rail.qposadr[0]] = .13
    j = rail.dofadr[0]
    data.qvel[j],data.qacc_warmstart[j],data.qfrc_applied[j] = .17,.21,.28
    data.ctrl[0],data.act[0],data.eq_active[0] = .21,-.17,tick%2
    data.mocap_pos[0] = [.38,.32,.135]
    data.mocap_quat[0] = [.9805806756909201,0.,0.,.19611613513818404]
    data.xfrc_applied[model.body("ram").id] = [.21,-.08,.03,.004,-.013,.019]
    data.userdata[:] = [.13,4.52]
    data.time = tick*DT
    return data


def set_pose(models,data,name,kinds,variant,dense,singular=False):
    scalar, free = (0,1) if kinds[0]=="scalar" else (1,0)
    m,record = models[scalar],data[scalar]
    slides = [m.joint(label).qposadr[0] for label in ids(name,"slide")]
    hinges = [m.joint(label).qposadr[0] for label in ids(name,"hinge")]
    angles = [.43,.014,-.012] if dense else [(-.69 if variant==0 else -.37),-.53,.82]
    if singular:
        angles[1] = math.pi/2
    record.qpos[hinges] = m.qpos0[hinges]+angles
    record.qpos[slides] += [.052,-.035,.083]
    body = m.body(name).id
    mujoco.mj_kinematics(m,record)
    orientation = record.xmat[body].reshape(3,3)
    nominal_height = .063 if dense else np.abs(orientation[2])@SHAPE-.002
    slide_z = 1 if variant==0 else 2
    slide_id = m.joint(ids(name,"slide")[slide_z]).id
    record.qpos[slides[slide_z]] += (nominal_height-record.xpos[body,2])/record.xaxis[slide_id,2]
    mujoco.mj_kinematics(m,record)
    fi = models[free].joint(name+"-float").qposadr[0]
    data[free].qpos[fi:fi+3] = record.xpos[body]
    q = record.xquat[body]
    data[free].qpos[fi+3:fi+7] = q if q[0]>=0. else -q


def set_physics(models,data,name,kinds,dense):
    cols = [column_indices(m,name,kind) for m,kind in zip(models,kinds,strict=True)]
    bodies = [m.body(name).id for m in models]
    translations = [.095,-.043,-.13] if dense else [.29,-.19,-.21]
    for m,d,body,indices in zip(models,data,bodies,cols,strict=True):
        mujoco.mj_forward(m,d)
        d.qvel[indices] = np.linalg.solve(jac(m,d,body,indices),translations+[.79,-.87,1.02])
        wrench = np.zeros(m.nv)
        p = d.xpos[body]+d.xmat[body].reshape(3,3)@np.array([.068,-.097,.045])
        mujoco.mj_applyFT(m,d,np.array([1.63,-1.12,1.61]),np.array([.072,-.041,.096]),p,body,wrench)
        d.qfrc_applied[indices] = wrench[indices]
        d.xfrc_applied[body] = [.017,-.033,.024,.0006,-.003,.002]
    for m,d in zip(models,data,strict=True):
        mujoco.mj_forward(m,d)
    measured = np.array([.83,-.74,.52,2.17,-1.53,2.86])
    if dense:
        m,d,body,indices = models[0],data[0],bodies[0],cols[0]
        measured = jac(m,d,body,indices)@d.qacc[indices]+bias(m,d,body)
    for m,d,body,indices in zip(models,data,bodies,cols,strict=True):
        d.qacc_warmstart[indices] = np.linalg.solve(jac(m,d,body,indices),measured-bias(m,d,body))


def mission(index, singular=False):
    direction = "free" if index%2==0 else "scalar"
    invert = {"free":"scalar","scalar":"free"}
    variant = index//2 % 2
    dense = index==4
    bodies = {"cargo":(direction,variant)}
    if index==5:
        bodies["second"] = (invert[direction],0)
    target_bodies = {name:(invert[kind],style) for name,(kind,style) in bodies.items()}
    begin = ("ram",*bodies,"fence")
    end = tuple(reversed(begin))
    descriptions = [packet(bodies,begin,dense,False),packet(target_bodies,end,dense,dense)]
    models = [native(spec) for spec in descriptions]
    tick = 27+index*4
    data = [common_state(m,tick) for m in models]
    for name,(kind,style) in bodies.items():
        set_pose(models,data,name,(kind,invert[kind]),style,dense,singular)
    if not singular:
        for name,(kind,_) in bodies.items():
            set_physics(models,data,name,(kind,invert[kind]),dense)
        for m,d in zip(models,data,strict=True):
            mujoco.mj_forward(m,d)
            assert d.ncon >= (4 if dense else 1)
    source = pack(models[0],data[0],descriptions[0],tick)
    expected = pack(models[1],data[1],descriptions[1],tick)
    # A one-iteration contact solver eventually magnifies roundoff into a different contact sequence.
    # Use a short continuation here and the longer windows for the other configured native solvers.
    last = tick+(14 if dense else 57)
    inner = tick+(8 if dense else 23)
    release = tick+(13 if dense else 29)
    request = {"source_model":descriptions[0],"target_model":descriptions[1],"checkpoint":source,
               "charts":[{"body":name,"source":descriptor(name,kind),"target":descriptor(name,invert[kind])}
                         for name,(kind,_) in bodies.items()],
               "end":last,"sample_ticks":[last,tick+1,tick,tick+12],
               "checkpoint_ticks":[tick+1,last,tick,inner],
               "updates":[update(tick+9,ctrl=[.52],eq_active=[1]),update(release,eq_active=[0])]}
    if dense:
        drift = deepcopy(expected)
        original = mujoco.MjData(models[1])
        mujoco.mj_setState(models[1],original,np.array(drift["integration"]),STATE)
        original.qacc_warmstart[column_indices(models[1],"cargo","scalar")] = 0.
        changed = pack(models[1],original,descriptions[1],tick)
        a = simulated(request|{"model":descriptions[1]},expected)["samples"][1]["qvel"]
        b = simulated(request|{"model":descriptions[1]},changed)["samples"][1]["qvel"]
        assert np.linalg.norm(np.asarray(a)-b) > .04
    return request,expected


def agrees(actual, expected):
    if isinstance(expected,dict):
        return isinstance(actual,dict) and actual.keys()==expected.keys() and all(
            agrees(actual[key],value) for key,value in expected.items())
    if isinstance(expected,list):
        return isinstance(actual,list) and len(actual)==len(expected) and all(
            agrees(a,b) for a,b in zip(actual,expected,strict=True))
    if isinstance(expected,(float,np.floating)):
        try:
            return type(actual) in (float,int) and math.isfinite(actual) and math.isclose(
                actual,expected,abs_tol=1e-6,rel_tol=5e-9)
        except OverflowError:
            return False
    return type(actual) is type(expected) and actual==expected


def same_fork(actual,expected,description):
    if (not isinstance(actual,dict) or actual.keys()!=expected.keys() or actual["tick"]!=expected["tick"]
            or actual["model_id"]!=expected["model_id"]):
        return False
    model = native(description)
    left,right = mujoco.MjData(model),mujoco.MjData(model)
    try:
        integration = np.asarray(actual["integration"],dtype=np.float64)
        if integration.shape!=(mujoco.mj_stateSize(model,STATE),) or not np.all(np.isfinite(integration)):
            return False
        mujoco.mj_setState(model,left,integration,STATE)
        mujoco.mj_setState(model,right,np.array(expected["integration"]),STATE)
    except (TypeError,ValueError,OverflowError):
        return False
    for field in ("qpos","qvel","qfrc_applied","qacc_warmstart","ctrl","act","eq_active","mocap_pos",
                  "mocap_quat","userdata","xfrc_applied","time"):
        threshold = 1e-6 if field=="qacc_warmstart" else 1e-8 if field in ("qpos","qvel","qfrc_applied") else 1e-10
        if not np.allclose(getattr(left,field),getattr(right,field),atol=threshold,rtol=0):
            return False
    return True


def run_positive(run,index):
    request, checkpoint = mission(index)
    target = request["target_model"]
    resumed = simulated(request|{"model":target},checkpoint)
    candidate = run("rechart",request)
    if (not isinstance(candidate,dict) or candidate.keys()!={"checkpoint","resumed"}
            or not same_fork(candidate["checkpoint"],checkpoint,target)
            or not agrees(candidate["resumed"],resumed)):
        return False
    # The reported fork also has to reproduce the continuation on the separate command.
    return agrees(run("resume",request|{"model":target,"checkpoint":candidate["checkpoint"]}),resumed)


def checks_rechart(run):
    cases = {}
    names = ("free_to_signed_scalar", "scalar_to_free", "free_to_permuted_scalar", "reverse_permuted",
             "dense_warm_contact_first_step", "two_roots_reorder_while_recharting")
    for index,name in enumerate(names):
        cases[name] = run_positive(run,index)
    singular = [mission(i,singular=True)[0] for i in (0,1)]
    cases["reject_singular_in_either_chart"] = all(run("rechart",spec,invalid=True) is True for spec in singular)
    request,_ = mission(0)
    no_descriptor = request|{"charts":[]}
    bad_order = deepcopy(request)
    bad_order["charts"][0]["target"]["hinges"].reverse()
    bad_tail = request|{"sample_ticks":[request["end"]+1]}
    bad_pivot = deepcopy(request)
    bad_pivot["target_model"]["xml"] = bad_pivot["target_model"]["xml"].replace(PIVOT,".04 -.1 .026",1)
    cases["reject_bad_chart_and_schedule_atomically"] = all(run("rechart",spec,invalid=True) is True
                                                            for spec in (no_descriptor,bad_order,bad_tail,bad_pivot))
    return cases
