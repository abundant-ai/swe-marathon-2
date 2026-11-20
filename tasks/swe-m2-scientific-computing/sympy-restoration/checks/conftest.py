"""Helpers for the task's development checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TASK_ROOT = Path(__file__).resolve().parent.parent
DRIVER = Path(__file__).resolve().parent / "fixtures" / "drive.py"


def _run_scenario(name: str) -> dict:
    """Run one verifier scenario in a fresh interpreter and return its JSON result."""
    done = subprocess.run([sys.executable, "-I", "-B", str(DRIVER), name], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


@pytest.fixture(scope="session")
def scenario():
    """Return a callable that runs a named verifier scenario in isolation."""
    return _run_scenario


@pytest.fixture(scope="session")
def task_root() -> Path:
    """Return the task's source directory."""
    return TASK_ROOT
