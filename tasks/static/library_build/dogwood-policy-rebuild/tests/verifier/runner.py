"""Run each case in its own process, as the requester's CI starts `dogwood`.

Every run gets a new, empty working directory holding only that case's files, new `HOME` and
`TMPDIR` directories, a fixed environment, pipes for its standard streams, and the brief's limits.
A run that hangs, crashes or overruns loses only its own case.
"""

from __future__ import annotations

import errno
import hashlib
import os
import resource
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .contracts import Case, CaseResult, EvaluationError, Limits
from .normalise import normalise
from .procs import capture, end_group, end_user, remove_files_of

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


def _can_start(limits: Limits) -> bool:
    """Whether the machine starts /bin/true as the runner, with the runner's limits."""
    try:
        return (
            subprocess.run(
                ["/bin/true"],
                check=False,
                env=ENV,
                user=RUNNER,
                group=RUNNER_GROUP,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=_limits(limits),
                timeout=10,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


def run_case(
    binary: Path, case: Case, bundles: Path, limits: Limits, sweep: bool = True
) -> tuple[object, bytes]:
    """Return (exit status, or 'timeout' / 'overflow' / 'could not start (...)', stdout).

    With `sweep` (one run at a time), every process of the runner is ended and whatever it left
    in the shared writable directories removed once the run is over, so runs share nothing."""
    try:
        return _run(binary, case, bundles, limits, sweep)
    finally:
        if sweep:
            remove_files_of(RUNNER)


def _run(
    binary: Path, case: Case, bundles: Path, limits: Limits, sweep: bool
) -> tuple[object, bytes]:
    with tempfile.TemporaryDirectory(prefix="case-", ignore_cleanup_errors=True) as tmp:
        # The run's folder stays root's (readable, not writable), so the run cannot move or
        # replace it, or the three directories inside, which are the run's own.
        root = Path(tmp)
        root.chmod(0o755)
        work, home, scratch = root / "work", root / "home", root / "tmp"
        shutil.copytree(bundles / case.bundle, work)
        home.mkdir()
        scratch.mkdir()
        for path in (home, scratch):
            shutil.chown(path, user=RUNNER, group=RUNNER_GROUP)
        # The private store is root-only; the run's own copy belongs to the user it runs as.
        for dirpath, _, filenames in os.walk(work):
            shutil.chown(dirpath, user=RUNNER, group=RUNNER_GROUP)
            for name in filenames:
                shutil.chown(Path(dirpath) / name, user=RUNNER, group=RUNNER_GROUP)
        env = dict(ENV, HOME=str(home), TMPDIR=str(scratch))
        feed = (work / case.stdin).open("rb") if case.stdin else None
        try:
            proc = subprocess.Popen(
                [str(binary), *case.args],
                cwd=work,
                env=env,
                user=RUNNER,
                group=RUNNER_GROUP,
                stdin=feed if feed is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                preexec_fn=_limits(limits),  # noqa: PLW1509 - the grader runs one case at a time, single-threaded
            )
        except OSError as exc:
            # The delivered program cannot be started (not a program this machine runs, a
            # missing loader, more than the memory limit to load): its own case fails. If the
            # machine cannot start /bin/true the same way either, the evaluation itself fails.
            if not _can_start(limits):
                raise EvaluationError(f"cannot start processes: {exc}") from exc
            return (
                f"could not start ({errno.errorcode.get(exc.errno or 0, exc.errno)})",
                b"",
            )
        finally:
            if feed is not None:
                feed.close()
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
    it does not remove them. The deadline leaves every case its full time limit, so it binds
    only a run that overruns; cases run in a fixed order mixed across families (by a hash of
    their ids), so what a deadline cuts is spread over them.
    """
    results: list[CaseResult] = []
    cases = sorted(cases, key=lambda c: hashlib.sha256(c.case_id.encode()).hexdigest())
    deadline = time.monotonic() + max(
        limits.deadline_sec,
        len(cases) * (limits.case_timeout_sec + limits.case_overhead_sec),
    )
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
