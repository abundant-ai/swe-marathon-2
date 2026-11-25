"""Independent route checks and actual closed-loop body traces for stages 1-3."""

from collections import deque
from cmath import exp, phase
import json
from math import hypot
from pathlib import Path
import tempfile

from layouts import course, revised
from transport import CLI_TIMEOUT_S, Driver, command, contents, report, require, run, writable

SENTINEL=b'{"previous":"valid"}\n'


def boxes(config):
    """Return the static occupied cell boxes directly from the supplied raster."""
    scale=config["resolution_m"]
    return [(x*scale,y*scale,(x+1)*scale,(y+1)*scale)
            for y,row in enumerate(config["rows"]) for x,char in enumerate(row) if char=="#"]


def center(config, index):
    """Convert sample cell indices into physical centers."""
    return complex(*[(slot+0.5)*config["resolution_m"] for slot in index])


def clearance(config, walls, point):
    """Measure center distance from rectangles and closed world exterior."""
    x,y=point.real,point.imag
    s=config["resolution_m"]
    room=min(x,y,len(config["rows"][0])*s-x,len(config["rows"])*s-y)
    return min([room]+[hypot(max(x0-x,0,x-x1),max(y0-y,0,y-y1)) for x0,y0,x1,y1 in walls])


def edge_clear(config,walls,a,b):
    """Independently check cardinal neighbors by dense support plus a travel allowance."""
    threshold=config["radius_m"]+config["margin_m"]
    if a==b:
        return clearance(config,walls,a)>threshold+1e-10
    for cells in (4,16,64):
        minimum=min(clearance(config,walls,a+(b-a)*u/cells) for u in range(cells+1))
        if minimum<=threshold:
            return False
        if minimum>threshold+abs(b-a)/(2*cells):
            return True
    return False


def shortest_length(config):
    """Compute optimum number of lattice moves independently of submitted path."""
    start,goal=map(tuple,(config["start"],config["goal"]))
    if config["radius_m"]+config["margin_m"] < config["resolution_m"]/2:
        # For small discs on a cardinal occupancy lattice, free neighbor centers
        # connect wholly inside the union of their cells.
        if any(config["rows"][j][i]=="#" for i,j in (start,goal)):
            return None
        def passable(a,b): return config["rows"][b[1]][b[0]]=="."
    else:
        obstacles=boxes(config)
        if not edge_clear(config,obstacles,center(config,start),center(config,start)):
            return None
        def passable(a,b): return edge_clear(config,obstacles,center(config,a),center(config,b))
    work=deque([(start,0)])
    seen={start}
    while work:
        (x,y),length=work.popleft()
        if (x,y)==goal:
            return length
        for n in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if n not in seen and 0<=n[0]<len(config["rows"][0]) and 0<=n[1]<len(config["rows"]) and passable((x,y),n):
                seen.add(n)
                work.append((n,length+1))
    return None


def publish(path,value):
    """Write a verifier input the candidate account may read but not change."""
    path.write_text(json.dumps(value,allow_nan=False))
    path.chmod(0o644)
    return path


def invoke(app,root,mode,spec,*,trace=None,invalid=False):
    """Run one CLI command on verifier-written inputs in a fresh directory."""
    with tempfile.TemporaryDirectory(dir=root,ignore_cleanup_errors=True) as scratch:
        work=Path(scratch)
        work.chmod(0o755)
        destination=writable(work/"out")/"result.json"
        extra=["--output",str(destination)]
        if trace is not None:
            extra+=["--input",str(publish(work/"trace.json",trace))]
        if invalid:
            destination.write_bytes(SENTINEL)
            destination.chmod(0o666)
        status=run(command(mode,publish(work/"layout.json",spec),*extra),app,writable(work/"home"))
        require(status is not None,f"qualification CLI did not finish within {CLI_TIMEOUT_S:g} s")
        if invalid:
            require(status!=0,"malformed input was accepted")
            require(contents(destination)==SENTINEL,"malformed input overwrote prior output")
            return None
        require(status==0,"qualification CLI exited with an error")
        return report(destination)


def plan_case(app,root,case):
    """Demand a shortest, truly swept-clear path or a justified blocked result."""
    spec=course(case["map"])
    expected=shortest_length(spec)
    answer=invoke(app,root,"plan",spec)
    cells=answer.get("cells")
    if expected is None:
        require(answer.get("status")=="blocked" and cells==[],"footprint cannot traverse this grid")
    else:
        require(answer.get("status")=="ready" and isinstance(cells,list) and len(cells)==expected+1,
                "route not shortest under independent grid")
        require(all(isinstance(index,list) and len(index)==2 and all(type(v) is int for v in index)
                    for index in cells),"bad route coordinates")
        require(cells[0]==spec["start"] and cells[-1]==spec["goal"],"route endpoints changed")
        obstacles=boxes(spec)
        for a,b in zip(cells,cells[1:]):
            require(sum(abs(x-y) for x,y in zip(a,b))==1 and edge_clear(spec,obstacles,center(spec,a),center(spec,b)),
                    "a lattice segment crosses the footprint boundary")
    if case.get("malformed"):
        spec["rows"][-1]=spec["rows"][-1]+"?"
        invoke(app,root,"plan",spec,invalid=True)
    return {"shortest_cells":expected,"status":"blocked" if expected is None else "ready"}


def trajectory(app,root,case):
    """Drive the actual submitted commands in a collision-checking unicycle."""
    spec=course(case["map"])
    grid=spec
    zone=boxes(grid)
    step=spec["dt"]
    radius=spec["radius_m"]+spec["margin_m"]
    route=0.0
    minimum=float("inf")
    start=center(spec,spec["start"])
    goal=center(spec,spec["goal"])
    z,yaw=start,case.get("yaw",1.75)
    driver=Driver(app,publish(root/"navigator.json",spec),writable(root/"home"))
    waits=0
    outcome=None
    try:
        for tick in range(spec["deadline"]+1):
            row={"tick":tick,"pose":[z.real,z.imag,yaw]}
            if case.get("dynamic")=="cut" and tick==23:
                grid=spec | {"rows":revised(spec,add=[(7,6)])}
                zone=boxes(grid)
                row|={"revision":2,"rows":grid["rows"]}
            if case.get("dynamic")=="reopen":
                if tick==44:
                    grid=spec|{"rows":revised(spec,remove=[(7,6)])}
                    zone=boxes(grid)
                    row|={"revision":2,"rows":grid["rows"]}
                if tick==49:
                    row|={"revision":1,"rows":spec["rows"]}
            if case.get("pose_loss") and 31<=tick<38:
                row["pose"]=None
            reply=driver.paced(row,tick,step)
            v,w=reply.get("v_mps"),reply.get("w_radps")
            status=reply.get("status")
            require(type(v) in (int,float) and 0<=v<=spec["max_v"]+1e-9
                    and type(w) in (int,float) and abs(w)<=spec["max_w"]+1e-9,"unsafe controller limits")
            if row["pose"] is None:
                require(v==w==0,"moved without a measured pose")
            if status=="waiting":
                waits+=1
                require(v==w==0,"the navigator still moved while waiting")
            if status in ("succeeded","timeout"):
                require(v==w==0,"a terminal state commanded motion")
                expected="timeout" if case.get("blocked") else "succeeded"
                require(status==expected and (abs(z-goal)<=spec["goal_tolerance_m"]+1e-9 if status=="succeeded"
                                             else tick==spec["deadline"]), f"false or late terminal status {status} at tick {tick}")
                outcome={"finish_tick":tick,"status":expected,"path_m":round(route,4),
                         "minimum_clearance_m":round(minimum,4) if minimum<1e9 else None,
                         "waiting_ticks":waits,"goal_error_m":round(abs(z-goal),4),
                         "max_reply_s":round(driver.slowest,4)}
                break
            require(status in ("running","waiting"),"unknown controller status")
            axis=exp(1j*yaw)
            closest=float("inf")
            for count in (8,32,128,512,2048):
                closest=float("inf")
                for i in range(count+1):
                    age=step*i/count
                    end=z+v*age*axis if abs(w)<1e-12 else z+v/(1j*w)*axis*(exp(1j*w*age)-1)
                    gap=clearance(grid,zone,end)-radius
                    require(gap>0,"actual swept robot clipped an occupied cell or map boundary")
                    closest=min(closest,gap)
                if closest>v*step/(2*count)+1e-10:
                    break
            else:
                require(False,"actual swept robot clearance could not be certified")
            minimum=min(minimum,closest)
            route+=v*step
            z,yaw=end,phase(exp(1j*(yaw+w*step)))
        require(outcome is not None,"did not return a physical mission outcome")
        require(waits>=case.get("min_wait",0),"the expected closed-corridor hold was not exercised")
        if case.get("blocked"):
            require(route<1e-8,"advanced toward an unreachable corridor")
        return outcome
    finally:
        driver.close()


def qualification(app,root,case):
    """Verify metric and priority on independently specified physical traces."""
    spec=course("authored")
    a,b=center(spec,spec["start"]),center(spec,spec["goal"])
    if case["kind"]=="collision":
        b=complex(b.real,a.imag)
        trace=[{"tick":3,"pose":[a.real,a.imag,0]},
               {"tick":17,"pose":[b.real,b.imag,0]}]
        expected=("collision",17)
    elif case["kind"]=="timeout":
        b=a+0.11
        trace=[{"tick":4,"pose":[a.real,a.imag,0]},
               {"tick":spec["deadline"],"pose":[b.real,b.imag,0]}]
        expected=("timeout",None)
    else:
        a=b-0.19j
        trace=[{"tick":9,"pose":[a.real,a.imag,0]},
               {"tick":12,"pose":[b.real,b.imag,0]}]
        expected=("succeeded",None)
    result=invoke(app,root,"qualify",spec,trace=trace)
    require((result.get("status"),result.get("first_collision_tick"))==expected,"wrong qualification outcome or crossing time")
    distance,duration=result.get("distance_m"),result.get("duration_s")
    require(all(type(x) in (int,float) and abs(x)<=1e6 for x in (distance,duration)),"trajectory measures must be numbers")
    length,span=abs(b-a),(trace[-1]["tick"]-trace[0]["tick"])*spec["dt"]
    require(abs(distance-length)<1e-8 and abs(duration-span)<1e-8,"wrong trajectory measures")
    return {"status":expected[0],"first_collision_tick":expected[1],"distance_m":round(length,6),"duration_s":round(span,6)}


CASES=[
    (1,"shortest_authored_clutter_plan",plan_case,{"map":"authored","malformed":True}),
    (1,"recorded_world_zero_crop_plan",plan_case,{"map":"barn"}),
    (1,"footprint_cannot_fit_shallow_pinch",plan_case,{"map":"pinch"}),
    (2,"closed_loop_staggered_aisles",trajectory,{"map":"authored"}),
    (2,"closed_loop_real_obstacle_crop",trajectory,{"map":"barn","yaw":-2.3}),
    (2,"no_safe_route_waits",trajectory,{"map":"sealed","blocked":True,"min_wait":30}),
    (3,"temporary_gate_opens_with_old_revision_noise",trajectory,{"map":"release","dynamic":"reopen","min_wait":44}),
    (3,"midrun_cell_closure_and_lost_pose",trajectory,{"map":"authored","dynamic":"cut","pose_loss":True,"min_wait":7}),
    (3,"traversal_crosses_wall_between_samples",qualification,{"kind":"collision"}),
    (3,"independent_completion_metric",qualification,{"kind":"success"}),
    (3,"independent_timeout_metric",qualification,{"kind":"timeout"}),
]
