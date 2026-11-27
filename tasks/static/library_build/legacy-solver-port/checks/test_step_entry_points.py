"""Each step's verify.py must score its own step (a copy-paste slip once left steps 5 and 6 scoring step 4)."""

import re
import tomllib
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]


def test_every_step_entry_point_scores_its_own_step():
    names = [
        s["name"] for s in tomllib.loads((TASK / "task.toml").read_text())["steps"]
    ]
    for number, name in enumerate(names, 1):
        text = (TASK / "steps" / name / "tests" / "verify.py").read_text()
        assert re.search(rf'"--step",\s*"{number}"', text), name
        assert name.startswith(f"{number:02d}-")


def test_every_step_has_its_own_references_and_verifier_files():
    names = [
        s["name"] for s in tomllib.loads((TASK / "task.toml").read_text())["steps"]
    ]
    for name in names:
        tests = TASK / "steps" / name / "tests"
        assert (tests / "Dockerfile").is_file() and (tests / "test.sh").is_file()
