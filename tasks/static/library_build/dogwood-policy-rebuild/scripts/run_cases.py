"""Run one `dogwood` binary over a private case set, the way the grader runs a submission.

Runs inside a container as root (python3 -I), never on the host; it reuses the grader's own
runner, so the user, environment, limits and normalisation are the grader's. Each case runs
`--repeat` times; the output records every run's exit status and normalised standard output,
plus the raw output's hash, so determinism can be read off it.

Usage: run_cases.py --bin PATH --private DIR --out FILE [--repeat N] [--only REGEX] [--jobs N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tests"))

from verifier.contracts import Case, Limits
from verifier.normalise import normalise
from verifier.runner import run_case


def one(item) -> tuple[str, dict, float]:
    """Run one case `repeat` times; return its id, its record and its slowest run."""
    c, binary, private, repeat, parallel = item
    case = Case(
        c["id"],
        c["family"],
        c["bundle"],
        tuple(c["args"]),
        c["fmt"],
        c.get("pair"),
        0,
        "",
        c.get("stdin"),
    )
    runs = []
    slowest = 0.0
    for _ in range(repeat):
        t0 = time.monotonic()
        status, stdout = run_case(
            Path(binary), case, Path(private) / "bundles", Limits(), sweep=not parallel
        )
        slowest = max(slowest, time.monotonic() - t0)
        runs.append(
            {
                "rc": status,
                "raw": hashlib.sha256(stdout).hexdigest(),
                "norm": normalise(stdout, case.fmt),
            }
        )
    return (
        case.case_id,
        {"family": case.family, "pair": case.pair, "runs": runs},
        slowest,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True, type=Path)
    ap.add_argument("--private", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--only", default=None, help="regex over case ids")
    ap.add_argument("--jobs", type=int, default=1, help="cases run at once")
    a = ap.parse_args()
    only = re.compile(a.only) if a.only else None
    todo = []
    for raw in (a.private / "cases.jsonl").read_text().splitlines():
        if not raw.strip():
            continue
        c = json.loads(raw)
        if only and not only.search(c["id"]):
            continue
        todo.append(c)
    started = time.monotonic()
    work = [(c, str(a.bin), str(a.private), a.repeat, a.jobs > 1) for c in todo]
    if a.jobs > 1:
        with multiprocessing.Pool(a.jobs) as pool:
            done = pool.map(one, work, chunksize=8)
    else:
        done = [one(w) for w in work]
    results = {cid: entry for cid, entry, _ in done}
    slowest = max((s for _, _, s in done), default=0.0)
    a.out.write_text(json.dumps(results))
    raw_stable = sum(
        1
        for r in results.values()
        if len({(x["rc"], x["raw"]) for x in r["runs"]}) == 1
    )
    norm_stable = sum(
        1
        for r in results.values()
        if len({(x["rc"], x["norm"]) for x in r["runs"]}) == 1
    )
    print(
        json.dumps(
            {
                "cases": len(results),
                "repeat": a.repeat,
                "raw_stable": raw_stable,
                "normalised_stable": norm_stable,
                "seconds": round(time.monotonic() - started, 1),
                "slowest_case_seconds": round(slowest, 3),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
