"""Exercise bounded JSON-lines transport and durable state on cold restart."""

from pathlib import Path

import pytest

VERIFIER = Path(__file__).resolve().parents[1] / "common/verifier"


def test_coating_live_runner_keeps_only_the_declared_state_on_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Transport a request bigger than a pipe buffer and restart its process."""
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
args.state.mkdir(exist_ok=True)
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
