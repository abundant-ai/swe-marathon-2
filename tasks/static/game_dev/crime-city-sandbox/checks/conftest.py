"""Shared setup for the task's development checks: import paths and markers.

The kit (common/kit), the grader (tests/verifier) and the hostile-project builder
(checks/hostile_projects.py) are imported from the source tree. Checks that start Godot
are marked "godot" and run only with CC_GODOT_CHECKS=1 (each waits for free memory).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parent.parent
for sub in ("common/kit", "tests", "checks"):
    path = str(TASK / sub)
    if path not in sys.path:
        sys.path.insert(0, path)


def pytest_configure(config: pytest.Config) -> None:
    """Register the godot marker."""
    config.addinivalue_line("markers", "godot: starts Godot (needs CC_GODOT_CHECKS=1)")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip Godot checks unless CC_GODOT_CHECKS=1."""
    if os.environ.get("CC_GODOT_CHECKS") == "1":
        return
    skip = pytest.mark.skip(reason="starts Godot; set CC_GODOT_CHECKS=1")
    for item in items:
        if "godot" in item.keywords:
            item.add_marker(skip)
