"""Coverage inventory and kill matrix for the Weave task.

Usage: python3 -I coverage.py ANALYSIS.json CASES.json GENERATOR.py FEATURE_MUTANTS.py SPEC_DIR OUT.md

Feature level: each instruction-level feature's mutants and the kept cases they move (pass at 3).
Rule level: for every rule id defined in the specification, the kept cases of recipes that name
it, and the mutants that list it.
"""

from __future__ import annotations

import ast
import collections
import importlib.util
import json
import re
import sys
from pathlib import Path

RULE = re.compile(
    r"\[([A-Z]+(?:-[A-Z]+)*-[0-9A-Z]+(?:\.\.[0-9]+)?)\]|\b([A-Z]{2,}(?:-[A-Z]+)?-\d+(?:\.\.\d+)?)\b"
)


def expand(token: str) -> list[str]:
    """MATCH-2..6 -> MATCH-2 .. MATCH-6."""
    m = re.fullmatch(r"(.+-)(\d+)\.\.(\d+)", token)
    if m:
        return [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)]
    return [token]


def recipe_rules(generator: Path) -> dict[str, set[str]]:
    """Recipe function name -> rule ids its docstring names."""
    out = {}
    for node in ast.parse(generator.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("r_"):
            doc = ast.get_docstring(node) or ""
            ids = set()
            for a, b in RULE.findall(doc):
                for t in expand(a or b):
                    ids.add(t)
            out[node.name] = ids
    return out


def spec_rules(spec_dir: Path) -> dict[str, str]:
    """Rule id -> chapter file, for every bold rule marker in the specification."""
    out = {}
    for f in sorted(spec_dir.glob("[01][0-9]-*.md")):
        for rid in re.findall(
            r"\*\*\[([A-Z][A-Z0-9-]+)\]", f.read_text(encoding="utf-8")
        ):
            out.setdefault(rid, f.name)
    return out


def main() -> int:
    """Write the inventory as Markdown and print the totals."""
    analysis = json.loads(Path(sys.argv[1]).read_text())
    cases = {
        c["id"]: c for c in json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    }
    rrules = recipe_rules(Path(sys.argv[3]))
    spec = importlib.util.spec_from_file_location("fm", sys.argv[4])
    fm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fm)
    rules = spec_rules(Path(sys.argv[5]))
    kept = analysis["kept"]
    kills = analysis["summary"].get("kill_matrix", {})
    # feature level
    feat_rows, feat_kills = [], collections.defaultdict(int)
    for name, m in fm.MUTANTS.items():
        k = kills.get(f"mut-{name}")
        n = k["total"] if k else None
        if n is not None:
            feat_kills[m["feature"]] = max(feat_kills[m["feature"]], n)
        fams = ", ".join(
            f"{f} {c}" for f, c in sorted((k or {}).get("families", {}).items())
        )
        feat_rows.append(
            (m["feature"], name, m["family"], "not run" if n is None else n, fams)
        )
    # rule level
    per_rule = collections.Counter()
    for cid in kept:
        for rid in rrules.get(cases[cid].get("recipe", ""), ()):
            per_rule[rid] += 1
    mutant_rules = collections.defaultdict(list)
    for name, m in fm.MUTANTS.items():
        for rid in m["rules"]:
            for t in expand(rid):
                mutant_rules[t].append(name)
    lines = [
        "# Coverage inventory and kill matrix",
        "",
        "## Features (a mutant moves at least 3 kept cases)",
        "",
    ]
    lines += [
        "| Feature | Mutant | Family | Kept cases moved | By family |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {a} | `{b}` | {c} | {d} | {e} |" for a, b, c, d, e in sorted(feat_rows)
    ]
    short = sorted(f for f, n in feat_kills.items() if n < 3)
    lines += ["", f"Features below 3: {', '.join(short) if short else 'none'}.", ""]
    lines += [
        "## Rules of the specification",
        "",
        "| Rule | Chapter | Kept cases of recipes naming it | Mutants listing it |",
        "| --- | --- | --- | --- |",
    ]
    unexercised = []
    for rid, ch in sorted(rules.items()):
        n = per_rule.get(rid, 0)
        ms = ", ".join(f"`{x}`" for x in mutant_rules.get(rid, []))
        lines.append(f"| {rid} | {ch[:2]} | {n} | {ms} |")
        if n == 0 and not ms:
            unexercised.append(rid)
    lines += [
        "",
        f"Rules with neither a targeting recipe nor a mutant: {len(unexercised)} ({', '.join(unexercised)}).",
    ]
    Path(sys.argv[6]).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"features: {len(feat_kills)} measured, below 3: {short}; rules: {len(rules)}, unexercised: {len(unexercised)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
