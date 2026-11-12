"""Thin Harbor adapter and explicit orchestration of step-1 requirement tests."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

# The production entry point runs with Python -I, outside the submitted workspace.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from client import ApplicationClient
from contracts import CandidateFailure, CheckResult, EvaluationError, HeldOutCase, RegisteredCheck, VerificationContext, VerificationResult
from judge import HERB_REVISION, JUDGE_MODEL, JUDGE_REASONING, PROMPT_SHA256, HerbJudge
import test_requirements as requirements

CHECKS = (
    RegisteredCheck("interfaces", requirements.test_interfaces),
    RegisteredCheck("cli_help", requirements.test_cli_help),
    RegisteredCheck("answer_before_ingestion", requirements.test_answer_before_ingestion, ("interfaces", "cli_help")),
    RegisteredCheck("ingestion_and_persistence", requirements.test_ingestion_and_persistence, ("interfaces",)),
    RegisteredCheck("duplicate_documents", requirements.test_duplicate_documents, ("interfaces", "cli_help")),
    RegisteredCheck("refresh_replaces_index", requirements.test_refresh_replaces_index, ("interfaces", "cli_help")),
    RegisteredCheck("required_call_paths", requirements.test_required_call_paths, ("interfaces", "cli_help")),
    RegisteredCheck("cli_question_files", requirements.test_cli_question_files, ("interfaces", "cli_help")),
    RegisteredCheck("cli_stdin", requirements.test_cli_stdin, ("interfaces", "cli_help")),
    RegisteredCheck("self_generated_evaluation", requirements.test_self_generated_evaluation),
    RegisteredCheck("holdout_accuracy", requirements.test_holdout_accuracy, ("interfaces", "cli_help")),
)


def verify(context: VerificationContext) -> VerificationResult:
    """Run every registered check, record dependency skips, and aggregate results.

    Args:
        context: Trusted inputs and a fresh per-run diagnostics list.

    Returns:
        One result per registry entry, with all mandatory checks required to pass.

    Raises:
        EvaluationError: Infrastructure or judge failure. Completed records remain
            in context.completed for the entry-point adapter to preserve.
    """
    context.completed.clear()
    outcomes: dict[str, CheckResult] = {}
    for check in CHECKS:
        unmet = [name for name in check.requires if outcomes[name].status != "passed"]
        if unmet:
            result = CheckResult(check.name, "skipped", f"Unmet prerequisites: {', '.join(unmet)}")
        else:
            try:
                result = check.function(context)
            except CandidateFailure as exc:
                result = CheckResult(check.name, "failed", str(exc))
        outcomes[check.name] = result
        context.completed.append(result)
    metrics = {key: value for check in context.completed for key, value in check.metrics.items()}
    return VerificationResult(all(check.status == "passed" for check in context.completed), tuple(context.completed), metrics)


def load_inputs(private: Path) -> tuple[Path, tuple[HeldOutCase, ...], dict[str, Any]]:
    """Validate pinned private input hashes and the complete scoring denominator.

    Args:
        private: Trusted directory populated by scripts/prepare_data.py.

    Returns:
        Corpus path, all 238 content cases, and the provenance manifest.

    Raises:
        EvaluationError: Missing, corrupted, or mismatched evaluation inputs.
    """
    try:
        manifest = json.loads((private / "manifest.json").read_text())
        if manifest["herb_revision"] != HERB_REVISION:
            raise ValueError("HERB revision mismatch")
        for filename, key in (("corpus.jsonl", "corpus_sha256"), ("cases.jsonl", "cases_sha256")):
            if hashlib.sha256((private / filename).read_bytes()).hexdigest() != manifest[key]:
                raise ValueError(f"Hash mismatch: {filename}")
        cases = tuple(HeldOutCase(**json.loads(line)) for line in (private / "cases.jsonl").read_text().splitlines())
        if len(cases) != 238 or len({case.question_id for case in cases}) != 238:
            raise ValueError("Expected 238 unique held-out questions")
        return private / "corpus.jsonl", cases, manifest
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EvaluationError(f"Invalid private inputs: {exc}") from exc


def write_report(output: Path, context: VerificationContext | None, result: VerificationResult | None, error: str | None) -> None:
    """Publish diagnostics and a reward only for a completed, valid evaluation.

    Args:
        output: Trusted verifier log directory, inaccessible to the candidate UID.
        context: Partial observations, if context construction succeeded.
        result: Completed evaluation; None means no valid reward.
        error: Safe diagnostic for an infrastructure failure.
    """
    for name in ("reward.json", "reward.txt"):
        (output / name).unlink(missing_ok=True)
    payload = {
        "status": "evaluation_error" if result is None else "completed",
        "judge_model": JUDGE_MODEL, "judge_reasoning": JUDGE_REASONING,
        "herb_revision": HERB_REVISION, "prompt_sha256": PROMPT_SHA256,
        "score_definition": "Arithmetic mean of integer HERB ratings; missing/empty answers score zero",
        "error": error,
        "result": asdict(result) if result else None,
        "completed_checks": [asdict(check) for check in context.completed] if context else [],
    }
    (output / "report.json").write_text(json.dumps(payload, indent=2) + "\n")
    if result is not None:
        (output / "reward.json").write_text(json.dumps({"reward": float(result.passed)}) + "\n")


def main() -> int:
    """Build the isolated production context and map its result to Harbor files.

    Returns:
        Zero for a completed evaluation, including candidate failure; one for an
        invalid run. Candidate code is always executed as UID/GID 10001.
    """
    output = Path("/logs/verifier")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.chmod(0o700)
    for name in ("reward.json", "reward.txt"):
        (output / name).unlink(missing_ok=True)
    context: VerificationContext | None = None
    try:
        if os.geteuid() != 0:
            raise EvaluationError("Production verifier must start as root to isolate candidate UID")
        tests = Path(__file__).resolve().parent
        tests.chmod(0o700)
        corpus, cases, manifest = load_inputs(tests / "private")
        (output / "inputs.json").write_text(json.dumps(manifest, indent=2))
        app_root = Path("/app")
        # Harbor sanitizes artifact archives; do not follow links during ownership changes.
        for directory, subdirs, files in os.walk(app_root, followlinks=False):
            os.chown(directory, 10001, 10001, follow_symlinks=False)
            for name in subdirs + files:
                os.chown(Path(directory) / name, 10001, 10001, follow_symlinks=False)
        environment = {
            "ORANGE_OPENAI_API_KEY": os.environ["ORANGE_OPENAI_API_KEY"],
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        }
        app = ApplicationClient(app_root, uid=10001, environment=environment)
        context = VerificationContext(app, corpus, cases, HerbJudge(), output)
        result = verify(context)
        write_report(output, context, result, None)
        return 0
    except Exception as exc:
        message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
        write_report(output, context, None, message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
