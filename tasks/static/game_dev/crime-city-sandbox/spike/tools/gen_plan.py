#!/usr/bin/env python3
"""Generate the Phase 0 plan file: one downtown plan block (3 x 3 junctions, 2 x 2 city blocks).

Deterministic for a given --seed. The output follows the plan conventions written into the
file itself ("conventions"), so the game and the QA side can each derive lane geometry from it.
"""

import argparse
import json
import math
import random

SPACING = 120.0  # junction spacing (m)
LANE_W = 3.5  # lane width (m)
LANES_PER_DIR = 2
HALF_CARRIAGEWAY = LANE_W * LANES_PER_DIR  # 7.0 m
SIDEWALK_W = 3.0
CURB_H = 0.15
STOP_LINE_M = 10.5  # stop line distance from the junction centre
CROSSWALK = [7.0, 10.0]  # crosswalk band, distance from the junction centre


def node_id(c, r):
    return f"j_{c}{r}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rng = random.Random(a.seed)

    coords = [-SPACING, 0.0, SPACING]
    nodes = []
    for r in range(3):
        for c in range(3):
            nodes.append({"id": node_id(c, r), "p": [coords[c], 0.0, coords[r]]})

    edges = []

    def add_edge(c0, r0, c1, r1):
        a_id, b_id = node_id(c0, r0), node_id(c1, r1)
        eid = f"e_{a_id[2:]}_{b_id[2:]}"
        lanes = []
        for d in ("ab", "ba"):
            for k in range(LANES_PER_DIR):
                lanes.append({"id": f"{eid}:{d}{k}", "dir": d, "index": k})
        edges.append(
            {
                "id": eid,
                "a": a_id,
                "b": b_id,
                "lanes": lanes,
                "lane_width_m": LANE_W,
                "speed_kmh": 50,
                "elevation_m": 0.0,
                "sidewalk_m": SIDEWALK_W,
                "surface": "asphalt",
            }
        )

    for r in range(3):
        for c in range(2):
            add_edge(c, r, c + 1, r)
    for c in range(3):
        for r in range(2):
            add_edge(c, r, c, r + 1)

    # Junctions: every node. Signalised when 3+ roads meet.
    degree = {n["id"]: 0 for n in nodes}
    for e in edges:
        degree[e["a"]] += 1
        degree[e["b"]] += 1
    intersections = []
    for i, n in enumerate(nodes):
        approaches = []
        for e in edges:
            if e["b"] == n["id"]:
                approaches.append(
                    {"id": f"{n['id']}<{e['id']}", "edge": e["id"], "dir": "ab"}
                )
            elif e["a"] == n["id"]:
                approaches.append(
                    {"id": f"{n['id']}<{e['id']}", "edge": e["id"], "dir": "ba"}
                )
        sig = degree[n["id"]] >= 3
        entry = {
            "id": n["id"],
            "node": n["id"],
            "control": "signal" if sig else "none",
            "signalised": sig,
            "box_half_m": HALF_CARRIAGEWAY,
            "stop_line_m": STOP_LINE_M,
            "crosswalk_m": CROSSWALK,
            "approaches": approaches,
        }
        if sig:
            # one phase per approach, ordered by approach angle (clockwise from north)
            npos = n["p"]

            def ang(ap_, npos=npos):
                e = next(x for x in edges if x["id"] == ap_["edge"])
                other = e["a"] if ap_["dir"] == "ab" else e["b"]
                op = next(x for x in nodes if x["id"] == other)["p"]
                return math.atan2(op[0] - npos[0], -(op[2] - npos[2])) % (2 * math.pi)

            order = sorted(approaches, key=ang)
            entry["signal"] = {
                "phases": [[ap_["id"]] for ap_ in order],
                "green_s": 10.0,
                "amber_s": 3.0,
                "all_red_s": 1.0,
                "offset_s": round(7.0 * i % 14.0, 1),
            }
        intersections.append(entry)

    # City blocks (raised, curb at 7 m from road centrelines), sidewalks and parcels.
    blocks, sidewalks, parcels = [], [], []
    zoning = {
        "commercial": [12.0, 45.0],
        "residential": [8.0, 24.0],
        "civic": [10.0, 14.0],
    }
    pid = 0
    for br in range(2):
        for bc in range(2):
            x0 = coords[bc] + HALF_CARRIAGEWAY
            x1 = coords[bc + 1] - HALF_CARRIAGEWAY
            z0 = coords[br] + HALF_CARRIAGEWAY
            z1 = coords[br + 1] - HALF_CARRIAGEWAY
            bid = f"b_{bc}{br}"
            blocks.append(
                {
                    "id": bid,
                    "poly": [[x0, z0], [x1, z0], [x1, z1], [x0, z1]],
                    "elevation_m": CURB_H,
                }
            )
            o = SIDEWALK_W / 2.0
            sidewalks.append(
                {
                    "id": f"sw_{bc}{br}",
                    "block": bid,
                    "width_m": SIDEWALK_W,
                    "elevation_m": CURB_H,
                    "ring": [
                        [x0 + o, z0 + o],
                        [x1 - o, z0 + o],
                        [x1 - o, z1 - o],
                        [x0 + o, z1 - o],
                    ],
                }
            )
            ix0, ix1, iz0, iz1 = (
                x0 + SIDEWALK_W,
                x1 - SIDEWALK_W,
                z0 + SIDEWALK_W,
                z1 - SIDEWALK_W,
            )
            mx, mz = (ix0 + ix1) / 2.0, (iz0 + iz1) / 2.0
            for px0, px1 in ((ix0, mx), (mx, ix1)):
                for pz0, pz1 in ((iz0, mz), (mz, iz1)):
                    zone = "commercial" if rng.random() < 0.6 else "residential"
                    if bid == "b_00" and px0 == ix0 and pz0 == iz0:
                        zone = "civic"
                    if bid == "b_11" and px1 == ix1 and pz1 == iz1:
                        zone = "civic"
                    lo, hi = zoning[zone]
                    h = round(rng.uniform(lo, hi), 1)
                    parcels.append(
                        {
                            "id": f"p_{pid:02d}",
                            "block": bid,
                            "zoning": zone,
                            "poly": [[px0, pz0], [px1, pz0], [px1, pz1], [px0, pz1]],
                            "base_m": CURB_H,
                            "height_range_m": [lo, hi],
                            "height_m": h,
                            "setback_m": 4.0,
                        }
                    )
                    pid += 1

    # Points of interest with stable ids. exit = where vehicles leave the POI onto a lane.
    pois = [
        {
            "id": "police_station_a",
            "kind": "police_station",
            "p": [-85.0, CURB_H, -103.0],
            "exit": {"lane": "e_00_10:ab1", "s": 40.0},
        },
        {
            "id": "police_station_b",
            "kind": "police_station",
            "p": [85.0, CURB_H, 103.0],
            "exit": {"lane": "e_12_22:ba1", "s": 40.0},
        },
        {"id": "safehouse_a", "kind": "safehouse", "p": [-30.0, CURB_H, 25.0]},
        {"id": "shop_corner", "kind": "shop", "p": [30.0, CURB_H, -25.0]},
        {
            "id": "proving_ground",
            "kind": "test_area",
            "p": [0.0, -0.05, -600.0],
            "heading_deg": 90.0,
            "size_m": [2400.0, 400.0],
        },
    ]

    plan = {
        "schema": "spike-plan/0.1",
        "name": "downtown_block",
        "map": "downtown",
        "seed": a.seed,
        "conventions": {
            "axes": "x east, y up, z south (Godot); metres",
            "traffic": "right-hand",
            "lane_centre": "offset (index + 0.5) * lane_width_m to the right of the direction of travel; index 0 is next to the centreline",
            "lane_extent": "a lane runs from stop_line_m after its start junction to stop_line_m before its end junction",
            "dir": "ab runs from edge.a to edge.b; ba the other way",
            "approach": "an approach is one incoming direction of one edge at a junction; its stop line crosses all its lanes at stop_line_m from the junction centre",
            "connectors": "inside a junction every lane may continue to the same lane index of any other road; left turns use index 0, right turns index 1, straight either, unless that leaves a lane without a way out",
            "signal_cycle": "phases run in order: green_s, amber_s, all_red_s each; offset_s shifts the cycle start",
            "ground": "outside the blocks the ground is at y = -0.05; road surfaces are at elevation_m",
            "buildings": "one building per parcel, inset by setback_m, roof at base_m + height_m",
        },
        "nodes": nodes,
        "edges": edges,
        "intersections": intersections,
        "blocks": blocks,
        "sidewalks": sidewalks,
        "parcels": parcels,
        "pois": pois,
        "spawn": {"vehicles": "all lanes", "pedestrians": [s["id"] for s in sidewalks]},
        "density": {"vehicles_base": 40, "pedestrians_base": 60},
    }
    with open(a.out, "w") as f:
        json.dump(plan, f, indent=1)
    print(
        f"wrote {a.out}: {len(nodes)} nodes, {len(edges)} edges, {sum(len(e['lanes']) for e in edges)} lanes, "
        f"{len(parcels)} parcels, {len(pois)} POIs"
    )


if __name__ == "__main__":
    main()
