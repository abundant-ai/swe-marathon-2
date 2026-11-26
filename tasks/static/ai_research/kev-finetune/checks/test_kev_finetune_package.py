"""Regression checks for the kev-finetune task: verifier staging, pins and the runtime bundle."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import tomllib
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = load("kev_verify", TASK / "tests" / "verify.py")
package = load("kev_package", TASK / "scripts" / "package_task.py")


def write_checkpoint(directory: Path) -> None:
    directory.mkdir(parents=True)
    for name in verify.CHECKPOINT_FILES:
        (directory / name).write_bytes(b"x")


@pytest.fixture
def app(tmp_path, monkeypatch):
    model = tmp_path / "app" / "model"
    monkeypatch.setattr(verify, "APP_MODEL", model)
    return model


def test_stages_only_the_checkpoint_files(app, tmp_path):
    write_checkpoint(app)
    (app / "extra.bin").write_bytes(b"y")
    verify.stage_checkpoint(tmp_path / "stage")
    assert sorted(p.name for p in (tmp_path / "stage").iterdir()) == sorted(
        verify.CHECKPOINT_FILES
    )


@pytest.mark.parametrize("attack", ["symlink", "fifo", "missing"])
def test_refuses_unsafe_or_missing_files(app, tmp_path, attack):
    write_checkpoint(app)
    target = app / "head.pt"
    target.unlink()
    if attack == "symlink":
        target.symlink_to("/etc/passwd")
    elif attack == "fifo":
        os.mkfifo(target)
    with pytest.raises(verify.CandidateError):
        verify.stage_checkpoint(tmp_path / "stage")


def test_refuses_a_linked_or_absent_model_directory(app, tmp_path):
    with pytest.raises(verify.CandidateError):
        verify.stage_checkpoint(tmp_path / "stage-absent")
    real = tmp_path / "real"
    write_checkpoint(real)
    app.parent.mkdir(parents=True, exist_ok=True)
    app.symlink_to(real)
    with pytest.raises(verify.CandidateError):
        verify.stage_checkpoint(tmp_path / "stage-linked")


def test_refuses_oversized_files(app, tmp_path, monkeypatch):
    write_checkpoint(app)
    monkeypatch.setitem(verify.CHECKPOINT_FILES, "head.pt", 0)
    with pytest.raises(verify.CandidateError):
        verify.stage_checkpoint(tmp_path / "stage")


def test_pins_agree_between_images_and_grader():
    agent = (TASK / "environment" / "Dockerfile").read_text()
    verifier = (TASK / "tests" / "Dockerfile").read_text()
    grader = (TASK / "tests" / "grader.py").read_text()
    for key in ("KEV_COMMIT", "QWEN_BASE_REVISION", "KEV_08B_REVISION"):
        values = {
            re.search(rf"{key}=(\w+)", text).group(1) for text in (agent, verifier)
        }
        assert len(values) == 1, key
    revision = re.search(r"QWEN_BASE_REVISION=(\w+)", agent).group(1)
    assert f'BASE_REVISION = "{revision}"' in grader
    assert agent.split("\n", 1)[0] == verifier.split("\n", 1)[0]


def test_agent_image_ships_no_held_out_material():
    listed = [
        line
        for line in (TASK / "environment" / "kev-files.txt").read_text().split()
        if not line.startswith("#")
    ]
    assert not any(
        p.startswith("evals/") or "transfer" in p or "study_v3" in p for p in listed
    )
    assert (
        "rm -f /opt/kev/kev/study_v3.py /opt/kev/kev/transfer_v9.py"
        in (TASK / "environment" / "Dockerfile").read_text()
    )


def test_task_config():
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert "steps" not in config
    assert config["environment"]["allowed_hosts"] == ["api.anthropic.com"]
    assert config["verifier"]["network_mode"] == "no-network"
    assert config["verifier"]["environment_mode"] == "separate"


def test_bundle_holds_only_runtime_files(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    monkeypatch.setattr(package, "BUNDLE", bundle)
    package.main()
    shipped = sorted(
        str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file()
    )
    assert shipped == sorted(package.FILES)
    assert not any(
        p.startswith(("scripts/", "checks/", "experiment/")) or p == "README.md"
        for p in shipped
    )
    for relative in package.EXECUTABLE:
        assert os.access(bundle / relative, os.X_OK)


def test_public_examples_hide_source_names():
    for line in (
        (TASK / "environment" / "resources" / "public-20.jsonl")
        .read_text()
        .splitlines()
    ):
        record = json.loads(line)
        assert set(record) == {"state", "questions"}
        assert all("src" not in q for q in record["questions"].values())


def test_reward_is_gain_over_the_released_model():
    suites = {
        "transfer_test": {"acc": 0.70},
        "decision_test": {"acc": 0.84},
        "released_transfer_test": {"acc": 0.70},
        "released_decision_test": {"acc": 0.84},
    }
    assert verify.improvement(suites)["reward"] == 0.0
    suites["transfer_test"]["acc"] = 0.86
    gain = verify.improvement(suites)
    assert gain["reward"] == pytest.approx((0.85 - 0.77) / (0.85 - 0.77))
    suites["decision_test"]["acc"] = 0.60
    assert verify.improvement(suites)["reward"] == 0.0


def test_records_are_required(tmp_path, monkeypatch):
    monkeypatch.setattr(verify, "APP_TRAIN", tmp_path / "train")
    monkeypatch.setattr(verify, "APP_REPORT", tmp_path / "REPORT.md")
    with pytest.raises(verify.CandidateError):
        verify.check_records()
    (tmp_path / "REPORT.md").write_text("runs")
    (tmp_path / "train").mkdir()
    with pytest.raises(verify.CandidateError):
        verify.check_records()
    (tmp_path / "train" / "link.py").symlink_to("/etc/passwd")
    with pytest.raises(verify.CandidateError):
        verify.check_records()
    (tmp_path / "train" / "train.sh").write_text("python -m kev.train")
    verify.check_records()
