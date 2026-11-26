"""End-to-end checks with Godot (run with CC_GODOT_CHECKS=1; every process waits for free
memory, QA_MEM_FLOOR, default 30%). Run them one heavy job at a time:

    CC_GODOT_CHECKS=1 python scripts/heavy.py -- python -m pytest checks -m godot

Needs the Godot binary ($QA_GODOT or the spike's vendor copy) and the built library.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parent.parent
LIB = (
    TASK
    / "common/probe/build"
    / ("darwin-arm64" if sys.platform == "darwin" else "linux-x86_64")
)
LIB = LIB / ("libtelemetry.dylib" if sys.platform == "darwin" else "libtelemetry.so")
VENDOR = (
    Path.home()
    / "Documents/github/Abundant/game-spike/vendor/godot-4.7.2/Godot.app/Contents/MacOS/Godot"
)
pytestmark = pytest.mark.godot


def godot() -> str:
    """The Godot binary for these checks."""
    path = os.environ.get("QA_GODOT") or str(VENDOR)
    if not Path(path).is_file():
        pytest.skip("no Godot binary")
    return path


def grade(tmp_path: Path, project: Path, *extra: str) -> tuple[int, dict, Path]:
    """Run the real grader on a project; return (exit code, report, output folder)."""
    os.environ.setdefault("QA_MEM_FLOOR", "30")
    out = tmp_path / "out"
    cmd = [
        sys.executable, str(TASK / "tests/verify.py"),
        "--project", str(project), "--out", str(out), "--work", str(tmp_path / "work"),
        "--godot", godot(), "--library", str(LIB),
        "--instances", str(TASK / "tests/selftest/instances.json"), *extra,
    ]  # fmt: skip
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    report = (
        json.loads((out / "report.json").read_text())
        if (out / "report.json").exists()
        else {}
    )
    return proc.returncode, report, out


def test_selftest_then_our_project_scores_one(tmp_path: Path) -> None:
    """The self-test passes and our own project, graded as a submission, scores 1.0."""
    code, report, out = grade(tmp_path, TASK / "tests/selftest/project")
    assert code == 0 and report["selftest"]["ok"], report.get("selftest")
    assert (out / "reward.txt").read_text().strip() == "1.000000"


def test_crashing_game_scores_zero_with_a_reward(tmp_path: Path) -> None:
    """A game that crashes in every instance gets a written reward of 0."""
    sys.path.insert(0, str(TASK / "checks"))
    from hostile_projects import build

    project = build("crash", tmp_path / "project")
    code, report, out = grade(tmp_path, project, "--skip-selftest")
    assert code == 0 and (out / "reward.txt").read_text().strip() == "0.000000"
    assert all(i["failure"] == "standing:process" for i in report["instances"])


def test_failed_selftest_leaves_no_reward(tmp_path: Path) -> None:
    """When the self-test cannot pass (here: no telemetry library), no reward is written."""
    fake = tmp_path / "missing.dylib"
    fake.write_bytes(b"not a library")
    out = tmp_path / "out"
    out.mkdir()
    (out / "reward.txt").write_text("0.5\n")  # a stale reward must disappear
    cmd = [
        sys.executable, str(TASK / "tests/verify.py"),
        "--project", str(TASK / "tests/selftest/project"), "--out", str(out),
        "--work", str(tmp_path / "work"), "--godot", godot(), "--library", str(fake),
        "--instances", str(TASK / "tests/selftest/instances.json"),
    ]  # fmt: skip
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 1 and not (out / "reward.txt").exists()
    assert json.loads((out / "report.json").read_text())["status"] == "evaluation_error"
