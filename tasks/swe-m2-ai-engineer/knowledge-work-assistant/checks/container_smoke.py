"""Exercise the production UID boundary and adapter with controlled inputs."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "/tests")
sys.path.insert(0, "/checks")
sys.path.insert(0, "/scripts")

from contracts import HeldOutCase
from test_verifier import ExactJudge, context as context_fixture
import verify


def main() -> None:
    """Run the real adapter with a controlled app and judge in a Linux container.

    This deliberately substitutes fixture cases and a deterministic judge. It
    establishes packaging and process isolation, not task solvability or accuracy.
    Raises on any failed check or unexpected access to private files.
    """
    root = Path("/tmp/orange-smoke")
    root.mkdir()
    fixture = context_fixture.__wrapped__(root)
    shutil.copytree(fixture.app.root, "/app", dirs_exist_ok=True)

    def inputs(private: Path) -> tuple[Path, tuple[HeldOutCase, ...], dict[str, Any]]:
        """Supply two controlled cases to the production adapter.

        Args:
            private: Unused production private-input location.

        Returns:
            Fixture corpus, references, and an explicitly synthetic manifest.
        """
        return fixture.corpus_path, fixture.cases, {"mode": "controlled smoke"}

    verify.load_inputs = inputs
    verify.HerbJudge = ExactJudge
    os.environ["OPENAI_API_KEY"] = "synthetic-judge-only"
    os.environ["ORANGE_JUDGE_API_KEY"] = "synthetic-judge-only"
    os.environ["ORANGE_OPENAI_API_KEY"] = "synthetic-application-key"
    assert verify.main() == 0
    report = json.loads(Path("/logs/verifier/report.json").read_text())
    assert report["result"]["passed"], report
    assert json.loads(Path("/logs/verifier/reward.json").read_text()) == {"reward": 1.0}
    from client import ApplicationClient

    child = ApplicationClient(Path("/app"), uid=10001)
    probe = child.run([child.python(), "-c", "import os; print(os.getuid()); print(os.access('/tests/verify.py', os.R_OK)); print(os.access('/logs/verifier/reward.json', os.W_OK)); print('OPENAI_API_KEY' in os.environ)"])
    assert probe.stdout.splitlines() == ["10001", "False", "False", "False"], probe.stdout
    print(json.dumps({"mode": "controlled Linux smoke", "passed_checks": len(report["result"]["checks"]), "candidate_uid": 10001, "private_files_inaccessible": True}))


if __name__ == "__main__":
    main()
