"""Enumerate restorable-unit candidates in a Python package tree and blank/transplant bodies.

A unit is a module-level function or a method defined directly in a module-level
class (any nesting of classes), whose own docstring carries doctest examples and
whose body (after the docstring) starts on its own line.
"""
from __future__ import annotations

import ast
import json
import os
import sys

EXCLUDE_DIR_PARTS = {"tests", "benchmarks", "testing"}


def iter_py(root: str, pkg: str):
    base = os.path.join(root, pkg)
    for dp, dn, fn in os.walk(base):
        rel = os.path.relpath(dp, root)
        parts = set(rel.split(os.sep))
        if parts & EXCLUDE_DIR_PARTS:
            dn[:] = []
            continue
        dn.sort()
        for f in sorted(fn):
            if f.endswith(".py"):
                yield os.path.join(rel, f)


def module_name(relpath: str) -> str:
    p = relpath[:-3].replace(os.sep, ".")
    if p.endswith(".__init__"):
        p = p[: -len(".__init__")]
    return p


def _doc_and_rest(fn):
    b = fn.body
    if (
        b
        and isinstance(b[0], ast.Expr)
        and isinstance(getattr(b[0], "value", None), ast.Constant)
        and isinstance(b[0].value.value, str)
    ):
        return b[0], b[1:]
    return None, b


def _nstmts(nodes) -> int:
    return sum(1 for n in nodes for x in ast.walk(n) if isinstance(x, ast.stmt))


def find_units(src: str, relpath: str):
    """Return list of candidate dicts for one source file."""
    tree = ast.parse(src)
    lines = src.split("\n")
    out = []

    def visit(node, prefix):
        for ch in node.body:
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc, rest = _doc_and_rest(ch)
                if doc is None or ">>>" not in doc.value.value or not rest:
                    continue
                first = rest[0]
                # first statement must start on its own line, after the docstring
                if first.lineno <= doc.end_lineno:
                    continue
                line = lines[first.lineno - 1]
                indent = line[: len(line) - len(line.lstrip())]
                if len(indent) != first.col_offset or indent.strip():
                    continue
                # body must be the tail of the function
                end = ch.end_lineno
                deco_line = min([d.lineno for d in ch.decorator_list] + [ch.lineno])
                out.append(
                    {
                        "file": relpath,
                        "module": module_name(relpath),
                        "qualname": prefix + ch.name,
                        "name": ch.name,
                        "def_line": ch.lineno,
                        "deco_line": deco_line,
                        "doc_end": doc.end_lineno,
                        "body_start": first.lineno,
                        "body_end": end,
                        "indent": indent,
                        "n_stmts": _nstmts(rest),
                        "n_lines": end - first.lineno + 1,
                        "is_async": isinstance(ch, ast.AsyncFunctionDef),
                    }
                )
            elif isinstance(ch, ast.ClassDef):
                visit(ch, prefix + ch.name + ".")

    visit(tree, "")
    # occurrence index among ALL same-qualname definitions (property getter/setter pairs,
    # conditional redefinitions); keep a unit only if it is the single doctested one
    allq = {}

    def visit_all(node, prefix):
        for ch in node.body:
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                allq.setdefault(prefix + ch.name, []).append(ch.lineno)
            elif isinstance(ch, ast.ClassDef):
                visit_all(ch, prefix + ch.name + ".")

    visit_all(tree, "")
    seen = {}
    for u in out:
        seen.setdefault(u["qualname"], []).append(u)
    res = []
    for q, v in seen.items():
        if len(v) != 1:
            continue
        u = v[0]
        u["nocc"] = len(allq[q])
        u["occ"] = allq[q].index(u["def_line"])
        res.append(u)
    return res


def placeholder(indent: str, uid: str) -> str:
    return f'{indent}raise NotImplementedError("RESTORE {uid}")'


def blank_source(src: str, units) -> str:
    """Replace the body of each unit (dicts with body_start/body_end/indent/uid)."""
    lines = src.split("\n")
    for u in sorted(units, key=lambda u: -u["body_start"]):
        lines[u["doc_end"] : u["body_end"]] = [placeholder(u["indent"], u["uid"])]
    return "\n".join(lines)


def main():
    root, pkg, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    allu = []
    for rel in iter_py(root, pkg):
        try:
            src = open(os.path.join(root, rel), encoding="utf-8").read()
            allu.extend(find_units(src, rel))
        except SyntaxError as e:
            print("syntax", rel, e, file=sys.stderr)
    json.dump(allu, open(outp, "w"))
    print(len(allu), "candidates in", len({u["file"] for u in allu}), "files")


if __name__ == "__main__":
    main()
