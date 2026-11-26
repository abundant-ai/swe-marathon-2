"""Write the plan-swap playtest for a plan folder (author tool, never packaged).

GDD WD-8: given another plan folder (--plan-dir) with different roads and parcels and the
same point-of-interest ids, the game builds that world instead, and WD-1 to WD-7 hold on
it. This writes world.plan_swap/<label>: the steps and expectations of
world.plan_compliance (scripts/make_playtests.py, plan_compliance) with every ray and every
expected height and tag taken from the folder's downtown.json (scripts/plan_probes.py). It
cites WD-8 with WD-1 to WD-5 and AC-8.

The play names no plan folder itself: whoever runs it gives the game the folder (qa run
--plans DIR). In a release manifest (qa-instances/1) its entry names the folder ("plans",
relative to the manifest), so the grader runs it with --plan-dir=<a copy of that folder>
(tests/verifier/grade.py, load_manifest). --manifest adds that entry (replacing an earlier
plan-swap entry on the same folder) and keeps the family's instance count in step.

usage: python scripts/make_plan_swap.py --plans DIR --out DIR [--label LABEL]
           [--manifest FILE] [--family H]
The label defaults to downtown-<the first 8 hex digits of the plan file's SHA-256>.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))
sys.path.insert(0, str(TASK / "scripts"))

from make_instances import FAMILY_WEIGHTS
from make_playtests import Playtest, render
from plan_probes import Probes
from qakit.play import parse_play

MAP = "downtown"
TEMPLATE = "world.plan_swap"
RULES = ["WD-8", "WD-1", "WD-2", "WD-3", "WD-4", "WD-5", "AC-8"]


def plan_swap(plan_data: dict, label: str) -> Playtest:
    """The plan-swap playtest over one plan.

    Args:
        plan_data: The plan (city-plan/1) the game is given.
        label: The play's label (its name is world.plan_swap/<label>).

    Returns:
        The playtest: make_playtests.plan_compliance's steps and expectations, with this
        plan's rays.
    """
    p = Playtest(
        f"{TEMPLATE}/{label}",
        RULES,
        "QA gives the game another layout of Downtown through --plan-dir: other roads, "
        "blocks and parcels, the same points of interest. It casts rays over the whole of "
        "that layout: along every lane and sidewalk, across every crosswalk, over every "
        "parcel, through every door and room, and down onto every point of interest. What "
        "they hit has that layout's heights and the surface tags of chapter 17.",
        ["--role=solo", "--variation=1", "--save-dir={save_dir}"],
        limits={"step_s": 60},
    )
    rays = Probes(plan_data).build()
    p.step("observe", {"census": False, "every": 30})
    p.step("run", 30)
    step = p.step("query", rays.queries)
    p.step("run", 1)
    for e in rays.expects:
        p.expect(e["id"], e["check"], dict(e["args"], step=step), e["rule"], e["says"])
    return p


def ray_count(raw: dict) -> int:
    """How many rays a play's query steps cast."""
    return sum(
        len(q["points"]) if q.get("type") == "down" else 1
        for step in raw["steps"]
        for q in step.get("query", [])
    )


def add_to_manifest(manifest: Path, play_file: Path, plans: Path, family: str) -> dict:
    """Add (or replace) the plan-swap instance in a qa-instances/1 manifest.

    An earlier plan-swap entry on the same plan folder is replaced. The family's "n"
    becomes its number of entries; a family new to the manifest gets its weight from
    scripts/make_instances.py.

    Returns:
        The entry written.
    """
    data = json.loads(manifest.read_text())
    if data.get("format") != "qa-instances/1":
        raise SystemExit(f"{manifest} is not a qa-instances/1 manifest")
    base = manifest.resolve().parent
    entry = {
        "file": Path(os.path.relpath(play_file.resolve(), base)).as_posix(),
        "family": family,
        "plans": Path(os.path.relpath(plans.resolve(), base)).as_posix(),
    }
    kept = [
        i
        for i in data["instances"]
        if i["file"] != entry["file"]
        and not (
            i.get("plans") == entry["plans"]
            and Path(i["file"]).name.startswith(TEMPLATE + ".")
        )
    ]
    data["instances"] = [*kept, entry]
    fams = data.setdefault("families", {})
    fams.setdefault(family, {"w": FAMILY_WEIGHTS[family], "n": 0})
    fams[family]["n"] = sum(1 for i in data["instances"] if i["family"] == family)
    data["families"] = dict(sorted(fams.items()))
    manifest.write_text(json.dumps(data, indent=1) + "\n")
    return entry


def main() -> int:
    """Write the play (and the manifest entry)."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plans", type=Path, required=True, help="the plan folder")
    ap.add_argument("--out", type=Path, required=True, help="the folder for the play")
    ap.add_argument("--label", help="the play's label (default: downtown-<hash>)")
    ap.add_argument("--manifest", type=Path, help="a qa-instances/1 manifest to add to")
    ap.add_argument("--family", default="H")
    a = ap.parse_args()
    text = (a.plans / f"{MAP}.json").read_bytes()
    label = a.label or f"{MAP}-{hashlib.sha256(text).hexdigest()[:8]}"
    p = plan_swap(json.loads(text), label)
    parse_play(p.raw)  # the kit's own validation
    out = render(p.raw) + "\n"
    assert json.loads(out) == p.raw
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / (p.name.replace("/", ".") + ".json")
    path.write_text(out)
    print(f"wrote {path}: {ray_count(p.raw)} rays, {len(p.raw['expect'])} expectations")
    if a.manifest:
        entry = add_to_manifest(a.manifest, path, a.plans, a.family)
        print(f"{a.manifest}: {json.dumps(entry)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
