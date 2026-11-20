"""Measure a submitted SymPy tree. Decides nothing: checks and scoring read the result.

Inputs
  context.work_tree/sympy   the submitted tree (the declared artifact)
  context.skeleton          reference skeleton with the full upstream test suite
  context.private           unit list, sealed test list, recorded calls, reference results
Outputs
  context.output/artifacts  per-unit results, failing test ids, the graded unit files

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
import os
import pickle
import re
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
import gradelib  # noqa: E402
import restorelib  # noqa: E402
from canon import same  # noqa: E402

from verifier.contracts import EvaluationError, Measurement, VerificationContext  # noqa: E402

RUN_AS = "nobody"
SANDBOX_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8",
}


def log(*parts: object) -> None:
    """Print one progress line to the verifier log."""
    print("[grade]", *parts, flush=True)


def sandbox_prefix(run_group: str) -> list[str]:
    """Return the command prefix that drops to the unprivileged user.

    Args:
        run_group: Group the sandbox user runs with.

    Returns:
        The `setpriv` prefix every sandboxed command starts with.

    Raises:
        EvaluationError: The verifier is not root or cannot drop privileges, so
            submitted code must not be run and no reward is valid.
    """
    if os.geteuid() != 0:
        raise EvaluationError("Verifier must start as root to isolate submitted code")
    prefix = ["setpriv", "--reuid", RUN_AS, "--regid", run_group, "--clear-groups"]
    usable = shutil.which("setpriv") is not None
    if usable:
        try:
            usable = subprocess.run(prefix + ["true"], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=30).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            usable = False
    if not usable:
        raise EvaluationError("Could not drop privileges; submitted code was not run")
    return prefix


def reap(prefix: list[str]) -> None:
    """Kill whatever the sandbox user left running."""
    if not prefix or not shutil.which("pkill"):
        return
    for _ in range(25):
        subprocess.run(["pkill", "-9", "-u", RUN_AS], check=False)
        if not shutil.which("pgrep") or subprocess.run(["pgrep", "-u", RUN_AS], stdout=subprocess.DEVNULL).returncode != 0:
            return
        time.sleep(0.2)


def read_vector_records(path: str, want: set) -> tuple[dict, set]:
    """Read the results a replay job has written so far.

    Args:
        path: File the sandboxed runner appends one JSON line per call to.
        want: Ids of the calls of this job.

    Returns:
        The canonical result per call id, and the ids reported more than once.
    """
    got: dict = {}
    dup: set = set()
    try:
        if os.path.getsize(path) <= 200_000_000:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if len(line) > 500_000:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    vid = rec.get("v") if isinstance(rec, dict) else None
                    if vid in want:
                        if vid in got:
                            dup.add(vid)
                        got[vid] = rec.get("c")
    except OSError:
        pass
    return got, dup


def run_vectors(payload, restored_uids, prefix, *, scratch, pub, cand_nt, cfg, cpus):
    """Replay recorded calls in the sandbox, one process per module.

    The runner works through a module's calls in order and writes each result
    as it goes. A call can end the process (a crash in the interpreter) or keep
    it busy past its own time limit. The calls queued behind it say nothing
    about the submission, so the job is started again without that call, which
    counts as not matching. A job is given up when two starts in a row produce
    nothing, after `vector_job_restart_limit` restarts, or when the phase's
    time budget ends.

    Args:
        payload: Per module, its units and their recorded calls.
        restored_uids: Units the submission restored.
        prefix: Command prefix that drops to the sandbox user.
        scratch: Private working directory of the verifier.
        pub: Directory readable by the sandbox user that holds the runner.
        cand_nt: Tree without test directories that the calls run in.
        cfg: Limits from grade_config.json.
        cpus: Number of modules replayed at the same time.

    Returns:
        The canonical result per call id; None for a call that did not finish
        or was reported twice. Calls that were not reached are absent.
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
    restart_limit = max(0, int(cfg.get("vector_job_restart_limit", 8)))
    rv = os.path.join(pub, "rvector.py")
    deadline = time.time() + float(cfg.get("vector_budget_sec", 1200))

    def one(job):
        k, mod, units, vecs, op = job
        want = {v[0] for v in vecs}
        unfinished: set = set()
        got: dict = {}
        dup: set = set()
        pending = vecs
        barren = 0
        for attempt in range(restart_limit + 1):
            left = deadline - time.time()
            if not pending or left <= 5:
                break
            ip = os.path.join(vdir, f"i{k}.{attempt}.pkl")
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
            try:
                watch(cmd, cwd=cand_nt, env=SANDBOX_ENV, log_path=os.devnull, res_path=op,
                      deadline=time.time() + max(5.0, min(per_vec * len(pending) + 60, left)),
                      collect_sec=load_sec, stall_sec=stall_sec, marker=None)
            except OSError:
                break
            got, dup = read_vector_records(op, want)
            rest = [v for v in pending if v[0] not in got]
            if not rest:
                break
            barren = barren + 1 if len(got) == before else 0
            if barren >= 2 or time.time() >= deadline - 5:
                break
            # the process ended, or stopped, at the first call without a result
            unfinished.add(rest[0][0])
            pending = rest[1:]
        for vid in unfinished | dup:
            got[vid] = None
        return got

    results = {}
    with ThreadPoolExecutor(cpus) as ex:
        for got in ex.map(one, jobs):
            results.update(got)
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
                except ValueError:
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


def watch(cmd, *, cwd, env, log_path, res_path, deadline, collect_sec, stall_sec, marker=START_RECORD):
    """Run one sandboxed process until it ends, stops reporting or its time ends.

    Until its work starts, the process is starting up (pytest is collecting, a
    replay job is importing) and gets `collect_sec` in total. After that,
    `stall_sec` may pass between records.

    Args:
        cmd: Command to start.
        cwd: Directory to start it in.
        env: Its environment.
        log_path: File that receives its output.
        res_path: File its plugin appends records to; growth means progress.
        deadline: Wall-clock time at which the phase's budget ends.
        collect_sec: Seconds allowed before the work starts.
        stall_sec: Seconds allowed between records once it has started.
        marker: Bytes of a record that shows the work has started (for pytest,
            a test start); None lets any record count.

    Returns:
        "done", "stalled" or "budget", and the seconds until the work started.

    Raises:
        OSError: The process could not be started.
    """
    began = last = time.time()
    first = None
    offset = 0
    tail = b""
    with open(log_path, "w", encoding="utf-8") as lf:
        # its own process group, so that ending it also ends the workers it started
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while True:
                try:
                    proc.wait(timeout=1.0)
                    ended = True
                except subprocess.TimeoutExpired:
                    ended = False
                now = time.time()
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
                    return "done", first
                if now >= deadline:
                    return "budget", first
                if (first is None and now - began > collect_sec) or (first is not None and now - last > stall_sec):
                    return "stalled", first
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
        deadline: Wall-clock time at which the phase's budget ends.
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
        state, first = watch(cmd, cwd=cand, env=env, log_path=log_path, res_path=res_path, deadline=deadline,
                             collect_sec=float(collect_sec), stall_sec=float(cfg.get("pytest_stall_sec", 180)))
    except OSError as exc:
        raise EvaluationError("The test runner could not be started in the verifier image") from exc
    with open(log_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    outcome, started, uncollectable = read_records(res_path, want)
    return {"state": state, "text": text, "outcome": outcome, "started": started,
            "uncollectable": uncollectable, "first_test_sec": first}


def run_sealed_tests(sealed_ids, prefix, notes, *, scratch, pub, cand, art, cfg, cpus) -> SealedResult:
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
    Everything happens inside one time budget.

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
    deadline = time.time() + float(cfg.get("pytest_budget_sec", 2400))
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
    while pending and not flags["budget"] and passes < pass_limit and time.time() < deadline - 1:
        passes += 1
        by_file: dict[str, list[str]] = collections.defaultdict(list)
        for nid in pending:
            by_file[nid.split("::")[0]].append(nid)

        def one(job, number=passes):
            k, (path, ids) = job
            if time.time() >= deadline - 1:
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
    timed_out = flags["budget"] or (bool(pending) and time.time() >= deadline - 1)
    if timed_out:
        notes.append("sealed test run hit its time budget; unfinished tests count as failed")
    if session["state"] == "stalled":
        notes.append("the test session stopped reporting and was ended")
    if resumed:
        notes.append(f"{resumed} tests the session did not finish were settled with one process per test file")
    return SealedResult(outcome, flags["selfcheck_ok"], timed_out, sum(tallies) if tallies else None,
                        flags["tally_exceeded"], flags["runs"], passes, session["first_test_sec"])


def measure(context: VerificationContext) -> Measurement:
    """Build the graded tree and run the three measurements once.

    Args:
        context: Trusted paths, limits and thresholds for this evaluation.

    Returns:
        Fixed denominators, passing numerators, self-check trips and the full
        diagnostic record. A missing artifact or a tree with no restored unit
        is a completed measurement with zero numerators.

    Raises:
        EvaluationError: Private inputs are unreadable, privileges cannot be
            dropped, or a runner cannot be started. No reward is valid then.
    """
    t_start = time.time()
    cfg = dict(context.limits)
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
    except (OSError, ValueError, KeyError, pickle.UnpicklingError) as e:
        raise EvaluationError(f"Private verifier inputs are unreadable: {type(e).__name__}") from e
    if not os.path.isdir(skel):
        raise EvaluationError("Reference skeleton is missing from the verifier image")
    U, T, V = len(units), len(sealed_ids), len(gold)
    metrics: dict[str, Any] = {
        "units_total": U, "units_restored": 0, "units_passing": 0,
        "vectors_total": V, "vectors_passing": 0,
        "tests_total": T, "tests_passing": 0,
        "tamper": [], "notes": [],
        "unit_bar": context.scoring.unit_bar, "vector_bar": context.scoring.call_bar,
        "test_bar": context.scoring.test_bar,
    }

    def finish(artifact_present: bool) -> Measurement:
        metrics["grade_seconds"] = round(time.time() - t_start, 1)
        counts = {k: int(metrics[k]) for k in (
            "units_total", "units_restored", "units_passing",
            "vectors_total", "vectors_passing", "tests_total", "tests_passing")}
        return Measurement(artifact_present, counts, tuple(metrics["tamper"]), metrics)

    tree = os.path.join(work_tree, "sympy")
    if not os.path.isdir(tree) or os.path.islink(tree):
        metrics["notes"].append("artifact /app/sympy is missing")
        return finish(False)

    # 1. candidate tree = reference skeleton + restored bodies (nothing else is taken over)
    if os.path.exists(cand):
        shutil.rmtree(cand)
    shutil.copytree(skel, cand, symlinks=False)
    states, _notes = restorelib.build_candidate(skel, work_tree, cand, byfile, None)
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
    prefix = sandbox_prefix(str(cfg.get("run_group", "nogroup")))
    restored = {u["uid"] for u in units if states[u["uid"]] == "restored"}

    # 2. docstring examples of every restored unit
    t0 = time.time()
    dt_scratch = os.path.join(scratch, "dt")
    os.makedirs(dt_scratch, exist_ok=True)
    os.chmod(dt_scratch, 0o755)
    run = collections.defaultdict(list)
    for u in units:
        if u["uid"] in restored:
            run[u["module"]].append(u["dotted"])
    results, tamper, dt_not_reached = gradelib.run_doctests(
        cand_nt, run, os.path.join(pub, "rdoctest.py"), workers=cpus,
        timeout=float(cfg.get("unit_timeout_sec", 20)), prefix_cmd=prefix, scratch=dt_scratch,
        env=SANDBOX_ENV, budget_sec=float(cfg.get("doctest_budget_sec", 1800)))
    reap(prefix)
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
    metrics["doctest_seconds"] = round(time.time() - t0, 1)
    metrics["units_not_reached"] = dt_not_reached
    log(f"unit examples: {n_examples}/{U} pass in {metrics['doctest_seconds']}s; self-check failures={tamper[:3]}")

    # 3. recorded calls, replayed in the sandbox and compared here with the reference results
    t0 = time.time()
    uid_of = {v[0]: v[1] for p in payload.values() for v in p["vectors"]}
    vres = run_vectors(payload, restored, prefix, scratch=scratch, pub=pub, cand_nt=cand_nt, cfg=cfg, cpus=cpus)
    reap(prefix)
    v_pass, vrows = 0, {}
    for vid, g in gold.items():
        c = vres.get(vid)
        ok = c is not None and same(c, g)
        v_pass += ok
        vrows[vid] = ok
    metrics["vectors_passing"] = v_pass
    metrics["vectors_not_reached"] = sum(1 for vid in gold if uid_of.get(vid) in restored and vid not in vres)
    metrics["vector_seconds"] = round(time.time() - t0, 1)
    log(f"reference comparison: {v_pass}/{V} recorded calls match in {metrics['vector_seconds']}s")
    per_unit = collections.defaultdict(lambda: [0, 0])
    for vid, ok in vrows.items():
        per_unit[uid_of.get(vid, "?")][0 if ok else 1] += 1
    # a unit passes when its examples pass and at least one of its recorded calls matches
    # the reference: the examples alone are reported by the sandbox
    n_pass = 0
    for row in unit_rows:
        a, b = per_unit.get(row["uid"], (0, 0))
        row["calls_matching"], row["calls_total"] = a, a + b
        row["pass"] = bool(row["examples_pass"] and a >= 1)
        n_pass += row["pass"]
    metrics["units_passing"] = n_pass
    # units whose examples are reported as passing while most of their calls do not match
    metrics["units_examples_without_calls"] = sum(
        1 for row in unit_rows if row["examples_pass"] and 2 * row["calls_matching"] < row["calls_total"])
    with open(os.path.join(art, "unit_results.json"), "w", encoding="utf-8") as f:
        json.dump(unit_rows, f)

    # 4. sealed upstream tests, on the tree that has them
    t0 = time.time()
    subprocess.run(["chmod", "-R", "a+rX,go-w", cand], check=False)
    sealed_result = run_sealed_tests(
        sealed_ids, prefix, metrics["notes"], scratch=scratch, pub=pub, cand=cand, art=art, cfg=cfg, cpus=cpus)
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
    metrics["pytest_seconds"] = round(time.time() - t0, 1)
    metrics["pytest_timed_out"] = timed_out
    log(f"sealed tests: {t_pass}/{T} pass in {metrics['pytest_seconds']}s; self-check ok={tw_ok}")
    with open(os.path.join(art, "sealed_test_failures.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(t for t in sealed_ids if outcome.get(t) != "passed")[:20000], f)
    metrics["tests_passing"] = t_pass
    return finish(True)
