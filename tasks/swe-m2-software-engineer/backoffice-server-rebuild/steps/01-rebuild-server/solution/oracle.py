"""Reference solution: install the original Stockwell server as the delivered server."""

from __future__ import annotations

import shutil
from pathlib import Path

# The verifier starts `run` with PORT and DATA_DIR and nothing else of note; /opt/py holds the packages the server needs in
# both images. The server's settings come from stockwell.env, the one file the sealed server, the recordings and this
# solution share, with {data} standing for the data directory.
RUN = """#!/bin/sh
cd "$(dirname "$0")"
data="${DATA_DIR:-/tmp}"
while IFS= read -r line; do
    [ -n "$line" ] && export "$(printf '%s\\n' "$line" | sed "s|{data}|$data|g")"
done < "$PWD/stockwell.env"
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
exec "${STOCKWELL_PYTHON:-/opt/py/bin/python}" -B -m stockwell serve --host 127.0.0.1 --port "${PORT:-8080}" --workers 1
"""


def settings_file() -> Path:
    """stockwell.env: beside this file in a bundle (solution/data), or in the task's environment folder."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "data" / "stockwell.env", here.parents[2] / "environment" / "stockwell.env"):
        if candidate.is_file():
            return candidate
    raise RuntimeError("The server's settings (stockwell.env) are missing")


def oracle(reference: Path, target: Path) -> None:
    """Copy the reference package and its settings into the delivery directory and add its start script.

    Args:
        reference: Directory holding the `stockwell` package.
        target: The /app/server directory.

    Raises:
        RuntimeError: The reference package or its settings are missing.
    """
    package = reference / "stockwell"
    if not (package / "app.py").is_file() and not (package / "app.pyc").is_file():  # source, or the bytecode the bundle ships
        raise RuntimeError("Reference server package is missing")
    target.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(target / "stockwell", ignore_errors=True)
    shutil.copytree(package, target / "stockwell")
    shutil.copyfile(settings_file(), target / "stockwell.env")
    (target / "run").write_text(RUN)
    (target / "run").chmod(0o755)
    print("installed the reference server")


if __name__ == "__main__":
    oracle(Path(__file__).resolve().parent / "data", Path("/app/server"))
