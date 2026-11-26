"""Check a city-plan/1 file against the rules of common/design/plan/FORMAT.md.

Author tool (never packaged). Prints one line per problem and exits 1 if there is any.
With --gdd it also checks that every point of interest the design document names for the
plan's map exists in the plan (the ids of maps not given are listed as still to come).

Usage: python scripts/check_plan.py [--gdd common/design/GDD.md] PLAN [PLAN ...]
"""

import argparse
import itertools
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

ZONINGS = {
    "commercial",
    "residential",
    "civic",
    "industrial",
    "plaza",
    "park",
    "parking",
}
BUILT = {"commercial", "residential", "civic", "industrial"}
CLASSES = {"arterial", "street", "highway", "dock", "track"}
STRUCTURES = {"ground", "bridge", "tunnel"}
NODE_KINDS = {"junction", "bend", "end", "portal"}
CONTROLS = {"signal", "stop", "none"}
POI_FIELDS = {
    "police_station": {"parcel", "exit", "respawn"},
    "hospital": {"parcel", "exit", "respawn"},
    "shop": {"shop", "parcel", "point"},
    "garage": {"zone", "driveway", "capacity"},
    "safehouse": {"parcel", "point"},
    "bank": {"parcel", "vault"},
    "mission_giver": {"giver"},
    "mission_point": {"radius_m"},
    "checkpoint": {"race", "index", "radius_m"},
    "ferry_terminal": {"dock", "ramp", "queue"},
    "portal": {"node", "link"},
    "plaza": {"parcel"},
}
TOL = 0.05

# The points of interest the design document names, by the map that holds them.
GDD_POIS = {
    "downtown": [
        "safehouse_downtown", "garage_downtown", "bank_downtown", "giver_delivery",
        "giver_race", "giver_heist", "d1_pickup", "d1_dropoff", "r1_start",
        *(f"r1_cp{i}" for i in range(1, 9)), "h1_car", "h1_stash",
    ],
    "port": [
        "giver_chase", "garage_port", "ferry_terminal_port", "c1_start", "c2_start",
        "d2_pickup", "d2_dropoff", "h2_van", "h2_stash",
    ],
    "hills": [
        "garage_hills", "ferry_terminal_hills", "r2_start",
        *(f"r2_cp{i}" for i in range(1, 13)),
    ],
}  # fmt: skip
# Checkpoint ranges the design document writes as "first-last".
GDD_RANGES = {"r1_cp": 8, "r2_cp": 12}
POI_LIKE = re.compile(
    r"`((?:[a-z]+_)*(?:downtown|port|hills)|[cdhr][12]_[a-z0-9_]+|giver_[a-z]+)`"
)


def inside(poly, x, z, tol=TOL):
    """Point in polygon (even-odd), counting points within tol of an edge as inside."""
    n = len(poly)
    hit = False
    for i in range(n):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % n]
        if seg_dist(x, z, x0, z0, x1, z1) <= tol:
            return True
        if (z0 > z) != (z1 > z):
            xc = x0 + (z - z0) * (x1 - x0) / (z1 - z0)
            if x < xc:
                hit = not hit
    return hit


def seg_dist(x, z, x0, z0, x1, z1):
    dx, dz = x1 - x0, z1 - z0
    ll = dx * dx + dz * dz
    t = 0.0 if ll == 0 else max(0.0, min(1.0, ((x - x0) * dx + (z - z0) * dz) / ll))
    return math.hypot(x - (x0 + t * dx), z - (z0 + t * dz))


def on_outline(poly, x, z, tol=TOL):
    n = len(poly)
    return any(seg_dist(x, z, *poly[i], *poly[(i + 1) % n]) <= tol for i in range(n))


def inset_rect(poly, d):
    xs = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    return [
        [min(xs) + d, min(zs) + d],
        [max(xs) - d, min(zs) + d],
        [max(xs) - d, max(zs) - d],
        [min(xs) + d, max(zs) - d],
    ]


def heading_vec(h):
    r = math.radians(h)
    return math.sin(r), -math.cos(r)


def cut(pts, d0, d1):
    """The part of a 2D polyline between distances d0 and d1 along it."""
    out, walked = [], 0.0
    for p, q in itertools.pairwise(pts):
        seg = math.dist(p, q)
        if seg <= 0:
            continue
        s0, s1 = walked, walked + seg
        if s1 >= d0 and s0 <= d1:
            a = max(0.0, min(1.0, (d0 - s0) / seg))
            b = max(0.0, min(1.0, (d1 - s0) / seg))
            pa = (p[0] + (q[0] - p[0]) * a, p[1] + (q[1] - p[1]) * a)
            if not out or math.dist(out[-1], pa) > 1e-9:
                out.append(pa)
            out.append((p[0] + (q[0] - p[0]) * b, p[1] + (q[1] - p[1]) * b))
        walked = s1
    return out


def length_of(pts):
    return sum(math.dist(p, q) for p, q in itertools.pairwise(pts))


def unit(p, q):
    d = math.dist(p, q)
    return ((q[0] - p[0]) / d, (q[1] - p[1]) / d)


class Plan:
    def __init__(self, data):
        self.d = data
        self.err = []
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = {e["id"]: e for e in data["edges"]}
        self.lanes = {}
        for e in data["edges"]:
            for ln in e["lanes"]:
                self.lanes[ln["id"]] = (e, ln)
        self.inters = {i["node"]: i for i in data["intersections"]}
        self.blocks = {b["id"]: b for b in data["blocks"]}
        self.parcels = {p["id"]: p for p in data["parcels"]}

    def bad(self, msg):
        self.err.append(msg)

    def unique(self, key, items):
        seen = set()
        for it in items:
            if it["id"] in seen:
                self.bad(f"{key}: duplicate id {it['id']}")
            seen.add(it["id"])

    def centreline(self, e):
        """The edge's centreline from a to b as (x, z) points."""
        pts = [self.nodes[e["a"]]["p"], *e.get("points", []), self.nodes[e["b"]]["p"]]
        return [(float(p[0]), float(p[2])) for p in pts]

    def leg(self, node, edge):
        for leg in self.inters[node]["legs"]:
            if leg["edge"] == edge:
                return leg
        raise KeyError((node, edge))

    def lane_frame(self, lane_id):
        """(centre polyline of the lane from s=0 to its end, length, start node, end node,
        start direction, end direction)."""
        e, ln = self.lanes[lane_id]
        start, end = (e["a"], e["b"]) if ln["dir"] == "ab" else (e["b"], e["a"])
        pts = self.centreline(e)
        if ln["dir"] == "ba":
            pts = pts[::-1]
        n = len(e["lanes"])
        w = e["lane_width_m"]
        off = (ln["index"] + 0.5 - (n / 2.0 if e["oneway"] else 0.0)) * w
        s0 = self.leg(start, e["id"])["box_m"]
        s1 = (self.leg(end, e["id"])["approach"] or {}).get("stop_line_m", 0.0)
        total = length_of(pts)
        mid = cut(pts, s0, total - s1)
        lane = []
        for i, p in enumerate(mid):
            a = mid[max(i - 1, 0)]
            b = mid[min(i + 1, len(mid) - 1)]
            ux, uz = unit(a, b) if math.dist(a, b) > 0 else (0.0, 0.0)
            lane.append((p[0] - uz * off, p[1] + ux * off))
        return (
            lane,
            total - s0 - s1,
            start,
            end,
            unit(pts[0], pts[1]),
            unit(pts[-2], pts[-1]),
        )

    def check(self):
        d = self.d
        if d.get("format") != "city-plan/1":
            self.bad("format is not city-plan/1")
        for key in ("nodes", "edges", "intersections", "blocks", "sidewalks"):
            self.unique(key, d[key])
        for key in ("parcels", "pois", "districts", "turfs"):
            self.unique(key, d.get(key, []))
        self.unique("lanes", [ln for e in d["edges"] for ln in e["lanes"]])
        for part in (
            self.check_edges,
            self.check_intersections,
            self.check_lanes,
            self.check_blocks,
            self.check_pois,
            self.check_portals,
            self.check_bounds,
            self.check_districts,
        ):
            try:
                part()
            except (
                KeyError,
                IndexError,
                TypeError,
                ValueError,
                ZeroDivisionError,
            ) as exc:
                self.bad(f"{part.__name__} could not finish: {exc!r}")
        return self.err

    def check_edges(self):
        for e in self.d["edges"]:
            for end in ("a", "b"):
                if e[end] not in self.nodes:
                    self.bad(f"edge {e['id']}: unknown node {e[end]}")
            if e.get("class") not in CLASSES:
                self.bad(f"edge {e['id']}: unknown class {e.get('class')}")
            if e.get("structure") not in STRUCTURES:
                self.bad(f"edge {e['id']}: unknown structure {e.get('structure')}")
            if any(len(p) != 3 for p in e.get("points", [])):
                self.bad(f"edge {e['id']}: points must be [x, y, z]")
            per_dir = defaultdict(list)
            for ln in e["lanes"]:
                per_dir[ln["dir"]].append(ln["index"])
            if e["oneway"] and set(per_dir) != {"ab"}:
                self.bad(f"edge {e['id']}: one-way edge with lanes not all ab")
            for dr, idx in per_dir.items():
                if sorted(idx) != list(range(len(idx))):
                    self.bad(f"edge {e['id']}: lane indices {dr} not 0..n-1")
        for n in self.d["nodes"]:
            if n.get("kind") not in NODE_KINDS:
                self.bad(f"node {n['id']}: unknown kind {n.get('kind')}")

    def check_intersections(self):
        touching = defaultdict(set)
        for e in self.d["edges"]:
            touching[e["a"]].add(e["id"])
            touching[e["b"]].add(e["id"])
        for node, edges in touching.items():
            it = self.inters.get(node)
            if it is None:
                self.bad(f"node {node}: no intersection record")
                continue
            if it.get("control") not in CONTROLS:
                self.bad(f"{node}: unknown control {it.get('control')}")
            legs = {leg["edge"] for leg in it["legs"]}
            if legs != edges:
                self.bad(f"intersection {node}: legs {sorted(legs)} != {sorted(edges)}")
            approaches = []
            crosswalks = set()
            for leg in it["legs"]:
                e = self.edges[leg["edge"]]
                entering = "ab" if e["b"] == node else "ba"
                lanes_in = any(ln["dir"] == entering for ln in e["lanes"])
                ap = leg["approach"]
                if lanes_in != (ap is not None):
                    self.bad(f"{node}/{e['id']}: approach presence wrong")
                if ap is not None:
                    approaches.append(ap["id"])
                    if ap["dir"] != entering:
                        self.bad(f"{ap['id']}: dir should be {entering}")
                    if ap["stop_line_m"] < leg["box_m"] - TOL:
                        self.bad(f"{ap['id']}: stop line inside the box")
                cw = leg["crosswalk"]
                if it["control"] == "none":
                    if cw is not None:
                        self.bad(f"{node}: crosswalk at an uncontrolled node")
                    if ap is not None and abs(ap["stop_line_m"] - leg["box_m"]) > TOL:
                        self.bad(f"{node}: uncontrolled stop line not at the box edge")
                elif cw is not None:
                    crosswalks.add(cw["id"])
                    if not leg["box_m"] <= cw["from_m"] < cw["to_m"]:
                        self.bad(f"{cw['id']}: band not outside the box")
                    if ap is not None and cw["to_m"] > ap["stop_line_m"]:
                        self.bad(f"{cw['id']}: band beyond the stop line")
                self.check_leg_straight(node, e, leg)
            if it["control"] == "signal":
                self.check_signal(it, approaches, crosswalks)
            elif "signal" in it:
                self.bad(f"{node}: signal program without signal control")

    def check_leg_straight(self, node, e, leg):
        """The box, crosswalk band and stop line of a leg lie on its first straight piece."""
        pts = self.centreline(e)
        if e["b"] == node:
            pts = pts[::-1]
        reach = max(
            leg["box_m"],
            (leg["crosswalk"] or {}).get("to_m", 0.0),
            (leg["approach"] or {}).get("stop_line_m", 0.0),
        )
        if reach > math.dist(pts[0], pts[1]) + TOL:
            self.bad(
                f"{node}/{e['id']}: box, crosswalk or stop line past the first straight"
            )

    def check_signal(self, it, approaches, crosswalks):
        sig = it.get("signal")
        if not sig:
            self.bad(f"{it['id']}: signal control without a program")
            return
        greens = [a for ph in sig["phases"] for a in ph["green"]]
        if sorted(greens) != sorted(approaches):
            self.bad(f"{it['id']}: every approach must be green in exactly one phase")
        for ph in sig["phases"]:
            if ph["green_s"] <= 0:
                self.bad(f"{it['id']}: phase with no green time")
            for cw in ph["walk"]:
                if cw not in crosswalks:
                    self.bad(f"{it['id']}: walk refers to unknown crosswalk {cw}")
        if sig["amber_s"] <= 0 or sig["all_red_s"] < 0:
            self.bad(f"{it['id']}: bad amber or all-red time")

    def successors(self, frames):
        """Lane-to-lane movements allowed by the turn rules of FORMAT.md, plus the way
        out and back in at each portal (the road goes on on another map)."""
        leaving = defaultdict(list)
        for lid, f in frames.items():
            leaving[f[2]].append(lid)
        kinds = {n["id"]: n["kind"] for n in self.d["nodes"]}
        succ = defaultdict(set)
        for lid, (_, _, _, end, _, (ux, uz)) in frames.items():
            e, ln = self.lanes[lid]
            if kinds[end] == "portal":
                succ[lid].update(
                    x for x in leaving[end] if self.lanes[x][0]["id"] == e["id"]
                )
                continue
            n_in = sum(1 for x in e["lanes"] if x["dir"] == ln["dir"])
            bend = len(self.inters[end]["legs"]) == 2
            exits = defaultdict(list)
            for nxt in leaving[end]:
                if self.lanes[nxt][0]["id"] != e["id"]:
                    exits[self.lanes[nxt][0]["id"]].append(nxt)
            for out in exits.values():
                ox, oz = frames[out[0]][4]
                theta = math.degrees(math.atan2(ux * oz - uz * ox, ux * ox + uz * oz))
                ordered = sorted(out, key=lambda x: self.lanes[x][1]["index"])
                n_out = len(ordered)
                i = ln["index"]
                if bend or abs(theta) <= 30.0:
                    succ[lid].add(ordered[max(0, min(i, n_out - 1))])
                elif 30.0 < theta <= 150.0 and i == n_in - 1:
                    succ[lid].add(ordered[-1])
                elif -150.0 <= theta < -30.0 and i == 0:
                    succ[lid].add(ordered[0])
        return succ

    def check_lanes(self):
        frames = {lid: self.lane_frame(lid) for lid in self.lanes}
        for lid, f in frames.items():
            if f[1] < 5.0:
                self.bad(f"lane {lid}: length {f[1]:.2f} m under 5 m")
        succ = self.successors(frames)
        kinds = {n["id"]: n["kind"] for n in self.d["nodes"]}
        for lid in self.lanes:
            end = frames[lid][3]
            if not succ[lid] and kinds[end] != "end":
                self.bad(f"lane {lid}: no way out at {end}")
        # every lane reachable from every other (one connected traffic network)
        start = next(iter(self.lanes))
        for graph in (succ, self.reverse(succ)):
            seen, todo = {start}, [start]
            while todo:
                for nxt in graph[todo.pop()]:
                    if nxt not in seen:
                        seen.add(nxt)
                        todo.append(nxt)
            if len(seen) != len(self.lanes):
                self.bad(f"lane network not strongly connected ({len(seen)} lanes)")

    @staticmethod
    def reverse(succ):
        pred = defaultdict(set)
        for a, bs in succ.items():
            for b in bs:
                pred[b].add(a)
        return pred

    def check_blocks(self):
        for sw in self.d["sidewalks"]:
            blk = self.blocks.get(sw["block"])
            if blk is None:
                self.bad(f"sidewalk {sw['id']}: unknown block")
                continue
            if not all(inside(blk["poly"], x, z) for x, z in sw["ring"]):
                self.bad(f"sidewalk {sw['id']}: ring leaves its block")
        for p in self.d["parcels"]:
            blk = self.blocks.get(p["block"])
            if blk is None or not all(inside(blk["poly"], x, z) for x, z in p["poly"]):
                self.bad(f"parcel {p['id']}: outside its block")
            if p["zoning"] not in ZONINGS:
                self.bad(f"parcel {p['id']}: unknown zoning {p['zoning']}")
            lo, hi = p["height_range_m"]
            if p["zoning"] in BUILT:
                if not lo <= p["height_m"] <= hi or p["height_m"] <= 0:
                    self.bad(f"parcel {p['id']}: height outside its range")
            elif p["height_m"] != 0:
                self.bad(f"parcel {p['id']}: open parcel with a height")
            if p["interior"]:
                self.check_interior(p)

    def check_interior(self, p):
        foot = inset_rect(p["poly"], p["setback_m"])
        it = p["interior"]
        dx, dz = it["door"]["p"]
        if not on_outline(foot, dx, dz):
            self.bad(f"parcel {p['id']}: door not on the footprint outline")
        hx, hz = heading_vec(it["door"]["heading_deg"])
        if not inside(foot, dx + hx, dz + hz, tol=0.0):
            self.bad(f"parcel {p['id']}: door heading does not point inside")
        for room in it["rooms"]:
            if not all(inside(foot, x, z) for x, z in room["poly"]):
                self.bad(f"parcel {p['id']}: room {room['id']} outside the footprint")
            if room["ceiling_m"] - room["floor_m"] < 2.6:
                self.bad(f"parcel {p['id']}: room {room['id']} lower than 2.6 m")
        for name, (x, _, z) in it["points"].items():
            if not any(inside(r["poly"], x, z) for r in it["rooms"]):
                self.bad(f"parcel {p['id']}: point {name} not in a room")

    def surface_at(self, x, z):
        """'road', 'block' or None for a ground point of the plan."""
        for lid in self.lanes:
            pts = self.lane_frame(lid)[0]
            w = self.lanes[lid][0]["lane_width_m"]
            if any(
                seg_dist(x, z, *p, *q) <= w / 2.0 + TOL
                for p, q in itertools.pairwise(pts)
            ):
                return "road"
        if any(inside(b["poly"], x, z) for b in self.d["blocks"]):
            return "block"
        return None

    def check_pois(self):
        races = defaultdict(list)
        for poi in self.d["pois"]:
            kind = poi["kind"]
            need = POI_FIELDS.get(kind)
            if need is None:
                self.bad(f"poi {poi['id']}: unknown kind {kind}")
                continue
            missing = need - set(poi)
            if missing:
                self.bad(f"poi {poi['id']}: missing {sorted(missing)}")
            x, _, z = poi["p"]
            if kind != "portal" and self.surface_at(x, z) is None:
                self.bad(f"poi {poi['id']}: p is not on a road or a block")
            for key in ("exit", "driveway"):
                if key in poi:
                    lane = poi[key]["lane"]
                    if lane not in self.lanes:
                        self.bad(f"poi {poi['id']}: {key} on unknown lane {lane}")
                    elif not 0 <= poi[key]["s"] <= self.lane_frame(lane)[1]:
                        self.bad(f"poi {poi['id']}: {key} s outside the lane")
            if "parcel" in poi and poi["parcel"] not in self.parcels:
                self.bad(f"poi {poi['id']}: unknown parcel")
            if kind in ("shop", "safehouse", "bank"):
                interior = self.parcels[poi["parcel"]]["interior"]
                if not interior:
                    self.bad(f"poi {poi['id']}: parcel has no interior")
                elif kind == "bank" and poi["vault"] not in [
                    r["id"] for r in interior["rooms"]
                ]:
                    self.bad(f"poi {poi['id']}: vault room missing")
                elif kind != "bank" and poi["point"] not in interior["points"]:
                    self.bad(f"poi {poi['id']}: interior point missing")
            if kind == "checkpoint":
                races[poi["race"]].append(poi["index"])
        for race, idx in races.items():
            if sorted(idx) != list(range(1, len(idx) + 1)):
                self.bad(f"race {race}: checkpoint indices not 1..n")

    def check_portals(self):
        """Portal nodes end one edge on the map's edge, uncontrolled, and one portal point
        of interest names each; portal points of interest name a portal node and a link."""
        (x0, z0), (x1, z1) = self.d["bounds"]["min"], self.d["bounds"]["max"]
        named = defaultdict(list)
        for poi in self.d["pois"]:
            if poi["kind"] != "portal":
                continue
            node = self.nodes.get(poi.get("node"))
            if node is None or node["kind"] != "portal":
                self.bad(f"poi {poi['id']}: names {poi.get('node')}, not a portal node")
                continue
            named[node["id"]].append(poi["id"])
            if not isinstance(poi.get("link"), str) or not poi["link"]:
                self.bad(f"poi {poi['id']}: no link")
            if (
                math.dist((poi["p"][0], poi["p"][2]), (node["p"][0], node["p"][2]))
                > 0.5
            ):
                self.bad(f"poi {poi['id']}: p is not at its node")
        for n in self.d["nodes"]:
            if n["kind"] != "portal":
                continue
            x, _, z = n["p"]
            if min(abs(x - x0), abs(x - x1), abs(z - z0), abs(z - z1)) > TOL:
                self.bad(f"portal {n['id']}: not on the edge of bounds")
            inter = self.inters.get(n["id"])
            if inter is None or len(inter["legs"]) != 1:
                self.bad(f"portal {n['id']}: must end exactly one edge")
            elif inter["control"] != "none" or inter["legs"][0]["box_m"] != 0:
                self.bad(f"portal {n['id']}: must be uncontrolled with box_m 0")
            if len(named[n["id"]]) != 1:
                self.bad(
                    f"portal {n['id']}: named by {len(named[n['id']])} points of interest"
                )

    def check_bounds(self):
        """Everything the plan places lies inside bounds."""
        (x0, z0), (x1, z1) = self.d["bounds"]["min"], self.d["bounds"]["max"]

        def out(x, z):
            return not (x0 - TOL <= x <= x1 + TOL and z0 - TOL <= z <= z1 + TOL)

        for n in self.d["nodes"]:
            if out(n["p"][0], n["p"][2]):
                self.bad(f"node {n['id']}: outside the bounds")
        for e in self.d["edges"]:
            if any(out(p[0], p[2]) for p in e.get("points", [])):
                self.bad(f"edge {e['id']}: a point outside the bounds")
        for key in ("blocks", "parcels"):
            for item in self.d[key]:
                if any(out(x, z) for x, z in item["poly"]):
                    self.bad(f"{key[:-1]} {item['id']}: outside the bounds")
        for poi in self.d["pois"]:
            if out(poi["p"][0], poi["p"][2]):
                self.bad(f"poi {poi['id']}: outside the bounds")

    def check_districts(self):
        (x0, z0), (x1, z1) = self.d["bounds"]["min"], self.d["bounds"]["max"]
        polys = [dd["poly"] for dd in self.d["districts"]]
        steps = 20
        for i in range(steps + 1):
            for j in range(steps + 1):
                x = x0 + (x1 - x0) * i / steps
                z = z0 + (z1 - z0) * j / steps
                if not any(inside(p, x, z) for p in polys):
                    self.bad(f"point ({x:.1f}, {z:.1f}) is in no district")
                    return


def gdd_problems(gdd_text, plans):
    """Points of interest the design document names: each must be in the plan of its map.

    Returns (problems, still to come): problems for the maps given, and the ids of maps
    not given.
    """
    problems = []
    listed = {i for ids in GDD_POIS.values() for i in ids}
    for found in sorted(set(POI_LIKE.findall(gdd_text))):
        if found not in listed and not any(found.startswith(r) for r in GDD_RANGES):
            problems.append(f"GDD names {found}, which no map lists")
    for ident in sorted(listed):
        rng = next((r for r in GDD_RANGES if ident.startswith(r)), None)
        if rng is None and f"`{ident}`" not in gdd_text:
            problems.append(f"{ident} is listed but the GDD does not name it")
        if rng and f"`{rng}1`" not in gdd_text:
            problems.append(f"the GDD does not name the {rng} range")
    by_map = {p["map"]: {poi["id"] for poi in p["pois"]} for p in plans}
    pending = {}
    for map_id, ids in GDD_POIS.items():
        if map_id not in by_map:
            pending[map_id] = ids
            continue
        for ident in ids:
            if ident not in by_map[map_id]:
                problems.append(f"{map_id}: point of interest {ident} missing")
    return problems, pending


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--gdd", type=Path, help="also cross-check the design document's ids"
    )
    ap.add_argument("plans", nargs="+")
    a = ap.parse_args(argv)
    failed = False
    loaded = []
    for path in a.plans:
        with open(path) as f:
            data = json.load(f)
        loaded.append(data)
        plan = Plan(data)
        errors = plan.check()
        for msg in errors:
            print(f"{path}: {msg}")
        lanes = len(plan.lanes)
        print(
            f"{path}: {len(errors)} problems ({lanes} lanes, {len(plan.parcels)} parcels)"
        )
        failed = failed or bool(errors)
    if a.gdd:
        problems, pending = gdd_problems(a.gdd.read_text(), loaded)
        for msg in problems:
            print(f"{a.gdd}: {msg}")
        for map_id, ids in pending.items():
            print(
                f"{a.gdd}: {map_id} (no plan yet): {len(ids)} points of interest to come"
            )
        print(f"{a.gdd}: {len(problems)} problems")
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
