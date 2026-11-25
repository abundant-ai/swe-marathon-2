"""Reference solution: install the original Stockwell server as the server in /app/server.

usage: oracle.py [TARGET]   (default /app/server)

Everything it installs comes from `data/` beside this file: the `stockwell` package, the server's
Python source, and `stockwell.env`, the server's settings. Nothing is read from outside this folder.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# `run` is started with PORT and DATA_DIR and nothing else of note; /opt/py holds the packages the server needs. The
# server's settings come from stockwell.env beside `run`, with {data} standing for the data directory.
RUN = """#!/bin/sh
cd "$(dirname "$0")"
data="${DATA_DIR:-/tmp}"
while IFS= read -r line; do
    [ -n "$line" ] && export "$(printf '%s\\n' "$line" | sed "s|{data}|$data|g")"
done < "$PWD/stockwell.env"
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
exec "${STOCKWELL_PYTHON:-/opt/py/bin/python}" -B -m stockwell serve --host 127.0.0.1 --port "${PORT:-8080}" --workers 1
"""


def oracle(reference: Path, target: Path, settings: Path | None = None) -> None:
    """Copy the reference package and its settings into the target directory and add its start script.

    Args:
        reference: Directory holding the `stockwell` package (`data/` beside this file).
        target: The /app/server directory.
        settings: The settings file; by default `stockwell.env` in `reference`.

    Raises:
        RuntimeError: The reference package or its settings are missing.
    """
    package = reference / "stockwell"
    settings = settings or reference / "stockwell.env"
    if not (package / "app.py").is_file() and not (package / "app.pyc").is_file():  # the source in `data/`, or bytecode
        raise RuntimeError(f"The reference server package is missing from {reference}")
    if not settings.is_file():
        raise RuntimeError(f"The server's settings are missing ({settings})")
    target.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(target / "stockwell", ignore_errors=True)
    shutil.copytree(package, target / "stockwell")
    shutil.copyfile(settings, target / "stockwell.env")
    (target / "run").write_text(RUN)
    (target / "run").chmod(0o755)
    print(f"installed the reference server in {target}")


if __name__ == "__main__":
    oracle(DATA, Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/app/server"))
