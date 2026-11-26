"""Record the expected result of every private case from the 1.2.0 release build.

Runs at verifier image build time, in a stage that holds the release binary; only the recorded
results reach the final image. Each case runs three times the way the grader runs it (same user,
environment and limits). A case whose normalised output or exit status differs between runs
stops the build: the case set must only hold cases with one answer.

Usage: python3 -I -B record.py <release-binary> <private-dir> <out-gold.jsonl>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier.contracts import Case, Limits
from verifier.normalise import normalise
from verifier.runner import run_case

RUNS = 3


def main(binary: Path, private: Path, out: Path) -> int:
    limits = Limits()
    unstable: list[str] = []
    lines: list[str] = []
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
        )
        seen = set()
        for _ in range(RUNS):
            status, stdout = run_case(binary, case, private / "bundles", limits)
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
    out.write_text("\n".join(lines) + "\n")
    print(f"recorded {len(lines)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
