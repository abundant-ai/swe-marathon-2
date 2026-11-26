"""Facts about the machine the grader runs on, and the development memory gate.

On the shared development Mac, every game process waits until `memory_pressure`
reports at least QA_MEM_FLOOR percent free memory (re-checking every
QA_MEM_POLL_S seconds). In the verifier container the variable is unset and nothing
waits.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable


def free_memory_percent() -> int | None:
    """System-wide free memory in percent from memory_pressure (macOS), else None."""
    if not shutil.which("memory_pressure"):
        return None
    out = subprocess.run(
        ["memory_pressure"], capture_output=True, text=True, check=False
    ).stdout
    m = re.search(r"System-wide memory free percentage:\s*(\d+)%", out)
    return int(m.group(1)) if m else None


def memory_gate() -> Callable[[], None] | None:
    """A before-start hook that waits for free memory, or None when no floor is set.

    Returns:
        A callable that blocks until free memory is at least $QA_MEM_FLOOR percent, or
        None when QA_MEM_FLOOR is unset or memory_pressure is unavailable.
    """
    floor = os.environ.get("QA_MEM_FLOOR")
    if not floor or not shutil.which("memory_pressure"):
        return None
    floor_pct = int(floor)
    poll = float(os.environ.get("QA_MEM_POLL_S", "120"))

    def wait() -> None:
        while True:
            pct = free_memory_percent()
            if pct is None or pct >= floor_pct:
                return
            print(
                f"waiting for free memory: {pct}% < {floor_pct}%",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(poll)

    return wait


def describe() -> dict:
    """Platform, CPU and Python facts for the report."""
    return {
        "platform": sys.platform,
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpus": os.cpu_count(),
    }
