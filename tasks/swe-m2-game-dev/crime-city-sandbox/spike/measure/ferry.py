#!/usr/bin/env python3
"""Item 9 (second half): the ferry deck carrying a parked car of each implementation.
usage: ferry.py GAME OUT.json   (runs with the raycast car aware and unaware of moving ground)"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qa"))
from harness import GODOT, memgate
game, out = sys.argv[1], sys.argv[2]
res = {}
for gv in ("1", "0"):
    memgate(30, wait_s=600)
    p = subprocess.run([GODOT, "--headless", "--fixed-fps", "60", "--path", game, "--", "--role=ferry", f"--ground_vel={gv}"],
                       capture_output=True, text=True, timeout=300)
    line = next((l for l in p.stdout.splitlines() if l.startswith("FERRY_RESULT ")), None)
    res["ground_velocity_aware" if gv == "1" else "ground_velocity_unaware"] = json.loads(line[13:]) if line else {"error": p.stdout[-600:]}
    print(gv, json.dumps(res[list(res)[-1]])[:400], flush=True)
json.dump(res, open(out, "w"), indent=1)
