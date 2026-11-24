"""Run the rear docking controller with atomic replayable state."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from .controller import Record, advance, initial_state


def save(path: Path, state: Record) -> None:
    """Commit state and its cached response before the response becomes visible."""
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(state, stream, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            temporary.replace(path)
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            temporary.unlink(missing_ok=True)


def main() -> int:
    """Read one mission configuration and serve its observation stream."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    args.state.mkdir(parents=True, exist_ok=True)
    path = args.state / "docking.json"
    state = json.loads(path.read_text()) if path.is_file() else initial_state()
    for line in sys.stdin:
        observation = json.loads(line)
        if state["last_tick"] != observation["tick"]:
            decision = advance(state, config, observation)
            state.update(last_tick=observation["tick"], reply=decision)
            save(path, state)
        print(json.dumps(state["reply"], allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] in (["guarded-undock"], ["undock-receipt"]):
        from .departure import command

        sys.exit(command(sys.argv[1:], save))
    if sys.argv[1:2] in (["guarded-dock"], ["dock-receipt"]):
        from .native import command

        sys.exit(command(sys.argv[1:], save))
    if sys.argv[1:2] == ["compile"]:
        from .compiler import command

        sys.exit(command(sys.argv[2:], save))
    sys.exit(main())
