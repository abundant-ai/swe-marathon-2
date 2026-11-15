"""Make author-side verifier modules importable without packaging candidate code."""

import sys
from pathlib import Path

AUTHORING_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AUTHORING_ROOT / "scripts"))
from task_paths import TASK_ROOT

sys.path.insert(0, str(TASK_ROOT / "steps/01-build-rag/tests"))
