"""Score the process checkpoints with cumulative, independently observed evidence."""

import argparse
from collections.abc import Callable
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate import EXISTING_REPORT, artifact_ready, call, make_immutable
from offline_cases import OfflineCase, offline_cases
from offline_plan import audit_offline
from registration_verify import VerificationContext, decode_report, verify as verify_registration

WEIGHTS = (1, 2, 3, 6)


@dataclass(frozen=True)
class ProcessCheck:
    """Verdict and trusted evidence for one declared process behavior."""

    name: str
    status: Literal["passed", "failed"]
    explanation: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class ProcessContext:
    """Input paths for the isolated verifier process."""

    app: Path
    assets: Path
    level: int


def job_with_assets(job: dict[str, Any], assets: Path) -> dict[str, Any]:
    """Point the case at its public, readable URDF/SRDF inside this runner."""
    return {
        **job,
        "robot_model": {
            **job["robot_model"],
            "urdf_path": str(assets / "arm.urdf"),
            "srdf_path": str(assets / "arm.srdf"),
        },
    }


def test_offline(context: ProcessContext, case: OfflineCase) -> ProcessCheck:
    """Exercise one planner CLI and audit physical dose and robot motion."""
    coordinated = case.stage == 3
    command = "plan-coordinated" if coordinated else "plan-pass"
    job = job_with_assets(case.job, context.assets)
    response = call(context.app, command, {"job": job, "registration": case.registration}, timeout_s=110)
    if case.expectation == "malformed":
        passed = (
            response.exit_code is not None and response.exit_code > 0
            and response.original_untouched and not response.replaced and response.output == EXISTING_REPORT
        )
        detail = "Invalid input left the prior plan untouched." if passed else (
            "An invalid job or registration must be rejected without altering the previous plan."
        )
        return ProcessCheck(case.name, "passed" if passed else "failed", detail, {})
    report = decode_report(response.output)
    if response.exit_code != 0 or report is None or not response.replaced or not response.original_untouched:
        return ProcessCheck(case.name, "failed", f"{response.detail} No usable replacement plan.", {})
    measured = audit_offline(
        job, case.registration, report, urdf=context.assets / "arm.urdf", srdf=context.assets / "arm.srdf",
        coordinated=coordinated,
    )
    if measured.status == "unresolved":
        raise RuntimeError(f"Independent clearance could not be resolved for the submitted {case.name} path.")
    passed = measured.status == case.expectation
    explanation = (
        "Independent replay matched the expected physical outcome." if passed else
        " ".join(measured.explanations) or f"Expected {case.expectation}, observed {measured.status}."
    )
    return ProcessCheck(case.name, "passed" if passed else "failed", explanation, asdict(measured))


def group_reward(checks: tuple[ProcessCheck, ...], positive: frozenset[str]) -> float:
    """Apply the fixed positive-outcome gate and retain the original denominator."""
    if not any(check.name in positive and check.status == "passed" for check in checks):
        return 0.0
    return sum(check.status == "passed" for check in checks) / len(checks)


def verify(
    context: ProcessContext,
    live_group: Callable[[ProcessContext], tuple[tuple[ProcessCheck, ...], frozenset[str]]] | None = None,
) -> dict[str, Any]:
    """Run implemented groups and combine them with the declared stage weights."""
    if not artifact_ready(context.app):
        return {"stage": context.level, "reward": 0.0, "groups": {}, "application_missing": True}
    make_immutable(context.app)
    registration = verify_registration(VerificationContext(context.app))
    scores = [registration.metrics["reward"]]
    groups: dict[str, Any] = {"registration": asdict(registration)}
    for number in range(2, min(context.level, 3) + 1):
        cases = offline_cases(number)
        checks = tuple(test_offline(context, case) for case in cases)
        score = group_reward(checks, frozenset(case.name for case in cases if case.expectation == "qualified"))
        scores.append(score)
        groups["coordinated" if number == 3 else "fixed"] = {
            "reward": score, "checks": [asdict(check) for check in checks],
        }
    if context.level == 4:
        if live_group is None:
            raise RuntimeError("Live checkpoint has no configured mission driver.")
        checks, positive = live_group(context)
        score = group_reward(checks, positive)
        scores.append(score)
        groups["interruption"] = {"reward": score, "checks": [asdict(check) for check in checks]}
    weights = WEIGHTS[:len(scores)]
    reward = sum(weight * score for weight, score in zip(weights, scores, strict=True)) / sum(weights)
    return {"stage": context.level, "reward": reward, "groups": groups}


def main() -> None:
    """Evaluate the selected packaged checkpoint, then publish trusted evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", required=True, type=int, choices=(2, 3, 4))
    parser.add_argument("--app", type=Path, default=Path("/app"))
    parser.add_argument("--assets", type=Path, default=Path("/app/examples/cell"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.logs.mkdir(mode=0o700, exist_ok=True, parents=True)
    args.logs.chmod(0o700)
    reward = args.logs / "reward.json"
    reward.unlink(missing_ok=True)
    hook = None
    if args.level == 4:
        from verify_live import test_live_group
        hook = test_live_group
    evidence = verify(ProcessContext(args.app, args.assets.resolve(), args.level), hook)
    (args.logs / "checkpoint.json").write_text(json.dumps(evidence, allow_nan=False) + "\n", encoding="utf-8")
    reward.write_text(json.dumps({"reward": evidence["reward"]}) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
