"""Generate the Downtown core block in the city-plan/1 format.

Author tool (never packaged). The format is defined in common/design/plan/FORMAT.md.
The layout below is the public Downtown core: a 4 x 4 junction grid with uneven spacing,
mixed road classes (arterials, two-way streets, one one-way street), signalised and
all-way-stop junctions, nine city blocks, parcels with zoning and interiors, and the
points of interest the missions and shops use. --seed only draws building heights, parcel
splits and signal offsets; the output never names it.

Usage: python scripts/gen_plan.py --out common/design/plan/downtown.json
"""

import argparse
import json
import math
import random
from pathlib import Path

FORMAT = "city-plan/1"
CURB_M = 0.15
SIDEWALK_W = 3.0
SETBACK_M = 3.0
CROSSWALK_GAP_M = 0.5
CROSSWALK_W = 3.0
STOP_GAP_M = 1.0

# Road classes: lanes per direction (one-way: total lanes), lane width, speed limit.
ROAD = {
    "arterial": {"lanes": 2, "width": 3.5, "speed": 50, "oneway": False},
    "street": {"lanes": 1, "width": 3.25, "speed": 40, "oneway": False},
    "oneway": {"lanes": 2, "width": 3.25, "speed": 40, "oneway": True},
}
RANK = {"arterial": 2, "oneway": 1, "street": 1}

# Columns run north-south (constant x), rows run east-west (constant z). Row 0 is north.
XS = [-190.0, -70.0, 60.0, 180.0]
ZS = [-180.0, -60.0, 50.0, 170.0]
COL_CLASS = ["street", "arterial", "street", "street"]
ROW_CLASS = ["street", "oneway", "arterial", "street"]

ZONING = {
    "commercial": [14.0, 60.0],
    "residential": [9.0, 30.0],
    "civic": [10.0, 22.0],
    "industrial": [6.0, 14.0],
    "plaza": [0.0, 0.0],
    "park": [0.0, 0.0],
    "parking": [0.0, 0.0],
}
BUILT = {"commercial", "residential", "civic", "industrial"}

# Parcel zoning per block, quadrants in the order NW, NE, SW, SE. A single entry means one
# parcel covers the block.
BLOCKS = {
    "b_00": ["residential", "residential", "commercial", "residential"],
    "b_10": ["commercial", "residential", "commercial", "commercial"],
    "b_20": ["civic", "residential", "residential", "commercial"],
    "b_01": ["commercial", "parking", "commercial", "commercial"],
    "b_11": ["plaza"],
    "b_21": ["civic", "commercial", "commercial", "commercial"],
    "b_02": ["commercial", "parking", "residential", "residential"],
    "b_12": ["civic", "commercial", "commercial", "parking"],
    "b_22": ["parking", "commercial", "residential", "parking"],
}
QUADS = ["NW", "NE", "SW", "SE"]

# Points of interest placed on parcels: (block, quadrant) -> spec.
PARCEL_POIS = {
    ("b_00", "NW"): {
        "id": "safehouse_downtown",
        "kind": "safehouse",
        "room": (8.0, 8.0),
    },
    ("b_00", "SW"): {"id": "shop_food_downtown", "kind": "shop", "shop": "food"},
    ("b_10", "NW"): {"id": "shop_clothes_downtown", "kind": "shop", "shop": "clothes"},
    ("b_20", "NW"): {"id": "hospital_downtown", "kind": "hospital"},
    ("b_01", "NW"): {"id": "shop_weapons_downtown", "kind": "shop", "shop": "weapons"},
    ("b_01", "NE"): {"id": "garage_downtown", "kind": "garage"},
    ("b_21", "NW"): {"id": "bank_downtown", "kind": "bank"},
    ("b_02", "NE"): {"id": "d1_pickup", "kind": "mission_point"},
    ("b_12", "NW"): {"id": "police_station_downtown", "kind": "police_station"},
    ("b_12", "SE"): {"id": "h1_car", "kind": "mission_point"},
    ("b_22", "NW"): {"id": "h1_stash", "kind": "mission_point"},
    ("b_22", "SE"): {"id": "d1_dropoff", "kind": "mission_point"},
}


def nid(c, r):
    return f"j_{c}{r}"


def heading_of(dx, dz):
    """Heading in degrees clockwise from north (-z) of a horizontal direction."""
    return round(math.degrees(math.atan2(dx, -dz)) % 360.0, 3)


def half_width(cls):
    spec = ROAD[cls]
    if spec["oneway"]:
        return spec["lanes"] * spec["width"] / 2.0
    return spec["lanes"] * spec["width"]


def build_network():
    nodes, edges = [], []
    for r, z in enumerate(ZS):
        for c, x in enumerate(XS):
            nodes.append({"id": nid(c, r), "p": [x, 0.0, z], "kind": "junction"})

    def add_edge(a, b, cls):
        spec = ROAD[cls]
        eid = f"e_{a[2:]}_{b[2:]}"
        dirs = ["ab"] if spec["oneway"] else ["ab", "ba"]
        lanes = [
            {"id": f"{eid}:{d}{k}", "dir": d, "index": k}
            for d in dirs
            for k in range(spec["lanes"])
        ]
        edges.append(
            {
                "id": eid,
                "a": a,
                "b": b,
                "class": "arterial" if cls == "arterial" else "street",
                "oneway": spec["oneway"],
                "lane_width_m": spec["width"],
                "speed_kmh": spec["speed"],
                "surface": "asphalt",
                "structure": "ground",
                "points": [],
                "lanes": lanes,
                "_cls": cls,
            }
        )

    for c in range(len(XS)):
        for r in range(len(ZS) - 1):
            add_edge(nid(c, r), nid(c, r + 1), COL_CLASS[c])
    for r in range(len(ZS)):
        for c in range(len(XS) - 1):
            add_edge(nid(c, r), nid(c + 1, r), ROW_CLASS[r])
    return nodes, edges


def build_intersections(nodes, edges, rng):
    pos = {n["id"]: n["p"] for n in nodes}
    incident = {n["id"]: [] for n in nodes}
    for e in edges:
        incident[e["a"]].append(e)
        incident[e["b"]].append(e)
    out = []
    for n in nodes:
        nid_ = n["id"]
        inc = incident[nid_]
        p = pos[nid_]
        has_arterial = any(e["_cls"] == "arterial" for e in inc)
        if len(inc) <= 2:
            control = "none"
            n["kind"] = "bend" if len(inc) == 2 else "end"
        elif has_arterial:
            control = "signal"
        else:
            control = "stop"

        def away(e, p=p, nid_=nid_):
            other = pos[e["b"] if e["a"] == nid_ else e["a"]]
            return other[0] - p[0], other[2] - p[2]

        legs = []
        for e in sorted(inc, key=lambda e: heading_of(*away(e))):
            dx, dz = away(e)
            cross = [
                half_width(o["_cls"])
                for o in inc
                if o is not e and abs(dx * away(o)[0] + dz * away(o)[1]) < 1e-6
            ]
            box = max(cross) if cross else 0.0
            entering = "ab" if e["b"] == nid_ else "ba"
            has_lanes_in = any(ln["dir"] == entering for ln in e["lanes"])
            if control == "none":
                crosswalk = None
                stop = box
            else:
                crosswalk = {
                    "id": f"cw_{nid_}_{e['id']}",
                    "from_m": box + CROSSWALK_GAP_M,
                    "to_m": box + CROSSWALK_GAP_M + CROSSWALK_W,
                }
                stop = crosswalk["to_m"] + STOP_GAP_M
            approach = None
            if has_lanes_in:
                approach = {
                    "id": f"{nid_}<{e['id']}",
                    "dir": entering,
                    "stop_line_m": stop,
                }
            legs.append(
                {
                    "edge": e["id"],
                    "box_m": box,
                    "crosswalk": crosswalk,
                    "approach": approach,
                }
            )
        rec = {"id": nid_, "node": nid_, "control": control, "legs": legs}
        if control == "signal":
            phases = []
            for leg in legs:
                if leg["approach"] is None:
                    continue
                cls = next(e["_cls"] for e in inc if e["id"] == leg["edge"])
                phases.append(
                    {
                        "green": [leg["approach"]["id"]],
                        "walk": [],
                        "green_s": 12.0 if cls == "arterial" else 9.0,
                    }
                )
            walk = [leg["crosswalk"]["id"] for leg in legs if leg["crosswalk"]]
            phases.append({"green": [], "walk": walk, "green_s": 7.0})
            cycle = sum(ph["green_s"] + 3.0 + 1.0 for ph in phases)
            rec["signal"] = {
                "phases": phases,
                "amber_s": 3.0,
                "all_red_s": 1.0,
                "offset_s": round(rng.uniform(0.0, cycle), 1),
            }
        out.append(rec)
    return out


def rect(x0, z0, x1, z1):
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


def block_rect(bc, br):
    x0 = XS[bc] + half_width(COL_CLASS[bc])
    x1 = XS[bc + 1] - half_width(COL_CLASS[bc + 1])
    z0 = ZS[br] + half_width(ROW_CLASS[br])
    z1 = ZS[br + 1] - half_width(ROW_CLASS[br + 1])
    return x0, z0, x1, z1


def facing_side(bc, br, quad):
    """The parcel side (N, S, E, W) that faces the busier of its two outer roads."""
    ns = "N" if quad[0] == "N" else "S"
    ew = "W" if quad[1] == "W" else "E"
    row = br if ns == "N" else br + 1
    col = bc if ew == "W" else bc + 1
    if RANK[COL_CLASS[col]] > RANK[ROW_CLASS[row]]:
        return ew
    return ns


INWARD = {"N": 180.0, "S": 0.0, "W": 90.0, "E": 270.0}


def side_mid(fx0, fz0, fx1, fz1, side):
    return {
        "N": ((fx0 + fx1) / 2.0, fz0),
        "S": ((fx0 + fx1) / 2.0, fz1),
        "W": (fx0, (fz0 + fz1) / 2.0),
        "E": (fx1, (fz0 + fz1) / 2.0),
    }[side]


def inward_vec(side):
    return {"N": (0.0, 1.0), "S": (0.0, -1.0), "W": (1.0, 0.0), "E": (-1.0, 0.0)}[side]


def room_rect(door, side, depth, width, foot):
    """A room behind the door, depth into the building, width across, inside the walls."""
    fx0, fz0, fx1, fz1 = foot
    ix, iz = inward_vec(side)
    dx, dz = door
    if ix == 0.0:
        x0, x1 = dx - width / 2.0, dx + width / 2.0
        z0, z1 = sorted([dz, dz + iz * depth])
    else:
        z0, z1 = dz - width / 2.0, dz + width / 2.0
        x0, x1 = sorted([dx, dx + ix * depth])
    wall = 0.3
    x0, x1 = max(x0, fx0 + wall), min(x1, fx1 - wall)
    z0, z1 = max(z0, fz0 + wall), min(z1, fz1 - wall)
    return [round(x0, 2), round(z0, 2), round(x1, 2), round(z1, 2)]


def r2(v):
    return [round(a, 3) for a in v]


def build_blocks(rng):
    blocks, sidewalks, parcels, placed = [], [], [], []
    pid = 0
    for br in range(3):
        for bc in range(3):
            bid = f"b_{bc}{br}"
            x0, z0, x1, z1 = block_rect(bc, br)
            blocks.append(
                {"id": bid, "poly": rect(x0, z0, x1, z1), "elevation_m": CURB_M}
            )
            o = SIDEWALK_W / 2.0
            sidewalks.append(
                {
                    "id": f"sw_{bc}{br}",
                    "block": bid,
                    "width_m": SIDEWALK_W,
                    "elevation_m": CURB_M,
                    "ring": rect(x0 + o, z0 + o, x1 - o, z1 - o),
                }
            )
            ix0, iz0 = x0 + SIDEWALK_W, z0 + SIDEWALK_W
            ix1, iz1 = x1 - SIDEWALK_W, z1 - SIDEWALK_W
            zones = BLOCKS[bid]
            if len(zones) == 1:
                cells = [("ALL", (ix0, iz0, ix1, iz1))]
            else:
                mx = round(ix0 + (ix1 - ix0) * rng.uniform(0.4, 0.6), 2)
                mz = round(iz0 + (iz1 - iz0) * rng.uniform(0.4, 0.6), 2)
                cells = [
                    ("NW", (ix0, iz0, mx, mz)),
                    ("NE", (mx, iz0, ix1, mz)),
                    ("SW", (ix0, mz, mx, iz1)),
                    ("SE", (mx, mz, ix1, iz1)),
                ]
            for (quad, (px0, pz0, px1, pz1)), zone in zip(cells, zones):
                lo, hi = ZONING[zone]
                height = round(rng.uniform(lo, hi), 1) if zone in BUILT else 0.0
                parcel = {
                    "id": f"p_{pid:02d}",
                    "block": bid,
                    "zoning": zone,
                    "poly": rect(px0, pz0, px1, pz1),
                    "base_m": CURB_M,
                    "height_m": height,
                    "height_range_m": [lo, hi],
                    "setback_m": SETBACK_M if zone in BUILT else 0.0,
                    "interior": None,
                }
                parcels.append(parcel)
                placed.append((bid, bc, br, quad, parcel))
                pid += 1
    return blocks, sidewalks, parcels, placed


def lane_geometry(edges, nodes, intersections):
    """Start point, unit direction and length of every lane, following FORMAT.md."""
    pos = {n["id"]: n["p"] for n in nodes}
    legs = {}
    for it in intersections:
        for leg in it["legs"]:
            legs[(it["node"], leg["edge"])] = leg
    out = {}
    for e in edges:
        pa, pb = pos[e["a"]], pos[e["b"]]
        n = sum(1 for ln in e["lanes"])
        for ln in e["lanes"]:
            start, end = (e["a"], e["b"]) if ln["dir"] == "ab" else (e["b"], e["a"])
            ps, pe = (pa, pb) if ln["dir"] == "ab" else (pb, pa)
            dx, dz = pe[0] - ps[0], pe[2] - ps[2]
            length = math.hypot(dx, dz)
            ux, uz = dx / length, dz / length
            rx, rz = -uz, ux
            w = e["lane_width_m"]
            if e["oneway"]:
                off = (ln["index"] + 0.5 - n / 2.0) * w
            else:
                off = (ln["index"] + 0.5) * w
            s0 = legs[(start, e["id"])]["box_m"]
            s1 = legs[(end, e["id"])]["approach"]["stop_line_m"]
            origin = (ps[0] + ux * s0 + rx * off, ps[2] + uz * s0 + rz * off)
            out[ln["id"]] = {
                "origin": origin,
                "dir": (ux, uz),
                "length": length - s0 - s1,
                "y": ps[1],
            }
    return out


def lane_point(geo, lane_id, s):
    g = geo[lane_id]
    x = g["origin"][0] + g["dir"][0] * s
    z = g["origin"][1] + g["dir"][1] * s
    return [round(x, 3), g["y"], round(z, 3)], heading_of(*g["dir"])


def nearest_lane(geo, x, z):
    best = None
    for lid, g in geo.items():
        ox, oz = g["origin"]
        ux, uz = g["dir"]
        s = (x - ox) * ux + (z - oz) * uz
        s = min(max(s, 1.0), g["length"] - 1.0)
        px, pz = ox + ux * s, oz + uz * s
        d = math.hypot(x - px, z - pz)
        if best is None or d < best[0]:
            best = (d, lid, round(s, 2))
    return best[1], best[2]


def place_pois(placed, geo):
    pois = []
    for bid, bc, br, quad, parcel in placed:
        spec = PARCEL_POIS.get((bid, quad))
        if spec is None:
            continue
        (px0, pz0), _, (px1, pz1), _ = parcel["poly"]
        centre = ((px0 + px1) / 2.0, (pz0 + pz1) / 2.0)
        side = facing_side(bc, br, quad)
        ix, iz = inward_vec(side)
        kind = spec["kind"]
        poi = {"id": spec["id"], "kind": kind}
        if kind in ("mission_point",):
            poi["p"] = [round(centre[0], 2), CURB_M, round(centre[1], 2)]
            poi["heading_deg"] = INWARD[side]
            poi["radius_m"] = 6.0
            pois.append(poi)
            continue
        if kind == "garage":
            sx, sz = side_mid(px0, pz0, px1, pz1, side)
            zx, zz = sx + ix * 4.0, sz + iz * 4.0
            half_w, half_d = 4.5, 3.5
            if ix == 0.0:
                zone = rect(zx - half_w, zz - half_d, zx + half_w, zz + half_d)
            else:
                zone = rect(zx - half_d, zz - half_w, zx + half_d, zz + half_w)
            lane, s = nearest_lane(geo, sx - ix * 6.0, sz - iz * 6.0)
            poi["p"] = [round(zx, 2), CURB_M, round(zz, 2)]
            poi["heading_deg"] = INWARD[side]
            poi["zone"] = {"poly": [r2(v) for v in zone], "heading_deg": INWARD[side]}
            poi["driveway"] = {"lane": lane, "s": s}
            poi["capacity"] = 2
            pois.append(poi)
            continue
        foot = (px0 + SETBACK_M, pz0 + SETBACK_M, px1 - SETBACK_M, pz1 - SETBACK_M)
        door = side_mid(*foot, side)
        depth, width = spec.get("room", (10.0, 12.0))
        rooms = [
            {
                "id": "main",
                "poly": rect(*room_rect(door, side, depth, width, foot)),
                "floor_m": CURB_M,
                "ceiling_m": CURB_M + 3.6,
            }
        ]
        points = {}
        inside = (door[0] + ix * (depth - 3.0), door[1] + iz * (depth - 3.0))
        if kind == "bank":
            vault_door = (door[0] + ix * depth, door[1] + iz * depth)
            vault = room_rect(vault_door, side, 6.0, 8.0, foot)
            rooms.append(
                {
                    "id": "vault",
                    "poly": rect(*vault),
                    "floor_m": CURB_M,
                    "ceiling_m": CURB_M + 3.0,
                }
            )
        if kind == "shop":
            points["counter"] = [round(inside[0], 2), CURB_M, round(inside[1], 2)]
        if kind == "safehouse":
            points["save"] = [round(inside[0], 2), CURB_M, round(inside[1], 2)]
        # Only shops, safehouses and the bank have interiors (GDD scope); the police
        # station and the hospital keep a front door point outside the facade.
        if kind in ("shop", "safehouse", "bank"):
            parcel["interior"] = {
                "door": {
                    "p": [round(door[0], 2), round(door[1], 2)],
                    "heading_deg": INWARD[side],
                    "width_m": 2.0,
                    "height_m": 2.6,
                },
                "rooms": rooms,
                "points": points,
            }
        outside = [
            round(door[0] - ix * 1.5, 2),
            CURB_M,
            round(door[1] - iz * 1.5, 2),
        ]
        poi["parcel"] = parcel["id"]
        if kind == "shop":
            poi["shop"] = spec["shop"]
            poi["point"] = "counter"
            poi["p"] = points["counter"]
            poi["heading_deg"] = INWARD[side]
        elif kind == "safehouse":
            poi["point"] = "save"
            poi["p"] = points["save"]
            poi["heading_deg"] = INWARD[side]
        elif kind == "bank":
            poi["vault"] = "vault"
            poi["p"] = outside
            poi["heading_deg"] = INWARD[side]
        else:
            lane, s = nearest_lane(geo, door[0] - ix * 9.0, door[1] - iz * 9.0)
            poi["p"] = outside
            poi["heading_deg"] = INWARD[side]
            poi["exit"] = {"lane": lane, "s": s}
            poi["respawn"] = outside
        pois.append(poi)
    return pois


def race_pois(geo, edges):
    """R1: two laps clockwise round the perimeter, start on the north street."""
    by_id = {e["id"]: e for e in edges}
    north = [f"e_{c}0_{c + 1}0" for c in range(3)]
    east = [f"e_3{r}_3{r + 1}" for r in range(3)]
    south = [f"e_{c}3_{c + 1}3" for c in range(3)][::-1]
    west = [f"e_0{r}_0{r + 1}" for r in range(3)][::-1]
    route = [
        (north[2], "ab"),
        (east[0], "ab"),
        (east[2], "ab"),
        (south[0], "ba"),
        (south[2], "ba"),
        (west[0], "ba"),
        (west[2], "ba"),
        (north[0], "ab"),
    ]
    pois = []
    lane = f"{north[1]}:ab0"
    p, h = lane_point(geo, lane, geo[lane]["length"] / 2.0)
    pois.append(
        {
            "id": "r1_start",
            "kind": "mission_point",
            "p": p,
            "heading_deg": h,
            "radius_m": 12.0,
        }
    )
    for i, (eid, d) in enumerate(route, start=1):
        assert eid in by_id
        lane = f"{eid}:{d}0"
        p, h = lane_point(geo, lane, geo[lane]["length"] / 2.0)
        pois.append(
            {
                "id": f"r1_cp{i}",
                "kind": "checkpoint",
                "race": "R1",
                "index": i,
                "p": p,
                "heading_deg": h,
                "radius_m": 12.0,
            }
        )
    return pois


def ring_point(sidewalk, frac_side, side_index):
    ring = sidewalk["ring"]
    a, b = ring[side_index], ring[(side_index + 1) % len(ring)]
    x = a[0] + (b[0] - a[0]) * frac_side
    z = a[1] + (b[1] - a[1]) * frac_side
    return [round(x, 2), CURB_M, round(z, 2)]


def people_pois(sidewalks, parcels):
    sw = {s["id"]: s for s in sidewalks}
    plaza = next(p for p in parcels if p["zoning"] == "plaza")
    (px0, pz0), _, (px1, pz1), _ = plaza["poly"]
    cx, cz = (px0 + px1) / 2.0, (pz0 + pz1) / 2.0
    return [
        {
            "id": "plaza_central",
            "kind": "plaza",
            "parcel": plaza["id"],
            "p": [round(cx, 2), CURB_M, round(cz, 2)],
            "heading_deg": 0.0,
        },
        {
            "id": "giver_delivery",
            "kind": "mission_giver",
            "giver": "giver_delivery",
            "p": [round(cx + 12.0, 2), CURB_M, round(cz - 8.0, 2)],
            "heading_deg": 270.0,
        },
        {
            "id": "giver_race",
            "kind": "mission_giver",
            "giver": "giver_race",
            "p": ring_point(sw["sw_10"], 0.5, 0),
            "heading_deg": 0.0,
        },
        {
            "id": "giver_heist",
            "kind": "mission_giver",
            "giver": "giver_heist",
            "p": ring_point(sw["sw_02"], 0.5, 0),
            "heading_deg": 0.0,
        },
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    nodes, edges = build_network()
    intersections = build_intersections(nodes, edges, rng)
    blocks, sidewalks, parcels, placed = build_blocks(rng)
    geo = lane_geometry(edges, nodes, intersections)
    pois = place_pois(placed, geo) + race_pois(geo, edges)
    pois += people_pois(sidewalks, parcels)
    for e in edges:
        del e["_cls"]

    margin = 40.0
    bounds = {
        "min": [XS[0] - margin, ZS[0] - margin],
        "max": [XS[-1] + margin, ZS[-1] + margin],
    }
    (bx0, bz0), (bx1, bz1) = bounds["min"], bounds["max"]
    plan = {
        "format": FORMAT,
        "map": "downtown",
        "name": "downtown",
        "revision": 1,
        "note": "Downtown core block; the rest of Downtown is laid out around it.",
        "bounds": bounds,
        "ground_m": 0.0,
        "nodes": nodes,
        "edges": edges,
        "intersections": intersections,
        "blocks": blocks,
        "sidewalks": sidewalks,
        "parcels": parcels,
        "water": [],
        "terrain": None,
        "districts": [
            {
                "id": "downtown_residential",
                "poly": rect(bx0, bz0, bx1, ZS[1]),
            },
            {"id": "downtown_core", "poly": rect(bx0, bz0, bx1, bz1)},
        ],
        "turfs": [
            {
                "id": "turf_crew_a",
                "crew": "crew_a",
                "poly": rect(XS[0], ZS[2], XS[1], ZS[3]),
            }
        ],
        "pois": pois,
        "spawn": {
            "vehicle_edges": "all",
            "pedestrian_areas": [s["id"] for s in sidewalks]
            + [p["id"] for p in parcels if p["zoning"] in ("plaza", "park")],
            "no_spawn": [],
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=1) + "\n")
    lanes = sum(len(e["lanes"]) for e in edges)
    controls = [i["control"] for i in intersections]
    print(
        f"wrote {out}: {len(nodes)} nodes, {len(edges)} edges, {lanes} lanes, "
        f"{controls.count('signal')} signalised, {controls.count('stop')} all-way stop, "
        f"{len(blocks)} blocks, {len(parcels)} parcels, {len(pois)} points of interest"
    )


if __name__ == "__main__":
    main()
