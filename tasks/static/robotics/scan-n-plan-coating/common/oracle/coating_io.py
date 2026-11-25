"""Read and atomically publish the public coating CLI records."""

import json
from pathlib import Path
import tempfile
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    """Read one JSON object, rejecting malformed input before calculation.

    Args:
        path: Input selected on the command line.

    Returns:
        The parsed top-level object.

    Raises:
        OSError: The file cannot be read.
        ValueError: The source is not a JSON object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def publish(path: Path, report: dict[str, Any]) -> None:
    """Publish one complete report by replacing the destination atomically.

    Args:
        path: Existing or new output path in an existing directory.
        report: Result returned by the registration domain logic.
    """
    content = json.dumps(report, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        pending = Path(stream.name)
        try:
            stream.write(content)
            stream.close()
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)
