"""Reference solution: install the original Stockwell server as the delivered server."""

from __future__ import annotations

import shutil
from pathlib import Path

# The verifier starts `run` with PORT and DATA_DIR and nothing else of note; /opt/py holds the
# packages the server needs in both images.
RUN = """#!/bin/sh
cd "$(dirname "$0")"
data="${DATA_DIR:-/tmp}"
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 \\
    STOCKWELL_AUTH_MODE=proxy STOCKWELL_CREATE_SCHEMA=true \\
    STOCKWELL_DATABASE_URL="sqlite:///$data/stockwell.db" STOCKWELL_DATA_DIR="$data" \\
    STOCKWELL_LOG_LEVEL=WARNING STOCKWELL_ACCESS_LOG=false STOCKWELL_REQUEST_LOG=false STOCKWELL_METRICS_ENABLED=false
exec "${STOCKWELL_PYTHON:-/opt/py/bin/python}" -B -m stockwell serve --host 127.0.0.1 --port "${PORT:-8080}" --workers 1
"""


def oracle(reference: Path, target: Path) -> None:
    """Copy the reference package into the delivery directory and add its start script.

    Args:
        reference: Directory holding the `stockwell` package.
        target: The /app/server directory.

    Raises:
        RuntimeError: The reference package is missing.
    """
    package = reference / "stockwell"
    if not (package / "app.py").is_file() and not (package / "app.pyc").is_file():  # source, or the bytecode the bundle ships
        raise RuntimeError("Reference server package is missing")
    target.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(target / "stockwell", ignore_errors=True)
    shutil.copytree(package, target / "stockwell")
    (target / "run").write_text(RUN)
    (target / "run").chmod(0o755)
    print("installed the reference server")


if __name__ == "__main__":
    oracle(Path(__file__).resolve().parent / "data", Path("/app/server"))
