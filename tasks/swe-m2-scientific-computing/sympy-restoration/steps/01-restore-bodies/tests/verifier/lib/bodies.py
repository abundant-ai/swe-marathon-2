"""Facts about unit bodies the measurement reports, kept out of the transplant code the restore tool shares."""
from __future__ import annotations

import ast
import hashlib
import os

import restorelib


def body_facts(root: str, units) -> dict:
    """{uid: [non-blank lines, sha256 of the syntax tree]} of each unit's body after its docstring.

    `units` are records of units.json; files are read under `root`. A unit whose file cannot be
    read or parsed, whose function is not found exactly as often as recorded, or whose body is
    empty is left out; the hash is None for a tree too deep to dump.
    """
    out: dict = {}
    by_file: dict = {}
    for u in units:
        by_file.setdefault(u["file"], []).append(u)
    for rel, file_units in by_file.items():
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as f:
                src = f.read()
            funcs = restorelib.index_functions(ast.parse(src))
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError, RecursionError, MemoryError):
            continue
        lines = src.splitlines()
        for u in file_units:
            nodes = funcs.get(u["qualname"]) or []
            if len(nodes) != u.get("nocc", 1):
                continue
            _doc, rest = restorelib._doc_and_rest(nodes[u.get("occ", 0)])
            if not rest:
                continue
            count = sum(1 for i in range(rest[0].lineno - 1, min(rest[-1].end_lineno, len(lines))) if lines[i].strip())
            try:
                dump = ast.dump(ast.Module(body=rest, type_ignores=[]), include_attributes=False)
                digest = hashlib.sha256(dump.encode("utf-8")).hexdigest()
            except (RecursionError, MemoryError, ValueError):
                digest = None
            out[u["uid"]] = [count, digest]
    return out
