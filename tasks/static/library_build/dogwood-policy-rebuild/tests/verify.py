"""Build the delivered `dogwood` project, run every private case, write the reward and metrics.

Candidate failures (no project, a failed build, wrong output, a hang) are results. The metrics
also list any delivered file that is a copy of Dogwood's own source, for review against the
clean-room rule; that list does not change the reward. A failure of the evaluation itself exits
non-zero and leaves no reward file.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier import integrity, procs
from verifier.build import build
from verifier.contracts import (
    Case,
    EvaluationError,
    VerificationContext,
    VerificationResult,
)
from verifier.runner import run_all
from verifier.scoring import family_pass_rates, reward

REWARD_FILES = ("reward.txt", "reward.json")


def load_cases(private: Path) -> list[Case]:
    """Join the case list with the expected results recorded from the release build."""
    gold: dict[str, dict] = {}
    for line in (private / "gold.jsonl").read_text().splitlines():
        if line.strip():
            entry = json.loads(line)
            gold[entry["id"]] = entry
    cases: list[Case] = []
    for line in (private / "cases.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        g = gold.get(c["id"])
        if g is None:
            raise EvaluationError(f"case {c['id']} has no recorded result")
        cases.append(
            Case(
                case_id=c["id"],
                family=c["family"],
                bundle=c["bundle"],
                args=tuple(c["args"]),
                fmt=c["fmt"],
                pair=c.get("pair"),
                expected_rc=g["rc"],
                expected_stdout=g["stdout"],
                stdin=c.get("stdin"),
            )
        )
    if not cases:
        raise EvaluationError("the private case set is empty")
    return cases


def verify(context: VerificationContext) -> VerificationResult:
    cases = load_cases(context.private)
    baselines_path = context.private / "baselines.json"
    baselines = (
        json.loads(baselines_path.read_text()) if baselines_path.is_file() else {}
    )
    started = time.monotonic()
    copied = (
        integrity.findings(context.submission) if context.submission.is_dir() else []
    )
    built = build(context.submission, context.work, context.limits)
    results = run_all(built.binary, cases, context.private / "bundles", context.limits)
    rates = family_pass_rates(results)
    score, detail = reward(rates, baselines)
    passed = sum(1 for r in results if r.passed)
    metrics = {
        "reward": score,
        "build": {
            "ok": built.ok,
            "detail": built.detail,
            "seconds": round(built.seconds, 1),
        },
        "cases": len(results),
        "cases_passed": passed,
        "families": rates,
        "weighting": detail,
        "all_cases": passed == len(results),
        "at_least_99pct": passed >= 0.99 * len(results),
        "at_least_95pct": passed >= 0.95 * len(results),
        "seconds": round(time.monotonic() - started, 1),
        "failed_cases": [r.case_id for r in results if not r.passed][:200],
        "dogwood_source_files": copied,
        "leftover_processes_ended": dict(procs.LEFTOVERS),
    }
    return VerificationResult(reward=score, metrics=metrics)


def main() -> int:
    adopts_orphans = procs.become_subreaper()
    logs = Path("/logs/verifier")
    logs.mkdir(parents=True, exist_ok=True)
    for name in REWARD_FILES:
        (logs / name).unlink(missing_ok=True)
    context = VerificationContext(
        submission=Path("/app/dogwood-rebuild"),
        private=Path("/tests/private"),
        logs=logs,
        work=Path(tempfile.mkdtemp(prefix="dw-build-")),
    )
    try:
        result = verify(context)
    except Exception:  # noqa: BLE001 - any failure here is the evaluation's, never the candidate's
        (logs / "evaluation-error.txt").write_text(traceback.format_exc())
        return 1
    metrics = dict(result.metrics, adopts_orphans=adopts_orphans)
    (logs / "metrics.json").write_text(json.dumps(metrics, indent=1, sort_keys=True))
    (logs / "reward.txt").write_text(f"{result.reward}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
