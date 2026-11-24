"""Maintain causal RTC queue replay and shared clock evidence across physical branches."""

import mujoco

from .actions import INTEGRATION, native_clone, restore, witnessed


def dot(c, vertex):
    return c[0]*vertex[0]+c[1]*vertex[1]


def clip(vertices, coeff, upper):
    boundary = []
    for a,b in zip(vertices,vertices[1:]+vertices[:1],strict=True):
        va,vb = dot(coeff,a)-upper,dot(coeff,b)-upper
        if va <= 1e-9:
            boundary.append(a)
        if (va <= 1e-9)!=(vb <= 1e-9):
            alpha=va/(va-vb)
            boundary.append(tuple(x+alpha*(y-x) for x,y in zip(a,b,strict=True)))
    return boundary


def clock_parts(sync, local):
    first, last = sync
    ratio = (local-first["local_us"])/(last["local_us"]-first["local_us"])
    center = (1-ratio)*first["ref_center_us"]+ratio*last["ref_center_us"]
    return (1-ratio,ratio),center


def initial_bounds(clocks):
    return {name:[(x,y) for x,y in ((-s[0]["error_us"],-s[1]["error_us"]),
                                      (s[0]["error_us"],-s[1]["error_us"]),
                                      (s[0]["error_us"],s[1]["error_us"]),
                                      (-s[0]["error_us"],s[1]["error_us"]))]
            for name,s in clocks.items()}


def extend(bounds, journal, row, end, period):
    name = row["clock"]
    coeff, center = clock_parts(journal["clock_sync"][name],row["local_us"])
    polygon = clip(bounds[name],coeff,end-center)
    polygon = clip(polygon,tuple(-v for v in coeff),center-(end-period+1))
    return (bounds|{name:polygon}) if polygon else None


def candidate_latches(journal,bounds,row,times,period):
    for tick,end in times:
        revised=extend(bounds,journal,row,end,period)
        if revised is not None:
            yield tick,revised


def perform(journal, installed):
    """Replay the ordered replacement queue at a given feasible set of merge cuts."""
    live_key = None
    cursor,offset = 0,0
    active = None
    writes=[]
    for f in range(journal["frame_count"]):
        auth=journal["frame_authority"][f]
        key=auth["boot"], auth["generation"]
        if key!=live_key:
            live_key = key
            active = None
            cursor = 0
        for row in installed.get(f,()):
            if key != (row["snapshot_boot"],row["snapshot_generation"]) or row["source"]!=auth["controller"]:
                continue
            active = row
            if row["source"]=="policy":
                lag=cursor-row["snapshot_cursor"]
                if lag<0:
                    return None
                offset=min(row["reported_delay"],lag)
            else:
                offset=0
        if active is None:
            return None
        if auth["controller"]=="policy":
            if active["source"]!="policy" or offset>=len(active["positions"]):
                return None
            command=(f"{active['event_id']}:{offset}","policy",tuple(active["positions"][offset]))
            cursor+=1
            offset+=1
        else:
            if active["source"]!="operator":
                return None
            command=(active["event_id"],"operator",tuple(active["positions"][0]))
        writes.append(command)
    return tuple(writes)


def schedule_options(journal):
    length=journal["frame_period_us"]
    zero=initial_bounds(journal["clock_sync"])
    times=[(f,journal["origin_us"]+f*length) for f in range(journal["frame_count"])]
    events=journal["chunk_replies"]+journal["teleop_updates"]
    assignments=[({},zero,{})]
    for row in events:
        updated=[]
        for schedule,bounds,prior_by_clock in assignments:
            for f,narrowed in candidate_latches(journal,bounds,row,times,length):
                if f<prior_by_clock.get(row["clock"],-1):
                    continue
                candidate=schedule|{f:(*schedule.get(f,()),row)}
                updated.append((candidate,narrowed,prior_by_clock|{row["clock"]:f}))
        assignments=updated
    possible=[]
    for schedule,bounds,_ in assignments:
        writes=perform(journal,schedule)
        if writes is not None:
            possible.append((writes,bounds))
    return possible


def signature(snapshot, clocks):
    return snapshot.tobytes(), tuple((name,tuple(vertices)) for name,vertices in clocks.items())


def update_layer(layer, snapshot, clocks, former, step):
    key = signature(snapshot,clocks)
    existing = layer.get(key)
    if existing is None:
        layer[key] = (snapshot,clocks,(*former,{step}))
        return
    history = existing[2]
    for left,right in zip(history[:-1],former,strict=True):
        left.update(right)
    history[-1].add(step)


def execute(model, data, snapshot, values, substep, stride):
    mujoco.mj_setState(model,data,snapshot,INTEGRATION)
    for step in range(stride):
        if step==substep:
            data.ctrl[:]=values
        mujoco.mj_step(model,data)
    return native_clone(model,data)


def physical_histories(model, names, journal, bounds):
    data = restore(model,journal["initial"],names)
    initial = native_clone(model,data)
    outcomes = [set() for _ in range(journal["frame_count"])]
    substep_us = journal["substep_us"]
    for writes, clocks in schedule_options(journal):
        layer = [(initial,clocks,())]
        for frame,receipt in enumerate(journal["ordered_accepts"]):
            start = journal["origin_us"]+frame*journal["frame_period_us"]
            times = [(j,start+j*substep_us) for j in range(journal["steps_per_frame"])]
            sensor = journal["encoders"].get(frame)
            label,controller,target = writes[frame]
            updated = {}
            for snapshot,clock_state,former in layer:
                for j,narrowed in candidate_latches(journal,clock_state,receipt,times,substep_us):
                    state = execute(model,data,snapshot,target,j,journal["steps_per_frame"])
                    if sensor is None or witnessed(data,sensor,*bounds):
                        evidence = (label,controller,target,j)
                        # Each causal prefix is independent until an identical physical and clock state joins it.
                        update_layer(updated,state,narrowed,tuple(set(row) for row in former),evidence)
            if not updated:
                layer = []
                break
            layer = updated.values()
        for _,_,history in layer:
            for possible,accepted in zip(outcomes,history,strict=True):
                possible.update(accepted)
    return outcomes
