#!/usr/bin/env python3
"""Plumbing smoke test: probe handshake, setup commands, census counts, a few ticks."""

import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qa"))
from harness import Session, memgate

game = sys.argv[1]
memgate(30)
s = Session(
    game,
    ["--role=solo", "--seed=3"],
    log_path=os.path.join(os.path.dirname(os.path.abspath(game)), "smoke.log"),
)
print("hello:", json.dumps(s.hello))
f = s.frame
print("first frame t", f["t"], "census", len(f.get("census", [])))
f = s.step(
    1,
    dev=[["world.reset", {"seed": 3}], ["state", {}]],
    observe={"census": True, "state": True},
)
print(
    "after reset t",
    f["t"],
    collections.Counter(e["k"] for e in f["census"]),
    "dev:",
    json.dumps(f["dev"])[:300],
)
t0 = time.time()
for i in range(100):
    f = s.step(6, observe={"census": True, "state": True})
wall = time.time() - t0
cars = [e for e in f["census"] if e["k"] == "vehicle"]
peds = [e for e in f["census"] if e["k"] == "npc"]
print(
    "t", f["t"], f"wall {wall:.2f}s for 600 ticks", "cars", len(cars), "peds", len(peds)
)
sp = [
    ((e.get("v") or [0, 0, 0])[0] ** 2 + (e.get("v") or [0, 0, 0])[2] ** 2) ** 0.5
    for e in cars
]
print("car speeds m/s:", [round(x, 1) for x in sp[:20]])
print(
    "car y:",
    [round(e["p"][1], 2) for e in cars[:10]],
    "up:",
    [round(e["up"], 2) for e in cars[:10]],
)
print("ped y:", [round(e["p"][1], 2) for e in peds[:10]])
print(
    "events:", json.dumps(f["events"])[:300], "state:", json.dumps(f.get("state"))[:300]
)
print("perf:", f["perf"])
print("rtt median ms %.3f" % (1000 * sorted(s.rtt)[len(s.rtt) // 2]))
print("exit", s.close())
