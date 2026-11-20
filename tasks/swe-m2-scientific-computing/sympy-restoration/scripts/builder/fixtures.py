"""Write a work tree of bodies that restore nothing, for grading the reward's floor through the verifier.

Build time only.

usage: fixtures.py <rule> <original_root> <out_root> [<inputs.pkl> <gold.json> <documented.json>]

Every unit body after its docstring becomes one statement:
  raise      `raise NotImplementedError` (no unit marker, so every unit counts as restored)
  identity   `return <first parameter>`, the unit's first argument unchanged
  flip       for a unit whose documented results are all one boolean, the other boolean of the same
             kind (a Python bool, or SymPy's true and false); otherwise as `identity` (the last
             three arguments say which results are documented)
"""
from __future__ import annotations

import ast
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UNITS = os.path.join(HERE, "..", "..", "environment", "data", "units.json")


def flipped(inputs, gold_path, documented_path):
    """{uid: (kind, the boolean a unit's documented results never are)}, for units with only one."""
    payload = pickle.load(open(inputs, "rb"))
    gold = json.load(open(gold_path, encoding="utf-8"))
    documented = set(json.load(open(documented_path, encoding="utf-8"))["calls"])
    shown = {}
    for p in payload.values():
        for vid, uid, _blob in p["vectors"]:
            if vid in documented and vid in gold:
                shown.setdefault(uid, []).append(gold[vid])
    out = {}
    for uid, results in shown.items():
        kinds = {(r[0], r[1]) for r in results if isinstance(r, list) and len(r) == 2 and r[0] in ("B", "SB")}
        if len(kinds) == 1 and all(isinstance(r, list) and len(r) == 2 and r[0] in ("B", "SB") for r in results):
            kind, value = next(iter(kinds))
            out[uid] = (kind, not value)
    return out


def main():
    rule, orig, out = sys.argv[1], sys.argv[2], sys.argv[3]
    flips = flipped(*sys.argv[4:7]) if rule == "flip" else {}
    units = json.load(open(UNITS, encoding="utf-8"))
    by_file = {}
    for u in units:
        by_file.setdefault(u["file"], []).append(u)
    counts = {"files": 0, "units": 0, "flipped": 0}
    for rel, file_units in sorted(by_file.items()):
        src = open(os.path.join(orig, rel), encoding="utf-8").read()
        lines = src.splitlines(keepends=True)
        idx = {}

        def visit(node, prefix):
            for ch in node.body:
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    idx.setdefault(prefix + ch.name, []).append(ch)
                elif isinstance(ch, ast.ClassDef):
                    visit(ch, prefix + ch.name + ".")

        visit(ast.parse(src), "")
        spans = []
        for u in file_units:
            fn = idx[u["qualname"]][u.get("occ", 0)]
            first = fn.body[0]
            has_doc = isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
                and isinstance(first.value.value, str)
            rest = fn.body[1:] if has_doc else fn.body
            indent = " " * rest[0].col_offset
            a = fn.args
            params = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs] + ([a.vararg.arg] if a.vararg else [])
            if rule == "raise":
                statement = "raise NotImplementedError"
            elif u["uid"] in flips:
                kind, value = flips[u["uid"]]
                statement = f"return {value!r}" if kind == "B" else \
                    f"from sympy.logic.boolalg import {str(value).lower()} as _flipped\n{indent}return _flipped"
                counts["flipped"] += 1
            else:
                statement = f"return {params[0] if params else 'None'}"
            spans.append((rest[0].lineno - 1, fn.end_lineno, indent + statement + "\n"))
            counts["units"] += 1
        for start, end, text in sorted(spans, reverse=True):
            lines[start:end] = [text]
        new = "".join(lines)
        ast.parse(new)
        path = os.path.join(out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        counts["files"] += 1
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
