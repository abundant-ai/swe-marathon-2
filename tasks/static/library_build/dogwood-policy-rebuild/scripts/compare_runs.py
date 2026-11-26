"""Family signature of one build's run against the release build's run (python3 -I).

Both inputs are `run_cases.py` outputs over the same case set. A case passes when its first run's
exit status and normalised output equal the release build's first run. Families report case pass
rates and, where cases come in pairs, pair pass rates (both members must pass). The weighted
score uses the grader's own weights and normalisation.

Usage: compare_runs.py --gold RUN.json --other RUN.json [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tests"))

from verifier.contracts import CaseResult
from verifier.scoring import family_pass_rates, reward


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True, type=Path)
    ap.add_argument("--other", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    gold = json.loads(a.gold.read_text())
    other = json.loads(a.other.read_text())
    results: list[CaseResult] = []
    case_rates: dict[str, list[int]] = {}
    for cid, g in gold.items():
        o = other.get(cid)
        ok = o is not None and (o["runs"][0]["rc"], o["runs"][0]["norm"]) == (
            g["runs"][0]["rc"],
            g["runs"][0]["norm"],
        )
        results.append(CaseResult(cid, g["family"], g.get("pair"), ok, ""))
        tot = case_rates.setdefault(g["family"], [0, 0])
        tot[0] += 1
        tot[1] += 1 if ok else 0
    units = family_pass_rates(results)
    score, _ = reward(units, {})
    summary = {
        "score": score,
        "families": {
            f: {
                "cases": case_rates[f][0],
                "case_rate": round(case_rates[f][1] / case_rates[f][0], 4),
                "units": units[f]["units"],
                "unit_rate": round(units[f]["rate"], 4),
            }
            for f in sorted(units)
        },
    }
    if a.out:
        a.out.write_text(
            json.dumps(
                {**summary, "failing": [r.case_id for r in results if not r.passed]},
                indent=1,
            )
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
