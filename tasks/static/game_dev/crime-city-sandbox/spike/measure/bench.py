#!/usr/bin/env python3
"""Item 3: simulation speed of the block with N cars and M people.

Runs the game's bench role (no probe), samples the process CPU time at the start and end of the
measured window with ps, and reports wall-clock and CPU-normalised speed (simulated seconds per
CPU second, i.e. the speed one core would give if the work were serialised).

usage: bench.py GAME OUT.jsonl LABEL [game args...]
"""

import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qa"))
from harness import GODOT, memgate


def cputime(pid):
    out = subprocess.run(
        ["ps", "-o", "time=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    parts = [float(x) for x in re.split("[:]", out.replace("-", ":"))]
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def threads(pid):
    out = subprocess.run(
        ["ps", "-M", "-p", str(pid)], check=False, capture_output=True, text=True
    ).stdout
    return max(0, len(out.strip().splitlines()) - 1)


def rss_mb(pid):
    out = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return int(out) / 1024.0 if out else None


def main():
    game, out, label = sys.argv[1], sys.argv[2], sys.argv[3]
    gargs = sys.argv[4:]
    pct = memgate(30, wait_s=600)
    cmd = [
        GODOT,
        "--headless",
        "--fixed-fps",
        "60",
        "--path",
        game,
        "--",
        "--role=bench",
    ] + gargs
    t0 = time.time()
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    c0 = c1 = None
    res = None
    thr = rss = None
    errors = []
    for line in p.stdout:
        line = line.rstrip()
        if line == "BENCH_START":
            c0 = cputime(p.pid)
        elif line.startswith("BENCH_END "):
            c1 = cputime(p.pid)
            thr = threads(p.pid)
            rss = rss_mb(p.pid)
            res = json.loads(line[len("BENCH_END ") :])
        elif "ERROR" in line:
            errors.append(line)
    p.wait(timeout=60)
    if res is None:
        raise SystemExit(f"bench failed: {errors[:5]}")
    cpu = c1 - c0
    res.update(
        {
            "label": label,
            "args": gargs,
            "cpu_s": round(cpu, 3),
            "cpu_per_wall": round(cpu / res["wall_s"], 2),
            "speedup_one_core": round(res["sim_s"] / cpu, 2),
            "threads": thr,
            "rss_mb": round(rss, 1),
            "total_s": round(time.time() - t0, 2),
            "mem_free_pct_before": pct,
            "errors": errors[:5],
        }
    )
    for k in (
        "speedup",
        "ms_mean",
        "ms_p50",
        "ms_p95",
        "ms_max",
        "wall_s",
        "mem_static_mb",
    ):
        res[k] = round(res[k], 3)
    with open(out, "a") as f:
        f.write(json.dumps(res) + "\n")
    print(
        json.dumps(
            {
                k: res[k]
                for k in (
                    "label",
                    "speedup",
                    "speedup_one_core",
                    "cpu_per_wall",
                    "ms_mean",
                    "ms_p95",
                    "cars",
                    "cars_moving",
                    "peds",
                    "ped_bones",
                    "threads",
                    "rss_mb",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
