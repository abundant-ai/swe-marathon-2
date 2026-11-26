"""Check a city-plan/1 file against the rules of common/design/plan/FORMAT.md.

Author tool (never packaged). Prints one line per problem and exits 1 if there is any.

Usage: python scripts/check_plan.py common/design/plan/downtown.json [more plans]
"""

import json
import math
import sys
from collections import defaultdict

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

    def lane_frame(self, lane_id):
        e, ln = self.lanes[lane_id]
        start, end = (e["a"], e["b"]) if ln["dir"] == "ab" else (e["b"], e["a"])
        ps, pe = self.nodes[start]["p"], self.nodes[end]["p"]
        dx, dz = pe[0] - ps[0], pe[2] - ps[2]
        full = math.hypot(dx, dz)
        ux, uz = dx / full, dz / full
        n = len(e["lanes"])
        w = e["lane_width_m"]
        off = (ln["index"] + 0.5 - (n / 2.0 if e["oneway"] else 0.0)) * w
        s0 = self.leg(start, e["id"])["box_m"]
        s1 = (self.leg(end, e["id"])["approach"] or {}).get("stop_line_m", 0.0)
        ox, oz = ps[0] + ux * s0 - uz * off, ps[2] + uz * s0 + ux * off
        return (ox, oz), (ux, uz), full - s0 - s1, start, end

    def leg(self, node, edge):
        for leg in self.inters[node]["legs"]:
            if leg["edge"] == edge:
                return leg
        raise KeyError((node, edge))

    def check(self):
        d = self.d
        if d.get("format") != "city-plan/1":
            self.bad("format is not city-plan/1")
        for key in ("nodes", "edges", "intersections", "blocks", "sidewalks"):
            self.unique(key, d[key])
        self.unique("parcels", d["parcels"])
        self.unique("pois", d["pois"])
        self.unique("lanes", [ln for e in d["edges"] for ln in e["lanes"]])
        self.check_edges()
        self.check_intersections()
        self.check_lanes()
        self.check_blocks()
        self.check_pois()
        self.check_districts()
        return self.err

    def check_edges(self):
        for e in self.d["edges"]:
            for end in ("a", "b"):
                if e[end] not in self.nodes:
                    self.bad(f"edge {e['id']}: unknown node {e[end]}")
            per_dir = defaultdict(list)
            for ln in e["lanes"]:
                per_dir[ln["dir"]].append(ln["index"])
            if e["oneway"] and set(per_dir) != {"ab"}:
                self.bad(f"edge {e['id']}: one-way edge with lanes not all ab")
            for dr, idx in per_dir.items():
                if sorted(idx) != list(range(len(idx))):
                    self.bad(f"edge {e['id']}: lane indices {dr} not 0..n-1")

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
            if it["control"] == "signal":
                self.check_signal(it, approaches, crosswalks)
            elif "signal" in it:
                self.bad(f"{node}: signal program without signal control")

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
        """Lane-to-lane movements allowed by the turn rules of FORMAT.md."""
        leaving = defaultdict(list)
        for lid, (_, _, _, start, _) in frames.items():
            leaving[start].append(lid)
        succ = defaultdict(set)
        for lid, (_, (ux, uz), _, _, end) in frames.items():
            e, ln = self.lanes[lid]
            n_in = sum(1 for x in e["lanes"] if x["dir"] == ln["dir"])
            bend = len(self.inters[end]["legs"]) == 2
            exits = defaultdict(list)
            for nxt in leaving[end]:
                if self.lanes[nxt][0]["id"] != e["id"]:
                    exits[self.lanes[nxt][0]["id"]].append(nxt)
            for out in exits.values():
                ox, oz = frames[out[0]][1]
                theta = math.degrees(math.atan2(ux * oz - uz * ox, ux * ox + uz * oz))
                by_index = {self.lanes[x][1]["index"]: x for x in out}
                n_out = len(out)
                i = ln["index"]
                if bend or abs(theta) <= 30.0:
                    succ[lid].add(by_index[min(i, n_out - 1)])
                elif 30.0 < theta <= 150.0 and i == n_in - 1:
                    succ[lid].add(by_index[n_out - 1])
                elif -150.0 <= theta < -30.0 and i == 0:
                    succ[lid].add(by_index[0])
        return succ

    def check_lanes(self):
        frames = {lid: self.lane_frame(lid) for lid in self.lanes}
        for lid, (_, _, length, _, _) in frames.items():
            if length < 5.0:
                self.bad(f"lane {lid}: length {length:.2f} m under 5 m")
        succ = self.successors(frames)
        kinds = {n["id"]: n["kind"] for n in self.d["nodes"]}
        for lid in self.lanes:
            end = frames[lid][4]
            if not succ[lid] and kinds[end] not in ("end", "portal"):
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
            (ox, oz), (ux, uz), length, _, _ = self.lane_frame(lid)
            w = self.lanes[lid][0]["lane_width_m"]
            s = (x - ox) * ux + (z - oz) * uz
            lat = abs(-(x - ox) * uz + (z - oz) * ux)
            if -1.0 <= s <= length + 1.0 and lat <= w / 2.0 + TOL:
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
            if self.surface_at(x, z) is None:
                self.bad(f"poi {poi['id']}: p is not on a road or a block")
            for key in ("exit", "driveway"):
                if key in poi:
                    lane = poi[key]["lane"]
                    if lane not in self.lanes:
                        self.bad(f"poi {poi['id']}: {key} on unknown lane {lane}")
                    elif not 0 <= poi[key]["s"] <= self.lane_frame(lane)[2]:
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


def main(paths):
    failed = False
    for path in paths:
        with open(path) as f:
            plan = Plan(json.load(f))
        errors = plan.check()
        for msg in errors:
            print(f"{path}: {msg}")
        lanes = len(plan.lanes)
        print(
            f"{path}: {len(errors)} problems ({lanes} lanes, {len(plan.parcels)} parcels)"
        )
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
