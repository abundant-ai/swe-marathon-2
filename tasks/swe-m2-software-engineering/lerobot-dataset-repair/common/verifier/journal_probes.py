"""Build native encoder truth from authored causal queues, without the candidate solver."""

from copy import deepcopy
import json
import math
from pathlib import Path
import shutil

import mujoco
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

START = 4_000_000
COUNT = 20
STRIDE = 6

def clock_factory(period,reboot):
    cfg = {"policy-host":(1.00042,100_000,480,1000),
           "teleop-handset":(.99923,310_000,-240,850),
           "device-A":(.99968,36_000,110,410),
           "device-B":(1.00073,7_000,-125,410)}
    birth = {name:START-120_000 for name in cfg}
    birth["device-B"] = START+reboot*period-4_000
    def stamp(source, master):
        scale,base,_,_ = cfg[source]
        return round(base+(master-birth[source])/scale)
    anchors={}
    for source, (_,_,bias,error) in cfg.items():
        pairs=[]
        low = birth[source]+2_000
        for master, extra in ((low,0),(START+2_000_000,65)):
            pairs.append({"local_us":stamp(source,master),"ref_center_us":master+bias+extra,"error_us":error})
        anchors[source]=pairs
    return stamp,anchors



def make_journal(model, seed, reordered):
    step_us=int(round(model.opt.timestep*1e6))
    period=step_us*STRIDE
    reboot=4 if reordered else 12
    stamp,sync=clock_factory(period,reboot)
    spans = ([("A",0,"policy",0,4),("B",0,"policy",4,8),("B",1,"operator",8,10),
              ("B",2,"policy",10,20)] if reordered else
             [("A",0,"policy",0,8),("A",1,"operator",8,10),("A",2,"policy",10,12),
              ("B",0,"policy",12,20)])
    neutral=np.array([.16,-.40,.46,.22,-.14,.48])
    episode=seed%475+10
    body={"episode_index":episode,"origin_us":START,"clock_sync":sync,
          "initial":{"joints":[model.actuator(i).name for i in range(6)],"position_rad":neutral.tolist(),
                     "velocity_rad_s":[0.]*6,"held_target_rad":neutral.tolist()},
          "authority":[{"boot":boot,"generation":gen,"controller":owner,"start":a,"end":b}
                       for boot,gen,owner,a,b in spans],
          "chunk_replies":[],"teleop_updates":[],"accepted":[],"encoders":{}}
    rand=np.random.default_rng(seed)
    def targets(length):
        vectors=neutral+rand.uniform(-.017,.017,(length,6))
        for i,vector in enumerate(vectors):
            vector[(i+seed)%4]+=.23*(-1.)**i
            vector[3]+=.065*(-1.)**(i//2)
        return vectors
    stash={}
    def emit(event_id,boot,gen,frame,shift,cursor,delay,data,operator=False):
        clock="teleop-handset" if operator else "policy-host"
        shard="teleop_updates" if operator else "chunk_replies"
        body[shard].append({"event_id":event_id,"snapshot_boot":boot,"snapshot_generation":gen,
                            "snapshot_cursor":cursor,"reported_delay":delay,"clock":clock,
                            "local_us":stamp(clock,START+period*frame+shift),"positions":data.tolist()})
        stash[event_id]=data

    a0,a1,a2,b0,b1,handset,rearm=[targets(13) for _ in range(7)]
    a1[1]=a0[2]
    # These alternatives are identical in physics, but only valid queue timing can identify the producer.
    a2[2]=a1[4]
    b1[2]=b0[2]
    emit("prefix","A",0,0,-period//2,0,0,a0)
    emit("update","A",0,2,-30 if reordered else -180,0,1,a1)
    plan=[("prefix",0),("prefix",1),("update",1),("update",2)]
    if reordered:
        emit("new-boot","B",0,4,-period//2,0,0,b0)
        emit("update-B","B",0,6,-340,0,4,b1)
        emit("late-retired","A",0,7,-period//2,0,10,targets(13))
        emit("rearm","B",2,10,-period//2,0,0,rearm)
        emit("operator","B",1,8,-period//2,0,0,handset[:1],operator=True)
        plan.extend([("new-boot",0),("new-boot",1),("update-B",2),("update-B",3),
                     ("operator",0),("operator",0)])
        plan.extend(("rearm",i) for i in range(10))
    else:
        emit("later-overlap","A",0,5,-70,3,4,a2)
        emit("rearm","A",2,10,-period//2,0,0,rearm)
        emit("new-boot","B",0,12,-period//2,0,0,b0)
        emit("late-retired","A",0,13,-period//2,0,10,targets(13))
        emit("operator","A",1,8,-period//2,0,0,handset[:1],operator=True)
        plan.extend([("update",3),("later-overlap",2),("later-overlap",3),("later-overlap",4),
                     ("operator",0),("operator",0),("rearm",0),("rearm",1)])
        plan.extend(("new-boot",i) for i in range(8))

    data=mujoco.MjData(model)
    data.qpos[:]=neutral
    data.ctrl[:]=neutral
    mujoco.mj_forward(model,data)
    expected=[]
    for frame,(label,k) in enumerate(plan):
        boot="A" if frame<reboot else "B"
        index=(frame*17)%COUNT+episode*173
        ctrl="operator" if label=="operator" else "policy"
        ticket=label if ctrl=="operator" else f"{label}:{k}"
        substep=(2,4,1,3,2)[frame%5]
        counter=frame if boot=="A" else frame-reboot
        when=START+frame*period+substep*step_us-(150 if frame%4==2 else step_us//2)
        clock="device-"+boot
        body["accepted"].append({"clock":clock,"local_us":stamp(clock,when),"boot":boot,"counter":counter})
        vector=stash[label][k]
        for sub in range(STRIDE):
            if sub==substep:
                data.ctrl[:]=vector
            mujoco.mj_step(model,data)
        if frame in (1,4,7,9,11,14,17,19):
            body["encoders"][str(frame)]={"position_rad":data.qpos.tolist(),
                                         "velocity_rad_s":data.qvel.tolist() if frame%2 else None}
        row={"index":index,"device_boot":boot,"device_counter":counter,"feasible_dispatch_substeps":[substep]}
        if frame==5 and not reordered:
            row.update(decision="ambiguous",receipt=None,controller=None,action=None,
                       feasible_receipts=["later-overlap:2","update:4"])
        else:
            row.update(decision="confirmed",receipt=ticket,controller=ctrl,action=vector.tolist(),
                       feasible_receipts=[ticket])
        expected.append(({"index":index,"episode_index":episode,"frame_index":frame,
                          "action":[0.]*6},row))
    assert len(expected)==COUNT
    body["accepted"].append(body["accepted"][5].copy())
    rand.shuffle(body["accepted"])
    return body,expected


def case(run,root,name,seed,reordered,variant=None):
    root.mkdir(mode=0o755)
    model_name="so101-headless.xml"
    model_path=root/model_name
    shutil.copyfile(Path(__file__).with_name(model_name),model_path)
    model=mujoco.MjModel.from_xml_path(str(model_path))
    body, records=make_journal(model,seed,reordered)
    episodes=[body]
    if name=="mixed_global_shard":
        other,more=make_journal(model,seed+837,not reordered)
        episodes.append(other)
        records.extend(more)
    dataset, ledger = root/"frames.parquet",root/"journal.json"
    result_dir=root/"result"
    result_dir.mkdir(mode=0o777)
    result_dir.chmod(0o777)
    result=result_dir/"audit.parquet"
    if variant=="bad_duplicate":
        duplicate=deepcopy(body["accepted"][0])
        duplicate["local_us"]+=1
        body["accepted"].append(duplicate)
        sentinel=b"old report retained\n"
        result.write_bytes(sentinel)
    elif variant=="bad_readback":
        body["encoders"]["7"]["position_rad"][0]+=.25
        for _,row in records:
            row.update(decision="inconsistent",receipt=None,controller=None,action=None,feasible_receipts=[],
                       feasible_dispatch_substeps=[])
    frame_rows,expected=map(list,zip(*records,strict=True))
    pq.write_table(pa.Table.from_pylist(list(reversed(frame_rows))),dataset)
    ledger.write_text(json.dumps({"model":model_name,"steps_per_frame":STRIDE,
                                  "position_tolerance_rad":2e-5,"velocity_tolerance_rad_s":2.5e-4,
                                  "episodes":episodes}),encoding="utf-8")
    ret=run("reconstruct-actions","--dataset",dataset,"--journal",ledger,"--output",result)
    if variant=="bad_duplicate":
        return ret not in (0,124) and result.read_bytes()==sentinel
    if ret!=0 or not result.is_file():
        return False
    try:
        actual=pq.read_table(result)
    except pa.ArrowException:
        return False
    schema=pa.schema([("index",pa.int64()),("decision",pa.string()),("action",pa.list_(pa.float64())),
                      ("receipt",pa.string()),("controller",pa.string()),("feasible_receipts",pa.list_(pa.string())),
                      ("device_boot",pa.string()),("device_counter",pa.int64()),
                      ("feasible_dispatch_substeps",pa.list_(pa.int64()))])
    return actual.schema==schema and actual.to_pylist()==sorted(expected,key=lambda row:row["index"])


def journal_cases(run, root):
    probes=[("recover_overlapping_chunks",260731,False,None),
            ("reboot_before_takeover",614536,True,None),
            ("mixed_global_shard",399118,True,None),
            ("inconsistent_physical_readback",370021,False,"bad_readback"),
            ("reject_conflicting_device_acceptance",676913,True,"bad_duplicate")]
    return {name:case(run,root/("journal-"+name),name,seed,reordered,variant)
            for name,seed,reordered,variant in probes}
