"""Independent frame, physical rollout and downstream bridge probes."""

from copy import deepcopy
from cmath import phase
import json
import os
from pathlib import Path
import subprocess
import sys

from fixtures import rotate,scene
from transport import identity,require


def call(app,root,mode,world,spec=None,trace=None,invalid=False):
    """Run the submitted CLI, requiring atomicity on malformed inputs."""
    path=root/"world.sdf"
    path.write_text(world)
    results=root/"write"
    results.mkdir(exist_ok=True)
    results.chmod(0o777)
    output=results/"report.json"
    args=[sys.executable,"-B","-m","sim_regression",mode,"--world",str(path),"--output",str(output)]
    if spec is not None:
        spec_path=root/"run.json"
        spec_path.write_text(json.dumps(spec))
        args.extend(("--spec",str(spec_path)))
    if trace is not None:
        trace_path=root/"trace.json"
        trace_path.write_text(json.dumps(trace))
        args.extend(("--input",str(trace_path)))
    if invalid:
        marker=b'{"existing":true}\n'
        output.write_bytes(marker)
        output.chmod(0o666)
    env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"HOME":str(results),"LC_ALL":"C.UTF-8",
         "MUJOCO_GL":"disable","OPENBLAS_NUM_THREADS":"1"}
    execution=subprocess.run(args,cwd=app,**identity(),env=env,capture_output=True,timeout=15)
    if invalid:
        require(execution.returncode!=0 and output.read_bytes()==marker,"rejected input changed existing output")
        return None
    require(execution.returncode==0 and output.is_file() and output.stat().st_size<500_000,
            "simulator command failed before emitting a valid report")
    return json.loads(output.read_text())


def check_pose(actual,expected,tolerance=1e-8):
    """Compare finite transform coordinates with wrapped yaw."""
    require(type(actual) is list and len(actual)==4 and all(type(x) in (int,float) for x in actual),
            "invalid emitted pose")
    require(max(abs(a-b) for a,b in zip(actual[:3],expected[:3]))<tolerance
            and abs(phase(rotate(actual[3]-expected[3])))<tolerance,"incorrect transform")


def inspect(app,root,case):
    """Verify nested transforms, world references, topic names and exact cadence."""
    world,fixture,spec=scene(case["other"])
    found=call(app,root,"inspect",world)
    require(found.get("dt_ns")==round(fixture["dt"]*1e9) and found.get("frames",{}).keys()==fixture["frames"].keys(),
            "unknown frame set or timestep")
    for key,pose in fixture["frames"].items():
        check_pose(found["frames"][key],pose)
    expected={topic:{k:v for k,v in record.items() if k!="relative"}
              for topic,record in fixture["sensors"].items()}
    require(found.get("sensors")==expected,"wrong clock cadence or registered sensor wiring")
    if not case["other"]:
        invalid=world.replace('relative_to="mount"','relative_to="missing-frame"',1)
        call(app,root,"inspect",invalid,invalid=True)
        invalid=world.replace('relative_to="mount"','relative_to="late-frame"',1)
        call(app,root,"inspect",invalid,invalid=True)
    return {"frames":len(found["frames"]),"sensor_periods":sorted(row["period_steps"] for row in expected.values())}


def physical(app,root,case):
    """Compare actual native evolution, seeded contact timing and range response."""
    from shadow import shadow
    world,fixture,spec=scene(case["other"])
    truth=shadow(fixture,spec)["steps"]
    actual=call(app,root,"run",world,spec)["steps"]
    require(len(actual)==spec["steps"],"wrong native trace count")
    n=0
    hit_steps=[]
    region=set()
    for a,b in zip(actual,truth,strict=True):
        require(all(a.get(k)==b[k] for k in ("step","epoch","time_ns","contacts")),"incorrect clock, event reset or actual contact")
        check_pose(a.get("base"),b["base"],1e-6)
        if b["contacts"]:hit_steps.append(b["step"])
        before={m["topic"]:m for m in b["messages"]}
        after={m["topic"]:m for m in a["messages"]}
        require(after.keys()==before.keys() and len(after)==len(a["messages"]),"native sensor publication missed its physical cadence")
        for key,v in after.items():
            m=before[key]
            require(v.get("qos")==m["qos"] and v.get("frame")==m["frame"],"incorrect exported bridge metadata")
            check_pose(v.get("pose"),m["pose"],1e-6)
            expected=m["value"]
            actual_reading=v.get("value")
            require((actual_reading is None) if expected is None else
                    type(actual_reading) in (float,int) and abs(actual_reading-expected)<1e-6,
                    "incorrect observed ray or imu result")
            if key.endswith("/beam"):
                region.add(round(expected,4) if expected is not None else None)
            n+=1
    require(hit_steps and len(region)>=4,"fixture did not trigger physical contact and changed ray length")
    return {"ticks":len(truth),"first_physical_contact":hit_steps[0],"sensor_deliveries":n,"distinct_lidar_results":len(region),"contains_ray_miss":None in region}


def audit(app,root,case):
    """Challenge independent downstream regressions on an independently measured trace."""
    from shadow import shadow
    world,fixture,spec=scene(case["other"])
    truth=shadow(fixture,spec)
    first={"clock":None,"topic":None,"qos":None,"transform":None}
    kind=case["fault"]
    if kind=="composed":
        truth["steps"][4]["messages"][0]["pose"][1]+=0.19
        truth["steps"][5]["messages"].clear()
        truth["steps"][6]["messages"][0]["qos"]="wrong-profile"
        origin=spec["reset_steps"][0]
        truth["steps"][origin]["epoch"]=0
        truth["steps"][origin]["time_ns"]=round(fixture["dt"]*1e9)*origin
        first={"clock":origin,"topic":5,"qos":6,"transform":4}
    elif kind=="missing":
        del truth["steps"][13]
        first.update(clock=13,topic=13)
    elif kind=="empty":
        truth["steps"]=[]
        first.update(clock=0,topic=0)
    elif kind=="frame":
        truth["steps"][12]["messages"][0]["frame"]="old-joint-name"
        first.update(transform=12)
    report=call(app,root,"audit",world,spec,truth)
    status="fault" if any(v is not None for v in first.values()) else "ok"
    require(report.get("status")==status and report.get("first")==first,
            f"wrong earliest independent causes: expected {first!r}")
    if kind=="composed":
        broken=deepcopy(truth)
        broken["steps"].append(broken["steps"][0])
        call(app,root,"audit",world,spec,broken,invalid=True)
    return report


CASES=[
    (1,"inspect_relative_frame_chain",inspect,{"other":False}),
    (1,"inspect_changed_physics_rate_and_alias",inspect,{"other":True}),
    (2,"native_contact_seeded_move_and_reset",physical,{"other":False}),
    (2,"native_retimed_torque_and_ray",physical,{"other":True}),
    (3,"healthy_downstream",audit,{"other":True,"fault":"none"}),
    (3,"composed_clock_qos_tf_and_topic_faults",audit,{"other":False,"fault":"composed"}),
    (3,"dropped_clock_and_sensor_row",audit,{"other":True,"fault":"missing"}),
    (3,"silent_empty_bridge",audit,{"other":True,"fault":"empty"}),
    (3,"configured_frame_id_mismatch",audit,{"other":True,"fault":"frame"}),
]
