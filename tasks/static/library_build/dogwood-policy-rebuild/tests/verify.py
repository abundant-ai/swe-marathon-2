"""Build the delivered `dogwood` project, run every private case, write the reward and metrics.

Candidate failures (no project, a failed build, wrong output, a hang) are results. The metrics
also list any delivered file that is a copy of Dogwood's own source, for review against the
clean-room rule; that list does not change the reward. A failure of the evaluation itself exits
non-zero and leaves no reward file.

The output folder may be writable by every user, the build's and the runs' included, and a
reward file there is read as the result. So the grader opens the folder once without following
links and, before any build or run, closes it to everyone but its owner (its mode comes back at
the end), so a reward the submission plants cannot outlive a grader that dies mid-run. It also
ends every process of both users before it writes, removes whatever the submission left under
its output names, and creates each output fresh (no links followed, no file reused), writing the
reward last.
"""

from __future__ import annotations

import errno
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier import integrity, procs
from verifier.build import BUILDER, build
from verifier.contracts import (
    Case,
    EvaluationError,
    VerificationContext,
    VerificationResult,
)
from verifier.runner import RUNNER, run_all
from verifier.scoring import family_pass_rates, reward

REWARD_FILES = ("reward.txt", "reward.json")
OUTPUTS = (*REWARD_FILES, "metrics.json", "evaluation-error.txt")


class Outputs:
    """The output folder, opened once without following a link; every name is handled relative
    to that descriptor, so a link planted under an output name redirects nothing."""

    def __init__(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.mode = os.fstat(self.fd).st_mode & 0o7777
        try:  # closed to the build's and the runs' users while they can act
            os.fchmod(self.fd, 0o755)
            self.closed = True
        except OSError:
            self.closed = False

    def reopen(self) -> None:
        """Give the folder back its own mode, once no process of the submission is left."""
        if self.closed:
            os.fchmod(self.fd, self.mode)

    def remove(self, names: tuple[str, ...]) -> None:
        for name in names:
            try:
                os.unlink(name, dir_fd=self.fd)
            except FileNotFoundError:
                pass
            except OSError as exc:  # a directory planted under the name
                if exc.errno not in (errno.EISDIR, errno.EPERM):
                    raise
                shutil.rmtree(name, dir_fd=self.fd)

    def write(self, name: str, text: str) -> None:
        self.remove((name,))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        with os.fdopen(os.open(name, flags, 0o644, dir_fd=self.fd), "w") as f:
            f.write(text)


def settle(outputs: Outputs) -> None:
    """End every process of the build user and the run user, then remove whatever stands under
    the output names, so only what the grader writes next is there."""
    for user in (BUILDER, RUNNER):
        procs.end_user(user)
    outputs.remove(OUTPUTS)


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
    outputs = Outputs(logs)
    outputs.remove(OUTPUTS)
    context = VerificationContext(
        submission=Path("/app/dogwood-rebuild"),
        private=Path("/tests/private"),
        logs=logs,
        work=Path(tempfile.mkdtemp(prefix="dw-build-")),
    )
    try:
        result = verify(context)
    except Exception:  # noqa: BLE001 - any failure here is the evaluation's, never the candidate's
        error = traceback.format_exc()
        settle(outputs)
        outputs.write("evaluation-error.txt", error)
        outputs.reopen()
        return 1
    settle(outputs)
    metrics = dict(
        result.metrics,
        adopts_orphans=adopts_orphans,
        output_folder_closed=outputs.closed,
    )
    outputs.write("metrics.json", json.dumps(metrics, indent=1, sort_keys=True))
    # Last: the reward exists only once everything else is done.
    outputs.write("reward.txt", f"{result.reward}\n")
    outputs.reopen()
    return 0


if __name__ == "__main__":
    sys.exit(main())
