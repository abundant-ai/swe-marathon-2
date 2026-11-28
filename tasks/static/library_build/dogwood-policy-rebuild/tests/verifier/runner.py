"""Run each case in its own process, as the requester's CI starts `dogwood`.

Every run gets a new, empty working directory holding only the files its command line names,
new `HOME` and `TMPDIR` directories, a fixed environment, pipes for its standard streams, and the
brief's limits. A run that hangs, crashes or overruns loses only its own case. Once a run is
over, every process of the run's user is ended and everything it left anywhere it could write is
removed, so runs share nothing.
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

from . import listing
from .contracts import Case, CaseResult, EvaluationError, Limits
from .normalise import normalise
from .procs import (
    capture,
    clear_user,
    drop_to,
    end_group,
    end_user,
    expendable,
    remove_tree,
)

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
        expendable()
        resource.setrlimit(
            resource.RLIMIT_AS, (limits.case_memory_bytes, limits.case_memory_bytes)
        )
        resource.setrlimit(resource.RLIMIT_NPROC, (512, 512))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 << 20, 256 << 20))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        drop_to(RUNNER)  # last: the score and the limits are set while still root

    return apply


def _can_start(limits: Limits) -> bool:
    """Whether the machine starts /bin/true as the runner, with the runner's limits."""
    try:
        return (
            subprocess.run(
                ["/bin/true"],
                check=False,
                env=ENV,
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


def _stage(bundle: Path, case: Case, work: Path) -> None:
    """Copy into `work` the bundle entries the case's command line names (all, without a list)."""
    names = case.files if case.files is not None else sorted(os.listdir(bundle))
    work.mkdir()
    for name in names:
        source = bundle / name
        if source.is_dir():
            shutil.copytree(source, work / name, symlinks=True)
        elif source.is_file():
            shutil.copyfile(source, work / name, follow_symlinks=False)


def run_case(
    binary: Path, case: Case, bundles: Path, limits: Limits, sweep: bool = True
) -> tuple[object, bytes]:
    """Return (exit status, or 'timeout' / 'overflow' / 'could not start (...)', stdout).

    With `sweep` (one run at a time), every process of the runner is ended and whatever it left
    in the shared writable directories removed once the run is over, so runs share nothing."""
    root = Path(tempfile.mkdtemp(prefix="case-"))
    try:
        result = _run(binary, case, bundles, limits, sweep, root)
    finally:
        if sweep:
            clear_user(RUNNER)
        cleaned = remove_tree(os.fsencode(root))
    if not cleaned:
        return "left files the grader could not remove", b""
    return result


def _run(
    binary: Path, case: Case, bundles: Path, limits: Limits, sweep: bool, root: Path
) -> tuple[object, bytes]:
    # The run's folder stays root's (readable, not writable), so the run cannot move or replace
    # it, or the three directories inside, which are the run's own.
    root.chmod(0o755)
    work, home, scratch = root / "work", root / "home", root / "tmp"
    _stage(bundles / case.bundle, case, work)
    home.mkdir()
    scratch.mkdir()
    # The private store is root-only; the run's own copy belongs to the user it runs as.
    for path in (work, home, scratch):
        listing.chown_tree(os.fsencode(path), RUNNER)
    env = dict(ENV, HOME=str(home), TMPDIR=str(scratch))
    # Standard input comes from the private store itself, which the run cannot reach.
    feed = (
        os.open(bundles / case.bundle / case.stdin, os.O_RDONLY | os.O_NOFOLLOW)
        if case.stdin
        else None
    )
    try:
        proc = subprocess.Popen(
            [str(binary), *case.args],
            cwd=work,
            env=env,
            stdin=feed if feed is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=_limits(limits),  # noqa: PLW1509 - the grader runs one case at a time, single-threaded
        )
    except OSError as exc:
        # The delivered program cannot be started (not a program this machine runs, a missing
        # loader, more than the memory limit to load): its own case fails. If the machine cannot
        # start /bin/true the same way either, the evaluation itself fails.
        if not _can_start(limits):
            raise EvaluationError(f"cannot start processes: {exc}") from exc
        return (
            f"could not start ({errno.errorcode.get(exc.errno or 0, exc.errno)})",
            b"",
        )
    finally:
        if feed is not None:
            os.close(feed)
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
    binary: Path | None,
    cases: list[Case],
    bundles: Path,
    limits: Limits,
    until: float | None = None,
) -> list[CaseResult]:
    """Run every case under one global deadline; cases left when it passes fail.

    The denominator never changes: a missing binary, a timeout or the deadline fails cases,
    it does not remove them. The deadline leaves every case its full time limit, so it binds
    only a run that overruns, and it never passes `until` (a time.monotonic() value: the time
    the grader keeps for itself before its own limit); cases run in a fixed order mixed across
    families (by a hash of their ids), so what a deadline cuts is spread over them.
    """
    results: list[CaseResult] = []
    cases = sorted(cases, key=lambda c: hashlib.sha256(c.case_id.encode()).hexdigest())
    deadline = time.monotonic() + max(
        limits.deadline_sec,
        len(cases) * (limits.case_timeout_sec + limits.case_overhead_sec),
    )
    if until is not None:
        deadline = min(deadline, until)
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
