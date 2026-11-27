"""A quick estimate of the stub zoo from recorded answers, before any stub is built.

Usage: python3 -I stub_estimate.py --private DIR --gold RUN.json

For each trivial program it predicts which units (a single case, or a pair that counts only when
both members pass) it would pass, from the release build's recorded answers alone: printing
nothing (with exit 0, or with each command's most common status), each command's most common
answer, the accept line of `validate`, DENY or ALLOW-rule-0 for every event of a trace, and
`format` as `cat`. The stub zoo itself (stubs.py, built and run by the grader) is the proof; this
only flags a selection that would let one through.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

LINE = re.compile(r"^@(-?\d+) \(time point (\d+)\): ")
ACCEPT = {
    "OK: validation passed with no errors or warnings.\n",
    json.dumps(
        {"errors": [], "passed": True, "passed_without_warnings": True, "warnings": []},
        sort_keys=True,
    ),
}


def key(c: dict) -> str:
    args = c["args"]
    if args and args[0] == "schema":
        head = f"schema-{args[1] if len(args) > 1 else ''}"
    elif args and args[0] == "lower":
        head = f"lower-{args[args.index('--emit') + 1] if '--emit' in args else 'both'}"
    elif args and args[0] == "explain" and "--policy-schema" not in args:
        head = "explain-bare"
    else:
        head = args[0] if args else ""
    fmt = args[args.index("--format") + 1] if "--format" in args else "human"
    return f"{head}/{fmt}"


def stream(text: str, verdict: str) -> str:
    """The stream a stub prints for the decision points of a recorded human stream."""
    out = []
    for line in text.splitlines():
        m = LINE.match(line)
        if m:
            out.append(f"@{m.group(1)} (time point {m.group(2)}): {verdict}")
    return "\n".join(out) + ("\n" if out else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", required=True, type=Path)
    ap.add_argument("--gold", required=True, type=Path)
    a = ap.parse_args()
    cases = [
        json.loads(x)
        for x in (a.private / "cases.jsonl").read_text().splitlines()
        if x.strip()
    ]
    gold = json.loads(a.gold.read_text())

    def answer(c):
        r = gold[c["id"]]["runs"][0]
        return r["rc"], r["norm"]

    common: dict[str, Counter] = defaultdict(Counter)
    for c in cases:
        common[key(c)][answer(c)] += 1
    top = {k: ans for k, v in common.items() for ans, n in v.most_common(1) if n >= 2}
    status = {k: v.most_common(1)[0][0][0] for k, v in common.items()}
    human = {c["id"]: answer(c)[1] for c in cases if key(c).endswith("/human")}

    def passes(stub: str, c: dict) -> bool:
        rc, out = answer(c)
        cmd = c["args"][0] if c["args"] else ""
        if stub == "silent":
            return rc == 0 and not out.strip()
        if stub == "usual-status":
            return rc == status[key(c)] and not out.strip()
        if stub == "most-common":
            return (rc, out) == top.get(key(c))
        if stub == "accept":
            return cmd == "validate" and rc == 0 and out in ACCEPT
        if stub in ("deny", "allow") and cmd == "replay":
            twin = human.get(c["id"].rsplit("/", 1)[0] + "/human", out)
            want = stream(twin, "DENY" if stub == "deny" else "ALLOW  [rules: 0]")
            return rc == 0 and bool(want) and twin == want
        if stub == "cat" and cmd == "format" and len(c["args"]) > 1:
            name = c.get("stdin") if c["args"][1] == "-" else c["args"][1]
            path = a.private / "bundles" / c["bundle"] / (name or "")
            if not (name and path.is_file()):
                return False
            return rc == 0 and out == path.read_text(errors="replace")
        return False

    units: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        units[c.get("pair") or c["id"]].append(c)
    report = {}
    for stub in (
        "silent",
        "usual-status",
        "most-common",
        "accept",
        "deny",
        "allow",
        "cat",
    ):
        passed = [
            u for u, members in units.items() if all(passes(stub, m) for m in members)
        ]
        report[stub] = {"units_passed": len(passed), "examples": sorted(passed)[:5]}
    print(json.dumps({"units": len(units), "stubs": report}, indent=1))
    return 1 if any(v["units_passed"] for v in report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
