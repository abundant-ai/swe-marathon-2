"""Write the plan of a full sweep: fonts, candidates, relinked drivers, missing builds, every driver of every build,
repeated base runs, and the classification into the private selection (development tooling).

usage: plan_sweep.py PLAN_OUT --tag TAG [--seed N] [--per-unit N]

Builds that already exist under CACHE/work/out/hb are reused (relinked); the missing releases, the regenerated base,
reverts, partial reverts (PARTIALS) and mutants (MUTANTS: W and the verification-gap companions) are built.
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
# Partial reverts (classify.PARTIALS): build rk-<name> is the release with only CACHE/work/patches-lib/<name>/
# reverted. 25a-hist: 15.1.0 without 90417543f (CoreText's kerx format 1 history), so that classify.py can leave out
# the 25a cases that depend on it.
PARTIALS = {"25a-hist": "15.1.0"}
# Mutants, all on 15.2.0: W widens every conditional note (scripts/pipeline/mutants/W); V takes every tier-C unit out
# (patches-lib/ALLV), R_unbuilt every F4 and F5 unit (ALLRu); W_literal is W without QA pass 17's non-literal
# widenings (patches-lib/LITW). assemble_reverts.py writes ALLV and ALLRu; notes/DESIGN.md section 10.
MUTANTS = {"mut-W": "W", "mut-V": "ALLV", "mut-Ru": "ALLRu", "mut-Wlit": "LITW"}
RELEASE_BUILDS = {
    "rel-14.3.0": {"release": "14.3.0"},
    "rel-15.0.0": {"release": "15.0.0"},
    "rel-15.1.0": {"release": "15.1.0"},
    "rel-15.2.0": {"release": "15.2.0"},
    "rel-15.2.0-nofma": {
        "release": "15.2.0",
        "meson_extra": "-Dc_args=-ffp-contract=off -Dcpp_args=-ffp-contract=off",
    },
}


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
    out_hb = WORK / "out" / "hb"
    have = (
        {d.name for d in out_hb.iterdir() if (d / "lib" / "libharfbuzz.a").exists()}
        if out_hb.is_dir()
        else set()
    )
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
    ]
    if have:
        ops.append(
            {
                "op": "sh",
                "args": ["sh", "-c", "sh /pipe/relink.sh /work/out/hb/*"],
                "cpus": 4,
            }
        )
    for bid, spec in RELEASE_BUILDS.items():
        if bid not in have:
            ops.append({"op": "build", "id": bid, "jobs": 4, "cpus": 6, **spec})
    if "regen-14.3.0" not in have:
        # 14.3.0 with its Unicode tables regenerated from the shipped Unicode 18 files (unit 33 is added forward).
        regen = (
            "test ! -e /work/regen/tree && sh /pipe/regen_unicode.sh /work/regen/tree"
            " && sh /pipe/hb_build.sh /work/regen/tree /work/out/hb/regen-14.3.0 '' 4 on"
            " && rm -r /work/regen/tree"
        )
        ops.append({"op": "sh", "args": ["sh", "-c", regen], "cpus": 6})
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
    for name, release in PARTIALS.items():
        if f"rk-{name}" not in have:
            ops.append(
                {
                    "op": "build",
                    "id": f"rk-{name}",
                    "release": release,
                    "unit": name,  # CACHE/work/patches-lib/<name>, reverted
                    "jobs": 4,
                    "cpus": 6,
                }
            )
    for bid, unit in MUTANTS.items():
        if bid not in have:
            ops.append(
                {
                    "op": "build",
                    "id": bid,
                    "release": "15.2.0",
                    "unit": unit,
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
                "unit": "ALLX",  # every single-commit unit's revert at once (CACHE/work/patches-lib/ALLX)
                "jobs": 4,
                "cpus": 6,
            }
        )
    builds = [
        "rel-14.3.0", "rel-15.0.0", "rel-15.1.0", "rel-15.2.0", "rel-15.2.0-nofma", "regen-14.3.0",
        *(f"rk-{u}" for u in reverts), *(f"rk-{p}" for p in PARTIALS), *MUTANTS, "rk-ALL",
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
                "--rows-to", str(WORK / f"classified-{args.tag}.jsonl"), "--cut-to", str(WORK / f"cut-{args.tag}.json"),
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
