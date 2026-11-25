"""Metric occupancy, swept disc geometry and shortest lattice routes."""

from collections import deque
from math import hypot, isfinite
from typing import Any

Record = dict[str, Any]
Cell = tuple[int, int]
Point = tuple[float, float]


def value(raw: object, *, zero_allowed: bool = False) -> float:
    """Require a finite metric quantity, normally strictly positive."""
    if type(raw) not in (int,float) or not isfinite(raw) or raw < 0 or (not zero_allowed and raw == 0):
        raise ValueError("invalid metric quantity")
    return float(raw)


def pose(raw: object) -> tuple[float, float, float]:
    """Read a finite planar chassis pose."""
    if type(raw) is not list or len(raw) != 3 or not all(type(v) in (int,float) and isfinite(v) for v in raw):
        raise ValueError("invalid pose")
    return tuple(raw)


def point_line(p: Point, a: Point, b: Point) -> float:
    """Compute Euclidean point-to-segment distance with clamped projection."""
    x,y = b[0]-a[0], b[1]-a[1]
    length = x*x+y*y
    u = max(0.0,min(1.0,((p[0]-a[0])*x+(p[1]-a[1])*y)/length)) if length else 0.0
    return hypot(p[0]-a[0]-u*x,p[1]-a[1]-u*y)


def rectangle_distance(a: Point, b: Point, box: tuple[float,float,float,float]) -> float:
    """Compute minimum distance from a segment to a closed rectangle."""
    x0,y0,x1,y1 = box
    lower, upper = 0.0, 1.0
    for coordinate, end, low, high in ((a[0],b[0],x0,x1),(a[1],b[1],y0,y1)):
        if coordinate == end:
            if not low <= coordinate <= high:
                lower,upper=1.0,0.0
        else:
            first,last=sorted(((low-coordinate)/(end-coordinate),(high-coordinate)/(end-coordinate)))
            lower,upper=max(lower,first),min(upper,last)
    if lower <= upper:
        return 0.0
    distances = [point_line((x,y),a,b) for x in (x0,x1) for y in (y0,y1)]
    for x,y in (a,b):
        distances.append(hypot(max(x0-x,x-x1,0.0),max(y0-y,y-y1,0.0)))
    return min(distances)


class Grid:
    """Index immutable occupancy at one accepted map revision."""

    def __init__(self, config: Record, rows: list[str] | None = None) -> None:
        """Validate declared rows, dimensions and endpoint cells."""
        rows=config["rows"] if rows is None else rows
        if (type(rows) is not list or not rows or type(rows[0]) is not str or not rows[0]
             or not all(type(row) is str and len(row)==len(rows[0]) and set(row)<=set(".#") for row in rows)):
            raise ValueError("malformed occupancy map")
        self.w,self.h=len(rows[0]),len(rows)
        self.res=value(config["resolution_m"])
        self.gap=value(config["radius_m"])+value(config["margin_m"],zero_allowed=True)
        self.start,self.goal=(self.cell(config[key]) for key in ("start","goal"))
        self.boxes=[(x*self.res,y*self.res,(x+1)*self.res,(y+1)*self.res)
                    for y,row in enumerate(rows) for x,mark in enumerate(row) if mark=="#"]

    def cell(self, raw: object) -> Cell:
        """Read a permitted integer grid index."""
        if type(raw) is not list or len(raw)!=2 or not all(type(v) is int for v in raw):
            raise ValueError("invalid cell")
        x,y=raw
        if not (0<=x<self.w and 0<=y<self.h):
            raise ValueError("cell outside map")
        return x,y

    def center(self, cell: Cell) -> Point:
        """Convert a lattice index to its metric center."""
        return ((cell[0]+0.5)*self.res,(cell[1]+0.5)*self.res)

    def inside(self, p: Point, extra: float = 0.0) -> bool:
        """Confirm that a footprint remains within the supported world."""
        x,y=p
        edge = self.gap + extra
        return edge < x < self.w*self.res-edge and edge < y < self.h*self.res-edge

    def safe(self, a: Point, b: Point, extra: float = 0.0) -> bool:
        """Check the complete swept disc using exact segment-to-obstacle distances."""
        if not self.inside(a, extra) or not self.inside(b, extra):
            return False
        left, right=sorted((a[0],b[0]))
        small, large=sorted((a[1],b[1]))
        r=self.gap + extra
        return all(x1 < left-r or x0 > right+r or y1 < small-r or y0 > large+r
                   or rectangle_distance(a,b,(x0,y0,x1,y1)) > r+1e-12
                   for x0,y0,x1,y1 in self.boxes)

    def tree(self) -> dict[Cell, Cell | None]:
        """Compute shortest successor links from reachable cells to the goal."""
        g=self.goal
        p=self.center(g)
        if not self.safe(p,p):
            return {}
        queue=deque([g])
        came={g: None}
        while queue:
            x,y=queue.popleft()
            p=self.center((x,y))
            for u,v in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                q=(u,v)
                if q not in came and 0<=u<self.w and 0<=v<self.h and self.safe(p,self.center(q)):
                    came[q]=(x,y)
                    queue.append(q)
        return came


def path(tree: dict[Cell, Cell | None], start: Cell) -> list[Cell]:
    """Follow a shortest successor tree if the requested start is connected."""
    if start not in tree:
        return []
    result=[]
    current=start
    while current is not None:
        result.append(current)
        current=tree[current]
    return result
