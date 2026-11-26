"""Check that every GDD rule is exercised by a check in the Phase 1 plan's coverage map.

Author tool (never packaged). Reads the rule ids of common/design/GDD.md and the check catalog
and coverage map of notes/PHASE1-PLAN.md, and fails when:
- a GDD rule has no coverage row, or more than one;
- a coverage row names a rule the GDD does not have;
- a row names no assertion, or an assertion of a template missing from the catalog;
- a row's kind (P, R, G, I) is not the kind of one of the templates it names;
- a catalog template is named by no row.

Usage: python scripts/check_coverage.py [--gdd PATH] [--plan PATH]
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
RULE = re.compile(r"^- \*\*([A-Z]{2}-\d+)\*\*", re.MULTILINE)
CATALOG_ROW = re.compile(r"^\| `([a-z_.]+)` \| ([A-M-]) \| ([PRGI]) \|", re.MULTILINE)
MAP_ROW = re.compile(r"^\| ([A-Z]{2}-\d+) \|(.*)$", re.MULTILINE)
CHECK_REF = re.compile(r"`([a-z_]+\.[a-z_]+): ([a-z_0-9]+)`")


def parse(gdd_text, plan_text):
    rules = RULE.findall(gdd_text)
    catalog = {name: kind for name, _family, kind in CATALOG_ROW.findall(plan_text)}
    rows = []
    for rule, rest in MAP_ROW.findall(plan_text):
        cells = [c.strip() for c in rest.split("|")]
        rows.append(
            {
                "rule": rule,
                "checks": CHECK_REF.findall(cells[1]) if len(cells) > 1 else [],
                "kind": cells[2] if len(cells) > 2 else "",
            }
        )
    return rules, catalog, rows


def problems(rules, catalog, rows):
    out = []
    known = set(rules)
    for rule, n in Counter(rules).items():
        if n > 1:
            out.append(f"GDD rule {rule} defined {n} times")
    counted = Counter(r["rule"] for r in rows)
    for rule in rules:
        if counted[rule] == 0:
            out.append(f"{rule}: no coverage row")
        elif counted[rule] > 1:
            out.append(f"{rule}: {counted[rule]} coverage rows")
    used = set()
    for row in rows:
        rule = row["rule"]
        if rule not in known:
            out.append(f"{rule}: coverage row for a rule the GDD does not have")
        if not row["checks"]:
            out.append(f"{rule}: no assertion named")
        kinds = set()
        for template, _assertion in row["checks"]:
            if template not in catalog:
                out.append(f"{rule}: template {template} not in the catalog")
                continue
            used.add(template)
            kinds.add(catalog[template])
        if row["kind"] not in kinds:
            out.append(
                f"{rule}: kind {row['kind']} but its templates are {sorted(kinds)}"
            )
    for template in sorted(set(catalog) - used):
        out.append(f"catalog template {template} is named by no coverage row")
    return out


def main():
    ap = argparse.ArgumentParser(description="Check GDD rule coverage.")
    ap.add_argument("--gdd", default=str(TASK / "common/design/GDD.md"))
    ap.add_argument("--plan", default=str(TASK / "notes/PHASE1-PLAN.md"))
    args = ap.parse_args()
    rules, catalog, rows = parse(
        Path(args.gdd).read_text(), Path(args.plan).read_text()
    )
    found = problems(rules, catalog, rows)
    for msg in found:
        print(msg)
    kinds = Counter(r["kind"] for r in rows)
    print(
        f"{len(rules)} rules, {len(rows)} coverage rows, {len(catalog)} templates, "
        f"rows by kind {dict(sorted(kinds.items()))}, {len(found)} problems"
    )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
