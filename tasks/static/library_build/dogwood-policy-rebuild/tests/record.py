"""Record the expected result of every private case from the 1.2.0 release build.

Runs at verifier image build time, in a stage that holds the release binary; only the recorded
results reach the final image. Each case runs three times the way the grader runs it (same user,
environment and limits), except that a run may take 10 seconds instead of 1: the recording needs
the build's answer, and a slow or busy build machine must not stop the image. A case whose
normalised output or exit status differs between runs stops the build: the case set must only
hold cases with one answer. The SHA-256 of the recorded results and the slowest run are printed
and kept beside them, so the results recorded here can be compared with the ones reviewed when
the case set was made.

Usage: python3 -I -B record.py <release-binary> <private-dir> <out-gold.jsonl> <out-meta.json>
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier.contracts import Case, Limits
from verifier.normalise import normalise
from verifier.runner import run_case

RUNS = 3
RECORD_LIMIT_SEC = 10.0


def main(binary: Path, private: Path, out: Path, meta_out: Path) -> int:
    limits = Limits(case_timeout_sec=RECORD_LIMIT_SEC)
    unstable: list[str] = []
    lines: list[str] = []
    slowest = (0.0, "")
    for raw in (private / "cases.jsonl").read_text().splitlines():
        if not raw.strip():
            continue
        c = json.loads(raw)
        case = Case(
            c["id"],
            c["family"],
            c["bundle"],
            tuple(c["args"]),
            c["fmt"],
            c.get("pair"),
            0,
            "",
            c.get("stdin"),
            tuple(c["files"]) if "files" in c else None,
        )
        seen = set()
        for _ in range(RUNS):
            t0 = time.monotonic()
            status, stdout = run_case(binary, case, private / "bundles", limits)
            slowest = max(slowest, (time.monotonic() - t0, case.case_id))
            seen.add((status, normalise(stdout, case.fmt)))
        if len(seen) != 1:
            unstable.append(case.case_id)
            continue
        ((status, text),) = seen
        if not isinstance(status, int):
            unstable.append(f"{case.case_id} ({status})")
            continue
        lines.append(
            json.dumps(
                {"id": case.case_id, "rc": status, "stdout": text}, sort_keys=True
            )
        )
    if unstable:
        print(
            "cases without a single answer:",
            *unstable[:50],
            sep="\n  ",
            file=sys.stderr,
        )
        return 1
    data = ("\n".join(lines) + "\n").encode("utf-8")
    out.write_bytes(data)
    meta = {
        "cases": len(lines),
        "sha256": hashlib.sha256(data).hexdigest(),
        "slowest_run_seconds": round(slowest[0], 3),
        "slowest_case": slowest[1],
    }
    meta_out.write_text(json.dumps(meta, sort_keys=True) + "\n")
    print(f"recorded {len(lines)} cases: {json.dumps(meta, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    sys.exit(
        main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    )
