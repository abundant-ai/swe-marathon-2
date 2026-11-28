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


# Rules no recipe names and no mutant lists, with the reason each is still covered or why it is
# not graded on its own.
NOT_TARGETED = {
    "every case": (
        (
            "CLI-1 CLI-2 CLI-3 CLI-4 CLI-5 CLI-8 ENT-1 ENT-2 ENT-3 ENT-4 ENT-5 ENT-6 ENT-7 MATCH-1 "
            "CELL-1 CELL-2 CELL-3 CELL-4 CELL-5 CELL-6 IMP-1 LAY-1"
        ),
        (
            "the invocation, the entity model, identity and the basic cell dispositions have no off "
            "state: every case passes through them, and a build that gets one wrong fails broadly"
        ),
    ),
    "every conflict or check": (
        "CLI-9 GATE-1 GATE-2 GATE-6 BOX-1 BOX-2 BOX-6 CELL-17 SAME-4",
        (
            "the order and hand-off of the checks, the scope and line endings of boxes, git's own "
            "boxes and the no-loss guard run on every conflicted or checked result (the gate, "
            "refinement and settle mutants move them)"
        ),
    ),
    "every rename or data case": (
        "CELL-13 CELL-14 CELL-15 CELL-16 CELL-18 DATA-1 DATA-2 PLACE-4",
        (
            "the rename cells, the names carried to chapter 9, the JSON and TOML readers and the "
            "survivor union apply to every rename, data or modify/delete case (the rename, call-site "
            "and data mutants move them)"
        ),
    ),
    "fast paths a trivial program reproduces": (
        "ROUTE-1 ROUTE-3",
        (
            "identical sides and one side unchanged give one input back; every such candidate is "
            "reproduced by taking one side, so none is kept"
        ),
    ),
    "not behaviour": (
        "ROUTE-5 OUT-1 OUT-2 OUT-3 OUT-4 OUT-5 OUT-6 OUT-7 OUT-8",
        "a stub kept for numbering, and the chapter 16 list of what the replacement need not do",
    ),
}
RESTRICTIONS = [
    (
        "Called as `BASE OURS THEIRS -o OUT -l 7 -p PATH`",
        "every case uses that form; `-p` decides the file type and the hint's path",
    ),
    (
        "Status 2 writes nothing",
        "the binary and non-UTF-8 cases (90 kept); mutant `cli_nowrite`",
    ),
    (
        "Binary means a NUL in the first 8,192 bytes",
        "NUL at 8,001-8,191 (status 2) paired with a NUL after 8,192 (merged); mutant `binary`",
    ),
    (
        "Input that is not UTF-8 ends with status 2",
        "the non-UTF-8 cases; mutant `binary`",
    ),
    (
        "10 seconds and 4 GB per merge",
        "enforced by the runner (timeout and address-space limit)",
    ),
    (
        "Build with `cargo build --release --offline` in `/app/driver`",
        "the verifier builds that way, as an unprivileged user, with no network",
    ),
    (
        "Only the toolchain and the offline registry",
        "the verifier's registry holds the same 64 crates only",
    ),
    (
        "Must not call the installed build",
        "the verifier image has none; a wrapper around it scores 0",
    ),
    (
        "Inputs of at most 100 KB",
        "our promise: the export refuses larger cases (largest kept 9.4 KB)",
    ),
    (
        "Hint on the first closing marker only",
        "two boxes far apart (60 kept); mutant `cli_hint`",
    ),
]


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
        f"Rules with neither a targeting recipe nor a mutant: {len(unexercised)}.",
        "",
    ]
    lines += ["| Why | Rules | Coverage |", "| --- | --- | --- |"]
    classified = set()
    for why, (ids, reason) in NOT_TARGETED.items():
        lines.append(f"| {why} | {ids} | {reason} |")
        classified.update(ids.split())
    left = [r for r in unexercised if r not in classified]
    lines += ["", f"Unclassified: {', '.join(left) if left else 'none'}.", ""]
    lines += [
        "## Stated restrictions",
        "",
        "| Restriction | Failing case or enforcing check |",
    ]
    lines += ["| --- | --- |", *[f"| {a} | {b} |" for a, b in RESTRICTIONS]]
    Path(sys.argv[6]).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"features: {len(feat_kills)} measured, below 3: {short}; rules: {len(rules)}, unexercised: {len(unexercised)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
