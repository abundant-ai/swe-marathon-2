"""The combinations of `scripts/combos.py` against the release build (fix round 1, QA 17 F2/F5).

Each such bundle records the answer the guide's sentences give (`expect` in `bundle_tags.json`:
one token per trace line, ALLOW, DENY or REJECTED). This reads the release build's recorded human
replay answer of the bundle's trace, takes the same tokens from it, and reports every kind whose
bundles the build answers otherwise. Such a kind is dropped from the case set: the guide must
decide every graded answer, and the build's word alone does not.

Usage: python3 -I combos_check.py --candidates DIR --run RUN.json [--report FILE]
Exit status 1 when a bundle disagrees.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

LINE = re.compile(r"^@-?\d+ \((?:time point \d+|event \d+ of the trace)\): (\S+)")


def tokens(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        m = LINE.match(line)
        if m:
            out.append("REJECTED" if m.group(1).startswith("REJECTED") else m.group(1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True, type=Path)
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()
    tags = json.loads((a.candidates / "bundle_tags.json").read_text())
    run = json.loads(a.run.read_text())
    by_kind: dict[str, dict] = defaultdict(
        lambda: {"bundles": 0, "agree": 0, "disagree": []}
    )
    for bundle, t in sorted(tags.items()):
        expect = (t or {}).get("expect")
        if not expect:
            continue
        for trace, want in expect.items():
            rec = run.get(f"{bundle}/{trace}/replay/human")
            k = by_kind[t["kind"]]
            k["bundles"] += 1
            got = tokens(rec["runs"][0]["norm"]) if rec else None
            if got == want:
                k["agree"] += 1
            else:
                k["disagree"].append(
                    {"bundle": bundle, "expected": want, "recorded": got}
                )
    report = dict(sorted(by_kind.items()))
    if a.report:
        a.report.write_text(json.dumps(report, indent=1) + "\n")
    for kind, k in report.items():
        flag = "" if not k["disagree"] else f"  DISAGREE {len(k['disagree'])}"
        print(f"{kind:28s} {k['agree']}/{k['bundles']}{flag}")
    return 1 if any(k["disagree"] for k in report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
