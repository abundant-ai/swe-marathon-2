"""Validate the deliverable using Harbor's real task parser."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

import pytest
import yaml
from harbor.models.task.task import Task
from harbor.models.task.verifier_mode import resolve_step_verifier_mode, resolve_verifier_environment_definition
from harbor.models.trial.config import AgentConfig, EnvironmentConfig, VerifierConfig
from harbor.trial.network_policy import resolve_trial_network_plan

from verifier.judging.client import KnowledgeJudge
from package_step import package_step
from verifier.inputs import load_inputs
from verifier.dataset import QUESTION_COUNT
from verifier.registry import CHECKS

from task_paths import TASK_ROOT


def test_complete_bundle_round_trip(tmp_path: Path, chroma_endpoint: dict[str, str]) -> None:
    """Load extracted runtime code with separately supplied author test fixtures.

    Args:
        tmp_path: Temporary archive/extraction destination.
        chroma_endpoint: Local service used by the extracted verifier process.
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
        assert all(not name.endswith(".jsonl") for name in names)
        archive.extractall(extracted, filter="data")
    root = extracted / "swe-m2_ai-engineering_knowledge-work-assistant"
    assert Path(result["task_path"]).name == root.name
    assert {path.name for path in root.iterdir()} == {
        "task.toml", "environment", "steps", "BUNDLE_MANIFEST.json",
    }
    task = Task(root)
    assert task.config.task.name == "abundant/swe-m2_ai-engineering_knowledge-work-assistant"
    assert task.config.task.name.rsplit("/", 1)[-1] == root.name
    assert task.config.metadata["reward_type"] == "continuous"
    assert task.has_steps
    assert [step.name for step in task.config.steps] == ["01-build-rag"]
    solution = root / "steps/01-build-rag/solution"
    assert (solution / "solve.sh").stat().st_mode & 0o111
    assert (solution / "oracle.py").is_file()
    assert (solution / "app/main.py").is_file()
    assert not (root / "environment/solution").exists()
    definition = resolve_verifier_environment_definition(task.config, task.paths, task.config.steps[0])
    assert definition is not None and definition.bundled_tests
    assert definition.directory == root / "steps/01-build-rag/tests"
    compose_source = (root / "environment/docker-compose.yaml").read_bytes()
    assert (definition.directory / "docker-compose.yaml").read_bytes() == compose_source
    services = yaml.safe_load(compose_source)["services"]
    assert "volumes" not in services["main"]
    assert "ports" not in services["chroma"]
    assert "deploy" not in services["chroma"]
    assert services["chroma"]["volumes"] == ["/var/lib/orange-chroma"]
    assert services["chroma"]["environment"]["CHROMA_MAX_READ_RECORDS"] == "100"
    assert services["chroma"]["read_only"] is True
    service_root = root / "environment/chroma-service"
    for source in service_root.rglob("*"):
        if source.is_file():
            assert (definition.directory / "chroma-service" / source.relative_to(service_root)).read_bytes() == source.read_bytes()
    for source in (root / "environment").rglob("*"):
        if source.is_file() and source.name not in {"Dockerfile", ".dockerignore", "docker-compose.yaml"} and "chroma-service" not in source.parts:
            staged = definition.directory / "gpu-runtime" / source.relative_to(root / "environment")
            assert staged.read_bytes() == source.read_bytes()
    _, cases, manifest = load_inputs(root / "steps/01-build-rag/tests/private", allow_ci_fixtures=True)
    assert len(cases) == QUESTION_COUNT
    assert all(case.rubric for case in cases)
    assert manifest["sample_records"] == 1570
    assert len(json.loads((root / "environment/data/corpus.json").read_text())) == 1570
    assert "HERB" not in (root / "environment/resources/README.md").read_text()
    assert all("license" not in Path(name).name.lower() and "notice" not in Path(name).name.lower() for name in names)
    assert {path.name for path in (root / "environment/data").iterdir()} == {"corpus.json"}
    # Fixtures are author test support, never part of the shipped task artifact.
    support = tmp_path / "author-support" / "checks"
    shutil.copytree(TASK_ROOT / "checks", support, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(TASK_ROOT / "task.toml", support.parent / "task.toml")
    shutil.copy2(TASK_ROOT / "scripts/prepare_data.py", support / "prepare_data.py")
    shutil.copy2(TASK_ROOT / "scripts/task_paths.py", support / "task_paths.py")
    # Runtime imports must resolve from the extracted package in a fresh process.
    script = """
import json
import runpy
import sys
from pathlib import Path
root, workspace, support = map(Path, sys.argv[1:])
for directory in (support, root / "steps/01-build-rag/tests"):
    sys.path.insert(0, str(directory))
entry = runpy.run_path(str(root / "steps/01-build-rag/tests/verify.py"), run_name="packaged_entry")
import task_paths
task_paths.TASK_ROOT = root
from test_verifier import context
from verifier.runner import verify
assert entry["verify"] is verify
result = verify(context.__wrapped__(workspace, {}))
assert result.passed, result
assert result.metrics["reward"] == 1.0
print(json.dumps({"checks": len(result.checks), "reward": result.metrics["reward"]}))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(root), str(tmp_path / "package-run"), str(support)],
        cwd=tmp_path, capture_output=True, text=True, timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"checks": len(CHECKS), "reward": 1.0}




def test_package_selection_excludes_local_experiments_and_development_files(tmp_path: Path) -> None:
    """Keep local task development material outside deployable image inputs.

    Exercise the packager's selection boundary with experiments at the task root
    and nested inside a runtime directory. Neither may leak into a runtime bundle.

    Args:
        tmp_path: Isolated source task populated with small synthetic inputs;
            no prepared corpus, local experiments, or network access is needed.
    """
    from package_step import selected_files

    runtime = {
        "task.toml", "environment/data/corpus.json",
        "environment/resources/README.md",
        "steps/01-build-rag/tests/private/cases.json",
        "steps/01-build-rag/tests/private/rubrics.json",
        "steps/01-build-rag/tests/private/corpus.json",
    }
    development = {
        "README.md", "pyproject.toml", "checks/test_local.py",
        "scripts/prepare.py", "experiment/dist/old-bundle.tar.gz",
        "environment/experiment/private-report.json",
        "steps/01-build-rag/experiment/scratch.py",
        "common/private/unused-fixture.json",
    }
    for relative in runtime | development:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    selected = {str(path.relative_to(tmp_path)) for path in selected_files(tmp_path)}
    assert selected == runtime


def test_application_and_judge_credentials_do_not_collide_with_harnesses() -> None:
    """Keep coding-harness keys out of the application's connection contract."""
    config = tomllib.loads((TASK_ROOT / "task.toml").read_text())
    agent_environment = config["environment"]["env"]
    assert "ORANGE_JUDGE_API_KEY" not in agent_environment
    assert "OPENAI_API_KEY" not in agent_environment
    assert agent_environment["ORANGE_OPENAI_API_KEY"] == "${OPENAI_API_KEY}"
    assert config["solution"]["env"] == {"ORANGE_OPENAI_API_KEY": "${OPENAI_API_KEY}"}
    assert config["verifier"]["env"]["ORANGE_JUDGE_API_KEY"] == "${OPENAI_API_KEY}"
    assert config["verifier"]["env"]["ORANGE_OPENAI_API_KEY"] == "${OPENAI_API_KEY}"
    resources = json.loads((TASK_ROOT / "environment/resources/resources.json").read_text())
    assert resources["generation"]["credential_env"] == "ORANGE_OPENAI_API_KEY"


def test_step_timeouts_match_declared_execution_budgets() -> None:
    """Prevent Harbor's default step timeout from shortening evaluation.

    Inspect parsed steps as well as the root configuration: the deployed Harbor
    runner prefers a step's verifier timeout, whose default is only 600 seconds.
    Explicit step settings must preserve the requested four/twenty-eight-hour budgets.
    """
    task = Task(TASK_ROOT)
    assert task.config.agent.timeout_sec == 4 * 60 * 60
    assert task.config.verifier.timeout_sec == 28 * 60 * 60
    for step in task.config.steps:
        assert "timeout_sec" in step.agent.model_fields_set
        assert "timeout_sec" in step.verifier.model_fields_set
        assert step.agent.timeout_sec == task.config.agent.timeout_sec
        assert step.verifier.timeout_sec == task.config.verifier.timeout_sec


def test_judge_never_falls_back_to_a_harness_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail configuration when the dedicated judge credential is absent.

    Args:
        monkeypatch: Isolated synthetic environment with only a harness key.
    """
    monkeypatch.delenv("ORANGE_JUDGE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-harness-key")
    with pytest.raises(KeyError, match="ORANGE_JUDGE_API_KEY"):
        KnowledgeJudge()


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
        for policy in (plan.agent_env_baseline, plan.agent_phase, plan.verifier_env_baseline, plan.verifier_phase):
            assert policy is not None
            assert policy.network_mode == "allowlist"
            assert policy.allowed_hosts == ["api.openai.com"]
        assert step.min_reward is None


def test_candidate_resources_omit_dataset_identity() -> None:
    """Check prepared candidate inputs for upstream dataset names and revision.

    Used by the packaging suite after data preparation to catch provenance
    leaking into candidate resources or instructions. Returns no value;
    assertions identify any disclosed dataset identity.
    """
    environment = TASK_ROOT / "environment"
    for path in (environment / "resources/README.md", environment / "resources/corpus/manifest.json",
                 environment / "data/corpus.json", TASK_ROOT / "steps/01-build-rag/instruction.md"):
        text = path.read_text().lower()
        assert "enterpriserag-bench" not in text
        assert "69916e31c68aa5963c00248fd7f0bc12d04fd235" not in text
        assert "salesforceairesearch" not in text
        assert "db3bf9b3f911745726c579c9dbf9f7f6b2c05b36" not in text


def test_sample_covers_the_described_domain() -> None:
    """Retain every source type while allowing incomplete threads in the sample."""
    from prepare_data import SOURCE_KEYS

    sample = json.loads((TASK_ROOT / "environment/data/corpus.json").read_text())
    manifest = json.loads((TASK_ROOT / "steps/01-build-rag/tests/private/manifest.json").read_text())
    assert {row["source_type"] for row in sample} == {*SOURCE_KEYS, "directory"}
    assert len(sample) < .05 * manifest["corpus_records"]
    instruction = (TASK_ROOT / "steps/01-build-rag/instruction.md").read_text()
    assert "90%" not in instruction
    assert "software company" in instruction
    config = tomllib.loads((TASK_ROOT / "task.toml").read_text())
    assert "ORANGE_EVAL_ACCURACY_TARGET" not in config["verifier"]["env"]


def test_chroma_reference_matches_installed_and_locked_version(chroma_endpoint: dict[str, str]) -> None:
    """Run the shipped examples against the pinned service and check image inclusion.

    Args:
        chroma_endpoint: Isolated HTTP service exported through the same connection
            variables used in the development container. Examples write only here.
    """
    import re
    from importlib.metadata import version
    from typing import Any

    installed = version("chromadb")
    for directory in (TASK_ROOT, TASK_ROOT / "environment", TASK_ROOT / "environment/application",
                      TASK_ROOT / "common/chroma-service", TASK_ROOT / "steps/01-build-rag/tests"):
        project = tomllib.loads((directory / "pyproject.toml").read_text())
        assert f"chromadb=={installed}" in project["project"]["dependencies"]
        lock = tomllib.loads((directory / "uv.lock").read_text())
        assert next(row["version"] for row in lock["package"] if row["name"] == "chromadb") == installed
    resources = TASK_ROOT / "environment/resources"
    reference = (resources / "chroma-api.md").read_text()
    assert reference.startswith(f"# Chroma {installed} Python API reference")
    examples = re.findall(r"```python\n(.*?)\n```", reference, re.DOTALL)
    assert examples
    namespace: dict[str, Any] = {}
    for example in examples:
        exec(compile(example, str(resources / "chroma-api.md"), "exec"), namespace)
    assert namespace["records"]["ids"] == ["doc-1"]
    assert namespace["records"]["documents"] == ["The release is Friday."]
    assert namespace["neighbors"]["ids"] == [["doc-1"]]
    assert set(namespace["all_ids"]) == {"doc-1", "doc-2"}
    assert "COPY resources/ /opt/resources/" in (TASK_ROOT / "environment/Dockerfile").read_text()


def test_judge_environment_is_locked_and_bundled() -> None:
    """Keep application and judge SDKs isolated from SGLang's older OpenAI pin.

    Check the shipped locks and both image recipes so the oracle's PydanticAI
    tool runtime is also available to candidates and restored submissions.
    """
    from package_step import selected_files

    files = {str(path.relative_to(TASK_ROOT)) for path in selected_files(TASK_ROOT)}
    assert {"steps/01-build-rag/tests/pyproject.toml", "steps/01-build-rag/tests/uv.lock"} <= files
    judge_lock = tomllib.loads((TASK_ROOT / "steps/01-build-rag/tests/uv.lock").read_text())
    app_lock = tomllib.loads((TASK_ROOT / "environment/uv.lock").read_text())
    judge_packages = {row["name"]: row["version"] for row in judge_lock["package"]}
    app_packages = {row["name"]: row["version"] for row in app_lock["package"]}
    assert judge_packages["pydantic-ai-slim"] == "2.68.0"
    assert judge_packages["openai"] == "3.49.0"
    assert app_packages["openai"] == "2.6.1"
    assert "pydantic-ai-slim" not in app_packages
    assert "sglang" not in judge_packages
    application_lock = tomllib.loads((TASK_ROOT / "environment/application/uv.lock").read_text())
    application_packages = {row["name"]: row["version"] for row in application_lock["package"]}
    assert application_packages["pydantic-ai-slim"] == judge_packages["pydantic-ai-slim"]
    assert application_packages["openai"] == judge_packages["openai"]
    assert application_packages["chromadb"] == judge_packages["chromadb"]
    assert "sglang" not in application_packages
    assert {"environment/application/pyproject.toml", "environment/application/uv.lock"} <= files
    for recipe in (TASK_ROOT / "environment/Dockerfile", TASK_ROOT / "steps/01-build-rag/tests/Dockerfile"):
        assert "UV_PROJECT_ENVIRONMENT=/opt/application uv sync --project /opt/application-project --frozen" in recipe.read_text()
        assert 'ENV PATH="/app:/opt/application/bin:/opt/runtime/bin:${PATH}"' in recipe.read_text()
    dockerfile = (TASK_ROOT / "steps/01-build-rag/tests/Dockerfile").read_text()
    assert "COPY pyproject.toml uv.lock /opt/verifier-project/" in dockerfile
    assert "/opt/verifier" not in (TASK_ROOT / "environment/Dockerfile").read_text()
    assert "UV_PROJECT_ENVIRONMENT=/opt/verifier uv sync --project /opt/verifier-project --frozen" in dockerfile
    assert "exec /opt/verifier/bin/python -I /tests/verify.py" in (TASK_ROOT / "steps/01-build-rag/tests/test.sh").read_text()


def test_dedicated_verifier_reuses_gpu_recipe_and_bundles_private_inputs() -> None:
    """Require a separate image with matching GPU setup and build-time tests.

    Compare executable Dockerfile instructions so runtime changes cannot silently
    drift between development and evaluation. Harbor must select the step's
    dedicated build rather than fall back to the agent image.
    """
    task = Task(TASK_ROOT)
    definition = resolve_verifier_environment_definition(task.config, task.paths, task.config.steps[0])
    tests = TASK_ROOT / "steps/01-build-rag/tests"
    assert definition is not None and definition.bundled_tests
    assert definition.directory == tests
    agent = (TASK_ROOT / "environment/Dockerfile").read_text()
    verifier = (tests / "Dockerfile").read_text()
    gpu_setup = verifier.split("# Only the verifier image", 1)[0].replace("gpu-runtime/", "")
    assert [line for line in gpu_setup.splitlines() if line.strip() and not line.startswith("#")] == [
        line for line in agent.splitlines() if line.strip() and not line.startswith("#")
    ]
    for instruction in ("COPY test.sh verify.py /tests/", "COPY verifier/ /tests/verifier/",
                        "COPY private/ /tests/private/", "RUN chmod 700 /tests"):
        assert instruction in verifier
    assert "COPY private/" not in agent
    assert not (TASK_ROOT / "environment/verifier").exists()
