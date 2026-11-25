"""QA-side reading of the plan file: lanes, approaches and stop lines, sidewalks, parcels.

Written independently of the game's plan.gd from the plan's "conventions" block, so the
checks measure the game against the plan rather than against the game's own reading of it.
"""
import json
import math


def _norm(x, z):
    l = math.hypot(x, z)
    return (x / l, z / l)


class PlanGeom:
    def __init__(self, path):
        self.data = json.load(open(path))
        d = self.data
        self.nodes = {n["id"]: (n["p"][0], n["p"][2]) for n in d["nodes"]}
        self.junctions = {j["id"]: j for j in d["intersections"]}
        self.edges = {e["id"]: e for e in d["edges"]}
        self.lanes = {}        # id -> dict(p0, p1, t, right, length, approach, elev)
        for e in d["edges"]:
            a, b = self.nodes[e["a"]], self.nodes[e["b"]]
            t_ab = _norm(b[0] - a[0], b[1] - a[1])
            lw = e["lane_width_m"]
            for ln in e["lanes"]:
                fwd = ln["dir"] == "ab"
                s_node, e_node = (e["a"], e["b"]) if fwd else (e["b"], e["a"])
                t = t_ab if fwd else (-t_ab[0], -t_ab[1])
                right = (-t[1], t[0])
                off = (ln["index"] + 0.5) * lw
                ps, pe = self.nodes[s_node], self.nodes[e_node]
                sl0 = self.junctions[s_node]["stop_line_m"]
                sl1 = self.junctions[e_node]["stop_line_m"]
                p0 = (ps[0] + t[0] * sl0 + right[0] * off, ps[1] + t[1] * sl0 + right[1] * off)
                p1 = (pe[0] - t[0] * sl1 + right[0] * off, pe[1] - t[1] * sl1 + right[1] * off)
                self.lanes[ln["id"]] = {"id": ln["id"], "p0": p0, "p1": p1, "t": t, "right": right,
                                        "length": math.hypot(p1[0] - p0[0], p1[1] - p0[1]),
                                        "approach": f"{e_node}<{e['id']}", "elev": e["elevation_m"],
                                        "junction": e_node}
        self.approaches = {}
        for j in d["intersections"]:
            jp = self.nodes[j["node"]]
            for ap in j["approaches"]:
                e = self.edges[ap["edge"]]
                a, b = self.nodes[e["a"]], self.nodes[e["b"]]
                t = _norm(b[0] - a[0], b[1] - a[1])
                if ap["dir"] == "ba":
                    t = (-t[0], -t[1])
                per_dir = sum(1 for ln in e["lanes"] if ln["dir"] == "ab")
                stop = (jp[0] - t[0] * j["stop_line_m"], jp[1] - t[1] * j["stop_line_m"])
                self.approaches[ap["id"]] = {"id": ap["id"], "junction": j["id"], "t": t,
                                             "right": (-t[1], t[0]), "stop": stop,
                                             "half_w": per_dir * e["lane_width_m"],
                                             "signalised": j["signalised"]}
        self.sidewalks = d["sidewalks"]
        self.parcels = d["parcels"]
        self.blocks = d["blocks"]
        self.pois = {p["id"]: p for p in d["pois"]}

    # ---- lanes
    def lane_offset(self, x, z, heading=None):
        """Smallest |lateral offset| to a lane centreline among lanes whose extent covers the
        point (outside junction boxes). Returns (offset, lane_id, aligned) or None."""
        best = None
        for ln in self.lanes.values():
            dx, dz = x - ln["p0"][0], z - ln["p0"][1]
            s = dx * ln["t"][0] + dz * ln["t"][1]
            if s < 0 or s > ln["length"]:
                continue
            lat = dx * ln["right"][0] + dz * ln["right"][1]
            if abs(lat) > 1.75 * 1.6:
                continue
            aligned = None
            if heading is not None:
                aligned = heading[0] * ln["t"][0] + heading[1] * ln["t"][1] > 0.7
                if not aligned:
                    continue
            if best is None or abs(lat) < abs(best[0]):
                best = (lat, ln["id"], aligned)
        return best

    def in_junction_box(self, x, z, margin=0.0):
        for j in self.junctions.values():
            jx, jz = self.nodes[j["node"]]
            h = j["stop_line_m"] + margin
            if abs(x - jx) <= h and abs(z - jz) <= h:
                return j["id"]
        return None

    def stop_line_side(self, ap_id, x, z):
        """Signed distance past the stop line (along travel) and lateral offset from the road
        centreline (positive to the right, the approach's own lanes are 0..half_w)."""
        ap = self.approaches[ap_id]
        dx, dz = x - ap["stop"][0], z - ap["stop"][1]
        return (dx * ap["t"][0] + dz * ap["t"][1], dx * ap["right"][0] + dz * ap["right"][1])

    # ---- walkable surfaces
    def on_sidewalk(self, x, z, tol=0.3):
        for b in self.blocks:
            (x0, z0), _, (x1, z1), _ = b["poly"]
            if x0 - tol <= x <= x1 + tol and z0 - tol <= z <= z1 + tol:
                return True
        return False

    def sidewalk_ring_points(self, step=10.0):
        pts = []
        for sw in self.sidewalks:
            ring = sw["ring"]
            for i in range(len(ring)):
                a, b = ring[i], ring[(i + 1) % len(ring)]
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                n = max(1, int(L // step))
                for k in range(n):
                    u = k / n
                    pts.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, sw["elevation_m"], sw["id"]))
        return pts

    def centreline_points(self, step=10.0):
        pts = []
        for ln in self.lanes.values():
            n = max(1, int(ln["length"] // step))
            for k in range(n + 1):
                u = k / n
                pts.append((ln["p0"][0] + (ln["p1"][0] - ln["p0"][0]) * u,
                            ln["p0"][1] + (ln["p1"][1] - ln["p0"][1]) * u, ln["elev"], ln["id"]))
        return pts

    def parcel_centres(self):
        out = []
        for p in self.parcels:
            (x0, z0), _, (x1, z1), _ = p["poly"]
            out.append(((x0 + x1) / 2, (z0 + z1) / 2, p["base_m"] + p["height_m"], p))
        return out
