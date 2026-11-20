"""Find the calls whose reference result is one of their own arguments, unchanged.

Build time only, inside the ORIGINAL tree. A body that returns an argument as it came answers such
a call without restoring anything, so these calls are documented (they never count for the
reward). Each argument is put in canonical form exactly as the call runner puts a result (with the
call's own Dummies and counted objects marked as given) and compared with the result by the unit's
profile.

usage:
  echoes.py <original_tree> <out.json> --calls <inputs.pkl> <gold.json>
  echoes.py <original_tree> <out.json> --screened <screened.pkl>   ([(cid, uid, blob, source, result)])

Writes {"echoes": [call ids], "checked": n, "unreadable": n}.
"""
from __future__ import annotations

import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "steps", "01-restore-bodies", "tests", "verifier", "lib")
UNITS = os.path.join(HERE, "..", "..", "environment", "data", "units.json")


def revive(args):
    """As the call runner does: rebuild SymPy objects whose class sets state in __init__."""
    from sympy.core.basic import Basic  # noqa: PLC0415

    for k, v in list(args.items()):
        if isinstance(v, Basic) and any("__init__" in vars(c) for c in type(v).__mro__
                                        if (c.__module__ or "").startswith("sympy") and c is not Basic):
            args[k] = type(v)(*v.args)
    return args


def main():
    tree, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    mode = sys.argv[3]
    sys.path[:0] = [tree, LIB]
    os.chdir(tree)
    import sympy  # noqa: F401, PLC0415
    from canon import canon, dummies, profile_of, same  # noqa: PLC0415

    units = {u["uid"]: u for u in json.load(open(UNITS, encoding="utf-8"))}
    rows = []   # (id, uid, blob, result)
    if mode == "--calls":
        payload = pickle.load(open(sys.argv[4], "rb"))
        gold = json.load(open(sys.argv[5], encoding="utf-8"))
        rows = [(vid, uid, blob, gold[vid]) for p in payload.values() for vid, uid, blob in p["vectors"] if vid in gold]
    else:
        rows = [(cid, uid, blob, result) for cid, uid, blob, _src, result in pickle.load(open(sys.argv[4], "rb"))]
    echoes, unreadable = [], 0
    for vid, uid, blob, result in rows:
        u = units[uid]
        profile = profile_of(f"{u['file']}::{u['qualname']}")
        try:
            args = revive(pickle.loads(blob))
            fixed = dummies(revive(pickle.loads(blob)))
        except Exception:  # noqa: BLE001
            unreadable += 1
            continue
        for value in args.values():
            try:
                form = canon(value, fixed)
            except Exception:  # noqa: BLE001
                continue
            if same(form, result, profile=profile):
                echoes.append(vid)
                break
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"echoes": sorted(echoes), "checked": len(rows), "unreadable": unreadable}, f)
    print(json.dumps({"echoes": len(echoes), "checked": len(rows), "unreadable": unreadable}))


if __name__ == "__main__":
    main()
