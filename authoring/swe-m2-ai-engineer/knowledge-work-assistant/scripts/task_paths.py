"""Locate this task's author tools separately from its deployable Harbor files."""

from pathlib import Path

AUTHORING_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = (AUTHORING_ROOT / "../../..").resolve()
TASK_ROOT = REPOSITORY_ROOT / "tasks/swe-m2-ai-engineer/knowledge-work-assistant"
