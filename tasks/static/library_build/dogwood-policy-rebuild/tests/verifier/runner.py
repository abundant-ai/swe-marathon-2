"""Run each case in its own process, as the requester's CI starts `dogwood`.

Every run gets a new, empty working directory holding only that case's files, new `HOME` and
`TMPDIR` directories, a fixed environment, pipes for its standard streams, and the brief's limits.
A run that hangs, crashes or overruns loses only its own case.
"""

from __future__ import annotations

import os
import resource
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .contracts import Case, CaseResult, Limits
from .normalise import normalise
from .procs import capture, end_group, end_user

RUNNER = "nobody"
RUNNER_GROUP = "nogroup"
ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TERM": "dumb",
    "NO_COLOR": "1",
}


def _limits(limits: Limits):
    def apply() -> None:
        resource.setrlimit(
            resource.RLIMIT_AS, (limits.case_memory_bytes, limits.case_memory_bytes)
        )
        resource.setrlimit(resource.RLIMIT_NPROC, (512, 512))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 << 20, 256 << 20))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    return apply


def run_case(
    binary: Path, case: Case, bundles: Path, limits: Limits, sweep: bool = True
) -> tuple[object, bytes]:
    """Return (exit status or 'timeout' / 'overflow', stdout) for one case."""
    with tempfile.TemporaryDirectory(prefix="case-") as tmp:
        root = Path(tmp)
        work, home, scratch = root / "work", root / "home", root / "tmp"
        shutil.copytree(bundles / case.bundle, work)
        home.mkdir()
        scratch.mkdir()
        for path in (root, home, scratch):
            shutil.chown(path, user=RUNNER, group=RUNNER_GROUP)
        # The private store is root-only; the run's own copy belongs to the user it runs as.
        for dirpath, _, filenames in os.walk(work):
            shutil.chown(dirpath, user=RUNNER, group=RUNNER_GROUP)
            for name in filenames:
                shutil.chown(Path(dirpath) / name, user=RUNNER, group=RUNNER_GROUP)
        env = dict(ENV, HOME=str(home), TMPDIR=str(scratch))
        proc = subprocess.Popen(
            [str(binary), *case.args],
            cwd=work,
            env=env,
            user=RUNNER,
            group=RUNNER_GROUP,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=_limits(limits),  # noqa: PLW1509 - the grader runs one case at a time, single-threaded
        )
        try:
            out, timed_out, overflow = capture(
                proc, limits.case_timeout_sec, limits.case_stdout_bytes
            )
        finally:
            end_group(proc)
            if sweep:  # a process that left its group, too
                end_user(RUNNER)
        if overflow:
            return "overflow", b""
        if timed_out:
            return "timeout", b""
        return proc.returncode, out


def run_all(
    binary: Path | None, cases: list[Case], bundles: Path, limits: Limits
) -> list[CaseResult]:
    """Run every case under one global deadline; cases left when it passes fail.

    The denominator never changes: a missing binary, a timeout or the deadline fails cases,
    it does not remove them.
    """
    results: list[CaseResult] = []
    deadline = time.monotonic() + limits.deadline_sec
    for case in cases:
        if binary is None:
            results.append(
                CaseResult(case.case_id, case.family, case.pair, False, "no binary")
            )
            continue
        if time.monotonic() > deadline:
            results.append(
                CaseResult(case.case_id, case.family, case.pair, False, "deadline")
            )
            continue
        status, out = run_case(binary, case, bundles, limits)
        if not isinstance(status, int):
            results.append(
                CaseResult(case.case_id, case.family, case.pair, False, str(status))
            )
            continue
        same = (
            status == case.expected_rc
            and normalise(out, case.fmt) == case.expected_stdout
        )
        detail = (
            ""
            if same
            else f"exit {status} (expected {case.expected_rc}) or output differs"
        )
        results.append(CaseResult(case.case_id, case.family, case.pair, same, detail))
    return results
