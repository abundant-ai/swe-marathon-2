"""Helpers for the task's development checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TASK_ROOT = Path(__file__).resolve().parent.parent
DRIVER = Path(__file__).resolve().parent / "fixtures" / "drive.py"
TESTS_DIR = TASK_ROOT / "steps" / "01-restore-bodies" / "tests"


def _run_scenario(name: str) -> dict:
    """Run one verifier scenario in a fresh interpreter and return its JSON result."""
    done = subprocess.run([sys.executable, "-I", "-B", str(DRIVER), name], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


def _verifier_call(code: str, timeout: float = 300) -> object:
    """Run a snippet with this task's verifier importable, in a process of its own; its last line as JSON."""
    prelude = f"import sys; sys.path[:0] = [{str(TESTS_DIR)!r}, {str(TASK_ROOT / 'common')!r}, {str(TESTS_DIR / 'verifier' / 'lib')!r}]\n"
    done = subprocess.run([sys.executable, "-I", "-B", "-c", prelude + code], capture_output=True, text=True, timeout=timeout)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-3000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="session")
def scenario():
    """Return a callable that runs a named verifier scenario in isolation."""
    return _run_scenario


@pytest.fixture(scope="session")
def verifier_call():
    """Return a callable that runs verifier code in isolation and returns its JSON result."""
    return _verifier_call


@pytest.fixture(scope="session")
def task_root() -> Path:
    """Return the task's source directory."""
    return TASK_ROOT
