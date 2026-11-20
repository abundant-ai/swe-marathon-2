"""Upper bound on the reward of bodies that return documented outputs for documented arguments and a
constant otherwise.

Build time only. Such a table answers only calls whose arguments a docstring example or a visible
test uses, which are not among the calls the reward counts, so on those calls only its fallback can
match. The bound lets every unit pick, after the fact, the constant that matches most of its own
counted calls, from its documented outputs and a list of common constants, and assumes every unit's
docstring examples pass ("best constant"). The fixture itself cannot see the counted calls' results:
its fallback is the unit's most frequent documented output ("documented constant"). A third
attacker returns its first argument unchanged.

usage: floor.py <original_tree> <inputs.pkl> <gold.json> <documented.json> [--share 0,0.5]
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


def main():
    tree, inputs, gold_path, documented_path = (os.path.abspath(p) for p in sys.argv[1:5])
    shares = [float(x) for x in (sys.argv[sys.argv.index("--share") + 1] if "--share" in sys.argv else "0,0.5").split(",")]
    sys.path[:0] = [tree, LIB]
    os.chdir(tree)
    import sympy  # noqa: PLC0415
    from canon import canon, same  # noqa: PLC0415
    from sympy import S, Tuple  # noqa: PLC0415

    payload = pickle.load(open(inputs, "rb"))
    gold = json.load(open(gold_path, encoding="utf-8"))
    documented = set(json.load(open(documented_path, encoding="utf-8"))["calls"])
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
            per_unit[uid]["documented" if vid in documented else "deciding"].append(vid)
            blobs[vid] = blob

    def first_argument(vid):
        try:
            args = pickle.loads(blobs[vid])
            return canon(next(iter(args.values()))) if args else None
        except Exception:  # noqa: BLE001
            return None

    set_units = [uid for uid, cell in per_unit.items() if cell["deciding"]]
    n_deciding = sum(len(per_unit[uid]["deciding"]) for uid in set_units)
    out = {"units_in_set": len(set_units), "deciding_calls": n_deciding, "by_share": {}}
    best_matches, identity_matches, fixture_matches = {}, {}, {}
    for uid in set_units:
        cell = per_unit[uid]
        candidates = list(common_forms) + [gold[v] for v in cell["documented"]]
        counts = []
        for form in candidates:
            counts.append(sum(1 for v in cell["deciding"] if same(form, gold[v])))
        best_matches[uid] = max(counts) if counts else 0
        seen = collections.Counter(json.dumps(gold[v], sort_keys=True) for v in cell["documented"])
        if seen:
            fallback = json.loads(seen.most_common(1)[0][0])
            fixture_matches[uid] = sum(1 for v in cell["deciding"] if same(fallback, gold[v]))
        else:
            fixture_matches[uid] = 0   # nothing documented: the fixture returns None, which no counted call is
        identity_matches[uid] = sum(1 for v in cell["deciding"] if (f := first_argument(v)) is not None and same(f, gold[v]))
    for share in shares:
        rows = {}
        for name, matches in (("best_constant", best_matches), ("documented_constant", fixture_matches),
                              ("first_argument", identity_matches)):
            units_pass = sum(1 for uid in set_units
                             if matches[uid] >= max(1, math.ceil(share * len(per_unit[uid]["deciding"]) - 1e-9)))
            calls = sum(matches.values())
            u, c = units_pass / len(set_units), calls / n_deciding
            rows[name] = {"units": units_pass, "unit_share": round(u, 4), "calls": calls, "call_share": round(c, 4),
                          "reward": round(min(u, c), 4)}
        out["by_share"][str(share)] = rows
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
