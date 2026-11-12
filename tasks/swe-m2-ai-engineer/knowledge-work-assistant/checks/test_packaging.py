"""Validate the deliverable using Harbor's real task parser."""

from __future__ import annotations

import json
import tarfile
import tomllib
from pathlib import Path

import pytest
from harbor.models.task.task import Task
from harbor.models.task.verifier_mode import resolve_step_verifier_mode
from harbor.models.trial.config import AgentConfig, EnvironmentConfig, VerifierConfig
from harbor.trial.network_policy import resolve_trial_network_plan

from judge import HerbJudge
from package_step import package_step
from verify import load_inputs

TASK_ROOT = Path(__file__).resolve().parents[1]


def test_complete_bundle_round_trip(tmp_path: Path) -> None:
    """Load an extracted distribution independently of the authoring workspace.

    Args:
        tmp_path: Temporary archive/extraction destination.
    """
    if not (TASK_ROOT / "steps/01-build-rag/tests/private").exists():
        pytest.skip("Prepare HERB inputs before testing the complete bundle")
    result = package_step(TASK_ROOT, tmp_path / "distribution")
    extracted = tmp_path / "extracted"
    with tarfile.open(result["archive"]) as archive:
        names = archive.getnames()
        assert all(".venv" not in name and "__pycache__" not in name for name in names)
        assert all("02-expand-corpus" not in name for name in names)
        assert all(not name.endswith(".env") for name in names)
        archive.extractall(extracted, filter="data")
    root = extracted / "knowledge-work-assistant"
    task = Task(root)
    assert task.has_steps
    assert [step.name for step in task.config.steps] == ["01-build-rag"]
    _, cases, manifest = load_inputs(root / "steps/01-build-rag/tests/private")
    assert len(cases) == 238
    assert manifest["sample_records"] == 1570
    assert len((root / "environment/data/corpus.jsonl").read_text().splitlines()) == 1570
    assert (root / "environment/data/HERB_LICENSE.txt").is_file()


def test_application_and_judge_credentials_do_not_collide_with_harnesses() -> None:
    """Keep coding-harness keys out of the application's connection contract."""
    config = tomllib.loads((TASK_ROOT / "task.toml").read_text())
    agent_environment = config["environment"]["env"]
    assert "ORANGE_JUDGE_API_KEY" not in agent_environment
    assert "OPENAI_API_KEY" not in agent_environment
    assert "ORANGE_OPENAI_API_KEY" in agent_environment
    assert "ORANGE_JUDGE_API_KEY" in config["verifier"]["env"]
    resources = json.loads((TASK_ROOT / "environment/resources/resources.json").read_text())
    assert resources["generation"]["credential_env"] == "ORANGE_OPENAI_API_KEY"


def test_judge_never_falls_back_to_a_harness_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail configuration when the dedicated judge credential is absent.

    Args:
        monkeypatch: Isolated synthetic environment with only a harness key.
    """
    monkeypatch.delenv("ORANGE_JUDGE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-harness-key")
    with pytest.raises(KeyError, match="ORANGE_JUDGE_API_KEY"):
        HerbJudge()


def test_fresh_verifier_has_restricted_network_and_local_gpu() -> None:
    """Check the parsed startup and grading policies, including verifier resources.

    A phase-only restriction would leave a public startup window. Separate verifier
    resources must be explicit because Harbor does not merge the two environment
    tables. This check complements the live container boundary smoke test.
    """
    task = Task(TASK_ROOT)
    verifier = task.config.verifier
    assert verifier.environment_mode == "separate"
    assert verifier.network_mode == "allowlist"
    assert verifier.allowed_hosts == ["api.openai.com"]
    assert verifier.environment is not None
    assert verifier.environment.network_mode == "allowlist"
    assert verifier.environment.allowed_hosts == ["api.openai.com"]
    assert task.config.artifacts == ["/app"]
    for environment in (task.config.environment, verifier.environment):
        assert environment.gpus == 1
        assert environment.gpu_types == ["L4"]
        assert environment.docker_image is None
        assert not any("MODAL_TOKEN" in key for key in environment.env)
    assert not any("MODAL_TOKEN" in key for key in verifier.env)
    resources = json.loads((TASK_ROOT / "environment/resources/resources.json").read_text())
    assert resources["embeddings"]["provider"] == "local"
    assert resources["embeddings"]["path"] == "/opt/models/jina"
    for step in task.config.steps:
        mode = resolve_step_verifier_mode(task.config, step)
        assert mode == "separate"
        plan = resolve_trial_network_plan(
            task.config, AgentConfig(), EnvironmentConfig(), VerifierConfig(), step,
            verifier_mode=mode,
        )
        for policy in (plan.verifier_env_baseline, plan.verifier_phase):
            assert policy is not None
            assert policy.network_mode == "allowlist"
            assert policy.allowed_hosts == ["api.openai.com"]
