"""Draw release instances from templates (author tool; never packaged).

A template is a play (qa-play/1) with three additions:
- "family": the reward family it counts in;
- "params": how to draw each parameter: {"choice": [...]}, {"randint": [lo, hi]},
  {"uniform": [lo, hi], "round": k} or {"const": value};
- "anchors": named plan anchors ({"poi": ...}, {"lane": ..., "s": ...}, a point, ...),
  which may use parameters.

"$name" anywhere in the template is replaced by the parameter's value (a string that is
exactly "$name" takes the value's type; "$name" inside a longer string is replaced by its
text), and "$anchor:name" by the anchor's resolved point [x, y, z]. The draw (a private
number in a private file) fixes every choice, so the same templates and draw always give
the same instances. Each instance records every drawn value and every anchor's resolved
position and heading, so it runs without this script or the plan.

usage: python scripts/make_instances.py --templates DIR --draw FILE --out DIR
           [--plan common/design/plan/downtown.json] [--per-template N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))

from qakit.plan import Plan
from qakit.play import parse_play

# Plan section 1: family weights (the manifest keeps those of the families present).
FAMILY_WEIGHTS = {
    "A": 0.09, "B": 0.10, "C": 0.09, "D": 0.08, "E": 0.12, "F": 0.11, "G": 0.05,
    "H": 0.07, "I": 0.04, "J": 0.05, "K": 0.04, "L": 0.12, "M": 0.04, "T": 0.04,
}  # fmt: skip


def draw_params(spec: dict, rng: random.Random) -> dict:
    """Draw every parameter of a template, in sorted name order.

    Args:
        spec: {name: distribution} from the template's "params".
        rng: The draw's random source.

    Returns:
        {name: value}.

    Raises:
        ValueError: A distribution of an unknown kind.
    """
    out = {}
    for name in sorted(spec):
        d = spec[name]
        if "choice" in d:
            out[name] = rng.choice(d["choice"])
        elif "randint" in d:
            out[name] = rng.randint(*d["randint"])
        elif "uniform" in d:
            out[name] = round(rng.uniform(*d["uniform"]), int(d.get("round", 3)))
        elif "const" in d:
            out[name] = d["const"]
        else:
            raise ValueError(f"parameter {name}: unknown distribution {d}")
    return out


def substitute(obj: object, values: dict) -> object:
    """Replace "$name" placeholders in a JSON value (see the module docstring)."""
    if isinstance(obj, str):
        if obj.startswith("$") and obj[1:] in values:
            return values[obj[1:]]
        for name in sorted(values, key=len, reverse=True):
            obj = obj.replace("$" + name, str(values[name]))
        return obj
    if isinstance(obj, list):
        return [substitute(v, values) for v in obj]
    if isinstance(obj, dict):
        return {k: substitute(v, values) for k, v in obj.items()}
    return obj


def expand(template: dict, rng: random.Random, plan: Plan) -> dict:
    """One instance from a template and the draw's random source.

    Returns:
        A valid qa-play/1 object with "family", "drawn" and "anchors" recorded.

    Raises:
        ValueError, AnchorError, PlayError: A malformed template.
    """
    values = draw_params(template.get("params", {}), rng)
    anchors = substitute(template.get("anchors", {}), values)
    resolved = {}
    for name, anchor in anchors.items():
        pl = plan.resolve(anchor)
        resolved[name] = {
            "anchor": anchor,
            "p": [round(c, 4) for c in pl.p],
            "heading_deg": pl.heading_deg,
        }
        values["anchor:" + name] = resolved[name]["p"]
    body = {k: v for k, v in template.items() if k not in ("params", "anchors")}
    inst = substitute(body, values)
    tag = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:8]
    inst["name"] = f"{template['name']}/{tag}"
    inst["drawn"] = {k: v for k, v in values.items() if not k.startswith("anchor:")}
    inst["anchors"] = resolved
    parse_play(inst)
    return inst


def main() -> int:
    """Expand every template per-template times; write the plays and the manifest."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, required=True)
    ap.add_argument("--draw", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--plan", type=Path, default=TASK / "common/design/plan/downtown.json"
    )
    ap.add_argument("--per-template", type=int, default=2)
    a = ap.parse_args()
    draw = json.loads(a.draw.read_text())["draw"]
    plan = Plan.load(a.plan)
    (a.out / "plays").mkdir(parents=True, exist_ok=True)
    instances, counts = [], {}
    for path in sorted(a.templates.glob("*.json")):
        template = json.loads(path.read_text())
        rng = random.Random(f"{draw}:{template['name']}")
        for _ in range(a.per_template):
            inst = expand(template, rng, plan)
            fname = inst["name"].replace("/", ".") + ".json"
            (a.out / "plays" / fname).write_text(json.dumps(inst, indent=1) + "\n")
            instances.append({"file": f"plays/{fname}", "family": template["family"]})
            counts[template["family"]] = counts.get(template["family"], 0) + 1
    manifest = {
        "format": "qa-instances/1",
        "release": f"draw-{hashlib.sha256(str(draw).encode()).hexdigest()[:8]}",
        "families": {
            f: {"w": FAMILY_WEIGHTS[f], "n": n} for f, n in sorted(counts.items())
        },
        "instances": instances,
    }
    (a.out / "instances.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{len(instances)} instances in {len(counts)} families -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
