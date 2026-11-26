"""Run one heavy job (any Godot run) at a time, and only with enough free memory.

Author tool for this shared Mac (never packaged). It takes an exclusive lock on one
lock file shared by every agent working on this task, then waits until
`memory_pressure` reports at least the floor of free memory (default 30%), re-checking
every few minutes, and only then runs the command. The lock is held until the command
ends, so heavy jobs never overlap.

Usage:
  python scripts/heavy.py [--floor 30] [--poll-s 180] [--lock PATH] -- COMMAND [ARGS...]

The lock file defaults to $CC_HEAVY_LOCK, else ~/.cache/crime-city/heavy.lock. On a
machine without memory_pressure (Linux) the memory check is skipped.
"""

import argparse
import fcntl
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def free_percent() -> int | None:
    """System-wide free memory percentage from memory_pressure, or None when unavailable.

    Returns:
        The percentage (0-100), or None when the tool is missing or its output unknown.
    """
    if not shutil.which("memory_pressure"):
        return None
    out = subprocess.run(
        ["memory_pressure"], capture_output=True, text=True, check=False
    ).stdout
    m = re.search(r"System-wide memory free percentage:\s*(\d+)%", out)
    return int(m.group(1)) if m else None


def wait_for_memory(floor: int, poll_s: float, log=print) -> int | None:
    """Block until free memory is at least floor percent.

    Args:
        floor: Minimum free percentage.
        poll_s: Seconds between checks while below the floor.
        log: Where progress lines go.

    Returns:
        The free percentage seen when the wait ended (None when it cannot be read).
    """
    while True:
        pct = free_percent()
        if pct is None or pct >= floor:
            return pct
        log(f"heavy: free memory {pct}% < {floor}%, re-checking in {poll_s:.0f} s")
        time.sleep(poll_s)


def main() -> int:
    """Take the lock, wait for memory, run the command; return its exit code."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--floor", type=int, default=30)
    ap.add_argument("--poll-s", type=float, default=180.0)
    ap.add_argument("--lock", default=None)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.command[1:] if a.command and a.command[0] == "--" else a.command
    if not cmd:
        ap.error("no command given")
    lock_path = Path(
        a.lock
        or os.environ.get("CC_HEAVY_LOCK")
        or Path.home() / ".cache/crime-city/heavy.lock"
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a") as lock:
        t0 = time.monotonic()
        fcntl.flock(lock, fcntl.LOCK_EX)
        waited = time.monotonic() - t0
        if waited > 1:
            print(f"heavy: waited {waited:.0f} s for the lock", flush=True)
        pct = wait_for_memory(a.floor, a.poll_s, lambda m: print(m, flush=True))
        print(f"heavy: free memory {pct}%, running: {' '.join(cmd)[:200]}", flush=True)
        env = dict(os.environ, CC_HEAVY_HELD="1")
        return subprocess.run(cmd, env=env, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
