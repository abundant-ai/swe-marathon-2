"""Write the plan of a full sweep: fonts, candidates, relinked drivers, missing builds, every driver of every build,
repeated base runs, and the classification into the private selection (development tooling).

usage: plan_sweep.py PLAN_OUT --tag TAG [--seed N] [--per-unit N]
       plan_sweep.py forward-33 TREE   (inside the pipeline image: the code half of unit 33, applied forward)

Builds that already exist under CACHE/work/out/hb are reused (relinked); the missing releases, the regenerated base,
unit 33's forward build (fwd-33), reverts, partial reverts (PARTIALS) and mutants (MUTANTS: W and the
verification-gap companions) are built. The probes that hb_build.sh and relink.sh do not compile (EXTRA_PROBES) are
compiled for every build before the runs. Candidates go to a fresh /work/cand-TAG and outputs to a fresh
/work/runs-TAG, so no sweep overwrites another.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
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
# Unit 33 is added forward (classify.ADDERS). fwd-33 is 14.3.0 with its Unicode tables regenerated from the shipped
# Unicode 18 files (regen_unicode.sh, as for regen-14.3.0) plus the code half of bf93d8671: the cases that route
# Jurchen, Proto-Cuneiform and Seal through USE (hb-ot-shaper.hh) and give Jurchen and Seal the ideographic baseline
# (hb-ot-layout.cc). Both hunks apply to 14.3.0 as they are.
FWD33_PATCH = Path("/work/patches-lib/33/001-bf93d8671.patch")
FWD33_FILES = ("src/hb-ot-layout.cc", "src/hb-ot-shaper.hh")
# Probes that hb_build.sh and relink.sh do not list; compiled here, with their commands, for every build (none now:
# hbapi33 joined their lists).
EXTRA_PROBES: tuple[str, ...] = ()


def forward_33(tree: Path) -> None:
    """Apply the code hunks of bf93d8671 (FWD33_FILES) forward to TREE."""
    parts = re.split(r"(?m)^(?=diff --git )", FWD33_PATCH.read_text())
    keep = [
        p for p in parts if any(p.startswith(f"diff --git a/{f} ") for f in FWD33_FILES)
    ]
    if len(keep) != len(FWD33_FILES):
        sys.exit(
            f"forward-33: {FWD33_PATCH} does not hold one section for each of {FWD33_FILES}"
        )
    subprocess.run(
        ["patch", "-p1", "--forward", "-s", "--no-backup-if-mismatch", "-d", str(tree)],
        input="".join(keep),
        text=True,
        check=True,
    )


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "forward-33":
        forward_33(Path(sys.argv[2]))
        return
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
    if "fwd-33" not in have:
        fwd = (
            "test ! -e /work/fwd33/tree && sh /pipe/regen_unicode.sh /work/fwd33/tree"
            f" && {py} -I /pipe/plan_sweep.py forward-33 /work/fwd33/tree"
            " && sh /pipe/hb_build.sh /work/fwd33/tree /work/out/hb/fwd-33 '' 4 on"
            " && rm -r /work/fwd33/tree"
        )
        ops.append({"op": "sh", "args": ["sh", "-c", fwd], "cpus": 6})
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
        "rel-14.3.0", "rel-15.0.0", "rel-15.1.0", "rel-15.2.0", "rel-15.2.0-nofma", "regen-14.3.0", "fwd-33",
        *(f"rk-{u}" for u in reverts), *(f"rk-{p}" for p in PARTIALS), *MUTANTS, "rk-ALL",
    ]  # fmt: skip
    # The probes hb_build.sh does not list, for every build (a probe a build cannot compile is left absent, and
    # run_cases.sh then answers !nobuild for its cases, as for the others).
    compile_extra = (
        'for OUT in /work/out/hb/*; do [ -f "$OUT/lib/libharfbuzz.a" ] || continue;'
        f' for d in {" ".join(EXTRA_PROBES)}; do rm -f "$OUT/$d";'
        ' { cc -O2 -Werror=implicit-function-declaration -c -I"$OUT/include/harfbuzz" -o "/tmp/$d.o" "/drv/$d.c"'
        ' && c++ -o "$OUT/$d" "/tmp/$d.o" "$OUT/lib/libharfbuzz.a" -lm; } > "$OUT/$d.compile.log" 2>&1'
        ' || rm -f "$OUT/$d"; done; done'
    )
    ops.append({"op": "sh", "args": ["sh", "-c", compile_extra], "cpus": 4})
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
