#!/usr/bin/env python3
"""Print the item 4 table from runs/spread/<config>/*.json."""

import glob
import json
import os
import sys
from pathlib import Path

root = sys.argv[1] if len(sys.argv) > 1 else "runs/spread"
for path in sorted(glob.glob(os.path.join(root, "*", "*.json"))):
    d = json.loads(Path(path).read_text())
    s = d["summary"]
    cfg = os.path.basename(os.path.dirname(path))
    rows = d["rows"]
    impl = (
        ""
        if s["scenario"] != "vehicle.handling"
        else (" raycast" if s["seed"] == 1 else " vehicle_body")
    )
    line = (
        f"{cfg:<13} {s['scenario']}{impl} seed {s['seed']}: n={s['n']} unique traces={s['unique_traces']} "
        f"score mean={s['mean_score']:.3f} min={s['min_score']:.3f}"
    )
    print(line)
    for k, v in s.items():
        if isinstance(v, dict):
            print(
                f"    {k:<12} min={v['min']:.4f} max={v['max']:.4f} mean={v['mean']:.4f} sd={v['stdev']:.4f} range={v['range']:.4f}"
            )
    fails = [r["failed"] for r in rows if r["failed"]]
    if fails:
        print("    failed assertions:", fails[:10])
