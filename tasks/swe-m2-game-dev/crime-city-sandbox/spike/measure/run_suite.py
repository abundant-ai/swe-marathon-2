#!/usr/bin/env python3
"""Run scenario instances one after another (one Godot process at a time, RAM-gated).

usage: run_suite.py GAME OUT SPEC [SPEC ...]   where SPEC = scenario.yaml:seed1,seed2,...
Writes OUT/summary.json with one row per instance.
"""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qa"))
from runner import Run, load_scenario
from harness import memgate

game, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
rows = []
for spec in sys.argv[3:]:
    path, seeds = spec.split(":")
    sc = load_scenario(path)
    for seed in [int(x) for x in seeds.split(",")]:
        pct = memgate(30, wait_s=600)
        t0 = time.time()
        try:
            r = Run(sc, seed, game, out, save_trace=False,
                    log_path=os.path.join(out, f"{sc['template']}_s{seed}.log")).run()
            row = {"template": sc["template"], "seed": seed, "score": r["score"], "gate_failed": r["gate_failed"],
                   "sim_s": round(r["sim_s"], 1), "wall_s": r["wall_s"], "speedup": r["speedup"],
                   "failed": [a["id"] for a in r["assertions"] if a.get("applies") and not a.get("pass")],
                   "params": {k: v for k, v in r["params"].items() if k != "seed"}, "mem_free_pct": pct}
        except Exception as ex:
            row = {"template": sc["template"], "seed": seed, "score": 0.0, "error": f"{type(ex).__name__}: {ex}",
                   "wall_s": round(time.time() - t0, 1), "mem_free_pct": pct}
        rows.append(row)
        print(json.dumps(row), flush=True)
        json.dump(rows, open(os.path.join(out, "summary.json"), "w"), indent=1)
