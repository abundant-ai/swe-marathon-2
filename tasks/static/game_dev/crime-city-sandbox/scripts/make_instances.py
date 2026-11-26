"""Draw release instances from templates (author tool; never packaged).

A template is a play (qa-play/1) with three additions:
- "family": the reward family it counts in;
- "params": how to draw each parameter: {"choice": [...]}, {"randint": [lo, hi]},
  {"uniform": [lo, hi], "round": k}, {"const": value}, or {"sum": [names or numbers]}
  drawn after the others (a drawn object's fields are "$name.field"), or
  {"expr": text, "round": k} computed last, once every parameter it names is known: the
  text is arithmetic (numbers, + - * /, parentheses, min, max, abs) over "$name" and
  "$name.field" of other parameters, rounded to k decimals (default 3; 0 gives a whole
  number, halves to even); it draws nothing, so the other parameters come out the same;
- "anchors": named plan anchors ({"poi": ...}, {"lane": ..., "s": ...}, a point, ...),
  which may use parameters.
An expectation may also carry "when": a value, usually "$name". The instance keeps the
expectation only when that value is true (not 0, false, null or empty), and the key itself
is not written; so a rule that holds only for some draws (one stated for daytime, say) is
checked only on those.

"$name" anywhere in the template is replaced by the parameter's value (a string that is
exactly "$name" takes the value's type; "$name" inside a longer string, or an object key
"$name", is replaced by its text), and "$anchor:name" by the anchor's resolved point. The draw (a private
number in a private file) fixes every choice, so the same templates and draw always give
the same instances. Each instance records every drawn value and every anchor's resolved
position and heading, so it runs without this script or the plan.

usage: python scripts/make_instances.py --templates DIR --draw FILE --out DIR
           [--plan common/design/plan/downtown.json] [--per-template N]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import operator
import random
import re
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


EXPR_NAME = re.compile(r"\$([A-Za-z_]\w*(?:\.\w+)?)")
EXPR_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}  # fmt: skip
EXPR_FUNCS = {"min": min, "max": max, "abs": abs}


def eval_expr(text: str, values: dict) -> float:
    """The value of an "expr" parameter's text (see the module docstring).

    Only numbers, the four operations, parentheses, min, max, abs and "$name" references
    to numeric parameters are accepted; nothing else is evaluated.

    Raises:
        ValueError: Anything else in the text, a name that is not a known number, or a
            division by zero.
    """
    refs: dict[str, str] = {}

    def ref(m: re.Match) -> str:
        refs[f"_p{len(refs)}"] = m.group(1)
        return f"_p{len(refs) - 1}"

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id in refs:
            v = values.get(refs[node.id])
            if type(v) not in (int, float):
                raise ValueError(f"expr {text!r}: ${refs[node.id]} is not a number")
            return v
        if isinstance(node, ast.UnaryOp) and type(node.op) in EXPR_OPS:
            return EXPR_OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in EXPR_OPS:
            return EXPR_OPS[type(node.op)](ev(node.left), ev(node.right))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in EXPR_FUNCS
            and node.args
            and not node.keywords
        ):
            return EXPR_FUNCS[node.func.id](*(ev(a) for a in node.args))
        raise ValueError(f"expr {text!r}: {type(node).__name__} is not allowed")

    try:
        return ev(ast.parse(EXPR_NAME.sub(ref, text), mode="eval"))
    except (SyntaxError, TypeError, ZeroDivisionError) as exc:
        raise ValueError(f"expr {text!r}: {exc}") from exc


def draw_params(spec: dict, rng: random.Random) -> dict:
    """Draw every parameter of a template, in sorted name order.

    Args:
        spec: {name: distribution} from the template's "params".
        rng: The draw's random source.

    Returns:
        {name: value}.

    Raises:
        ValueError: A distribution of an unknown kind, or "expr" parameters that name
            unknown parameters or each other in a cycle.
    """
    out = {}
    plain = sorted(n for n in spec if "sum" not in spec[n] and "expr" not in spec[n])
    derived = sorted(n for n in spec if "sum" in spec[n])
    for name in plain + derived:
        d = spec[name]
        if "sum" in d:
            out[name] = sum(out[x] if isinstance(x, str) else x for x in d["sum"])
        elif "choice" in d:
            out[name] = rng.choice(d["choice"])
        elif "randint" in d:
            out[name] = rng.randint(*d["randint"])
        elif "uniform" in d:
            out[name] = round(rng.uniform(*d["uniform"]), int(d.get("round", 3)))
        elif "const" in d:
            out[name] = d["const"]
        else:
            raise ValueError(f"parameter {name}: unknown distribution {d}")
        if isinstance(out[name], dict):  # a drawn object: its fields are $name.field
            for k, v in out[name].items():
                out[f"{name}.{k}"] = v
    pending = sorted(n for n in spec if "expr" in spec[n])
    while pending:
        ready = [
            n
            for n in pending
            if all(x in out for x in EXPR_NAME.findall(spec[n]["expr"]))
        ]
        if not ready:
            raise ValueError(f"parameters {pending}: unknown names or a cycle")
        for name in ready:
            x = eval_expr(spec[name]["expr"], out)
            k = int(spec[name].get("round", 3))
            out[name] = round(x) if k == 0 else round(x, k)
            pending.remove(name)
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
        return {
            (
                str(values[k[1:]]) if k.startswith("$") and k[1:] in values else k
            ): substitute(v, values)
            for k, v in obj.items()
        }
    return obj


def keep_when(expect: list) -> list:
    """The expectations to keep: those without "when", and those whose "when" is true,
    with the key taken out (see the module docstring)."""
    out = []
    for e in expect:
        if isinstance(e, dict) and "when" in e:
            if not e["when"]:
                continue
            e = {k: v for k, v in e.items() if k != "when"}
        out.append(e)
    return out


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
    if isinstance(inst.get("expect"), list):
        inst["expect"] = keep_when(inst["expect"])
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
