"""Validate boot-scoped actuator journals and publish a canonical provenance audit."""

from pathlib import Path
import re
from tempfile import NamedTemporaryFile

import mujoco
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .actions import ordered_target
from .dataset import natural, number, read_json
from .queue_recovery import physical_histories


def token(value):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}",value):
        raise ValueError("invalid journal identity")
    return value


def integer(value):
    if not natural(value) or value>=2**53:
        raise ValueError("expected a nonnegative integer timestamp or counter")
    return value


def array(value,maximum):
    if not isinstance(value,list) or len(value)>maximum:
        raise ValueError("journal array exceeds its declared capacity")
    return value


def controls(values,low,high):
    if not isinstance(values,list) or len(values)!=6 or not all(
            number(v) and a<=v<=b for v,a,b in zip(values,low,high,strict=True)):
        raise ValueError("target must contain six finite commissioned joint values")


def clock_records(clocks):
    if not isinstance(clocks,dict) or not 1<=len(clocks)<=32:
        raise ValueError("expected named clock synchronization records")
    for name,pair in clocks.items():
        token(name)
        a,b = array(pair,2)
        for anchor in pair:
            integer(anchor["local_us"])
            integer(anchor["ref_center_us"])
            uncertainty=integer(anchor["error_us"])
            if uncertainty>30000:
                raise ValueError("synchronization anchors are too imprecise")
        if b["local_us"]<=a["local_us"] or b["ref_center_us"]-b["error_us"]<=a["ref_center_us"]+a["error_us"]:
            raise ValueError("clock anchors do not define a positive affine clock")
    return clocks


def stamp(record,clocks):
    clock=token(record["clock"])
    local=integer(record["local_us"])
    a,b=clocks[clock]
    if not a["local_us"]<=local<=b["local_us"]:
        raise ValueError("local timestamp outside synchronization anchors")


def authority_frames(spans,frame_count):
    out=[]
    eras=set()
    seen_boots=set()
    previous=None
    for span in array(spans,100):
        boot=token(span["boot"])
        generation=integer(span["generation"])
        start,end=integer(span["start"]),integer(span["end"])
        key=boot,generation
        if span["controller"] not in ("policy","operator") or key in eras or start!=len(out) or not start<end<=frame_count:
            raise ValueError("authority epochs must partition the source frames")
        if previous is not None and previous[0]!=boot and boot in seen_boots:
            raise ValueError("a retired controller boot cannot resume")
        if previous is not None and previous[0]==boot and generation<=previous[1]:
            raise ValueError("controller generation must advance")
        previous=key
        seen_boots.add(boot)
        eras.add(key)
        out.extend([span]*(end-start))
    if len(out)!=frame_count:
        raise ValueError("authority journal omits source frames")
    return out


def accepts_by_frame(records,authority,clocks):
    unique={}
    for row in array(records,300):
        key = token(row["boot"]),integer(row["counter"])
        stamp(row,clocks)
        if key in unique and row!=unique[key]:
            raise ValueError("conflicting accepted transaction")
        unique[key]=row
    counters={}
    prior={}
    clock_boots={}
    result=[]
    for span in authority:
        boot=span["boot"]
        ordinal=counters.get(boot,0)
        receipt=unique.pop((boot,ordinal))
        key=receipt["clock"],receipt["local_us"]
        if clock_boots.setdefault(key[0],boot)!=boot:
            raise ValueError("a reboot requires a distinct device clock")
        if boot in prior and (key[0]!=prior[boot][0] or key[1]<=prior[boot][1]):
            raise ValueError("accepted transactions must advance in one clock per boot")
        prior[boot]=key
        counters[boot]=ordinal+1
        result.append(receipt)
    if unique:
        raise ValueError("accepted transaction outside source coverage")
    return result


def queue_events(raw,clocks,low,high):
    seen=set()
    streams={}
    for key,owner in (("chunk_replies","policy"),("teleop_updates","operator")):
        last={}
        result=[]
        for row in array(raw[key],24):
            ident=token(row["event_id"])
            if ident in seen:
                raise ValueError("duplicate scheduler event ID")
            seen.add(ident)
            stamp(row,clocks)
            clock,local=row["clock"],row["local_us"]
            if clock in last and local<last[clock]:
                raise ValueError("queue stream lost monotonic event order")
            last[clock]=local
            token(row["snapshot_boot"])
            for field in ("snapshot_generation","snapshot_cursor","reported_delay"):
                integer(row[field])
            if owner=="operator" and (row["snapshot_cursor"] or row["reported_delay"]):
                raise ValueError("handset updates have zero cursor and delay")
            targets=array(row["positions"],120)
            if not targets or (owner=="operator" and len(targets)!=1):
                raise ValueError("missing policy chunk or handset target")
            for target in targets:
                controls(target,low,high)
            result.append(row|{"source":owner})
        streams[key]=result
    if not seen:
        raise ValueError("missing queue events")
    return streams


def encoder_records(records,count):
    if not isinstance(records,dict):
        raise ValueError("expected encoder records indexed by frame")
    output={}
    for text,row in records.items():
        frame=integer(int(text))
        if frame>=count or str(frame)!=text:
            raise ValueError("invalid encoder frame index")
        channels=[]
        for field in ("position_rad","velocity_rad_s"):
            items=row[field]
            items=[None]*6 if items is None else items
            if not isinstance(items,list) or len(items)!=6 or any(v is not None and not number(v) for v in items):
                raise ValueError("invalid encoder sample")
            channels.append(items)
        output[frame]=dict(zip(("position_rad","velocity_rad_s"),channels,strict=True))
    return output


def prepare(raw,count,stride,substep,names,limits):
    origin=integer(raw["origin_us"])
    initial=raw["initial"]
    for field in ("position_rad","velocity_rad_s","held_target_rad"):
        values=initial[field]
        if not isinstance(values,list) or not all(number(v) for v in values):
            raise ValueError("initial six-axis state must be finite")
        ordered=ordered_target(values,initial["joints"],names)
        if field=="held_target_rad":
            controls(ordered,limits[:,0],limits[:,1])
    clocks=clock_records(raw["clock_sync"])
    authority=authority_frames(raw["authority"],count)
    accepted=accepts_by_frame(raw["accepted"],authority,clocks)
    events=queue_events(raw,clocks,limits[:,0],limits[:,1])
    samples=encoder_records(raw["encoders"],count)
    return raw|events|{"origin_us":origin,"frame_count":count,"frame_period_us":stride*substep,
                      "steps_per_frame":stride,"substep_us":substep,"frame_authority":authority,
                      "ordered_accepts":accepted,"encoders":samples}


def frame_ids(path):
    table=pq.read_table(path,columns=["index","episode_index","frame_index"])
    if not all(pa.types.is_integer(field.type) for field in table.schema):
        raise ValueError("native frame identities must be integers")
    output={}
    global_index=set()
    for row in table.to_pylist():
        idx,episode,frame=(row[key] for key in ("index","episode_index","frame_index"))
        if (type(idx) is not int or idx in global_index or not -(2**63)<=idx<2**63
                or not natural(episode) or not natural(frame) or frame in output.setdefault(episode,{})):
            raise ValueError("duplicate or invalid source frame identity")
        global_index.add(idx)
        output[episode][frame]=idx
    if not output or any(len(frames)>100 or set(frames)!=set(range(len(frames))) for frames in output.values()):
        raise ValueError("source frame order must begin at zero and be contiguous")
    return output


def audit_rows(indices,receipts,outcomes):
    for frame,(possible,receipt) in enumerate(zip(outcomes,receipts,strict=True)):
        labels={label:(controller,target) for label,controller,target,_ in possible}
        chosen=next(iter(labels)) if len(labels)==1 else None
        yield {"index":indices[frame],
               "decision":"confirmed" if chosen else "ambiguous" if labels else "inconsistent",
               "action":labels[chosen][1] if chosen else None,
               "receipt":chosen,"controller":labels[chosen][0] if chosen else None,
               "feasible_receipts":sorted(labels),"device_boot":receipt["boot"],"device_counter":receipt["counter"],
               "feasible_dispatch_substeps":sorted({item[-1] for item in possible})}


def reconstruct_actions(dataset:Path,journal:Path,output:Path):
    packet=read_json(journal)
    model_path=Path(packet["model"])
    if model_path.is_absolute() or ".." in model_path.parts:
        raise ValueError("expected a commissioned model path relative to the journal")
    model_path=journal.parent/model_path
    if output.resolve() in (dataset.resolve(),journal.resolve(),model_path.resolve()):
        raise ValueError("output would overwrite an input")
    model=mujoco.MjModel.from_xml_path(str(model_path))
    names=[model.actuator(i).name for i in range(model.nu)]
    if (model.nq!=6 or model.nv!=6 or model.nu!=6 or len(set(names))!=6 or not all(names)
            or not np.all(model.actuator_trntype==mujoco.mjtTrn.mjTRN_JOINT)
            or not np.array_equal(model.actuator_trnid[:,0],range(6))
            or not np.all(model.jnt_type==mujoco.mjtJoint.mjJNT_HINGE)):
        raise ValueError("expected six ordered SO-101 joint servos")
    substep=round(model.opt.timestep*1e6)
    stride=integer(packet["steps_per_frame"])
    if not 1<=stride<=20 or substep<=0:
        raise ValueError("invalid drive time step")
    tolerance=packet["position_tolerance_rad"],packet["velocity_tolerance_rad_s"]
    if not all(number(v) and v>=0. for v in tolerance):
        raise ValueError("invalid encoder tolerances")
    dataset_frames=frame_ids(dataset)
    rows=[]
    for raw in array(packet["episodes"],200):
        episode=integer(raw["episode_index"])
        frames=dataset_frames.pop(episode)
        validated=prepare(raw,len(frames),stride,substep,names,model.actuator_ctrlrange)
        outcomes=physical_histories(model,names,validated,tolerance)
        rows.extend(audit_rows(frames,validated["ordered_accepts"],outcomes))
    if dataset_frames:
        raise ValueError("journal episodes do not cover the source table")
    schema=pa.schema([("index",pa.int64()),("decision",pa.string()),("action",pa.list_(pa.float64())),
                      ("receipt",pa.string()),("controller",pa.string()),("feasible_receipts",pa.list_(pa.string())),
                      ("device_boot",pa.string()),("device_counter",pa.int64()),
                      ("feasible_dispatch_substeps",pa.list_(pa.int64()))])
    result=pa.Table.from_pylist(sorted(rows,key=lambda row:row["index"]),schema=schema)
    with NamedTemporaryFile(dir=output.parent,suffix=".parquet",delete=False) as tmp:
        temporary=Path(tmp.name)
    try:
        pq.write_table(result,temporary)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
