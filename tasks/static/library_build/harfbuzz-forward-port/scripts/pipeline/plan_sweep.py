"""Write the plan of a full sweep: fonts, candidates, relinked drivers, missing builds, every driver of every build,
repeated base runs, and the classification into the private selection (development tooling).

usage: plan_sweep.py PLAN_OUT --tag TAG [--seed N] [--per-unit N]

Builds that already exist under CACHE/work/out/hb are reused (relinked); the missing reverts and mutant W are built.
Candidates go to a fresh /work/cand-TAG and outputs to a fresh /work/runs-TAG, so no sweep overwrites another.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parent
TASK = PIPE.parent.parent
CACHE = Path.home() / "Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port"
WORK = CACHE / "work"
HOST_PY = str(Path.home() / "Documents/github/Abundant/swe-marathon-2/.venv/bin/python")
NO_REVERT = {"33", "47a"}  # 33 is added forward (regen-14.3.0); 47a is cut


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan", type=Path)
    p.add_argument("--seed", type=int, default=20261127)
    p.add_argument("--per-unit", type=int, default=2000)
    p.add_argument("--tag", required=True)
    args = p.parse_args()
    units = [
        r.split("\t") for r in (PIPE / "units.tsv").read_text().splitlines()[1:] if r
    ]
    have = {
        d.name
        for d in (WORK / "out" / "hb").iterdir()
        if (d / "lib" / "libharfbuzz.a").exists()
    }
    py = "/opt/py/bin/python"
    cand, runs = f"/work/cand-{args.tag}", f"/work/runs-{args.tag}"
    ops: list[dict] = [
        {
            "op": "sh",
            "args": [py, "-I", "/pipe/synth_fonts.py", "/work/fonts"],
            "cpus": 2,
        },
        {
            "op": "sh",
            "args": [
                "sh",
                "-c",
                f"test ! -e {cand} && mkdir -p {runs} && {py} -I /pipe/cases.py {cand} {args.seed} {args.per_unit}",
            ],
            "cpus": 2,
        },
        {
            "op": "sh",
            "args": ["sh", "-c", "sh /pipe/relink.sh /work/out/hb/*"],
            "cpus": 4,
        },
    ]
    reverts = []
    for unit, _window, release, *_ in units:
        if unit in NO_REVERT:
            continue
        reverts.append(unit)
        if f"rk-{unit}" not in have:
            ops.append(
                {
                    "op": "build",
                    "id": f"rk-{unit}",
                    "release": release,
                    "unit": unit,
                    "jobs": 4,
                    "cpus": 6,
                }
            )
    ops.append(
        {
            "op": "build",
            "id": "mut-W",
            "release": "15.2.0",
            "unit": "W",
            "jobs": 4,
            "cpus": 6,
        }
    )
    if "rk-ALL" not in have:
        ops.append(
            {
                "op": "build",
                "id": "rk-ALL",
                "release": "15.2.0",
                "unit": "ALL",
                "jobs": 4,
                "cpus": 6,
            }
        )
    builds = [
        "rel-14.3.0", "rel-15.0.0", "rel-15.1.0", "rel-15.2.0", "rel-15.2.0-nofma", "regen-14.3.0",
        *(f"rk-{u}" for u in reverts), "mut-W", "rk-ALL",
    ]  # fmt: skip
    for b in builds:
        ops.append(
            {"op": "sh", "args": ["sh", "/pipe/run_all.sh", b, cand, runs], "cpus": 2}
        )
    for name, perturb in (("rel-14.3.0-run2", "165"), ("rel-14.3.0-run3", "90")):
        ops.append(
            {
                "op": "sh",
                "args": [
                    "sh",
                    "-c",
                    f"MALLOC_PERTURB_={perturb} sh /pipe/run_all.sh rel-14.3.0 {cand} {runs} {name}",
                ],
                "cpus": 2,
            }
        )
    ops.append(
        {
            "op": "host",
            "args": [
                HOST_PY, "-I", "scripts/pipeline/classify.py", str(WORK / f"runs-{args.tag}"), str(WORK / f"cand-{args.tag}" / "meta.jsonl"),
                "scripts/pipeline/units.tsv", "--reverts", *reverts,
                "--select-to", "tests/private/selection.jsonl", "--salt-file", "private/salt.txt",
                "--rows-to", str(WORK / f"classified-{args.tag}.jsonl"),
            ],
        }
    )  # fmt: skip
    args.plan.write_text(json.dumps(ops, indent=1))
    print(
        json.dumps(
            {
                "ops": len(ops),
                "builds_new": sum(o["op"] == "build" for o in ops),
                "runs": len(builds) + 2,
            }
        )
    )
    if not (TASK / "private" / "salt.txt").exists():
        sys.exit("private/salt.txt missing")


if __name__ == "__main__":
    main()
