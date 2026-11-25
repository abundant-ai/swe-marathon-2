"""Exercise bounded JSON-lines transport and durable state on cold restart."""

from pathlib import Path
import subprocess

import pytest

VERIFIER = Path(__file__).resolve().parents[1] / "common/verifier"


def test_coating_launches_after_file_transfer_drops_execute_bits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Launch a regular transferred entry and continue to reject symlinks."""
    monkeypatch.syspath_prepend(str(VERIFIER))
    from candidate import artifact_ready, make_immutable

    app = tmp_path / "app"
    app.mkdir()
    entry = app / "coating"
    entry.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    entry.chmod(0o644)

    assert artifact_ready(app)
    make_immutable(app)
    assert entry.stat().st_mode & 0o777 == 0o755
    subprocess.run([str(entry)], check=True, timeout=4.0)

    untrusted = tmp_path / "linked-app"
    untrusted.mkdir()
    (untrusted / "coating").symlink_to(entry)
    assert not artifact_ready(untrusted)


def test_coating_live_runner_keeps_only_the_declared_state_on_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Use the supplied state directory for a large request and cold restart."""
    monkeypatch.syspath_prepend(str(VERIFIER))
    from live_candidate import supervisor

    app = tmp_path / "app"
    app.mkdir()
    entry = app / "coating"
    entry.write_text(
        '''#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("command")
parser.add_argument("--job")
parser.add_argument("--registration")
parser.add_argument("--state", type=Path)
args = parser.parse_args()
journal = args.state / "previous.json"
last = json.loads(journal.read_text()) if journal.exists() else None
for raw in sys.stdin:
    message = json.loads(raw)
    if message != last:
        last = message
        journal.write_text(json.dumps(last))
    print(json.dumps({"seq": message["seq"], "large": len(last["data"])}), flush=True)
''',
        encoding="utf-8",
    )
    entry.chmod(0o755)
    with supervisor(app, {}, {}, timeout_s=4.0) as runner:
        request = {"seq": 0, "data": "m" * 160_000}
        assert runner(request) == {"seq": 0, "large": 160_000}
        assert runner(request, restart=True) == {"seq": 0, "large": 160_000}
        assert runner({"seq": 1, "data": "x"}) == {"seq": 1, "large": 1}
