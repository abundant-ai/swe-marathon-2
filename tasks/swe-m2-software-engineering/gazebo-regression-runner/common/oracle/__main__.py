"""Inspect, execute, or audit a portable headless regression world."""

import argparse
import json
from math import isfinite
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

from .scene import World, Record, angle, read_world, relative, transform


def finite(raw: object) -> bool:
    """Identify ordinary finite JSON quantities."""
    return type(raw) in (int,float) and isfinite(raw)


def check_spec(spec: Record,world: World) -> None:
    """Validate declared schedule, robot and bridge settings before execution."""
    steps=spec["steps"]
    if (type(steps) is not int or steps<=0 or spec["robot"] not in world.models
            or type(spec["seed"]) is not int or not all(finite(spec[key]) for key in ("mass_kg","damping"))
            or spec["mass_kg"]<=0 or spec["damping"]<0):
        raise ValueError("invalid native scenario parameters")
    resets=spec["reset_steps"]
    if type(resets) is not list or any(type(s) is not int or not 0<s<steps for s in resets) or resets!=sorted(set(resets)):
        raise ValueError("invalid reset schedule")
    for collection in ("commands","relocations"):
        values=spec[collection]
        times=[row["step"] for row in values]
        if any(type(t) is not int or not 0<=t<steps for t in times) or times!=sorted(times):
            raise ValueError("nonmonotonic schedule")
        if collection=="commands":
            if not times or times[0]!=0 or len(set(times))!=len(times):
                raise ValueError("command schedule must begin at zero with unique steps")
            if not all(finite(row[key]) for row in values for key in ("force_n","torque_nm")):
                raise ValueError("invalid motor command")
        else:
            for row in values:
                if (row["model"] not in world.models or row["model"]==spec["robot"] or len(row["pose"])!=4
                        or not all(finite(value) for value in row["pose"]) or not finite(row["jitter_m"]) or row["jitter_m"]<0):
                    raise ValueError("invalid obstacle relocation")
    topics={topic for topic,row in world.sensors.items() if row["frame"].split("::")[0]==spec["robot"]}
    if (type(spec["qos"]) is not dict or not topics.issubset(spec["qos"])
            or not all(type(spec["qos"][t]) is str and spec["qos"][t] for t in topics)):
        raise ValueError("missing bridge QoS profiles")


def output(file: Path,document: Record) -> None:
    """Commit one full report only after it can be JSON serialized."""
    with tempfile.NamedTemporaryFile(mode="w",dir=file.parent,delete=False) as stream:
        temp=Path(stream.name)
        try:
            json.dump(document,stream,allow_nan=False)
            stream.close()
            temp.replace(file)
        finally:
            temp.unlink(missing_ok=True)


def audit(world: World, spec: Record, trace: Record) -> Record:
    """Audit independently against the declared frame, publication and clock scheduling contract."""
    entries=trace["steps"]
    if type(entries) is not list:
        raise ValueError("invalid trace")
    expected_steps=spec["steps"]
    lookup={}
    for row in entries:
        tick=row["step"]
        if type(tick) is not int or not 0<=tick<expected_steps or tick in lookup:
            raise ValueError("duplicate or out-of-range trace step")
        lookup[tick]=row
    name=spec["robot"]
    topics={t:r for t,r in world.sensors.items() if r["frame"].split("::")[0]==name}
    offsets={label:relative(world.frames[name],world.frames[row["frame"]]) for label,row in topics.items()}
    first={"clock":None,"topic":None,"qos":None,"transform":None}
    origin=epoch=0
    for step in range(expected_steps):
        if step in spec["reset_steps"]:
            origin=step
            epoch+=1
        row=lookup.get(step)
        local=step-origin
        expected={t for t,e in topics.items() if local%e["period_steps"]==0}
        if row is None:
            if first["clock"] is None: first["clock"]=step
            if first["topic"] is None: first["topic"]=step
            continue
        if (row.get("epoch")!=epoch or row.get("time_ns")!=local*round(world.dt*1e9)) and first["clock"] is None:
            first["clock"]=step
        messages=row["messages"]
        if type(messages) is not list or not all(type(m["topic"]) is str for m in messages):
            raise ValueError("invalid observed topic list")
        titles=[message["topic"] for message in messages]
        if (set(titles)!=expected or len(titles)!=len(expected)) and first["topic"] is None:
            first["topic"]=step
        base=row["base"]
        if type(base) is not list or len(base)!=4 or not all(map(finite,base)):
            raise ValueError("invalid recorded base pose")
        for message in messages:
            title=message["topic"]
            if title not in topics: continue
            if message.get("qos")!=spec["qos"][title] and first["qos"] is None:
                first["qos"]=step
            p=message.get("pose")
            goal=transform(base,offsets[title])
            if (message.get("frame")!=topics[title]["frame"] or type(p) is not list or len(p)!=4
                    or not all(map(finite,p)) or max(abs(p[i]-goal[i]) for i in range(3))>1e-7
                    or abs(angle(p[3]-goal[3]))>1e-7) and first["transform"] is None:
                first["transform"]=step
    return {"status":"ok" if all(v is None for v in first.values()) else "fault","first":first}


def main() -> int:
    """Run one regression command in the documented SDF subset."""
    cli=argparse.ArgumentParser()
    modes=cli.add_subparsers(dest="mode",required=True)
    for mode in ("inspect","run","audit"):
        cmd=modes.add_parser(mode)
        cmd.add_argument("--world",type=Path,required=True)
        cmd.add_argument("--output",type=Path,required=True)
        if mode!="inspect": cmd.add_argument("--spec",type=Path,required=True)
        if mode=="audit": cmd.add_argument("--input",type=Path,required=True)
    args=cli.parse_args()
    try:
        world=read_world(args.world)
        if args.mode=="inspect":
            report=world.inspect()
        else:
            spec=json.loads(args.spec.read_text())
            check_spec(spec,world)
            if args.mode=="run":
                from .native import run
                report=run(world,spec)
            else:
                report=audit(world,spec,json.loads(args.input.read_text()))
        output(args.output,report)
    except (ValueError,TypeError,OverflowError,KeyError,OSError,ET.ParseError) as error:
        print(f"sim regression: {error}",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    sys.exit(main())
