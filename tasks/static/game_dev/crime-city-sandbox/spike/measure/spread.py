#!/usr/bin/env python3
"""Item 4: spread over N same-seed runs of one scenario instance.

usage: spread.py GAME OUT_DIR SCENARIO SEED N [--arg k=v ...]
Each run is a fresh Godot process. Records the score, the measured values of selected
assertions and facts, and a hash of the full census trace (bit-identity check).
"""

import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qa"))
from harness import memgate
from runner import Run, load_scenario

KEYS = {
    "wanted.red_light": [
        ("arrival", "delay_s"),
        ("npc_lanes", "q95_offset_m"),
        ("kinematics", None),
    ],
    "vehicle.handling": [
        ("braking", "brake_m"),
        ("accel", "t_0_60_s"),
        ("wet", "wet_brake_m"),
        ("turning", "turn_circle_m"),
        ("top_speed", "top_speed_kmh"),
    ],
    "traffic.intersection_watch": [
        ("lanes", "q95_offset_m"),
        ("density", "median_moving"),
        ("obey", None),
    ],
}

ap = argparse.ArgumentParser()
ap.add_argument("game")
ap.add_argument("out")
ap.add_argument("scenario")
ap.add_argument("seed", type=int)
ap.add_argument("n", type=int)
ap.add_argument("--arg", action="append", default=[])
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
sc = load_scenario(a.scenario)
rows = []
for i in range(a.n):
    memgate(30, wait_s=900)
    r = Run(sc, a.seed, a.game, None, ["--" + x for x in a.arg], save_trace=False).run()
    row = {
        "i": i,
        "score": r["score"],
        "hash": r["trace_sha256"][:16],
        "wall_s": r["wall_s"],
        "frames": r["frames"],
    }
    for aid, key in KEYS.get(sc["template"], []):
        x = next((y for y in r["assertions"] if y["id"] == aid), None)
        if x and key:
            row[aid] = (x.get("measured") or {}).get(key)
        if aid == "kinematics" and x:
            row["vmax"] = max(
                [
                    v
                    for k, v in (x.get("measured") or {}).items()
                    if k.startswith("vmax_")
                ]
                or [None]
            )
    row["failed"] = [
        y["id"]
        for y in r["assertions"]
        if y.get("applies") and not y.get("pass") and y.get("w", 1) > 0
    ]
    rows.append(row)
    print(json.dumps(row), flush=True)
summary = {
    "scenario": sc["template"],
    "seed": a.seed,
    "n": len(rows),
    "args": a.arg,
    "unique_traces": len({r["hash"] for r in rows}),
    "mean_score": statistics.mean(r["score"] for r in rows),
    "min_score": min(r["score"] for r in rows),
}
for k in [k for _, k in KEYS.get(sc["template"], []) if k] + ["vmax"]:
    col = None
    for aid, key in KEYS.get(sc["template"], []):
        if key == k:
            col = aid
    col = col or k
    vals = [r[col] for r in rows if r.get(col) is not None]
    if vals:
        summary[col] = {
            "min": min(vals),
            "max": max(vals),
            "mean": statistics.mean(vals),
            "stdev": statistics.pstdev(vals),
            "range": max(vals) - min(vals),
            "n": len(vals),
        }
with open(
    os.path.join(a.out, f"{sc['template']}_s{a.seed}_n{a.n}.json"), "w"
) as stream:
    json.dump(
        {"summary": summary, "rows": rows},
        stream,
        indent=1,
    )
print("SUMMARY", json.dumps(summary))
