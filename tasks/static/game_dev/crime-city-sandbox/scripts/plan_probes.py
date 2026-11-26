"""Rays that check a built world against its plan (WD-1 to WD-5, AC-8).

Author tool (never packaged). scripts/make_playtests.py turns these into the
world.plan_compliance playtest: one query step with every ray, and one expectation per
rule. Every expected height and tag comes from the plan (common/design/plan/FORMAT.md)
and every number from the design document (chapter 12):

- WD-1: lane centres sampled every 10 m hit road at the lane's height within 0.10 m, for
  at least 98% of the points;
- WD-2: sidewalk rings sampled every 10 m hit sidewalk at its elevation within 0.05 m;
  crosswalk bands hit road surface tagged crosswalk;
- WD-3: roofs at base_m + height_m within 0.5 m over at least 95% of each footprint; just
  outside each parcel, on the sidewalk, no building; plazas, parks and parking lots at
  base_m within 0.05 m with their tag;
- WD-4: door openings clear over their width and height; room floors at floor_m within
  0.10 m tagged interior, empty up to 0.10 m under the ceiling, seen clear from the door;
  connected rooms joined by an opening at least 1.2 m wide;
- WD-5: a ray down from 0.6 m above each point of interest hits within 0.30 m of it;
- AC-8: every surface a ray hits carries one of the listed tags.
"""

from __future__ import annotations

import itertools
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))

from qakit.plan import Plan

SURFACES = [
    "road",
    "crosswalk",
    "sidewalk",
    "building",
    "interior",
    "plaza",
    "park",
    "parking",
    "terrain",
    "dock",
]
BUILT = ("commercial", "residential", "civic", "industrial")
OPEN = ("plaza", "park", "parking")
TOP = 100.0  # rays from the sky start here
BOTTOM = -20.0


def r2(v: float) -> float:
    return round(float(v), 2)


def r3(v: float) -> float:
    return round(float(v), 3)


def inside(poly: list, x: float, z: float) -> bool:
    """Point in polygon (even-odd)."""
    hit = False
    n = len(poly)
    for i in range(n):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % n]
        if (z0 > z) != (z1 > z):
            xc = x0 + (z - z0) * (x1 - x0) / (z1 - z0)
            if x < xc:
                hit = not hit
    return hit


def area2(poly: list) -> float:
    """Twice the signed area (positive when the vertices run anticlockwise in x-z)."""
    n = len(poly)
    return sum(
        poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1]
        for i in range(n)
    )


def inset(poly: list, d: float) -> list:
    """A convex polygon moved inwards by d (each edge shifted, neighbours intersected)."""
    n = len(poly)
    sign = 1.0 if area2(poly) > 0 else -1.0
    lines = []
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        length = math.hypot(x1 - x0, z1 - z0)
        # inward normal: left of the edge for anticlockwise polygons
        nx, nz = -(z1 - z0) / length * sign, (x1 - x0) / length * sign
        lines.append(((x0 + nx * d, z0 + nz * d), (x1 - x0, z1 - z0)))
    out = []
    for i in range(n):
        (p, u), (q, v) = lines[i - 1], lines[i]
        den = u[0] * v[1] - u[1] * v[0]
        if abs(den) < 1e-12:
            out.append([q[0], q[1]])
            continue
        t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
        out.append([p[0] + u[0] * t, p[1] + u[1] * t])
    return out


def grid(poly: list, nx: int, nz: int, margin: float) -> list:
    """nx x nz points spread over a polygon's bounding box, margin inside it, kept when
    inside the polygon."""
    xs = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    x0, x1 = min(xs) + margin, max(xs) - margin
    z0, z1 = min(zs) + margin, max(zs) - margin
    out = []
    for i in range(nx):
        for j in range(nz):
            x = x0 + (x1 - x0) * (i + 0.5) / nx
            z = z0 + (z1 - z0) * (j + 0.5) / nz
            if inside(poly, x, z):
                out.append([r2(x), r2(z)])
    return out


@dataclass
class Rays:
    """The rays of one query step and the expectations that read them."""

    queries: list[dict] = field(default_factory=list)
    expects: list[dict] = field(default_factory=list)

    def down(self, qid: str, points: list, y0: float = TOP, y1: float = BOTTOM) -> None:
        self.queries.append(
            {"id": qid, "type": "down", "points": points, "y0": y0, "y1": y1, "mask": 1}
        )

    def ray(self, qid: str, a: list, b: list) -> None:
        self.queries.append(
            {
                "id": qid,
                "type": "ray",
                "from": [r3(c) for c in a],
                "to": [r3(c) for c in b],
                "mask": 1,
            }
        )

    def expect(self, eid: str, check: str, args: dict, rule: str, says: str) -> None:
        self.expects.append(
            {"id": eid, "check": check, "args": args, "rule": rule, "says": says}
        )


class Probes:
    """Builds the rays for one plan."""

    def __init__(self, plan_data: dict) -> None:
        self.d = plan_data
        self.plan = Plan(plan_data)
        self.nodes = self.plan.nodes
        self.edges = self.plan.edges
        self.parcels = {p["id"]: p for p in plan_data["parcels"]}
        self.blocks = {b["id"]: b for b in plan_data["blocks"]}
        self.walks = {s["id"]: s for s in plan_data["sidewalks"]}
        self.rays = Rays()

    # ------------------------------------------------------------ road geometry
    def leg_frame(self, node_id: str, edge: dict) -> tuple:
        """(node xz, unit direction away from the node, node height) of an edge's leg."""
        pts = self.plan.centreline(edge)
        if edge["b"] == node_id:
            pts = pts[::-1]
        (x0, y0, z0), (x1, _, z1) = pts[0], pts[1]
        length = math.hypot(x1 - x0, z1 - z0)
        return (x0, z0), ((x1 - x0) / length, (z1 - z0) / length), y0

    def half_widths(self, edge: dict, node_id: str) -> tuple[float, float]:
        """Carriageway extent (left, right) of the centreline, seen leaving node_id."""
        w = float(edge["lane_width_m"])
        if edge.get("oneway"):
            half = len(edge["lanes"]) * w / 2.0
            return half, half
        away = "ab" if edge["a"] == node_id else "ba"
        right = sum(1 for ln in edge["lanes"] if ln["dir"] == away) * w
        left = sum(1 for ln in edge["lanes"] if ln["dir"] != away) * w
        return left, right

    def bands(self, edge: dict) -> list[tuple[str, float, float]]:
        """Crosswalk bands of an edge: (node, from_m, to_m) measured from that node."""
        out = []
        for inter in self.d["intersections"]:
            for leg in inter["legs"]:
                cw = leg.get("crosswalk")
                if leg["edge"] == edge["id"] and cw:
                    out.append((inter["node"], float(cw["from_m"]), float(cw["to_m"])))
        return out

    def centre_length(self, edge: dict) -> float:
        pts = self.plan.centreline(edge)
        return sum(
            math.hypot(b[0] - a[0], b[2] - a[2]) for a, b in itertools.pairwise(pts)
        )

    # ------------------------------------------------------------ WD-1
    def roads(self) -> None:
        points, ys = [], []
        for lane_id in sorted(self.plan.lanes):
            edge, lane = self.plan.lanes[lane_id]
            length = self.plan.lane_length(lane_id)
            total = self.centre_length(edge)
            start = edge["a"] if lane["dir"] == "ab" else edge["b"]
            box = float(self.plan._leg(start, edge["id"])["box_m"])
            bands = self.bands(edge)
            s = 0.0
            while s <= length + 1e-9:
                from_start = box + s
                skip = False
                for node, b0, b1 in bands:
                    d = from_start if node == start else total - from_start
                    if b0 - 0.3 <= d <= b1 + 0.3:
                        skip = True
                if not skip:
                    p = self.plan.lane_point(lane_id, s).p
                    points.append([r2(p[0]), r2(p[2])])
                    ys.append(r3(p[1]))
                s += 10.0
        self.rays.down("lanes", points)
        self.rays.expect(
            "roads", "rays",
            {"query": "lanes", "y": ys, "tol_m": 0.10, "tags": ["road"], "min_share": 0.98},
            "WD-1",
            "along every lane centre, sampled every 10 m, the road (tagged road) is at the "
            "lane's height within 0.10 m for at least 98% of the points",
        )  # fmt: skip

    # ------------------------------------------------------------ WD-2
    def crosswalks(self) -> None:
        points, ys = [], []
        for inter in sorted(self.d["intersections"], key=lambda i: i["id"]):
            node = inter["node"]
            for leg in inter["legs"]:
                cw = leg.get("crosswalk")
                if not cw:
                    continue
                edge = self.edges[leg["edge"]]
                (nx, nz), (ux, uz), y = self.leg_frame(node, edge)
                left, right = self.half_widths(edge, node)
                along = (float(cw["from_m"]) + float(cw["to_m"])) / 2.0
                rx, rz = -uz, ux  # right of the direction away from the node
                k, lat = 0, -left + 0.4
                while lat <= right - 0.4 + 1e-9:
                    x = nx + ux * along + rx * lat
                    z = nz + uz * along + rz * lat
                    points.append([r2(x), r2(z)])
                    ys.append(r3(y))
                    k += 1
                    lat += 1.5
        self.rays.down("crosswalks", points)
        self.rays.expect(
            "crosswalk_tags", "rays",
            {"query": "crosswalks", "y": ys, "tol_m": 0.10, "tags": ["crosswalk"]},
            "WD-2", "across every crosswalk band the road surface is tagged crosswalk",
        )  # fmt: skip

    def sidewalks(self) -> None:
        points, ys, groups = [], [], []
        for sid in sorted(self.walks):
            sw = self.walks[sid]
            ring = sw["ring"]
            total = sum(
                math.dist(ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring))
            )
            n, s = 0, 0.0
            while s < total - 1e-9:
                p = self.plan.sidewalk_point(sid, s).p
                points.append([r2(p[0]), r2(p[2])])
                ys.append(r3(sw["elevation_m"]))
                n += 1
                s += 10.0
            groups.append([sid, n])
        self.rays.down("sidewalks", points)
        self.rays.expect(
            "sidewalks", "rays",
            {"query": "sidewalks", "y": ys, "tol_m": 0.05, "tags": ["sidewalk"], "groups": groups},
            "WD-2",
            "along every sidewalk ring, sampled every 10 m, the sidewalk (tagged sidewalk) is "
            "at its elevation within 0.05 m",
        )  # fmt: skip

    # ------------------------------------------------------------ WD-3
    def buildings(self) -> None:
        points, ys, groups = [], [], []
        out_pts, out_groups = [], []
        for pid in sorted(self.parcels):
            p = self.parcels[pid]
            if p["zoning"] not in BUILT:
                continue
            foot = inset(p["poly"], float(p["setback_m"]))
            pts = grid(foot, 5, 4, 0.5)
            points += pts
            ys += [r3(float(p["base_m"]) + float(p["height_m"]))] * len(pts)
            groups.append([pid, len(pts)])
            outer = self.outer_points(p)
            out_pts += outer
            out_groups.append([pid, len(outer)])
        self.rays.down("roofs", points)
        self.rays.expect(
            "roofs", "rays",
            {"query": "roofs", "y": ys, "tol_m": 0.5, "tags": ["building"], "groups": groups,
             "min_share": 0.95},
            "WD-3",
            "every parcel zoned commercial, residential, civic or industrial has a building "
            "(tagged building) whose roof is at base_m + height_m within 0.5 m over at least "
            "95% of its footprint",
        )  # fmt: skip
        self.rays.down("beside_parcels", out_pts)
        self.rays.expect(
            "within_parcels", "rays",
            {"query": "beside_parcels", "not_tags": ["building"], "groups": out_groups},
            "WD-3",
            "just outside each built parcel, on the sidewalk around its block, there is no "
            "building surface",
        )  # fmt: skip

    def outer_points(self, parcel: dict) -> list:
        """Points 0.25 m outside the parcel's edges that face the sidewalk, every 8 m."""
        sw = next(
            (s for s in self.walks.values() if s["block"] == parcel["block"]), None
        )
        if sw is None:
            return []
        inner = inset(self.blocks[parcel["block"]]["poly"], float(sw["width_m"]))
        poly = parcel["poly"]
        sign = 1.0 if area2(poly) > 0 else -1.0
        out = []
        for i in range(len(poly)):
            (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % len(poly)]
            length = math.hypot(x1 - x0, z1 - z0)
            mx, mz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
            on_inner = any(
                self.seg_dist(mx, mz, inner[k], inner[(k + 1) % len(inner)]) < 0.1
                for k in range(len(inner))
            )
            if not on_inner or length < 1.0:
                continue
            nx, nz = (z1 - z0) / length * sign, -(x1 - x0) / length * sign  # outward
            n = max(1, int(length // 8.0))
            for k in range(n):
                t = (k + 0.5) / n
                out.append(
                    [
                        r2(x0 + (x1 - x0) * t + nx * 0.25),
                        r2(z0 + (z1 - z0) * t + nz * 0.25),
                    ]
                )
        return out

    @staticmethod
    def seg_dist(x: float, z: float, a: list, b: list) -> float:
        dx, dz = b[0] - a[0], b[1] - a[1]
        ll = dx * dx + dz * dz
        t = (
            0.0
            if ll == 0
            else max(0.0, min(1.0, ((x - a[0]) * dx + (z - a[1]) * dz) / ll))
        )
        return math.hypot(x - (a[0] + t * dx), z - (a[1] + t * dz))

    def open_parcels(self) -> None:
        for zoning in OPEN:
            pts, ys, groups = [], [], []
            for pid in sorted(self.parcels):
                p = self.parcels[pid]
                if p["zoning"] != zoning:
                    continue
                xs = [v[0] for v in p["poly"]]
                zs = [v[1] for v in p["poly"]]
                nx = max(2, int((max(xs) - min(xs)) // 10.0))
                nz = max(2, int((max(zs) - min(zs)) // 10.0))
                got = grid(p["poly"], nx, nz, 0.5)
                pts += got
                ys += [r3(p["base_m"])] * len(got)
                groups.append([pid, len(got)])
            if not pts:
                continue
            self.rays.down(f"open_{zoning}", pts)
            self.rays.expect(
                f"open_{zoning}", "rays",
                {"query": f"open_{zoning}", "y": ys, "tol_m": 0.05, "tags": [zoning],
                 "groups": groups},
                "WD-3",
                f"every {zoning} parcel is open ground at base_m within 0.05 m, tagged {zoning}",
            )  # fmt: skip

    # ------------------------------------------------------------ WD-4
    def interiors(self) -> None:
        door_n, up_n, see_n, open_n = 0, 0, 0, 0
        floors, up_groups, see_groups, open_groups, door_groups = [], [], [], [], []
        for pid in sorted(self.parcels):
            p = self.parcels[pid]
            it = p.get("interior")
            if not it:
                continue
            door = it["door"]
            rooms = it["rooms"]
            h = math.radians(float(door["heading_deg"]))
            ux, uz = math.sin(h), -math.cos(h)  # into the building
            rx, rz = -uz, ux
            dx, dz = door["p"]
            first = self.room_at(rooms, dx + ux * 0.6, dz + uz * 0.6) or rooms[0]
            floor = float(first["floor_m"])
            width, height = float(door["width_m"]), float(door["height_m"])
            n0 = door_n
            for lat in (-width / 2.0 + 0.05, 0.0, width / 2.0 - 0.05):
                for up in (0.15, height / 2.0, height - 0.05):
                    a = [dx - ux * 1.0 + rx * lat, floor + up, dz - uz * 1.0 + rz * lat]
                    b = [dx + ux * 1.0 + rx * lat, floor + up, dz + uz * 1.0 + rz * lat]
                    self.rays.ray(f"door.{door_n}", a, b)
                    door_n += 1
            door_groups.append([f"{pid} door", door_n - n0])
            for room in rooms:
                label = f"{pid}/{room['id']}"
                pts = grid(room["poly"], *self.room_grid(room["poly"]), 0.4)
                f, c = float(room["floor_m"]), float(room["ceiling_m"])
                qid = f"room_floor.{len(floors)}"
                self.rays.down(qid, pts, y0=c - 0.10, y1=f - 1.0)
                floors.append((qid, label, f))
                n0 = up_n
                for x, z in pts:
                    self.rays.ray(f"room_up.{up_n}", [x, f + 0.3, z], [x, c - 0.10, z])
                    up_n += 1
                up_groups.append([label, up_n - n0])
                if room is first:
                    sx, sz = dx + ux * 0.5, dz + uz * 0.5
                    n0 = see_n
                    for x, z in pts:
                        for up in (0.3, 1.5):
                            self.rays.ray(
                                f"room_seen.{see_n}", [sx, f + up, sz], [x, f + up, z]
                            )
                            see_n += 1
                    see_groups.append([label, see_n - n0])
            for i, a in enumerate(rooms):
                for b in rooms[i + 1 :]:
                    rays = self.opening_rays(a, b)
                    if rays:
                        n0 = open_n
                        for ra, rb in rays:
                            self.rays.ray(f"opening.{open_n}", ra, rb)
                            open_n += 1
                        open_groups.append([f"{pid}/{a['id']}-{b['id']}", open_n - n0])
        self.rays.expect(
            "doors", "rays",
            {"rays": {"prefix": "door.", "count": door_n}, "clear": True, "groups": door_groups},
            "WD-4",
            "each door is an open doorway at least as wide and as high as the plan says",
        )  # fmt: skip
        for qid, label, f in floors:
            self.rays.expect(
                f"floor_{label.replace('/', '_')}", "rays",
                {"query": qid, "y": f, "tol_m": 0.10, "tags": ["interior"]},
                "WD-4",
                f"room {label}: from 0.10 m under its ceiling down, the first surface is its "
                "floor at floor_m within 0.10 m, tagged interior",
            )  # fmt: skip
        self.rays.expect(
            "rooms_empty", "rays",
            {"rays": {"prefix": "room_up.", "count": up_n}, "clear": True, "groups": up_groups},
            "WD-4", "every room is empty from its floor to 0.10 m under its ceiling",
        )  # fmt: skip
        self.rays.expect(
            "rooms_open", "rays",
            {"rays": {"prefix": "room_seen.", "count": see_n}, "clear": True,
             "groups": see_groups},
            "WD-4", "from just inside the door, nothing stands in the room it opens into",
        )  # fmt: skip
        if open_n:
            self.rays.expect(
                "connected_rooms", "clear_run",
                {"rays": {"prefix": "opening.", "count": open_n}, "groups": open_groups,
                 "spacing_m": 0.1, "min_width_m": 1.2},
                "WD-4", "rooms listed together are joined by an opening at least 1.2 m wide",
            )  # fmt: skip

    @staticmethod
    def room_at(rooms: list, x: float, z: float) -> dict | None:
        return next((r for r in rooms if inside(r["poly"], x, z)), None)

    @staticmethod
    def room_grid(poly: list) -> tuple[int, int]:
        xs = [p[0] for p in poly]
        zs = [p[1] for p in poly]
        return (
            max(2, min(5, int((max(xs) - min(xs)) // 2.5))),
            max(2, min(5, int((max(zs) - min(zs)) // 2.5))),
        )

    def opening_rays(self, a: dict, b: dict) -> list:
        """Rays across the boundary two rooms share, 0.1 m apart (none when they share
        no edge)."""
        out = []
        pa, pb = a["poly"], b["poly"]
        y = max(float(a["floor_m"]), float(b["floor_m"])) + 1.0
        for i in range(len(pa)):
            e0, e1 = pa[i], pa[(i + 1) % len(pa)]
            for k in range(len(pb)):
                f0, f1 = pb[k], pb[(k + 1) % len(pb)]
                seg = self.overlap(e0, e1, f0, f1)
                if seg is None:
                    continue
                (sx, sz), (tx, tz), (nx, nz) = seg
                length = math.hypot(tx - sx, tz - sz)
                n = int(length // 0.1)
                for j in range(n + 1):
                    t = j / n if n else 0.5
                    x, z = sx + (tx - sx) * t, sz + (tz - sz) * t
                    out.append(
                        (
                            [x - nx * 0.3, y, z - nz * 0.3],
                            [x + nx * 0.3, y, z + nz * 0.3],
                        )
                    )
        return out

    @staticmethod
    def overlap(e0, e1, f0, f1):
        """The part two collinear room edges share, 0.05 m in from its ends, and the
        edge's unit normal (the rays cross it both ways, so its sign does not matter);
        None when the edges share less than 0.2 m."""
        dx, dz = e1[0] - e0[0], e1[1] - e0[1]
        length = math.hypot(dx, dz)
        if length < 1e-6:
            return None
        ux, uz = dx / length, dz / length
        for p in (f0, f1):
            if abs((p[0] - e0[0]) * uz - (p[1] - e0[1]) * ux) > 0.05:
                return None
        t0 = (f0[0] - e0[0]) * ux + (f0[1] - e0[1]) * uz
        t1 = (f1[0] - e0[0]) * ux + (f1[1] - e0[1]) * uz
        lo, hi = max(0.0, min(t0, t1)) + 0.05, min(length, max(t0, t1)) - 0.05
        if hi - lo < 0.2:
            return None
        return (
            (e0[0] + ux * lo, e0[1] + uz * lo),
            (e0[0] + ux * hi, e0[1] + uz * hi),
            (uz, -ux),
        )

    # ------------------------------------------------------------ WD-5
    def pois(self) -> None:
        ys = []
        for k, poi in enumerate(sorted(self.d["pois"], key=lambda p: p["id"])):
            x, y, z = (float(c) for c in poi["p"])
            self.rays.ray(f"poi.{k}", [x, y + 0.6, z], [x, y - 1.0, z])
            ys.append(r3(y))
        self.rays.expect(
            "pois", "rays",
            {"rays": {"prefix": "poi.", "count": len(ys)}, "y": ys, "tol_m": 0.30,
             "groups": [[p["id"], 1] for p in sorted(self.d["pois"], key=lambda p: p["id"])]},
            "WD-5",
            "a ray down from 0.6 m above every point of interest hits a surface within "
            "0.30 m of its height",
        )  # fmt: skip

    # ------------------------------------------------------------ all
    def build(self) -> Rays:
        self.roads()
        self.crosswalks()
        self.sidewalks()
        self.buildings()
        self.open_parcels()
        self.interiors()
        self.pois()
        self.rays.expect(
            "surface_tags", "surface_tags", {"allowed": SURFACES}, "AC-8",
            "every surface the rays hit is a world collider whose surface metadata is one of "
            "road, crosswalk, sidewalk, building, interior, plaza, park, parking, terrain, dock",
        )  # fmt: skip
        return self.rays
