"""Independent ULog-shaped capture and faulted closed-loop missions."""

import json
from pathlib import Path
import subprocess
import sys

from flight import local, mission
from transport import Record, identity, require


def replay(app: Path, root: Path) -> Record:
    """Check staggered reset wraps, stale rows, unresolved gaps and partial anchors."""
    cases = [
        (10, [1,2,-2], [0,0,0], [255,254], [0,0,0], {}, [1,2,-2]),
        (20, [2,3,-2], [0.3,-0.4,0], [0,254], [0.3,-0.4,0], {}, [2,3,-2]),
        (30, [3,4,-2], [0.3,-0.4,1.3], [0,255], [0.3,-0.4,1.3], {"z_valid":False}, [3,4,None]),
        (24, [9,9,9], [0,0,0], [12,71], [2,3,4], {}, None),
        (40, [4,5,-2], [0.3,-0.4,1.3], [0,255], [0.3,-0.4,1.3], {}, [4,5,-2]),
        (50, [5,6,-3], [3.1,-2,1.77], [2,0], [2.8,-1.6,0.47], {}, [None,None,-3]),
        (60, [6,7,-3], [3.1,-2,1.77], [2,0], [2.8,-1.6,0.47], {"anchor":[6,None,None]}, [None,None,-3]),
        (70, [7,8,-3], [3.1,-2,1.77], [2,0], [2.8,-1.6,0.47], {"anchor":[7,8,None]}, [7,8,-3]),
    ]
    capture, truth = [], []
    for index,(stamp,p,offset,count,delta,extra,expected) in enumerate(cases):
        row=local(stamp,p,[0.0]*3,offset,count,delta) | extra
        row["timestamp"] = 2000 + index
        capture.append(row)
        if expected is not None:
            truth.append({"timestamp_sample":stamp,"position":expected})
    out = root/"output"
    out.mkdir()
    out.chmod(0o777)
    destination = out/"report.json"
    input_path = root/"log.ndjson"
    arguments=[sys.executable,"-B","-m","px4_recovery","replay","--input",str(input_path),"--output",str(destination)]
    input_path.write_text("".join(json.dumps(row)+"\n" for row in capture))
    call = subprocess.run(arguments,cwd=app, **identity(), timeout=12, capture_output=True)
    require(call.returncode == 0 and destination.is_file(),"replay failed to produce a report")
    report=json.loads(destination.read_text())
    require(report.get("stale")==1 and report.get("unresolved")==2 and len(report.get("rows",[]))==7,
            "bad replay counts or missing rows")
    for series,expected in zip(report["rows"],truth,strict=True):
        require(series["timestamp_sample"]==expected["timestamp_sample"] and len(series["position"])==3,
                "bad replay chronology")
        for actual, reference in zip(series["position"],expected["position"],strict=True):
            require(actual is None if reference is None else isinstance(actual,(int,float)) and abs(actual-reference)<1e-9,
                    "replay continuity or axis validity mismatch")
    original=destination.read_bytes()
    capture[-1]["xy_reset_counter"]=256
    input_path.write_text("".join(json.dumps(row)+"\n" for row in capture))
    call=subprocess.run(arguments,cwd=app, **identity(), timeout=12, capture_output=True)
    require(call.returncode!=0 and destination.read_bytes()==original, "malformed input replaced earlier replay")
    return {"accepted":7,"stale":1,"unresolved":2}


CASES = [
    (1,"reset_ledger_and_partial_anchors",replay,{}),
    (2,"healthy_spatial_waypoints",mission,{}),
    (2,"altitude_and_horizontal_wrap",mission,{"resets":{15:([0,1],[0,0,0.95]),29:([1,0],[0.41,-0.7,0]),46:([1,1],[0.15,0.21,-1.2])},
     "stale":[12,40], "invalid_z":[34,35], "minimum_hold":4}),
    (3,"bounded_inertial_bridge_and_reset",mission,{"inertial":6,"drop":[(18,23),(48,60)],"minimum_dead_reckon":10,"minimum_hold":6,
     "resets":{32:([0,1],[0,0,-1.2])}}),
    (3,"missed_reset_then_independent_anchor",mission,{"inertial":5,"resets":{20:([2,0],[0.65,-0.37,0])},"anchor":42,
      "minimum_dead_reckon":5,"minimum_hold":14,"bad_imu":[26]}),
    (3,"wrong_imu_breaks_inertial_chain",mission,{"inertial":5,"drop":[(15,26)],"bad_imu":[17],"minimum_dead_reckon":2,
      "minimum_hold":9,"targets":[[-0.35,0.6,-2.19],[0.72,0.88,-1.74]]}),
    (3,"permanent_loss_holds_and_aborts",mission,{"inertial":4,"drop":[(29,300)],"minimum_dead_reckon":4,
      "minimum_hold":45,"abort":True,"deadline":105}),
]
