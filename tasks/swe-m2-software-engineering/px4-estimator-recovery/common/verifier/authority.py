"""Private independently scheduled estimator handover and containment missions."""

from hashlib import blake2s
from math import dist,hypot
from pathlib import Path
import json

from flight import local
from transport import Driver,Record,require


CASES_V2=(
    {"name":"silent-primary-position-innovation","kind":"jump","switches":[(2,0),(16,1),(29,0)]},
    {"name":"boot-epoch-requires-independent-anchor","kind":"boot","switches":[(2,0),(13,1),(29,0)]},
    {"name":"duplicate-backup-capture-cannot-qualify","kind":"duplicate","switches":[(2,0),(18,None),(24,0)],
     "brake":[(18,24)]},
    {"name":"broken-inertial-chain-and-anchored-recovery","kind":"broken","switches":[(2,0),(15,None),(43,0)],
     "brake":[(15,17)],"hold":[(17,43)]},
    {"name":"loss-during-high-velocity-stays-in-envelope","kind":"abort","switches":[(2,0)],"abort":True},
    {"name":"intermittent-health-does-not-flap-authority","kind":"flap","switches":[(2,0),(15,1),(28,0)]},
    {"name":"uncalibrated-backup-waits-for-anchor-and-dwell","kind":"unmapped","switches":[(2,0),(14,None),(18,1),(31,0)],
     "brake":[(14,18)]},
    {"name":"velocity-disagreement-with-continuous-position","kind":"velocity",
     "switches":[(2,0),(19,1),(32,0)]},
    {"name":"three-sources-under-overlapping-faults","kind":"cascade",
     "switches":[(2,0),(15,1),(22,2),(35,1),(51,0)]},
)


def within(tick: int, intervals) -> bool:
    """Find whether an externally authored fault covers the current tick."""
    return any(a<=tick<b for a,b in intervals)


def readings(case: Record,start: tuple[int,...], tick: int,p: list[float],v: list[float],
             sources: list[str],reset_at: int | None) -> Record:
    """Expose independent estimator state machines with known planted physical faults."""
    kind=case["kind"]
    now=1_000_000+tick*100_000
    answer={}
    for index, name in enumerate(sources):
        bias=([0.0,0.0,0.0],[0.78,-0.37,0.62],[-0.49,0.57,0.19])[index]
        delta=[0.0,0.0,0.0]
        generation=start[index]
        counters=[251 if index==0 else 255, 255]
        anchor=tick<3 and not(index==1 and kind=="unmapped")
        health=True
        capture=now
        if index==1 and tick>=8:
            shift=[0.37,-0.22,0.0]
            bias=[a+b for a,b in zip(bias,shift)]
            delta[:2]=shift[:2]
            counters[0]=0
        if index==1 and tick>=18:
            bias[2]+=0.56
            counters[1]=0
            delta[2]=0.56
        if kind=="jump" and index==0 and 16<=tick<23:
            bias[2]-=0.91
            bias[0]+=0.32
        if kind=="boot" and index==0 and tick>=13:
            generation+=1
            bias=[-0.63,0.83,-0.44]
            counters=[111,79]
            anchor=27<=tick<32
            if tick==25:
                generation-=1
                anchor=True
                bias=[2.0,-1.0,1.0]
        if kind=="duplicate":
            if 18<=tick<22:
                if index==0:
                    answer[name]=None
                    continue
                capture=1_000_000+17*100_000
            if 22<=tick<28:
                anchor=True
        if kind=="broken":
            if 15<=tick<41:
                answer[name]=None
                continue
            if 41<=tick<46:
                anchor=True
        if kind=="abort" and reset_at is not None:
            answer[name]=None
            continue
        if kind=="flap" and index==0 and (15<=tick<17 or tick==25):
            health=False
        if kind=="cascade":
            if index==0 and 15<=tick<49:
                health=False
            if index==1 and 22<=tick<29:
                bias=[a+b for a,b in zip(bias,[0.035,-0.035,0.035],strict=True)]
        if kind=="unmapped":
            if index==0 and 14<=tick<24:
                health=False
            if index==1 and 16<=tick<20:
                anchor=True
        observed=local(now,p,v,bias,counters,delta)
        observed["timestamp_sample"]=capture
        if kind=="velocity" and index==0 and 19<=tick<26:
            observed["velocity"]=[a+0.043 for a in v]
        if anchor:
            observed["anchor"]=p.copy()
        answer[name]={"epoch":generation,"healthy":health,"local":observed}
    return answer


def experiment(app: Path,root: Path,case: Record) -> Record:
    """Observe independent NED motion, source decisions, braking and actual mission outcome."""
    count=3 if case["kind"]=="cascade" else 2
    ids=[blake2s(f"{case['name']}:{i}".encode(),digest_size=4).hexdigest() for i in range(count)]
    dt=0.1
    targets=[[0.61,-0.43,-2.29],[1.48,0.16,-2.78]]
    lower=[-0.33,-0.73,-3.1]
    upper=[1.81,0.48,-1.59]
    if case["kind"]=="abort":
        targets=[[1.44,-0.22,-2.24],[1.56,0.05,-2.61]]
        upper[0]=1.63
    cfg={"dt":dt,"waypoints":targets,"max_accel":0.85,"position_tolerance":0.096,
         "speed_tolerance":0.13,"dwell_ticks":3,"deadline":117 if case.get("abort") else 194,"max_age_us":20_000,
         "max_inertial_ticks":6,"supervisor":{"sources":ids,"qualification_samples":3,"switch_delay_ticks":13,
           "max_position_innovation_m":0.045,"max_velocity_innovation_mps":0.06,"min_ned":lower,"max_ned":upper}}
    spec=root/"spec.json"
    spec.write_text(json.dumps(cfg))
    scratch=root/"candidate"
    scratch.mkdir()
    scratch.chmod(0o777)
    process=Driver(app,spec,scratch)
    p=[0.0,0.0,-1.85]
    v=[0.0]*3
    acceleration=[0.0]*3
    goal_index=dwell=0
    peak=0.0
    mode_counts={"hold":0,"dead_reckon":0,"track":0}
    last_chosen=None
    seen_switches=[]
    triggered=None
    trigger_speed=None
    try:
        for tick in range(cfg["deadline"]+1):
            if case["kind"]=="abort" and triggered is None and p[0]>0.59 and v[0]>0.40:
                triggered,trigger_speed=tick,v[0]
            reports=readings(case,(10,37,72),tick,p,v,ids,triggered)
            imu={"from_tick":tick-1,"accel":acceleration}
            if case["kind"]=="broken" and tick==17:
                imu["from_tick"]=15
            packet={"tick":tick,"now_us":1_001_700+tick*100_000,"reports":reports,"imu":imu}
            reply=process.exchange(packet)
            u,estimate=reply.get("acceleration"),reply.get("estimate")
            mode,selected=reply.get("mode"),reply.get("source")
            require(type(u) is list and len(u)==3 and all(type(a) in (int,float) and abs(a)<=cfg["max_accel"]+1e-9 for a in u),
                    f"out-of-envelope command at tick {tick}")
            expected=None
            for changed,n in case["switches"]:
                if changed<=tick: expected=n
            if triggered is not None:
                expected=None
            want_id=None if expected is None else ids[expected]
            if want_id!=last_chosen:
                seen_switches.append([tick,expected])
                last_chosen=want_id
            if expected is not None and dist(p,targets[goal_index])<=cfg["position_tolerance"]+1e-10 and hypot(*v)<=cfg["speed_tolerance"]+1e-10:
                dwell+=1
                if dwell==cfg["dwell_ticks"]:
                    dwell=0
                    goal_index+=1
            else:
                dwell=0
            require(reply.get("waypoint")==goal_index,"physical waypoint dwell was not respected")
            if goal_index==len(targets):
                require(not case.get("abort") and mode=="complete" and u==[0]*3 and selected==want_id,
                        "physical final dwell did not complete")
                return {"terminal":mode,"tick":tick,"source_changes":seen_switches,
                        "mode_counts":mode_counts,"peak_pose_error_m":peak}
            if tick==cfg["deadline"]:
                require(bool(case.get("abort")) and mode=="abort" and selected is None and u==[0]*3,
                        "could not safely finish or abort")
                require(triggered is not None and trigger_speed>0.40 and mode_counts["dead_reckon"]==cfg["max_inertial_ticks"],
                        "the intended moving blackout or bounded braking was not exercised")
                return {"terminal":mode,"tick":tick,"source_changes":seen_switches,
                        "mode_counts":mode_counts,"trigger_velocity_mps":trigger_speed,"final_pose_ned":p}
            require("source" in reply and selected==want_id,
                    f"incorrect estimator authority at tick {tick}; expected {expected!r}")
            if expected is not None:
                desired="track"
            else:
                brake=(triggered is not None and tick<triggered+cfg["max_inertial_ticks"]
                       or within(tick,case.get("brake",[])))
                desired="dead_reckon" if brake else "hold"
            require(mode==desired,f"wrong projected authority mode at tick {tick}; expected {desired}, observed {mode}")
            mode_counts[mode]+=1
            if desired=="hold":
                require(u==[0]*3 and estimate is None,"neutral hold retained an unsupported warm estimate")
            else:
                require(type(estimate) is list and len(estimate)==3 and dist(p,estimate)<1e-8,
                        "source switch introduced a physical pose jump")
                peak=max(peak,dist(p,estimate))
            if desired=="dead_reckon":
                target=[-max(-cfg["max_accel"],min(cfg["max_accel"],speed/dt)) for speed in v]
                require(dist(u,target)<1e-8,"loss of authority did not apply the commissioned position-independent braking")
            acceleration=[u_i-0.22*v_i for u_i,v_i in zip(u,v,strict=True)]
            future=[]
            for x,speed,a,lo,hi in zip(p,v,acceleration,lower,upper,strict=True):
                endpoint=x+dt*speed+0.5*dt**2*a
                turning=-speed/a if a else 0.0
                maximum_extent=[x,endpoint]
                if 0<turning<dt:
                    maximum_extent.append(x+turning*speed+0.5*turning**2*a)
                require(all(lo<=sample<=hi for sample in maximum_extent),
                        f"simulated vehicle left the independent NED envelope at tick {tick}")
                future.append(endpoint)
            p=future
            v=[a+dt*b for a,b in zip(v,acceleration,strict=True)]
    finally:
        process.close()
