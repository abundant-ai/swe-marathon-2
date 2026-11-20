"""Upper bounds on the reward of bodies that restore nothing, behind a table of documented outputs.

Build time only, inside the original tree. Every bound assumes that every unit's docstring examples
pass, which a table returning the documented outputs for the documented arguments makes them do;
such a table answers no counted call, so on those calls only its fallback can match. Fallbacks:

  documented constant  the unit's most frequent documented output (realizable)
  one constant         one of a list of common constants for every unit, the best of them
                       (realizable)
  best constant        per unit, the constant that matches most of its counted calls, from its
                       documented outputs and the common constants, chosen after seeing the counted
                       results (not realizable: a bound that uses the hidden results)
  first argument       the call's first argument unchanged
  flip                 for a unit whose documented results are all one boolean, the other boolean
  flip + first         flip where it applies, the first argument elsewhere
  renaming table       a table that also answers a call whose arguments are a documented call's up
                       to a renaming of symbols (assumptions kept), with that call's result renamed
                       the same way
  all                  renaming table, flip and first argument together

A documented output is the result of a call a docstring example or a visible test makes (the
documented.py output given as --shown; without it, every documented call's result).

usage: floor.py <original_tree> <inputs.pkl> <gold.json> <documented.json> [--shown <documented.py output>]
                [--share 0,0.5] [--out <json>]
"""
from __future__ import annotations

import collections
import json
import math
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "steps", "01-restore-bodies", "tests", "verifier", "lib")
UNITS = os.path.join(HERE, "..", "..", "environment", "data", "units.json")


def _symbol(node):
    return (isinstance(node, list) and len(node) == 3 and node[0] == "X" and isinstance(node[2], list) and len(node[2]) in (2, 3)
            and all(isinstance(i, list) and len(i) == 2 and i[0] == "S" and isinstance(i[1], str) for i in node[2])
            and node[2][1][1].startswith("["))


def _ident(node):
    return (node[1].rstrip("~"), node[2][0][1], node[2][1][1], node[2][2][1] if len(node[2]) == 3 else None)


def symbols_in(form, out):
    if _symbol(form):
        if _ident(form) not in out:
            out.append(_ident(form))
    elif isinstance(form, list):
        for x in form:
            symbols_in(x, out)
    return out


def rename(form, sigma):
    """Rename symbol nodes by sigma {identity: identity}; sort what canon sorts and the terms of sums
    and products (their order depends on names)."""
    if _symbol(form):
        new = sigma.get(_ident(form))
        if new is None:
            return form
        items = [["S", new[1]], ["S", new[2]]] + ([["S", new[3]]] if new[3] is not None else [])
        return ["X", form[1], items]
    if not isinstance(form, list):
        return form
    out = [rename(x, sigma) for x in form]
    if len(out) == 2 and out[0] in ("E", "D") and isinstance(out[1], list):
        out = [out[0], sorted(out[1], key=lambda x: json.dumps(x, sort_keys=True))]
    if len(out) == 3 and out[0] == "X" and out[1] in ("Add", "Mul") and isinstance(out[2], list):
        out = [out[0], out[1], sorted(out[2], key=lambda x: json.dumps(x, sort_keys=True))]
    return out


def placeholder(form):
    """(key equal for argument forms that differ by a renaming, the symbols in first-appearance order)."""
    names = symbols_in(form, [])
    sigma = {n: (n[0], f"v{i}", n[2], None) for i, n in enumerate(names)}
    return json.dumps(rename(form, sigma), sort_keys=True), names


def revive(args):
    from sympy.core.basic import Basic  # noqa: PLC0415

    for k, v in list(args.items()):
        if isinstance(v, Basic) and any("__init__" in vars(c) for c in type(v).__mro__
                                        if (c.__module__ or "").startswith("sympy") and c is not Basic):
            args[k] = type(v)(*v.args)
    return args


def main():
    tree, inputs, gold_path, documented_path = (os.path.abspath(p) for p in sys.argv[1:5])
    shares = [float(x) for x in (sys.argv[sys.argv.index("--share") + 1] if "--share" in sys.argv else "0,0.5").split(",")]
    out_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    shown_path = sys.argv[sys.argv.index("--shown") + 1] if "--shown" in sys.argv else None
    sys.path[:0] = [tree, LIB]
    os.chdir(tree)
    import sympy  # noqa: PLC0415
    from canon import canon, dummies, profile_of, same  # noqa: PLC0415
    from sympy import S, Tuple  # noqa: PLC0415

    units = {u["uid"]: u for u in json.load(open(UNITS, encoding="utf-8"))}
    profile = {uid: profile_of(f"{u['file']}::{u['qualname']}") for uid, u in units.items()}
    payload = pickle.load(open(inputs, "rb"))
    gold = json.load(open(gold_path, encoding="utf-8"))
    documented = set(json.load(open(documented_path, encoding="utf-8"))["calls"])
    visible = set(json.load(open(shown_path, encoding="utf-8"))["documented"]) & documented if shown_path else documented
    common = [True, False, 0, 1, -1, 2, [], (), {}, set(), "", None, S.Zero, S.One, S.NegativeOne, S.Half, S.Infinity,
              S.NegativeInfinity, S.ComplexInfinity, S.NaN, S.EmptySet, S.true, S.false, Tuple(), sympy.Symbol("x"),
              sympy.Matrix([]), sympy.Integer(0)]
    common_forms = []
    for value in common:
        form = canon(value)
        if all(not same(form, f) for f in common_forms):
            common_forms.append(form)
    per_unit = collections.defaultdict(lambda: {"deciding": [], "documented": []})
    blobs = {}
    for p in payload.values():
        for vid, uid, blob in p["vectors"]:
            if vid in gold:
                per_unit[uid]["documented" if vid in documented else "deciding"].append(vid)
                blobs[vid] = blob
    arg_forms = {}

    def arguments(vid):
        if vid not in arg_forms:
            try:
                args = revive(pickle.loads(blobs[vid]))
                arg_forms[vid] = (args, canon(args, dummies(revive(pickle.loads(blobs[vid])))))
            except Exception:  # noqa: BLE001
                arg_forms[vid] = (None, None)
        return arg_forms[vid]

    def first_argument(vid):
        args, _form = arguments(vid)
        if not args:
            return None
        try:
            return canon(next(iter(args.values())), dummies(revive(pickle.loads(blobs[vid]))))
        except Exception:  # noqa: BLE001
            return None

    set_units = [uid for uid, cell in per_unit.items() if cell["deciding"]]
    n_deciding = sum(len(per_unit[uid]["deciding"]) for uid in set_units)
    matches = {name: {} for name in ("documented_constant", "one_constant", "best_constant", "first_argument", "flip",
                                      "flip_first", "renaming_table", "all")}
    per_constant = [{} for _ in common_forms]
    for uid in set_units:
        cell, prof = per_unit[uid], profile[uid]
        shown = [gold[v] for v in cell["documented"] if v in visible]
        for k, form in enumerate(common_forms):
            per_constant[k][uid] = {v for v in cell["deciding"] if same(form, gold[v], profile=prof)}
        counts = [sum(1 for v in cell["deciding"] if same(form, gold[v], profile=prof)) for form in common_forms + shown]
        matches["best_constant"][uid] = set() if not counts else {
            v for v in cell["deciding"] if same((common_forms + shown)[counts.index(max(counts))], gold[v], profile=prof)}
        seen = collections.Counter(json.dumps(r, sort_keys=True) for r in shown)
        fallback = json.loads(seen.most_common(1)[0][0]) if seen else None
        matches["documented_constant"][uid] = {v for v in cell["deciding"] if fallback is not None and same(fallback, gold[v], profile=prof)}
        identity = {v for v in cell["deciding"] if (f := first_argument(v)) is not None and same(f, gold[v], profile=prof)}
        matches["first_argument"][uid] = identity
        values = {r[1] for r in shown if isinstance(r, list) and len(r) == 2 and r[0] == "B"}
        boolean = bool(shown) and len(values) == 1 and all(isinstance(r, list) and r[:1] == ["B"] for r in shown)
        flip = {v for v in cell["deciding"] if boolean and gold[v] == ["B", not next(iter(values))]}
        matches["flip"][uid] = flip
        matches["flip_first"][uid] = flip if boolean else identity
        renamed = set()
        parents = []
        for p in cell["documented"]:
            if p not in visible:
                continue
            _args, form = arguments(p)
            if form is not None:
                parents.append((p,) + placeholder(form))
        for d in cell["deciding"]:
            _args, form = arguments(d)
            if form is None or not parents:
                continue
            key, names = placeholder(form)
            target = rename(gold[d], {})
            for p, pkey, pnames in parents:
                if pkey != key or len(pnames) != len(names):
                    continue
                if same(rename(gold[p], dict(zip(pnames, names))), target, profile=prof):
                    renamed.add(d)
                    break
        matches["renaming_table"][uid] = renamed
        matches["all"][uid] = renamed | matches["flip_first"][uid]
    def score(per):
        calls = sum(len(per[uid]) for uid in set_units)
        return min(sum(1 for uid in set_units if per[uid]) / len(set_units), calls / n_deciding)

    matches["one_constant"] = max(per_constant, key=score)
    out = {"units_in_set": len(set_units), "deciding_calls": n_deciding, "by_share": {}}
    for share in shares:
        rows = {}
        for name, per in matches.items():
            units_pass = sum(1 for uid in set_units
                             if len(per[uid]) >= max(1, math.ceil(share * len(per_unit[uid]["deciding"]) - 1e-9)))
            calls = sum(len(per[uid]) for uid in set_units)
            u, c = units_pass / len(set_units), calls / n_deciding
            rows[name] = {"units": units_pass, "unit_share": round(u, 4), "calls": calls, "call_share": round(c, 4),
                          "reward": round(min(u, c), 4)}
        out["by_share"][str(share)] = rows
    text = json.dumps(out, indent=1)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)


if __name__ == "__main__":
    main()
