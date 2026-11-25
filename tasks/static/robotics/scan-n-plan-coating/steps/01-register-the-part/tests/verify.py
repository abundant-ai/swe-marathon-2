"""Grade the public registration CLI and write trusted checkpoint evidence."""

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate import EXISTING_REPORT, artifact_ready, make_immutable, register
from registration_cases import RegistrationCase, check_registration, registration_cases


@dataclass(frozen=True)
class VerificationContext:
    """Inputs for a fresh registration verification run."""

    app: Path


@dataclass(frozen=True)
class CheckResult:
    """One disclosed behavior exercised by an independently authored case."""

    name: str
    status: Literal["passed", "failed"]
    explanation: str
    measurements: dict[str, float]


@dataclass(frozen=True)
class VerificationResult:
    """Trusted case results and aggregated registration evidence."""

    passed: bool
    checks: tuple[CheckResult, ...]
    metrics: dict[str, float]


def decode_report(output: bytes | None) -> dict[str, Any] | None:
    """Parse a regular result as one JSON object, or return None for invalid output."""
    if output is None:
        return None
    try:
        value = json.loads(output)
    except (ValueError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def test_registration(context: VerificationContext, case: RegistrationCase) -> CheckResult:
    """Test the public CLI on one positive, review, or invalid-input case."""
    malformed = case.expectation == "malformed"
    response = register(context.app, case.job, case.scans)
    report = decode_report(response.output)
    if malformed:
        passed = response.exit_code is not None and response.exit_code > 0
        passed = passed and response.original_untouched and not response.replaced and response.output == EXISTING_REPORT
        reason = "Invalid input was rejected and the existing output was preserved." if passed else (
            "Invalid input must fail with the existing output preserved."
        )
        metrics = {}
    elif response.exit_code != 0 or report is None:
        passed, reason, metrics = False, f"{response.detail} No usable report.", {}
    elif not response.replaced or not response.original_untouched:
        passed, reason, metrics = False, "The completed report must replace the previous file.", {}
    else:
        passed, reason, metrics = check_registration(case, report)
    return CheckResult(case.name, "passed" if passed else "failed", reason, metrics)


def verify(context: VerificationContext) -> VerificationResult:
    """Run all registration checks and gate partial credit on usable registration."""
    cases = registration_cases()
    if not artifact_ready(context.app):
        checks = tuple(
            CheckResult(case.name, "failed", "The submitted coating executable is missing or invalid.", {})
            for case in cases
        )
        return VerificationResult(False, checks, {"reward": 0.0})
    make_immutable(context.app)
    checks = tuple(test_registration(context, case) for case in cases)
    positive = any(
        case.expectation == "registered" and check.status == "passed"
        for case, check in zip(cases, checks, strict=True)
    )
    passed_count = sum(check.status == "passed" for check in checks)
    reward = passed_count / len(checks) if positive else 0.0
    return VerificationResult(passed_count == len(checks), checks, {"reward": reward})


def main() -> None:
    """Run the registered verifier and publish the reward after evidence succeeds."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=Path("/app"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.logs.mkdir(mode=0o700, exist_ok=True, parents=True)
    args.logs.chmod(0o700)
    reward = args.logs / "reward.json"
    reward.unlink(missing_ok=True)
    result = verify(VerificationContext(args.app))
    (args.logs / "checkpoint.json").write_text(json.dumps(asdict(result), allow_nan=False) + "\n", encoding="utf-8")
    reward.write_text(json.dumps({"reward": result.metrics["reward"]}) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
