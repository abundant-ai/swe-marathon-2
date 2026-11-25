"""Write the non-blank line count and the syntax-tree hash of every original unit body.

Build time only. The hashes let the verifier report how many submitted bodies are identical to
the original by size of body, and the line counts weight the unit share; no body is shipped.

usage: unit_bodies.py <original_root> <units.json> <out.json>
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "..", "common"),
                os.path.join(HERE, "..", "..", "steps", "01-restore-bodies", "tests", "verifier", "lib")]
import bodies  # noqa: E402


def main():
    root, units_path, out = sys.argv[1:4]
    units = json.load(open(units_path, encoding="utf-8"))
    facts = bodies.body_facts(root, units)
    missing = [u["uid"] for u in units if u["uid"] not in facts]
    if missing:
        raise SystemExit(f"no body found for {len(missing)} units, first {missing[:5]}")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(facts.items())), f)
    print(json.dumps({"units": len(facts), "lines": sum(v[0] for v in facts.values())}))


if __name__ == "__main__":
    main()
