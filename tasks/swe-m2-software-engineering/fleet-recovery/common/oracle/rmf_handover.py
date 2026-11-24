"""Coordinate measured read-only traffic and a responsive delivery route."""

import argparse
from functools import lru_cache
from hashlib import sha256
from heapq import heappop, heappush
import json
from math import dist
import os
from pathlib import Path
import subprocess
import sys


def native(command, lines):
    """Invoke the pinned Jazzy starter on an explicit native route."""
    binary=os.environ.get("FLEET_RMF_NATIVE","rmf-native")
    result=subprocess.run([binary,command],input="\n".join(lines)+"\n",text=True,
                          capture_output=True,check=True,timeout=4)
    return result.stdout.strip().splitlines()


@lru_cache(maxsize=32)
def generate(profile, poses):
    """Get native integer time and measured waypoint identity."""
    header=" ".join(map(str,(*profile,len(poses))))
    rows=native("interpolate",[header,*(" ".join(map(str,row)) for row in poses)])
    count=int(rows[0])
    if len(rows)!=count+1:
        raise ValueError("native itinerary was incomplete")
    return tuple((int(values[0]),*(float(v) for v in values[1:]))
                 for line in rows[1:] for values in [line.split()])


def shifted(points, start_ns):
    return [(start_ns+row[0],*row[1:]) for row in points]


def route_lines(space, radius, points):
    return [f"{space} {radius} {len(points)}",*(" ".join(map(str,row)) for row in points)]


@lru_cache(maxsize=64)
def forecast(space, a_radius, a, b_radius, b, delay, checkpoint, release):
    """Read the native mirrored conflict and active-plan checkpoint dependency."""
    result=native("schedule",[f"{delay} {checkpoint} {release}",
                             *route_lines(space,a_radius,a),*route_lines(space,b_radius,b)])
    if len(result)!=2 or result[1] not in ("ready","blocked"):
        raise ValueError("incorrect native schedule reply")
    return (None if result[0]=="clear" else int(result[0])),result[1]=="ready"


def authority_plan(previous, notice):
    """Apply only measured-version-compatible updates to the local schedule."""
    if not notice:
        return previous
    if notice["kind"]=="snapshot" and (previous is None or notice["version"]>previous["version"]):
        return {key:notice[key] for key in ("version","plan_id","start_ns","poses")}|{"base_ns":notice["start_ns"]}
    if (notice["kind"]=="delta" and previous is not None and
        notice["base_version"]==previous["version"] and notice["version"]>previous["version"]):
        return previous | {"version":notice["version"],"start_ns":previous["start_ns"]+notice["delay_ns"]}
    return previous


def profile_values(record):
    return tuple(record[key] for key in ("radius","linear_speed","linear_accel","angular_speed","angular_accel"))


def route_to(spec, start, unavailable):
    """Choose shortest currently usable route, with deterministic ties."""
    todo=[(0.0,(start,))]
    seen=set()
    while todo:
        length,path=heappop(todo)
        current=path[-1]
        if current in seen:
            continue
        seen.add(current)
        if current==spec["goal_node"]:
            return path
        for edge in spec["edges"]:
            a,b=edge["from"],edge["to"]
            if a==current and b not in seen and (a,b) not in unavailable:
                heappush(todo,(length+dist(spec["nodes"][a],spec["nodes"][b]),(*path,b)))
    return None


def checkpoint_report(spec, plan, native_points, last, event):
    """Bind physical progress to the current native plan instead of vendor path length."""
    row=event["carrier"]
    now=event["time_ns"]
    if last and last["plan_id"]!=plan["plan_id"]:
        last=None
    if (row and type(row["capture_ns"]) is int and 0<=row["capture_ns"]<=now
        and now-row["capture_ns"]<=spec["telemetry_max_age_ns"] and row["plan_id"]==plan["plan_id"]
        and (last is None or row["capture_ns"]>last["sample_ns"])):
        axis=spec["crossing"]["axis"]
        sign=spec["crossing"]["sign"]
        coordinate=sign*row["position"][axis]
        orthogonal=1-axis
        lateral=native_points[0][orthogonal+1]
        if abs(row["position"][orthogonal]-lateral)<=spec["carrier_lane_tolerance_m"]:
            reached=max((i for i,point in enumerate(native_points) if sign*point[axis+1]<=coordinate+1e-7),default=-1)
            if last is None or reached>=last["checkpoint"]:
                last={"plan_id":plan["plan_id"],"sample_ns":row["capture_ns"],"checkpoint":reached}
    if last and now-last["sample_ns"]<=spec["telemetry_max_age_ns"]:
        return last,last["checkpoint"]
    return last,None


def rejected(tick):
    return {"tick":tick,"status":"rejected","schedule_version":None,"carrier_plan":None,
            "checkpoint":None,"conflict_at_ns":None,"command":None}


def step(spec, state, event):
    tick=event["tick"]
    if tick==state["tick"] and event==state["request"]:
        return state["reply"],False
    if type(tick) is not int or tick!=state["tick"]+1:
        return rejected(tick),False
    plan=authority_plan(state["plan"],event["schedule"])
    state["plan"]=plan
    up_to_date=plan is not None and plan["version"]==event["required_version"]
    advance=False
    checkpoint=None
    collision_ns=None
    if plan is not None:
        carrier=profile_values(spec["carrier_profile"])
        courier=profile_values(spec["courier_profile"])
        points=generate(carrier,tuple(tuple(x) for x in plan["poses"]))
        state["carrier"],reported=checkpoint_report(spec,plan,points,state["carrier"],event)
        if up_to_date:
            checkpoint=reported
            prefix=spec["crossing"]
            clear=next((i for i,row in enumerate(points) if prefix["sign"]*row[prefix["axis"]+1]>=prefix["clear_progress_m"]),None)
            probe=spec["probe"]
            proposed=generate(courier,tuple(tuple(x) for x in probe["poses"]))
            collision_ns,native_ready=forecast(spec["map"],carrier[0],tuple(shifted(points,plan["base_ns"])),courier[0],
                                  tuple(shifted(proposed,probe["start_ns"])),plan["start_ns"]-plan["base_ns"],
                                  -1 if checkpoint is None else checkpoint,-1 if clear is None else clear)
            advance=checkpoint is not None and clear is not None and checkpoint>=clear and native_ready
    pending=state["pending"]
    observed=event["courier"]
    if (pending and observed["settled"]==pending["id"]
        and dist(observed["position"],spec["nodes"][pending["to"]])<=spec["settle_tolerance_m"]):
        state["node"]=pending["to"]
        pending=None
    closed={tuple(edge) for edge in event["closed_edges"]}
    guarded={(edge["from"],edge["to"]) for edge in spec["edges"] if edge["requires_clearance"]}
    if not pending and state["node"]!=spec["goal_node"]:
        unavailable=closed if advance else closed|guarded
        path=route_to(spec,state["node"],unavailable)
        if path is None:
            path=route_to(spec,state["node"],closed)
        if path and len(path)>1 and (path[0],path[1]) not in unavailable:
            state["serial"]+=1
            pending={"id":f"move-{state['serial']}","from":path[0],"to":path[1],
                     "max_speed_mps":spec["courier_profile"]["linear_speed"]}
    state["pending"]=pending
    status=("moving" if pending else "done" if state["node"]==spec["goal_node"] else
            "wait_carrier" if up_to_date else "wait_schedule")
    reply={"tick":tick,"status":status,"schedule_version":None if plan is None else plan["version"],
           "carrier_plan":None if plan is None else plan["plan_id"],"checkpoint":checkpoint,
           "conflict_at_ns":collision_ns,"command":pending}
    state.update(tick=tick,request=event,reply=reply)
    return reply,True


def command(store_state):
    """Serve one scoped native traffic authority session."""
    parser=argparse.ArgumentParser()
    parser.add_argument("--spec",type=Path,required=True)
    parser.add_argument("--state",type=Path,required=True)
    args=parser.parse_args()
    raw=args.spec.read_bytes()
    spec=json.loads(raw)
    signature=sha256(raw).hexdigest()
    args.state.mkdir(parents=True,exist_ok=True)
    path=args.state/"rmf-handover.json"
    state=(json.loads(path.read_text()) if path.is_file() else
           {"signature":signature,"tick":-1,"request":None,"reply":None,"serial":0,
            "plan":None,"carrier":None,"node":spec["start_node"],"pending":None})
    if state["signature"]!=signature:
        raise ValueError("session manifest changed")
    for line in sys.stdin:
        result,changed=step(spec,state,json.loads(line))
        if changed:
            store_state(path,state)
        print(json.dumps(result,allow_nan=False),flush=True)
    return 0
