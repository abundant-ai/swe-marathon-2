"""Locate task sources and ignored outputs for development and packaging scripts."""

from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = TASK_ROOT.parents[2]
EXPERIMENT_ROOT = TASK_ROOT / "experiment"
