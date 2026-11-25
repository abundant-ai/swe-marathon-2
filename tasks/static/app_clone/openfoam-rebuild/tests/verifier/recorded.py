"""Replays a recorded program run and compares the outcome with the record.

One run gives several checks: "exit" (exit code), "files" (no expected file missing, and no
other file written, changed or removed), "stdout", "stderr", and "file <path>" for each file
the program wrote.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from concurrent.futures import FIRST_COMPLETED, wait
from dataclasses import dataclass, field
from pathlib import Path

from . import compare as C
from . import normalise as N

LOGS = [r"(.*/)?log\..*"]
RECORDING_HOME = "/home/dev"  # HOME of the user the tests were recorded as, where a record does not say


def processes(program, args):
    """Processors a recorded command keeps busy: the process count given to mpirun, else one."""
    if program == "mpirun":
        for flag in ("-n", "-np", "--np", "-c"):
            if flag in args:
                return int(args[args.index(flag) + 1])
    return 1


def run_packed(pool, jobs, cpus):
    """Runs jobs [(processors, fn, *args)] on `pool` in the given order, starting each only when
    its processors are free (one wider than the machine runs alone), so that runs are not slowed
    by sharing processors. Yields (index in jobs, result) as they finish."""
    running, free, nxt = {}, cpus, 0
    while nxt < len(jobs) or running:
        while nxt < len(jobs) and min(jobs[nxt][0], cpus) <= free:
            n, fn, *args = jobs[nxt]
            running[pool.submit(fn, *args)] = (nxt, min(n, cpus))
            free -= min(n, cpus)
            nxt += 1
        done, _ = wait(running, return_when=FIRST_COMPLETED)
        for f in done:
            i, n = running.pop(f)
            free += n
            yield i, f.result()


@dataclass
class Record:
    """A recorded run. `input` and `output` map a path in the case to the sha256 of its
    content (found by `blob`), None for an empty folder, or "link:<target>"."""

    command: dict
    input: dict
    output: dict
    removed: set
    exit: int
    stdout: str
    stderr: str
    blob: callable = field(repr=False)

    @classmethod
    def load(cls, path, files_dir):
        """A record file of the test dataset; contents are in files_dir/<h[:2]>/<h>."""
        r = json.loads(Path(path).read_text())
        return cls(
            r["command"],
            r["input"],
            r["output"],
            {x for x in r["removed"] if x},
            r["exit"],
            r["stdout"],
            r["stderr"],
            lambda h: os.path.join(files_dir, h[:2], h),
        )

    def files(self, part):
        """{path: content file} of the input or output files."""
        return {
            rel: self.blob(h)
            for rel, h in getattr(self, part).items()
            if h and not h.startswith("link:")
        }

    def links(self, part):
        return {
            rel: h[5:]
            for rel, h in getattr(self, part).items()
            if h and h.startswith("link:")
        }


@dataclass
class Limits:
    """How the program is run: base environment (HOME, TMPDIR and PWD are set per run),
    time limit and, when set, the user."""

    env: dict
    timeout: float
    uid: int | None = None
    gid: int | None = None


class Run:
    """Sets up the recorded input in a new folder and runs the command there."""

    def __init__(self, rec: Record, limits: Limits, work_root=None):
        self.rec = rec
        self.work = tempfile.mkdtemp(prefix="run-", dir=work_root)
        self.root = os.path.join(self.work, os.path.basename(rec.command["root"]))
        for rel, h in rec.input.items():
            if h is None:
                os.makedirs(os.path.join(self.root, rel), exist_ok=True)
            elif h.startswith("link:"):
                os.makedirs(
                    os.path.dirname(os.path.join(self.root, rel)), exist_ok=True
                )
                os.symlink(h[5:], os.path.join(self.root, rel))
        for rel, src in rec.files("input").items():
            dst = os.path.join(self.root, rel)
            if os.path.lexists(dst):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            os.chmod(dst, 0o755 if os.path.basename(rel).startswith("All") else 0o644)
        os.makedirs(self.root, exist_ok=True)
        self.before = os.path.join(self.work, ".before")
        shutil.copytree(self.root, self.before, symlinks=True)
        cwd = os.path.normpath(os.path.join(self.root, rec.command["cwd"]))
        os.makedirs(cwd, exist_ok=True)
        home, tmp = os.path.join(self.work, ".home"), os.path.join(self.work, ".tmp")
        self.home = home
        os.makedirs(home)
        os.makedirs(tmp)
        if limits.uid is not None:
            for d, dirs, fs in os.walk(self.work):
                if d.startswith(self.before):
                    continue
                for x in [d, *(os.path.join(d, f) for f in dirs + fs)]:
                    os.chown(x, limits.uid, limits.gid, follow_symlinks=False)
        env = {**limits.env, "HOME": home, "TMPDIR": tmp, "PWD": cwd}
        t0 = time.time()
        self.timed_out = False
        try:
            p = subprocess.Popen(
                [rec.command["program"], *rec.command["args"]],
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                user=limits.uid,
                group=limits.gid,
                extra_groups=[] if limits.uid is not None else None,
                start_new_session=True,
            )
        except OSError as e:  # program missing or not executable
            self.rc, self.out, self.err = None, b"", str(e).encode()
        else:
            try:
                self.out, self.err = p.communicate(timeout=limits.timeout)
                # a program killed by signal N: the shell reports 128+N, Python -N
                self.rc = p.returncode if p.returncode >= 0 else 128 - p.returncode
            except subprocess.TimeoutExpired:
                self.timed_out, self.rc, self.out, self.err = True, None, b"", b""
            finally:  # the program and anything it started
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.wait()
        self.seconds = time.time() - t0

    def close(self):
        shutil.rmtree(self.work, ignore_errors=True)


def check(run: Run, tols=None, masked=(), calibrating=False, host=None):
    """Compares a run with its record. Returns {check name: compare.Result}."""
    rec = run.rec
    tols = dict(tols or {})
    tols.update({k: math.inf for k in masked})
    checks = {name: C.Result() for name in ("exit", "files", "stdout", "stderr")}
    expected = rec.files("output")
    for rel in expected:
        checks[f"file {rel}"] = C.Result()
    if run.timed_out:
        for r in checks.values():
            r.fail("run", "timed out")
        return checks
    if run.rc != rec.exit:
        checks["exit"].fail("exit", f"{rec.exit} expected, got {run.rc}")
    for stream, got in (("stdout", run.out), ("stderr", run.err)):
        g = N.normalise(
            getattr(rec, stream),
            case_dir=rec.command["root"],
            host=rec.command["host"],
            home=rec.command.get("home", RECORDING_HOME),
            install=(N.RECORDED_INSTALL,),
        )
        c = N.normalise(
            got.decode("utf-8", "replace"),
            case_dir=run.root,
            host=host or socket.gethostname(),
            home=run.home,
            install=N.SUBMISSION_INSTALL,
        )
        C.compare_lines(
            g, c, tols, checks[stream], prefix=f"{stream} ", calibrating=calibrating
        )
    after = C.list_files(run.root, ignore=LOGS)
    before = set(C.list_files(run.before, ignore=LOGS))
    links = rec.links("output")
    for rel, target in links.items():
        got = os.path.join(run.root, rel)
        if not os.path.islink(got) or os.readlink(got) != target:
            checks["files"].fail(rel, f"symbolic link to {target!r} expected")
    for rel in after:
        if rel in expected or rel in links:
            continue
        if rel not in before:
            checks["files"].fail(rel, "written, but not by OpenFOAM")
        elif not _same(os.path.join(run.root, rel), os.path.join(run.before, rel)):
            checks["files"].fail(rel, "changed, but not by OpenFOAM")
    removed = before - set(after)
    if removed != rec.removed:
        checks["files"].fail(
            "removed", f"expected {sorted(rec.removed)[:5]}, got {sorted(removed)[:5]}"
        )
    for rel, src in expected.items():
        got = os.path.join(run.root, rel)
        if not os.path.isfile(got):
            checks["files"].fail(rel, "missing")
            checks[f"file {rel}"].fail(rel, "missing")
            continue
        C.compare_file(src, got, tols, checks[f"file {rel}"], rel, calibrating)
    return checks


def _same(a, b):
    with open(a, "rb") as f, open(b, "rb") as g:
        return f.read() == g.read()
