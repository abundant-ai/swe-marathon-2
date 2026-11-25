"""Find the calls whose reference result is one of their own arguments, unchanged.

Build time only, inside the ORIGINAL tree. A body that returns an argument as it came answers such
a call without restoring anything, so these calls are documented (they never count for the
reward). The arguments looked at are every argument of the call, every element of its `*args`
tuple and every value of its `**kwargs` mapping (the unit's own signature, read from its source,
names them). Each is put in canonical form exactly as the call runner puts a result (with the
call's own Dummies and counted objects marked as given) and compared with the result by the unit's
profile with the type of a value left out (`canon.same_loose`), since a body returning an argument
can as cheaply convert it (`sympify`, `int`, `tuple`). A result that also records changed
arguments (`NS`, `RS`) is never an echo: returning an argument does not make those changes.

usage:
  echoes.py <original_tree> <out.json> --calls <inputs.pkl> <gold.json>
  echoes.py <original_tree> <out.json> --screened <screened.pkl>   ([(cid, uid, blob, source, result)])

Writes {"echoes": [call ids], "checked": n, "unreadable": n, "by_element": n}.
"""

from __future__ import annotations

import ast
import json
import os
import pickle
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "tests", "verifier", "lib")
UNITS = os.path.join(HERE, "..", "..", "environment", "data", "units.json")


def revive(args):
    """As the call runner does: rebuild SymPy objects whose class sets state in __init__."""
    from sympy.core.basic import Basic

    for k, v in list(args.items()):
        if isinstance(v, Basic) and any(
            "__init__" in vars(c)
            for c in type(v).__mro__
            if (c.__module__ or "").startswith("sympy") and c is not Basic
        ):
            args[k] = type(v)(*v.args)
    return args


def star_names(tree, units):
    """uid -> (name of its *args parameter or None, name of its **kwargs parameter or None), from the source."""
    sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
    import restorelib

    parsed, out = {}, {}
    for uid, u in units.items():
        path = os.path.join(tree, u["file"])
        if path not in parsed:
            parsed[path] = restorelib.index_functions(
                ast.parse(Path(path).read_text(encoding="utf-8"))
            )
        nodes = parsed[path].get(u["qualname"]) or []
        if len(nodes) != u.get("nocc", 1):
            out[uid] = (None, None)
            continue
        fn = nodes[u.get("occ", 0)]
        out[uid] = (
            fn.args.vararg.arg if fn.args.vararg else None,
            fn.args.kwarg.arg if fn.args.kwarg else None,
        )
    return out


def main():
    tree, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    mode = sys.argv[3]
    sys.path[:0] = [tree, LIB]
    os.chdir(tree)
    import sympy  # noqa: F401
    from canon import canon, dummies, profile_of, same_loose

    units = {u["uid"]: u for u in json.loads(Path(UNITS).read_text(encoding="utf-8"))}
    stars = star_names(tree, units)
    rows = []  # (id, uid, blob, result)
    if mode == "--calls":
        with open(sys.argv[4], "rb") as stream:
            payload = pickle.load(stream)
        gold = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
        rows = [
            (vid, uid, blob, gold[vid])
            for p in payload.values()
            for vid, uid, blob in p["vectors"]
            if vid in gold
        ]
    else:
        with open(sys.argv[4], "rb") as stream:
            rows = [
                (cid, uid, blob, result)
                for cid, uid, blob, _src, result in pickle.load(stream)
            ]
    echoes, unreadable, by_element = [], 0, 0
    for vid, uid, blob, result in rows:
        if isinstance(result, list) and result[:1] in (["NS"], ["RS"]):
            continue
        u = units[uid]
        profile = profile_of(f"{u['file']}::{u['qualname']}")
        try:
            args = revive(pickle.loads(blob))
            fixed = dummies(revive(pickle.loads(blob)))
        except Exception:  # noqa: BLE001
            unreadable += 1
            continue
        varargs, varkw = stars[uid]
        values = [(value, False) for value in args.values()]
        if varargs and isinstance(args.get(varargs), tuple):
            values += [(value, True) for value in args[varargs]]
        if varkw and isinstance(args.get(varkw), dict):
            values += [(value, True) for value in args[varkw].values()]
        for value, element in values:
            try:
                form = canon(value, fixed)
            except Exception:  # noqa: BLE001, S112
                continue
            if same_loose(form, result, profile=profile):
                echoes.append(vid)
                by_element += element
                break
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "echoes": sorted(echoes),
                "checked": len(rows),
                "unreadable": unreadable,
                "by_element": by_element,
            },
            f,
        )
    print(
        json.dumps(
            {
                "echoes": len(echoes),
                "checked": len(rows),
                "unreadable": unreadable,
                "by_element": by_element,
            }
        )
    )


if __name__ == "__main__":
    main()
