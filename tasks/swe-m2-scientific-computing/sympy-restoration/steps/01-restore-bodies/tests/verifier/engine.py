"""Measure a submitted SymPy tree. Decides nothing: checks and scoring read the result.

Inputs
  context.work_tree/sympy   the submitted tree (the declared artifact), with the collect step's
                            signed mark and record of every entry (verifier/delivery.py)
  context.skeleton          reference skeleton with the full upstream test suite
  context.private           unit list, sealed test list, recorded calls, reference results,
                            the key the collect step signs with
Outputs
  context.output/artifacts  per-unit results, failing test ids, the measured unit files

Submitted code only ever runs as an unprivileged user. Three things are measured:
  1. docstring examples of every restored unit,
  2. recorded calls replayed in isolation: results are written by the sandbox and
     compared here with reference results the sandbox cannot read,
  3. sealed upstream test cases.
While 1 and 2 run, no test file is readable by the sandbox (the tree it sees has no test
directories, and the trees that have them are closed), so nothing on disk states what a
replayed call should return.
"""

from __future__ import annotations

import collections
import json
import math
import os
import pickle
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(LIB))
import bodies  # noqa: E402
import gradelib  # noqa: E402
import restorelib  # noqa: E402
from canon import profile_of, same  # noqa: E402

from verifier import delivery  # noqa: E402
from verifier.contracts import EvaluationError, Measurement, VerificationContext  # noqa: E402

RUN_AS = "nobody"
SANDBOX_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8",
}


def log(*parts: object) -> None:
    """Print one progress line to the verifier log."""
    print("[grade]", *parts, flush=True)


def host_benchmark(rounds: int = 3) -> float:
    """Seconds this machine takes for a fixed piece of pure-Python work, the fastest of `rounds` runs.
    It runs here, before any submitted code: nothing the submission does can slow it."""
    best = float("inf")
    for _ in range(rounds):
        began = time.perf_counter()
        table: dict = {}
        total = 0
        for i in range(2_000_000):
            key = (i * 7919) % 10007
            table[key] = table.get(key, 0) + i
            total += len(str(i))
        sorted(table.items())
        best = min(best, time.perf_counter() - began)
    return best


def time_needed(timing: Mapping, modules: Mapping, factor: float, default_load: float = 2.0, default_item: float = 0.5) -> float:
    """Worker-seconds the original would need on this machine for one phase over the given units.

    Args:
        timing: The original's own times on the machine its results were recorded on: per module
            the seconds its runner took to import it (`load`), per unit the seconds of its items
            (`units`: its examples, or all its calls).
        modules: The units the phase runs, per module.
        factor: How much slower this machine is (host_benchmark against the recorded benchmark).
        default_load: Seconds for a module the timing does not hold.
        default_item: Seconds for a unit the timing does not hold.
    """
    load, per = timing.get("load", {}), timing.get("units", {})
    total = 0.0
    for module, keys in modules.items():
        total += float(load.get(module, default_load))
        total += sum(float(per.get(key, default_item)) for key in keys)
    return factor * total


def _runs(prefix: list[str]) -> bool:
    try:
        return subprocess.run(prefix + ["true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def sandbox_prefix(run_group: str, address_space: int = 0, notes: list | None = None) -> list[str]:
    """Return the command prefix that limits memory and drops to the unprivileged user.

    Args:
        run_group: Group the sandbox user runs with.
        address_space: Bytes of address space each sandboxed process may use;
            0 sets no limit.
        notes: Diagnostic notes for metrics.json, appended to in place.

    Returns:
        The `prlimit` and `setpriv` prefix every sandboxed command starts with;
        without `prlimit` when the limit cannot be set here (noted).

    Raises:
        EvaluationError: The verifier is not root or cannot drop privileges, so
            submitted code must not be run and no reward is valid.
    """
    if os.geteuid() != 0:
        raise EvaluationError("Verifier must start as root to isolate submitted code")
    drop = ["setpriv", "--reuid", RUN_AS, "--regid", run_group, "--clear-groups"]
    if shutil.which("setpriv") is None or not _runs(drop):
        raise EvaluationError("Could not drop privileges; submitted code was not run")
    if address_space > 0:
        limited = ["prlimit", f"--as={int(address_space)}", "--core=0", "--"] + drop
        if shutil.which("prlimit") is not None and _runs(limited):
            return limited
        if notes is not None:
            notes.append("the address-space limit could not be set; submitted code ran without it")
    return drop


def reap(prefix: list[str]) -> None:
    """Kill whatever the sandbox user left running."""
    if not prefix or not shutil.which("pkill"):
        return
    for _ in range(25):
        subprocess.run(["pkill", "-9", "-u", RUN_AS], check=False)
        if not shutil.which("pgrep") or subprocess.run(["pgrep", "-u", RUN_AS], stdout=subprocess.DEVNULL).returncode != 0:
            return
        time.sleep(0.2)


def read_vector_records(path: str, want: set, keys: list) -> tuple[dict, set]:
    """Read the results a replay job has written so far.

    Args:
        path: File the sandboxed runner appends one signed JSON line per call to.
        want: Ids of the calls of this job.
        keys: The keys the job's starts were given; a line signed with none of them is not read.

    Returns:
        The canonical result per call id, and the ids reported more than once.
    """
    got: dict = {}
    dup: set = set()
    try:
        if os.path.getsize(path) <= 200_000_000:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if len(line) > 2_100_000:
                        continue
                    text = next((t for t in (gradelib.signed_text(line, key) for key in keys) if t is not None), None)
                    if text is None:
                        continue
                    try:
                        rec = json.loads(text)
                    except (ValueError, RecursionError, MemoryError):
                        continue
                    vid = rec.get("v") if isinstance(rec, dict) else None
                    if vid in want:
                        if vid in got:
                            dup.add(vid)
                        c = rec.get("c")
                        got[vid] = c if isinstance(c, list) else None
    except OSError:
        pass
    return got, dup


def run_vectors(payload, restored_uids, prefix, *, scratch, pub, cand_nt, cfg, cpus, deadline, stats=None):
    """Replay recorded calls in the sandbox, one process per module.

    The runner works through a module's calls in order and writes each result
    as it goes. A call can end the process (a crash in the interpreter) or keep
    it busy past its own time limit; the calls queued behind it say nothing
    about the submission. So the job is started again behind that call, which
    counts as not matching; when the start was barren (the very first call
    ended it), the rest of that call's unit counts as not matching too and the
    job resumes at the next unit. After a call that ran out of time the runner
    exits by itself and is started again behind it, since an interrupted body
    can leave global state behind. A unit whose calls ran out of time, or
    stopped the runner, `vector_unit_overrun_limit` times does not match on the
    rest of its calls, which are not run. A job whose module import never
    finishes loses all its calls at once, and so does the rest of a job after
    `vector_job_restart_limit` starts that ended or stopped. Calls left when
    `deadline` passes are not reached.

    Args:
        payload: Per module, its units and their recorded calls.
        restored_uids: Units the submission restored.
        prefix: Command prefix that drops to the sandbox user.
        scratch: Private working directory of the verifier.
        pub: Directory readable by the sandbox user that holds the runner.
        cand_nt: Tree without test directories that the calls run in.
        cfg: Limits from grade_config.json.
        cpus: Number of modules replayed at the same time.
        deadline: time.monotonic() value at which the phase ends.
        stats: A dict that gets the phase's counts: starts, calls that ran out
            of time, ends and stops of a runner, units whose rest was not run.

    Returns:
        The canonical result per call id; None for a call that did not finish
        or was reported twice. Calls that were not reached are absent.

    Raises:
        EvaluationError: The runner could not be started.
    """
    vdir = os.path.join(scratch, "vec")
    os.makedirs(vdir, exist_ok=True)
    os.chmod(vdir, 0o755)
    jobs = []
    for k, (mod, p) in enumerate(sorted(payload.items())):
        vecs = [v for v in p["vectors"] if v[1] in restored_uids]
        if not vecs:
            continue
        op = os.path.join(vdir, f"o{k}.jsonl")
        open(op, "w").close()
        os.chmod(op, 0o666)
        jobs.append((k, mod, p["units"], vecs, op))
    per_vec = float(cfg.get("vector_timeout_sec", 10))
    load_sec = float(cfg.get("vector_load_sec", 120))
    stall_sec = per_vec + float(cfg.get("vector_stall_margin_sec", 30))
    restart_limit = max(0, int(cfg.get("vector_job_restart_limit", 16)))
    overrun_limit = max(1, int(cfg.get("vector_unit_overrun_limit", 2)))
    rv = os.path.join(pub, "rvector.py")
    lock = threading.Lock()
    counts = {"starts": 0, "timeouts": 0, "ended_or_stopped": 0, "units_cut": 0}

    def count(name, n=1):
        with lock:
            counts[name] += n

    def one(job):
        k, mod, units, vecs, op = job
        want = {v[0] for v in vecs}
        unfinished: set = set()
        got: dict = {}
        dup: set = set()
        pending = vecs
        crashes = starts = 0
        keys: list = []
        overruns: collections.Counter = collections.Counter()   # per unit: calls past their time, stops of the runner

        def overran(uid, rest):
            """Count one overrun of `uid`; at the limit its calls left do not match and are not run."""
            overruns[uid] += 1
            if overruns[uid] < overrun_limit:
                return rest
            cut = [v for v in rest if v[1] == uid]
            if cut:
                unfinished.update(v[0] for v in cut)
                count("units_cut")
            return [v for v in rest if v[1] != uid]

        while pending:
            left = deadline - time.monotonic()
            if left <= 5:
                break
            starts += 1
            count("starts")
            ip = os.path.join(vdir, f"i{k}.{starts}.pkl")
            with open(ip, "wb") as f:
                pickle.dump({"units": {uid: units[uid] for _, uid, _ in pending}, "vectors": pending}, f, protocol=4)
            os.chmod(ip, 0o644)
            try:
                # a process that was ended in the middle of a line must not spoil the next line
                with open(op, "rb+") as f:
                    f.seek(0, os.SEEK_END)
                    if f.tell():
                        f.seek(-1, os.SEEK_END)
                        if f.read(1) != b"\n":
                            f.write(b"\n")
            except OSError:
                pass
            cmd = prefix + [sys.executable, "-P", "-s", "-B", rv, cand_nt, mod, ip, op, str(per_vec)]
            before = len(got)
            keys.append(secrets.token_hex(16))
            try:
                state, first, code = watch(cmd, cwd=cand_nt, env=SANDBOX_ENV, log_path=os.devnull, res_path=op,
                                           deadline=deadline, collect_sec=load_sec, stall_sec=stall_sec, marker=None,
                                           stdin_data=(keys[-1] + "\n").encode("ascii"))
            except OSError as exc:
                raise EvaluationError("The call runner could not be started") from exc
            got, dup = read_vector_records(op, want, keys)
            rest = [v for v in pending if v[0] not in got]
            if not rest or state == "budget":
                break
            if first is None:
                # not even the module's import finished: none of the job's calls can be replayed
                unfinished.update(v[0] for v in rest)
                break
            if state == "done" and code == 3 and len(got) > before:
                # the runner started afresh after a call that ran out of time
                for v in pending:
                    if got.get(v[0]) == ["EXC", "Timeout", []]:
                        count("timeouts")
                        rest = overran(v[1], rest)
                pending = rest
                continue
            # the process ended, or stopped, at the first call without a result
            culprit = rest[0]
            unfinished.add(culprit[0])
            count("ended_or_stopped")
            if len(got) == before:
                # not even the first call returned: the rest of its unit is not tried again
                unfinished.update(v[0] for v in rest if v[1] == culprit[1])
                pending = [v for v in rest if v[1] != culprit[1]]
            else:
                pending = overran(culprit[1], rest[1:]) if state == "stalled" else rest[1:]
            crashes += 1
            if crashes >= restart_limit:
                # the job's own bodies keep ending it: the calls left do not match
                unfinished.update(v[0] for v in pending)
                break
        for vid in unfinished | dup:
            got[vid] = None
        return got

    results = {}
    with ThreadPoolExecutor(cpus) as ex:
        for got in ex.map(one, jobs):
            results.update(got)
    if stats is not None:
        stats.update(counts)
    return results


CRASH_ITEM = re.compile(r"AssertionError: \('([^']+)', <WorkerController ")
SELFCHECK_FILE = "tripwire_checks/test_tripwire.py"
SELFCHECK_PASS = SELFCHECK_FILE + "::test_must_pass"
SELFCHECK_FAIL = SELFCHECK_FILE + "::test_must_fail"


@dataclass(frozen=True)
class SealedResult:
    """What the sealed test phase established.

    `outcome` holds "passed" or "failed" for every sealed test that was settled;
    a test missing from it was not reached. `runner_passed` is the sum of the
    pass tallies pytest printed, over the runs that printed one.
    """

    outcome: Mapping[str, str]
    selfcheck_ok: bool
    timed_out: bool
    runner_passed: int | None
    tally_exceeded: bool
    runs: int
    passes: int
    first_test_sec: float | None


def runner_tally(text: str) -> int | None:
    """Return the number of passes pytest printed at the end of one run.

    Args:
        text: What one pytest run printed.

    Returns:
        The count from the final summary line, or None when the run printed none.
    """
    for line in reversed(text[-4000:].splitlines()):
        m = re.search(r"\b(\d+) passed\b", line)
        if m and (" in " in line or "failed" in line or "error" in line or line.strip().startswith("=")):
            return int(m.group(1))
        if re.search(r"\b\d+ (failed|errors?)\b", line) and "passed" not in line:
            return 0
    return None


def read_records(res_path: str, want: set[str]) -> tuple[dict[str, str], set[str], set[str]]:
    """Read what one pytest run recorded through the runner plugin.

    Args:
        res_path: File the plugin appended one JSON record per event to.
        want: Test ids this run was asked for, with the two self-check tests.

    Returns:
        The outcome per test (a failure sticks), the tests reported as started
        and the test files pytest could not collect.
    """
    outcome: dict[str, str] = {}
    started: set[str] = set()
    uncollectable: set[str] = set()
    try:
        with open(res_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except (ValueError, RecursionError, MemoryError):
                    continue
                if not isinstance(rec, dict) or not isinstance(rec.get("id"), str):
                    continue
                nid, when, oc = rec["id"], rec.get("when"), rec.get("outcome")
                if when == "collect":
                    uncollectable.add(nid.split("::")[0])
                elif nid not in want:
                    continue
                elif when == "start":
                    started.add(nid)
                elif oc in ("passed", "failed"):
                    outcome[nid] = "failed" if oc == "failed" or outcome.get(nid) == "failed" else "passed"
    except OSError:
        pass
    return outcome, started, uncollectable


START_RECORD = b'"when": "start"'


def watch(cmd, *, cwd, env, log_path, res_path, deadline, collect_sec, stall_sec, marker=START_RECORD, stdin_data=None):
    """Run one sandboxed process until it ends, stops reporting or its time ends.

    Until its work starts, the process is starting up (pytest is collecting, a
    replay job is importing) and gets `collect_sec` in total. After that,
    `stall_sec` may pass between records. Only what this process appends to
    `res_path` counts: records an earlier run left there do not.

    Args:
        cmd: Command to start.
        cwd: Directory to start it in.
        env: Its environment.
        log_path: File that receives its output.
        res_path: File its plugin appends records to; growth means progress.
        deadline: time.monotonic() value at which the phase's budget ends.
        collect_sec: Seconds allowed before the work starts.
        stall_sec: Seconds allowed between records once it has started.
        marker: Bytes of a record that shows the work has started (for pytest,
            a test start); None lets any record count.
        stdin_data: Bytes written to the process's standard input, which is then
            closed (a runner's key); without them its input is empty.

    Returns:
        "done", "stalled" or "budget"; the seconds until the work started; and
        the process's exit status when it ended by itself, else None.

    Raises:
        OSError: The process could not be started.
    """
    began = last = time.monotonic()
    first = None
    try:
        offset = os.path.getsize(res_path)
    except OSError:
        offset = 0
    tail = b""
    with open(log_path, "w", encoding="utf-8") as lf:
        # its own process group, so that ending it also ends the workers it started
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
                                stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
        if stdin_data is not None:
            try:
                proc.stdin.write(stdin_data)
                proc.stdin.close()
            except OSError:
                pass
        try:
            while True:
                try:
                    proc.wait(timeout=1.0)
                    ended = True
                except subprocess.TimeoutExpired:
                    ended = False
                now = time.monotonic()
                try:
                    with open(res_path, "rb") as rf:
                        rf.seek(offset)
                        chunk = rf.read()
                except OSError:
                    chunk = b""
                if chunk:
                    offset += len(chunk)
                    last = now
                    if first is None and (marker is None or marker in tail + chunk):
                        first = round(now - began, 1)
                    tail = chunk[-len(marker):] if marker else b""
                if ended:
                    return "done", first, proc.returncode
                if now >= deadline:
                    return "budget", first, None
                if (first is None and now - began > collect_sec) or (first is not None and now - last > stall_sec):
                    return "stalled", first, None
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            if proc.poll() is None:
                proc.kill()
            proc.wait()


def sealed_run(ids, prefix, *, tag, workers, deadline, pub, scratch, cand, cfg):
    """Run pytest once over the given sealed tests and the two self-check tests.

    Args:
        ids: Sealed test ids to run.
        prefix: Command prefix that drops to the sandbox user.
        tag: Name that keeps this run's files apart from other runs'.
        workers: Number of xdist workers; 0 runs one plain pytest process.
        deadline: time.monotonic() value at which the phase's budget ends.
        pub: Directory readable by the sandbox user that holds the plugin.
        scratch: Private working directory of the verifier.
        cand: Tree the tests run in.
        cfg: Limits from grade_config.json.

    Returns:
        A dict with `state` ("done", "stalled" or "budget"), the `text` the run
        printed, the `outcome` per test, the tests it `started`, the test files
        it found `uncollectable` and `first_test_sec`.

    Raises:
        EvaluationError: pytest could not be started.
    """
    want = set(ids) | {SELFCHECK_PASS, SELFCHECK_FAIL}
    list_path = os.path.join(pub, f"sealed_ids.{tag}.json")
    res_path = os.path.join(scratch, f"pytest_results.{tag}.jsonl")
    log_path = os.path.join(scratch, f"pytest.{tag}.log")
    with open(list_path, "w", encoding="utf-8") as f:
        json.dump(sorted(want), f)
    os.chmod(list_path, 0o644)
    open(res_path, "w").close()
    os.chmod(res_path, 0o666)
    # the self-check file is collected first so that a run cut short still reports it
    files = [SELFCHECK_FILE] + sorted({t.split("::")[0] for t in ids})
    cmd = prefix + [
        sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-p", "sealed_plugin",
        "-o", "addopts=", "-m", "not slow and not tooslow", "-q", "--no-header",
    ]
    if workers:
        cmd += ["-n", str(workers)]
    cmd += ["--timeout", str(cfg.get("test_timeout_sec", 60))] + files
    env = dict(SANDBOX_ENV, PYTHONUNBUFFERED="1", PYTHONPATH=os.path.join(pub, "plugins"),
               SEALED_LIST=list_path, SEALED_RESULTS=res_path)
    collect_sec = cfg.get("pytest_collect_sec", 600) if workers else cfg.get("pytest_file_collect_sec", 120)
    try:
        state, first, _code = watch(cmd, cwd=cand, env=env, log_path=log_path, res_path=res_path, deadline=deadline,
                                    collect_sec=float(collect_sec), stall_sec=float(cfg.get("pytest_stall_sec", 180)))
    except OSError as exc:
        raise EvaluationError("The test runner could not be started") from exc
    with open(log_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    outcome, started, uncollectable = read_records(res_path, want)
    return {"state": state, "text": text, "outcome": outcome, "started": started,
            "uncollectable": uncollectable, "first_test_sec": first}


def run_sealed_tests(sealed_ids, prefix, notes, *, scratch, pub, cand, art, cfg, cpus, deadline) -> SealedResult:
    """Run the sealed upstream tests in the sandbox, with a two-test self-check.

    The first pass is one pytest session over every test. A session can end, or
    stop reporting, before it has run every test: an import that never returns
    blocks collection for all of them, and a timeout that lands inside pytest's
    own reporting code takes a worker or the whole session down. Tests lost
    that way say nothing about the submission, so the later passes run them
    again with one process per test file, where a hang or a crash costs only
    that file. A file is tried again only while it keeps settling tests, and
    never once pytest has reported it as uncollectable. A test that was running
    when its run ended gets one more run; left unfinished a second time, or
    named by a session as the test that brought it down, it counts as failed.
    Everything happens before `deadline`, the end of the whole measurement, so
    this phase has whatever time the earlier phases left. A test still without
    an outcome then is not reached.

    Args:
        sealed_ids: Ids of the sealed tests.
        prefix: Command prefix that drops to the sandbox user.
        notes: Diagnostic notes for metrics.json, appended to in place.
        scratch: Private working directory of the verifier.
        pub: Directory readable by the sandbox user.
        cand: Tree the tests run in.
        art: Directory for diagnostic artifacts.
        cfg: Limits from grade_config.json.
        cpus: Number of pytest workers, and of test files run at the same time.
        deadline: time.monotonic() value at which the measurement ends.

    Returns:
        The outcomes and the integrity signals of the phase.

    Raises:
        EvaluationError: pytest could not be started.
    """
    tw_dir = os.path.join(cand, "tripwire_checks")
    os.makedirs(tw_dir, exist_ok=True)
    shutil.copyfile(LIB / "test_selfcheck.py", os.path.join(tw_dir, "test_tripwire.py"))
    os.chmod(tw_dir, 0o755)
    os.chmod(os.path.join(tw_dir, "test_tripwire.py"), 0o644)
    log_path = os.path.join(art, "pytest_sealed.log")
    open(log_path, "w").close()
    pass_limit = max(1, int(cfg.get("pytest_pass_limit", 5)))
    sealed = set(sealed_ids)
    outcome: dict[str, str] = {}
    unfinished: collections.Counter[str] = collections.Counter()
    uncollectable: set[str] = set()
    tallies: list[int] = []
    flags = {"selfcheck_ok": True, "tally_exceeded": False, "budget": False, "runs": 0}
    lock = threading.Lock()

    def absorb(ids, run, header) -> int:
        """Fold one run into the totals and return how many of `ids` it settled."""
        with lock:
            flags["runs"] += 1
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"\n==== {header}: {run['state']} ====\n{run['text']}")
            got = run["outcome"]
            # a self-check that reports the wrong outcome means the runner was interfered with;
            # one that did not report at all (the run was cut short) is not counted against it
            if got.get(SELFCHECK_PASS, "passed") != "passed" or got.get(SELFCHECK_FAIL, "failed") != "failed":
                flags["selfcheck_ok"] = False
            if run["state"] == "budget":
                flags["budget"] = True
            tally = runner_tally(run["text"]) if run["state"] == "done" else None
            if tally is not None:
                # pytest prints its own tally; the records of a run may not claim more passes
                tallies.append(tally)
                if sum(1 for oc in got.values() if oc == "passed") > tally:
                    flags["tally_exceeded"] = True
            uncollectable.update(run["uncollectable"])
            before = sum(1 for t in ids if t in outcome)
            for nid, oc in got.items():
                if nid in sealed:
                    outcome[nid] = "failed" if oc == "failed" or outcome.get(nid) == "failed" else "passed"
            named = set(CRASH_ITEM.findall(run["text"])) & sealed
            for nid in sorted((run["started"] & sealed) | named):
                if nid in outcome:
                    continue
                unfinished[nid] += 1
                if nid in named or unfinished[nid] >= 2:
                    outcome[nid] = "failed"
            return sum(1 for t in ids if t in outcome) - before

    def retryable(ids, progressed=None) -> list[str]:
        """Return the tests without an outcome that another run could still settle."""
        return [t for t in ids if t not in outcome and t.split("::")[0] not in uncollectable
                and (progressed is None or progressed.get(t.split("::")[0], 0) > 0)]

    session_ids = sorted(sealed)
    session = sealed_run(session_ids, prefix, tag="s1", workers=cpus, deadline=deadline,
                         pub=pub, scratch=scratch, cand=cand, cfg=cfg)
    reap(prefix)
    absorb(session_ids, session, f"session over {len(session_ids)} tests")
    passes, resumed = 1, 0
    pending = retryable(session_ids)
    while pending and not flags["budget"] and passes < pass_limit and time.monotonic() < deadline - 1:
        passes += 1
        by_file: dict[str, list[str]] = collections.defaultdict(list)
        for nid in pending:
            by_file[nid.split("::")[0]].append(nid)

        def one(job, number=passes):
            k, (path, ids) = job
            if time.monotonic() >= deadline - 1:
                with lock:
                    flags["budget"] = True
                return path, 0
            run = sealed_run(ids, prefix, tag=f"p{number}f{k}", workers=0, deadline=deadline,
                             pub=pub, scratch=scratch, cand=cand, cfg=cfg)
            return path, absorb(ids, run, f"pass {number}, {path}, {len(ids)} tests")

        with ThreadPoolExecutor(max(1, cpus)) as ex:
            progressed = dict(ex.map(one, enumerate(sorted(by_file.items()))))
        reap(prefix)
        resumed += sum(progressed.values())
        pending = retryable(pending, progressed)
    timed_out = flags["budget"] or (bool(pending) and time.monotonic() >= deadline - 1)
    if timed_out:
        notes.append("the measurement's time ran out during the sealed tests; the tests without an outcome were not reached")
    if session["state"] == "stalled":
        notes.append("the test session stopped reporting and was ended")
    if resumed:
        notes.append(f"{resumed} tests the session did not finish were settled with one process per test file")
    return SealedResult(outcome, flags["selfcheck_ok"], timed_out, sum(tallies) if tallies else None,
                        flags["tally_exceeded"], flags["runs"], passes, session["first_test_sec"])


SIZE_CLASSES = (("1-3", 1, 3), ("4-10", 4, 10), ("11-30", 11, 30), ("over 30", 31, 10**9))


def identical_bodies(cand: str, units, states: Mapping[str, str], original_bodies: Mapping[str, list]) -> dict:
    """Share of restored bodies whose syntax tree equals the original's, by size of the original body.

    Reported only: it says how much of a result is recall of the original source. The original
    is known here only by a hash of each body's syntax tree.
    """
    restored = [u for u in units if states.get(u["uid"]) == "restored"]
    facts = bodies.body_facts(cand, restored)
    out = {}
    for label, low, high in SIZE_CLASSES + (("all", 1, 10**9),):
        rows = [u["uid"] for u in restored if low <= int((original_bodies.get(u["uid"]) or [0])[0] or 0) <= high]
        same_tree = sum(1 for uid in rows if uid in facts and facts[uid][1] is not None
                        and facts[uid][1] == (original_bodies.get(uid) or [0, None])[1])
        out[label] = {"identical": same_tree, "restored": len(rows), "share": round(same_tree / len(rows), 4) if rows else 0.0}
    return out


def withhold(skel: str, cand: str, byfile: Mapping[str, Mapping[str, str]], files, states: dict) -> None:
    """Put the skeleton back in the candidate for each of `files` and mark its units `late`."""
    for rel in files:
        shutil.copyfile(os.path.join(skel, rel), os.path.join(cand, rel))
        for uid in byfile.get(rel, {}).values():
            states[uid] = "late"


def measure(context: VerificationContext) -> Measurement:
    """Build the measured tree and run the three measurements once.

    Args:
        context: Trusted paths, limits and thresholds for this evaluation.

    Returns:
        Fixed denominators, passing numerators, self-check trips and the full
        diagnostic record. A delivery the collect step refused (no usable tree
        under its name, or one over its limits), or a tree with no restored
        unit, is a completed measurement with zero numerators.

    Raises:
        EvaluationError: Private inputs are unreadable or describe no unit or
            counted call, the verifier can reach the network, nothing arrived,
            the copy does not match the collect step's signed record, the
            collect step could not tell when the work ended and a unit is
            restored, privileges cannot be dropped, or a runner cannot be
            started. No reward is valid then.
    """
    t_start = time.monotonic()
    cfg = dict(context.limits)
    # one deadline for the whole measurement; each phase also has its own limit, and the test
    # phase has whatever time the others leave
    deadline = t_start + float(cfg.get("measure_budget_sec", 6000))
    work_tree, skel = str(context.work_tree), str(context.skeleton)
    out, scratch, private = str(context.output), str(context.scratch), str(context.private)
    cand = os.path.join(scratch, "cand")          # candidate tree with the upstream tests
    cand_nt = os.path.join(scratch, "cand_nt")    # the same tree without any test directory
    pub = os.path.join(scratch, "pub")
    art = os.path.join(out, "artifacts")
    # worker count: the verifier environment's CPU allowance, never more than the machine reports
    cpus = max(1, min(os.cpu_count() or 2, int(cfg.get("workers", 4))))
    os.makedirs(art, exist_ok=True)
    os.makedirs(scratch, exist_ok=True)
    try:
        units, byfile = restorelib.load_units(os.path.join(private, "units.json"))
        with open(os.path.join(private, "sealed_tests.json"), encoding="utf-8") as f:
            sealed_ids = json.load(f)["tests"]
        with open(os.path.join(private, "vectors", "inputs.pkl"), "rb") as f:
            payload = pickle.load(f)
        with open(os.path.join(private, "vectors", "gold.json"), encoding="utf-8") as f:
            gold = json.load(f)
        # recorded calls whose arguments a docstring example or a visible test also uses
        with open(os.path.join(private, "vectors", "documented.json"), encoding="utf-8") as f:
            documented = set(json.load(f)["calls"])
        with open(os.path.join(private, "unit_bodies.json"), encoding="utf-8") as f:
            original_bodies = json.load(f)
        # the original's own times, per module and unit, and the benchmark of the machine they were taken on
        with open(os.path.join(private, "timing.json"), encoding="utf-8") as f:
            timing = json.load(f)
        timing["doctest"], timing["vector"], float(timing["benchmark_sec"])
    except (OSError, ValueError, KeyError, TypeError, pickle.UnpicklingError) as e:
        raise EvaluationError(f"Private verifier inputs are unreadable: {type(e).__name__}") from e
    if not os.path.isdir(skel):
        raise EvaluationError("Reference skeleton is missing")
    U, T, V = len(units), len(sealed_ids), len(gold)
    uid_of = {v[0]: v[1] for p in payload.values() for v in p["vectors"]}
    deciding = sorted(vid for vid in gold if vid not in documented)
    unit_set = {uid_of[vid] for vid in deciding if vid in uid_of}
    if not deciding or not unit_set or not U:
        raise EvaluationError("Private verifier inputs hold no unit or no counted call")
    metrics: dict[str, Any] = {
        "units_total": U, "units_restored": 0, "units_passing": 0,
        "vectors_total": V, "vectors_passing": 0,
        "tests_total": T, "tests_passing": 0,
        # the reward's measure: units with a call no docstring example or visible test repeats,
        # and those calls
        "units_set": len(unit_set), "units_set_passing": 0, "units_left_out": U - len(unit_set),
        "deciding_total": len(deciding), "deciding_passing": 0, "documented_total": V - len(deciding),
        "unit_share": 0.0, "call_share": 0.0, "unit_share_if_reached": 0.0, "call_share_if_reached": 0.0,
        "units_examples_passing": 0, "units_documented_calls_only": 0, "units_left_out_passing": 0,
        # no test has run until the test phase says otherwise
        "unit_share_by_lines": 0.0, "units_not_reached": 0, "tests_not_reached": T, "identical_bodies": {},
        "unit_deciding_share": float(cfg.get("unit_deciding_share", 0.0)),
        "reward_tolerance": float(cfg.get("reward_tolerance", 0.001)),
        "late_files": [], "late_entries": 0, "egress_open": None, "end_from": None, "end_note": None,
        "tamper": [], "notes": [],
        "unit_bar": context.scoring.unit_bar, "vector_bar": context.scoring.call_bar,
        "test_bar": context.scoring.test_bar,
    }

    def finish(artifact_present: bool) -> Measurement:
        metrics["grade_seconds"] = round(time.monotonic() - t_start, 1)
        counts = {k: int(metrics[k]) for k in (
            "units_total", "units_restored", "units_passing",
            "vectors_total", "vectors_passing", "tests_total", "tests_passing",
            "units_set", "units_set_passing", "deciding_total", "deciding_passing")}
        return Measurement(artifact_present, counts, tuple(metrics["tamper"]), metrics)

    # submitted code must not reach the network from here
    reachable = delivery.network_open()
    if reachable is not None:
        raise EvaluationError(f"The verifier can reach {reachable}; it must run with no network")
    # what arrived, checked against the collect step's signed record before anything is measured
    tree = os.path.join(work_tree, "sympy")
    delivered = delivery.read_delivery(Path(tree), Path(private) / "fsmaint.key", delivery.PROGRESS)
    metrics["delivery"] = delivered.summary
    metrics["egress_open"] = delivered.summary.get("egress_open")
    metrics["notes"].extend(delivered.notes)
    late = {f"sympy/{path}" for path in delivered.late}
    metrics["late_files"] = sorted(late & set(byfile))[:500]
    metrics["late_entries"] = len(late)
    # unit files changed after the end of the work that the collect step replaced by its last copy before it
    metrics["copied_files"] = sorted(f"sympy/{path}" for path in delivered.copied)[:500]
    metrics["units_changed_after_the_end"] = sorted({str(uid) for c in delivered.copied.values()
                                                     for uid in (c.get("units_changed_after") or [])})[:2671]
    metrics["end_from"], metrics["end_note"] = delivered.end_from, delivered.end_note
    if delivered.state != "listed":
        reason = delivered.summary.get("refused") or delivered.state
        metrics["notes"].append(f"the collect step refused the tree ({reason}); nothing was delivered")
        return finish(False)

    # 1. candidate tree = reference skeleton + restored bodies (nothing else is taken over); a unit
    #    file changed after the end of the work is not taken over either
    if os.path.exists(cand):
        shutil.rmtree(cand)
    shutil.copytree(skel, cand, symlinks=False)
    states, _notes = restorelib.build_candidate(skel, work_tree, cand, byfile, None)
    if delivered.end_bound is None:
        # no end of the work is known: a tree that restores nothing scores 0 whenever it was written;
        # any other could hold files written after the work, and nothing here says which
        restored_count = sum(1 for state in states.values() if state == "restored")
        if restored_count:
            raise EvaluationError(f"The collect step could not tell when the work ended ({delivered.end_note}), "
                                  f"and {restored_count} units are restored")
        metrics["notes"].append(f"no end of the work is known ({delivered.end_note}); no unit is restored")
    withhold(skel, cand, byfile, metrics["late_files"], states)
    st_count = collections.Counter(s.split(":")[0] for s in states.values())
    metrics["unit_states"] = dict(st_count)
    metrics["units_restored"] = st_count.get("restored", 0)
    log("unit states:", dict(st_count))
    # closed until the test phase; phases 2 and 3 run on a copy without test directories
    subprocess.run(["chmod", "-R", "go-rwx", cand], check=False)
    for closed in (skel, private, work_tree, out):
        subprocess.run(["chmod", "go-rwx", closed], check=False)
    if os.path.exists(cand_nt):
        shutil.rmtree(cand_nt)
    shutil.copytree(cand, cand_nt, symlinks=False, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    subprocess.run(["chmod", "-R", "a+rX,go-w", cand_nt], check=False)
    try:
        with tarfile.open(os.path.join(art, "candidate_unit_files.tar.gz"), "w:gz") as tf:
            for rel in sorted(byfile):
                tf.add(os.path.join(cand, rel), arcname=rel)
    except OSError as e:
        metrics["notes"].append(f"could not write reproducer bundle: {e}")
    if metrics["units_restored"] == 0:
        # every measured item fails on the unrestored skeleton, so there is nothing to run
        metrics["notes"].append("no unit restored; nothing to measure")
        log("no unit restored")
        return finish(True)

    # the sandbox gets its own copies of the runner scripts; the verifier code stays private
    if os.path.exists(pub):
        shutil.rmtree(pub)
    os.makedirs(os.path.join(pub, "plugins"))
    for name in ("rdoctest.py", "rvector.py", "canon.py"):
        shutil.copyfile(LIB / name, os.path.join(pub, name))
    shutil.copyfile(LIB / "plugins" / "sealed_plugin.py", os.path.join(pub, "plugins", "sealed_plugin.py"))
    subprocess.run(["chmod", "-R", "a+rX,go-w", pub], check=False)
    os.chmod(scratch, 0o755)
    prefix = sandbox_prefix(str(cfg.get("run_group", "nogroup")), int(cfg.get("address_space_bytes", 0)), metrics["notes"])
    restored = {u["uid"] for u in units if states[u["uid"]] == "restored"}

    # how much slower than the machine the original's own times were taken on this one is, measured here
    # before any submitted code runs; it decides, with those times, whether a phase that ran out of time
    # did so because of the submission (its items then fail) or of the machine (an evaluation error)
    host = max(1.0, host_benchmark() / float(timing["benchmark_sec"]))
    attribution = float(cfg.get("attribution_factor", 2.0))
    metrics["host_factor"] = round(host, 3)

    def attributable(phase: str, modules: Mapping, began: float, phase_end: float) -> tuple[bool, float, float]:
        """Whether the original would need at most 1/attribution of the phase's worker-seconds here."""
        needed = time_needed(timing[phase], modules, host)
        available = cpus * max(0.0, phase_end - began)
        return attribution * needed <= available, needed, available

    # 2. docstring examples of every restored unit
    t0 = time.monotonic()
    dt_scratch = os.path.join(scratch, "dt")
    os.makedirs(dt_scratch, exist_ok=True)
    os.chmod(dt_scratch, 0o755)
    run = collections.defaultdict(list)
    for u in units:
        if u["uid"] in restored:
            run[u["module"]].append(u["dotted"])
    dt_end = min(deadline, t0 + float(cfg.get("doctest_budget_sec", 1800)))
    dt_stats: dict = {}
    try:
        results, tamper, dt_not_reached = gradelib.run_doctests(
            cand_nt, run, os.path.join(pub, "rdoctest.py"), watch=watch, workers=cpus, deadline=dt_end,
            timeout=float(cfg.get("unit_timeout_sec", 20)), prefix_cmd=prefix, scratch=dt_scratch, env=SANDBOX_ENV,
            load_sec=float(cfg.get("doctest_load_sec", 120)), stall_margin_sec=float(cfg.get("doctest_stall_margin_sec", 30)),
            restart_limit=int(cfg.get("doctest_module_restart_limit", 8)), stats=dt_stats)
    except gradelib.RunnerUnavailable as exc:
        raise EvaluationError("The docstring runner could not be started") from exc
    reap(prefix)
    metrics["doctest_runs"] = dt_stats
    if dt_not_reached:
        decided, needed, available = attributable("doctest", run, t0, dt_end)
        metrics["doctest_seconds_needed"], metrics["doctest_worker_seconds"] = round(needed, 1), round(available, 1)
        if decided:
            # the original needs a small share of this phase here: what used it up was the submission's own
            # bodies (slow, never ending, crashing), so the units it left count as failed, not as unknown
            for name, record in list(results.items()):
                if record.get("not_reached"):
                    results[name] = {"name": name, "status": "timeout",
                                     "exc": "not reached: the phase's time went on the submission's own bodies"}
            metrics["notes"].append(
                f"{dt_not_reached} units' examples were not reached in {available:.0f} worker-seconds, of which the original "
                f"needs about {needed:.0f} here: they count as failed")
            metrics["units_not_reached_failed"] = dt_not_reached
            dt_not_reached = 0
    unit_rows, n_examples = [], 0
    for u in units:
        s = states[u["uid"]]
        r = results.get(u["dotted"]) if s == "restored" else None
        ok = bool(r and r["status"] == "pass")
        n_examples += ok
        unit_rows.append({"uid": u["uid"], "unit": f"{u['file']}::{u['qualname']}", "state": s,
                          "result": (r or {}).get("status"), "examples_pass": ok})
    metrics["units_examples_passing"] = n_examples
    metrics["tamper"] = sorted(set(tamper))
    metrics["doctest_seconds"] = round(time.monotonic() - t0, 1)
    metrics["units_not_reached"] = dt_not_reached
    log(f"unit examples: {n_examples}/{U} pass in {metrics['doctest_seconds']}s; self-check failures={tamper[:3]}")

    # 3. recorded calls, replayed in the sandbox and compared here with the reference results
    t0 = time.monotonic()
    v_end = min(deadline, t0 + float(cfg.get("vector_budget_sec", 1200)))
    v_stats: dict = {}
    vres = run_vectors(payload, restored, prefix, scratch=scratch, pub=pub, cand_nt=cand_nt, cfg=cfg, cpus=cpus,
                       deadline=v_end, stats=v_stats)
    reap(prefix)
    metrics["vector_runs"] = v_stats
    v_unreached = [vid for vid in gold if uid_of.get(vid) in restored and vid not in vres]
    if v_unreached:
        replayed = collections.defaultdict(list)
        for mod, p in payload.items():
            replayed[mod] = sorted({uid for _, uid, _ in p["vectors"] if uid in restored})
        decided, needed, available = attributable("vector", {m: k for m, k in replayed.items() if k}, t0, v_end)
        metrics["vector_seconds_needed"], metrics["vector_worker_seconds"] = round(needed, 1), round(available, 1)
        if decided:
            for vid in v_unreached:
                vres[vid] = None
            metrics["notes"].append(
                f"{len(v_unreached)} recorded calls were not reached in {available:.0f} worker-seconds, of which the original "
                f"needs about {needed:.0f} here: they count as not matching")
            metrics["vectors_not_reached_failed"] = len(v_unreached)
    v_pass, vrows, unreadable = 0, {}, 0
    # each result compared by its unit's profile: exact, but for the relaxations that unit needs; a
    # result line the runner wrote that cannot be compared fails its call, never the evaluation
    key_of = {u["uid"]: f"{u['file']}::{u['qualname']}" for u in units}
    for vid, g in gold.items():
        c = vres.get(vid)
        try:
            ok = c is not None and same(c, g, profile=profile_of(key_of.get(uid_of.get(vid), "")))
        except Exception:  # noqa: BLE001 - same() is total; this guards the call itself
            ok, unreadable = False, unreadable + 1
        v_pass += ok
        vrows[vid] = ok
    if unreadable:
        metrics["notes"].append(f"{unreadable} call results could not be compared and count as not matching")
    metrics["vectors_passing"] = v_pass
    metrics["vectors_not_reached"] = sum(1 for vid in gold if uid_of.get(vid) in restored and vid not in vres)
    metrics["vector_seconds"] = round(time.monotonic() - t0, 1)
    log(f"reference comparison: {v_pass}/{V} recorded calls match in {metrics['vector_seconds']}s")
    per_unit = collections.defaultdict(lambda: {"all": [0, 0], "deciding": [0, 0, 0], "documented": [0, 0]})
    for vid, ok in vrows.items():
        uid = uid_of.get(vid, "?")
        per_unit[uid]["all"][0 if ok else 1] += 1
        if vid in documented:
            per_unit[uid]["documented"][0 if ok else 1] += 1
        else:
            per_unit[uid]["deciding"][0 if ok else 1] += 1
            if uid in restored and vid not in vres:
                per_unit[uid]["deciding"][2] += 1   # the call phase's time ran out before this call
    share_needed = metrics["unit_deciding_share"]
    examples_not_reached = {u["dotted"] for u in units if (results.get(u["dotted"]) or {}).get("not_reached")}
    dotted_of = {u["uid"]: u["dotted"] for u in units}
    n_pass = set_pass = set_pass_high = doc_only = 0
    lines_set = lines_pass = 0
    for row in unit_rows:
        cell = per_unit.get(row["uid"]) or {"all": [0, 0], "deciding": [0, 0, 0], "documented": [0, 0]}
        a, b = cell["all"]
        dm, dn, dr = cell["deciding"]
        row["calls_matching"], row["calls_total"] = a, a + b
        row["deciding_matching"], row["deciding_total"] = dm, dm + dn
        row["documented_matching"] = cell["documented"][0]
        # the bars of a complete restoration: examples pass and at least one recorded call matches
        row["pass"] = bool(row["examples_pass"] and a >= 1)
        n_pass += row["pass"]
        if dm + dn == 0:
            row["in_set"] = False
            continue
        # the reward's unit rule: examples pass and enough calls that nothing visible repeats match
        need = max(1, math.ceil(share_needed * (dm + dn) - 1e-9))
        row["in_set"] = True
        row["unit_pass"] = bool(row["examples_pass"] and dm >= need)
        set_pass += row["unit_pass"]
        examples_high = row["examples_pass"] or dotted_of[row["uid"]] in examples_not_reached
        set_pass_high += bool(row["state"] == "restored" and examples_high and dm + dr >= need)
        weight = int((original_bodies.get(row["uid"]) or [1])[0] or 1)
        lines_set += weight
        lines_pass += weight if row["unit_pass"] else 0
        if row["examples_pass"] and not row["unit_pass"] and row["documented_matching"]:
            doc_only += 1
    left_out_passing = sum(1 for row in unit_rows if not row.get("in_set") and row["examples_pass"] and row["documented_matching"])
    metrics["units_passing"] = n_pass
    metrics["units_set_passing"] = set_pass
    d_pass = sum(1 for vid in deciding if vrows.get(vid))
    d_unreached = sum(1 for vid in deciding if uid_of.get(vid) in restored and vid not in vres)
    metrics["deciding_passing"] = d_pass
    metrics["deciding_not_reached"] = d_unreached
    metrics["unit_share"] = round(set_pass / len(unit_set), 6) if unit_set else 0.0
    metrics["call_share"] = round(d_pass / len(deciding), 6) if deciding else 0.0
    metrics["unit_share_if_reached"] = round(set_pass_high / len(unit_set), 6) if unit_set else 0.0
    metrics["call_share_if_reached"] = round((d_pass + d_unreached) / len(deciding), 6) if deciding else 0.0
    metrics["unit_share_by_lines"] = round(lines_pass / lines_set, 6) if lines_set else 0.0
    # units in the set that pass their examples and match a documented call but no counted one (what a
    # table of documented outputs would show), and units outside the set that pass and match one
    metrics["units_documented_calls_only"] = doc_only
    metrics["units_left_out_passing"] = left_out_passing
    # units whose examples are reported as passing while most of their calls do not match
    metrics["units_examples_without_calls"] = sum(
        1 for row in unit_rows if row["examples_pass"] and 2 * row["calls_matching"] < row["calls_total"])
    metrics["identical_bodies"] = identical_bodies(cand, units, states, original_bodies)
    with open(os.path.join(art, "unit_results.json"), "w", encoding="utf-8") as f:
        json.dump(unit_rows, f)

    # 4. sealed upstream tests, on the tree that has them, with the time the measurement has left
    t0 = time.monotonic()
    subprocess.run(["chmod", "-R", "a+rX,go-w", cand], check=False)
    sealed_result = run_sealed_tests(
        sealed_ids, prefix, metrics["notes"], scratch=scratch, pub=pub, cand=cand, art=art, cfg=cfg, cpus=cpus,
        deadline=deadline)
    outcome, tw_ok, timed_out = sealed_result.outcome, sealed_result.selfcheck_ok, sealed_result.timed_out
    metrics["pytest_runs"] = sealed_result.runs
    metrics["pytest_passes"] = sealed_result.passes
    metrics["pytest_first_test_sec"] = sealed_result.first_test_sec
    if not tw_ok:
        metrics["tamper"].append("test-runner self-check")
    t_pass = sum(1 for t in sealed_ids if outcome.get(t) == "passed") if tw_ok else 0
    metrics["tests_passed_runner_tally"] = sealed_result.runner_passed
    if sealed_result.tally_exceeded:
        # a run has more passes on record than pytest counted in that run
        metrics["tamper"].append("test records exceed the runner's tally")
        t_pass = 0
    metrics["tests_reported"] = sum(1 for t in sealed_ids if t in outcome)
    metrics["tests_not_reached"] = T - metrics["tests_reported"]
    metrics["pytest_seconds"] = round(time.monotonic() - t0, 1)
    metrics["pytest_timed_out"] = timed_out
    log(f"sealed tests: {t_pass}/{T} pass in {metrics['pytest_seconds']}s; self-check ok={tw_ok}")
    with open(os.path.join(art, "sealed_test_failures.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(t for t in sealed_ids if outcome.get(t) != "passed")[:20000], f)
    metrics["tests_passing"] = t_pass
    return finish(True)
