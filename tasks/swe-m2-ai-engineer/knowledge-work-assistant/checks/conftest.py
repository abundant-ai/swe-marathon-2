"""Make author-side verifier modules importable without packaging candidate code."""

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_ROOT / "scripts"))

sys.path.insert(0, str(TASK_ROOT / "steps/01-build-rag/tests"))
