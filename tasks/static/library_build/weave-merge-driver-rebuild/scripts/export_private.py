"""Write the verifier's private inputs from the spike's analysis and the original's recording.

Usage: python3 -I export_private.py CASES.json ANALYSIS.json REF_RUN.json OUT_DIR
Writes OUT_DIR/cases.json (kept cases with their family), expected.json (status and output digest
of the original per case) and netting.json (per family, the best trivial program's pass rate).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    """Export the three private files."""
    cases_path, analysis_path, ref_path, out_dir = sys.argv[1:5]
    cases = {
        c["id"]: c for c in json.loads(Path(cases_path).read_text(encoding="utf-8"))
    }
    analysis = json.loads(Path(analysis_path).read_text())
    kept = analysis["kept"]
    ref = {r["id"]: r for r in json.loads(Path(ref_path).read_text())}
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for cid in sorted(kept):
        c = cases[cid]
        rows.append(
            {k: c[k] for k in ("id", "path", "base", "ours", "theirs")}
            | {"family": kept[cid], "feature": c["feature"]}
        )
    expected = {
        cid: {"status": ref[cid]["status"], "sha256": ref[cid]["sha256"]}
        for cid in sorted(kept)
    }
    netting = analysis["summary"]["netting"]["s_f"]
    with open(os.path.join(out_dir, "cases.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)
    with open(os.path.join(out_dir, "expected.json"), "w") as fh:
        json.dump(expected, fh)
    with open(os.path.join(out_dir, "netting.json"), "w") as fh:
        json.dump(netting, fh)
    print(f"exported {len(rows)} cases, netting for {len(netting)} families")


if __name__ == "__main__":
    main()
