"""Linux-only isolation of the graded game's processes: a cgroup per process and an
unprivileged user.

In the verifier container the grader runs as root. Each game process then:
- runs as the unprivileged user QA_USER (default "qa"), so it cannot touch the grader,
  its private inputs or the reward files;
- joins its own cgroup v2 under /sys/fs/cgroup/<QA_CGROUP_BASE>, with memory.max
  (PF-7's 1.5 GB plus a margin), memory.swap.max 0, pids.max (stops fork bombs) and
  cpu.max (one core), killed as a whole through cgroup.kill.

On macOS (development) none of this applies: Sandbox.available is False and the kit
falls back to rlimits, its memory watchdog and process-table kills.

Not yet exercised: it needs a Linux machine (notes/PHASE1B-REPORT.md).
"""

from __future__ import annotations

import itertools
import os
import pwd
import sys
from dataclasses import dataclass
from pathlib import Path

CGROUP_ROOT = Path("/sys/fs/cgroup")


@dataclass(frozen=True)
class CgroupLimits:
    """Limits written into each game process's cgroup.

    Attributes:
        memory_mb: memory.max in MiB.
        pids: pids.max.
        cpus: CPU cores (cpu.max quota over a 100 ms period).
    """

    memory_mb: int = 1792
    pids: int = 256
    cpus: float = 1.0


class Sandbox:
    """Creates per-process cgroups and names the unprivileged user (Linux, as root)."""

    def __init__(self, base: str | None = None, user: str | None = None) -> None:
        """Probe whether isolation is possible here.

        Args:
            base: cgroup folder name under /sys/fs/cgroup ($QA_CGROUP_BASE, "qa-grader").
            user: Unprivileged user name ($QA_USER, "qa").
        """
        self.base = CGROUP_ROOT / (
            base or os.environ.get("QA_CGROUP_BASE", "qa-grader")
        )
        self.user = user or os.environ.get("QA_USER", "qa")
        self._seq = itertools.count()
        self.available = (
            sys.platform.startswith("linux")
            and os.geteuid() == 0
            and (CGROUP_ROOT / "cgroup.controllers").is_file()
        )
        self.ids: tuple[int, int] | None = None
        if self.available:
            try:
                pw = pwd.getpwnam(self.user)
                self.ids = (pw.pw_uid, pw.pw_gid)
            except KeyError:
                self.ids = None

    def prepare_base(self) -> None:
        """Create the base cgroup and enable the memory, pids and cpu controllers in it."""
        if not self.available:
            return
        self.base.mkdir(exist_ok=True)
        try:
            (CGROUP_ROOT / "cgroup.subtree_control").write_text("+memory +pids +cpu")
        except OSError:
            pass
        (self.base / "cgroup.subtree_control").write_text("+memory +pids +cpu")

    def new_cgroup(self, limits: CgroupLimits) -> Path | None:
        """A fresh cgroup for one game process, with its limits written; None off Linux."""
        if not self.available:
            return None
        path = self.base / f"run-{os.getpid()}-{next(self._seq)}"
        path.mkdir()
        (path / "memory.max").write_text(str(limits.memory_mb * 1024 * 1024))
        (path / "memory.swap.max").write_text("0")
        (path / "pids.max").write_text(str(limits.pids))
        (path / "cpu.max").write_text(f"{int(limits.cpus * 100000)} 100000")
        return path

    @staticmethod
    def remove(path: Path | None) -> None:
        """Kill everything left in a cgroup and remove it (no-op for None)."""
        if path is None:
            return
        try:
            (path / "cgroup.kill").write_text("1")
        except OSError:
            pass
        try:
            path.rmdir()
        except OSError:
            pass
