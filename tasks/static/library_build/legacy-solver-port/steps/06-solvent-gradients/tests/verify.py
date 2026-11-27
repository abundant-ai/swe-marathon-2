"""Harbor entry point of step 6: scores the solver written in the agent container (artifact /workspace/solver)."""

import sys

sys.path.insert(0, "/tests")
import verify_core

verify_core.main(
    [
        "--step",
        "6",
        "--solver",
        "/workspace/solver",
        "--refs",
        "/tests/private",
        "--out",
        "/logs/verifier/reward.json",
    ]
)
