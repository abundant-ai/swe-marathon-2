"""Candidate calls for the units whose body a graded unit's body is a near-copy of: their twin's own
recorded arguments, under the unit's own parameter names.

Build time only. A near-copy and its twin are written the same way, and most take the same
arguments: every recorded call of the twin (its counted calls first) whose arguments fit the
near-copy's parameters by position (the same number of parameters of each kind, and no keyword the
near-copy lacks) becomes a candidate call of the near-copy. The candidates then go through the
variant builder's own steps (`variants.py contract`, `screen` and `select`, with `echoes.py` and
`documented.py` between), so that only deterministic calls whose result differs from the
placeholder's and that nothing visible answers are kept, recorded on the original.

usage: twin_calls.py <original_tree> <units.json> <inputs.pkl> <gold.json> <documented.json> <pairs.json> <out.pkl>
       twin_calls.py shown <selected_dir> <before_gold.json> <units.json> <documented.py output> [...]
<pairs.json> maps each near-copy's unit id to its twins' unit ids. Writes [(cid, uid, blob, "twin")].
The second form documents, among the calls `variants.py select` added (those not in <before_gold.json>), every
one whose result a visible example or test shows for its unit (the documented.py outputs' `shown`, compared
as finalize_documented.py compares them), and rewrites the selection's documented.json.
"""
from __future__ import annotations

import ast
import collections
import json
import os
import pickle
import sys


def parameters(tree, qualname, occ):
    """(positional names, has *args, keyword-only names, has **kwargs) of a function, from its source."""
    found = []

    def visit(node, prefix):
        for ch in node.body:
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)) and prefix + ch.name == qualname:
                found.append(ch)
            elif isinstance(ch, ast.ClassDef):
                visit(ch, prefix + ch.name + ".")

    visit(tree, "")
    fn = found[occ]
    a = fn.args
    return ([x.arg for x in a.posonlyargs + a.args], a.vararg.arg if a.vararg else None,
            [x.arg for x in a.kwonlyargs], a.kwarg.arg if a.kwarg else None)


def shown_mode():
    selected, before_path, units_path = sys.argv[2:5]
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "..", "steps", "01-restore-bodies", "tests", "verifier", "lib"))
    from canon import profile_of, same_loose  # noqa: PLC0415

    units = {u["uid"]: u for u in json.load(open(units_path, encoding="utf-8"))}
    gold = json.load(open(os.path.join(selected, "gold.json"), encoding="utf-8"))
    before = set(json.load(open(before_path, encoding="utf-8")))
    documented = set(json.load(open(os.path.join(selected, "documented.json"), encoding="utf-8"))["calls"])
    payload = pickle.load(open(os.path.join(selected, "inputs.pkl"), "rb"))  # noqa: S301 - build output
    owner = {vid: uid for p in payload.values() for vid, uid, _b in p["vectors"]}
    shown = collections.defaultdict(list)
    for path in sys.argv[5:]:
        for uid, forms in (json.load(open(path, encoding="utf-8")).get("shown") or {}).items():
            shown[uid].extend(forms)
    added = sorted(v for v in gold if v not in before)
    now_documented = []
    for vid in added:
        u = units[owner[vid]]
        profile = profile_of(f"{u['file']}::{u['qualname']}")
        if any(same_loose(gold[vid], form, profile=profile) for form in shown.get(owner[vid], ())):
            now_documented.append(vid)
    documented |= set(now_documented)
    with open(os.path.join(selected, "documented.json"), "w", encoding="utf-8") as f:
        json.dump({"calls": sorted(v for v in gold if v in documented)}, f)
    counted = [v for v in added if v not in documented]
    print(json.dumps({"added": len(added), "shown_now_documented": len(now_documented), "counted_added": len(counted),
                      "units_with_counted_added": len({owner[v] for v in counted})}))


def main():
    if sys.argv[1] == "shown":
        return shown_mode()
    tree_root, units_path, inputs, gold_path, documented_path, pairs_path, out = sys.argv[1:8]
    sys.path[:0] = [os.path.abspath(tree_root)]
    os.chdir(tree_root)
    import sympy  # noqa: F401, PLC0415 - the blobs hold SymPy objects

    units = {u["uid"]: u for u in json.load(open(units_path, encoding="utf-8"))}
    gold = json.load(open(gold_path, encoding="utf-8"))
    documented = set(json.load(open(documented_path, encoding="utf-8"))["calls"])
    pairs = json.load(open(pairs_path, encoding="utf-8"))
    payload = pickle.load(open(inputs, "rb"))  # noqa: S301 - the task's own build output
    calls = collections.defaultdict(list)
    existing = collections.defaultdict(set)
    for p in payload.values():
        for vid, uid, blob in p["vectors"]:
            if vid in gold:
                calls[uid].append((vid not in documented, vid, blob))
                existing[uid].add(blob)
    trees = {}

    def signature(uid):
        u = units[uid]
        if u["file"] not in trees:
            trees[u["file"]] = ast.parse(open(os.path.join(tree_root, u["file"]), encoding="utf-8").read())
        return parameters(trees[u["file"]], u["qualname"], u.get("occ", 0))

    cands, k, why = [], 0, collections.Counter()
    for near, twins in sorted(pairs.items()):
        mine = signature(near)
        for twin in twins:
            theirs = signature(twin)
            if (len(mine[0]), bool(mine[1]), len(mine[2]), bool(mine[3])) != \
                    (len(theirs[0]), bool(theirs[1]), len(theirs[2]), bool(theirs[3])):
                why["the parameters do not fit"] += 1
                continue
            rename = dict(zip(theirs[0], mine[0]))
            if theirs[1]:
                rename[theirs[1]] = mine[1]
            if theirs[3]:
                rename[theirs[3]] = mine[3]
            rename.update({name: name for name in theirs[2]})
            if not set(theirs[2]) <= set(mine[2]):
                why["a keyword the near-copy lacks"] += 1
                continue
            for _counted, vid, blob in sorted(calls[twin], reverse=True):   # its counted calls first
                try:
                    args = pickle.loads(blob)  # noqa: S301 - build output
                except Exception:  # noqa: BLE001
                    why["unreadable"] += 1
                    continue
                if set(args) - set(rename):
                    why["arguments outside the signature"] += 1
                    continue
                new = {rename[name]: value for name, value in args.items()}
                try:
                    b = pickle.dumps(new, protocol=4)
                except Exception:  # noqa: BLE001
                    why["unpicklable"] += 1
                    continue
                if b in existing[near] or len(b) > 30000:
                    why["already recorded"] += 1
                    continue
                existing[near].add(b)
                k += 1
                cands.append((f"T{k:06d}", near, b, "twin"))
    with open(out, "wb") as f:
        pickle.dump(cands, f, protocol=4)
    print(json.dumps({"near_copies": len(pairs), "candidates": len(cands), "units": len({c[1] for c in cands}),
                      "why": dict(why)}))


if __name__ == "__main__":
    main()
