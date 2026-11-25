"""Drive a constrained course or qualify externally observed navigation."""

import argparse
import json
from math import atan2, dist, floor, pi
from pathlib import Path
import sys
import tempfile

from .grid import Grid, Point, Record, path, pose, value


def write(path: Path, result: Record) -> None:
    """Atomically publish a validated complete report."""
    with tempfile.NamedTemporaryFile(mode="w",dir=path.parent,delete=False) as output:
        temp=Path(output.name)
        try:
            json.dump(result,output,allow_nan=False)
            output.close()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def result(status: str, v: float=0.0, w: float=0.0) -> Record:
    """Emit a unicycle command with its current decision status."""
    return {"status":status,"v_mps":v,"w_radps":w}


class Controller:
    """Maintain revisioned geometry and track safe waypoints from measured poses."""

    def __init__(self, spec: Record) -> None:
        """Capture immutable metric geometry and current occupancy."""
        self.spec=spec
        self.grid=Grid(spec)
        self.tree=self.grid.tree()
        self.route: list[Point] = []
        self.rev=0
        self.terminal=None

    def reconfigure(self, obs: Record) -> None:
        """Replace occupancy at a newer revision, invalidating old route guarantees."""
        rev=obs.get("revision",0)
        if rev>self.rev:
            grid=Grid(self.spec,obs["rows"])
            if (grid.w,grid.h)!=(self.grid.w,self.grid.h):
                raise ValueError("changed occupancy shape")
            self.grid,self.tree,self.route,self.rev=grid,grid.tree(),[],rev

    def connect(self, p: Point) -> list[Point]:
        """Join the reachable lattice near a possibly interrupted pose."""
        g=self.grid
        cx,cy=(floor(value/g.res) for value in p)
        options=[]
        for x in range(cx-1,cx+2):
            for y in range(cy-1,cy+2):
                if (x,y) not in self.tree:
                    continue
                q=g.center((x,y))
                if not g.safe(p,q,0.001):
                    continue
                route=path(self.tree,(x,y))
                options.append((dist(p,q)+(len(route)-1)*g.res,route))
        if not options:
            return []
        _, shortest=min(options)
        return [g.center(cell) for cell in shortest]

    def tick(self, obs: Record) -> Record:
        """Plan and follow a rotation/translation sequence safe on the current grid."""
        cfg=self.spec
        if self.terminal is not None:
            return result(self.terminal)
        self.reconfigure(obs)
        position=pose(obs["pose"]) if obs["pose"] is not None else None
        if position is not None and dist(position[:2],self.grid.center(self.grid.goal))<=cfg["goal_tolerance_m"]:
            self.terminal="succeeded"
        elif obs["tick"]>=cfg["deadline"]:
            self.terminal="timeout"
        if self.terminal is not None:
            return result(self.terminal)
        if position is None:
            return result("waiting")
        p=position[:2]
        if not self.route:
            self.route=self.connect(p)
        while self.route and dist(p,self.route[0])<1e-8:
            self.route.pop(0)
        if not self.route:
            return result("waiting")
        # A safe line of sight can skip unnecessary lattice turns; recheck measured start.
        for i in range(len(self.route)-1,-1,-1):
            if self.grid.safe(p,self.route[i],0.001):
                self.route=self.route[i:]
                break
        else:
            self.route=[]
            return result("waiting")
        aim=self.route[0]
        bearing=atan2(aim[1]-p[1],aim[0]-p[0])
        error=(bearing-position[2]+pi)%(2*pi)-pi
        if abs(error)>1e-10:
            return result("running",w=max(-cfg["max_w"],min(cfg["max_w"],error/cfg["dt"])))
        return result("running",v=min(cfg["max_v"],dist(p,aim)/cfg["dt"]))


def navigator(spec: Record):
    """Stream actor for a mission: the grid controller, or the field navigator when scans arrive."""
    if "scan" not in spec:
        return Controller(spec)
    try:
        from .movers import Tracker as Navigator
    except ModuleNotFoundError as missing:
        if missing.name!=f"{__package__}.movers":
            raise
        from .pilot import Pilot as Navigator  # the stage 4 reference has no mover handling
    return Navigator(spec)

def qualify(spec: Record, raw: object) -> Record:
    """Measure chronological trajectory, collision priority and physical outcome."""
    model=Grid(spec)
    if type(raw) is not list or not raw:
        raise ValueError("empty traversal trace")
    ticks=[entry["tick"] for entry in raw]
    if not all(type(t) is int and t>=0 for t in ticks) or any(a>=b for a,b in zip(ticks,ticks[1:])):
        raise ValueError("nonincreasing traversal ticks")
    points=[pose(entry["pose"])[:2] for entry in raw]
    collision=None if model.safe(points[0],points[0]) else ticks[0]
    length=0.0
    for a,b,tick in zip(points,points[1:],ticks[1:]):
        length+=dist(a,b)
        if collision is None and not model.safe(a,b):
            collision=tick
    status="incomplete"
    if collision is not None:
        status="collision"
    elif dist(points[-1],model.center(model.goal))<=value(spec["goal_tolerance_m"]):
        status="succeeded"
    elif ticks[-1]>=spec["deadline"]:
        status="timeout"
    return {"status":status,"duration_s":(ticks[-1]-ticks[0])*value(spec["dt"]),
            "distance_m":length,"first_collision_tick":collision}


def main() -> int:
    """Select route planning, a streamed controller or offline qualification."""
    parser=argparse.ArgumentParser()
    modes=parser.add_subparsers(dest="mode",required=True)
    for mode in ("plan","stream","qualify"):
        cmd=modes.add_parser(mode)
        cmd.add_argument("--spec",type=Path,required=True)
        if mode!="stream":
            cmd.add_argument("--output",type=Path,required=True)
        if mode=="qualify":
            cmd.add_argument("--input",type=Path,required=True)
    args=parser.parse_args()
    try:
        spec=json.loads(args.spec.read_text())
        if args.mode=="stream":
            actor=navigator(spec)
            for line in sys.stdin:
                print(json.dumps(actor.tick(json.loads(line)),allow_nan=False),flush=True)
        elif args.mode=="plan":
            grid=Grid(spec)
            route=path(grid.tree(),grid.start)
            write(args.output,{"status":"ready" if route else "blocked","cells":route})
        else:
            write(args.output,qualify(spec,json.loads(args.input.read_text())))
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as error:
        print(f"barn qualification: {error}",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    sys.exit(main())
