"""Verifier-side drivers of the sandboxed runners: one process per module, spoken to over pipes."""
from __future__ import annotations

import json
import os
import pickle
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

LINE_LIMIT = 4 << 20       # bytes of one line a runner writes, at most
TOTAL_LIMIT = 256 << 20    # bytes one start of a runner writes, at most
GRACE_SEC = 0.5            # a runner's own work around an item, beyond the item's bound
STATUSES = ("pass", "fail", "error", "timeout", "notfound")
UNIT_ID = re.compile(r"U\d{4}")


class RunnerUnavailable(Exception):
    """The runner could not be started at all."""


class Child:
    """A sandboxed runner the verifier speaks to over pipes. Its job is written to its standard input,
    which is then closed; it answers with one JSON object per line on its standard output, read here in
    pieces of at most 64 KiB, never more than LINE_LIMIT bytes for one line or TOTAL_LIMIT in all.
    Nothing it writes is trusted: whatever is not the next expected message ends it."""

    def __init__(self, cmd, *, cwd, env, job: bytes, line_limit: int = LINE_LIMIT, total_limit: int = TOTAL_LIMIT):
        self.proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
        self.line_limit, self.total_limit = line_limit, total_limit
        self.buffer = bytearray()
        self.total = 0
        self.fd = self.proc.stdout.fileno()
        os.set_blocking(self.fd, False)
        # fed from a thread of its own: a runner reads its job whole before anything else, and one that
        # never does is ended when its first answer does not come in time
        threading.Thread(target=self._feed, args=(job,), daemon=True).start()

    def _feed(self, job: bytes) -> None:
        try:
            self.proc.stdin.write(job)
            self.proc.stdin.close()
        except (OSError, ValueError):
            pass

    def message(self, deadline: float) -> tuple[str, dict | None]:
        """The runner's next line: ("message", object), or ("timeout", None) when none came by `deadline`
        (a time.monotonic() value), ("ended", None) when it closed its output, ("bad", None) for a line
        too long, not JSON or not an object, or past the total limit."""
        while True:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self.buffer[:newline])
                del self.buffer[:newline + 1]
                if len(line) > self.line_limit:
                    return "bad", None
                try:
                    found = json.loads(line)
                except (ValueError, RecursionError, MemoryError, UnicodeDecodeError):
                    return "bad", None
                return ("message", found) if isinstance(found, dict) else ("bad", None)
            if len(self.buffer) > self.line_limit:
                return "bad", None
            left = deadline - time.monotonic()
            if left <= 0:
                return "timeout", None
            try:
                ready, _, _ = select.select([self.fd], [], [], min(left, 1.0))
            except (OSError, ValueError):
                return "ended", None
            if not ready:
                continue
            try:
                chunk = os.read(self.fd, 1 << 16)
            except BlockingIOError:
                continue
            except OSError:
                return "ended", None
            if not chunk:
                return "ended", None
            self.total += len(chunk)
            if self.total > self.total_limit:
                return "bad", None
            self.buffer += chunk

    def stop(self) -> None:
        """End the runner and everything it started in its session."""
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        try:
            self.proc.kill()
        except OSError:
            pass
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            pass
        try:
            self.proc.stdout.close()
        except OSError:
            pass


class PrivateTmp:
    """A fresh folder for one start of a runner, owned by the sandbox user, removed afterwards; the
    runner gets it as TMPDIR and HOME. When no folder can be made (a full disk), none is given."""

    def __init__(self, root: str | None, owner: tuple[int, int] | None, cleanup=None):
        self.path = None
        if root is None:
            return
        for attempt in range(2):
            try:
                self.path = tempfile.mkdtemp(dir=root)
                if owner is not None:
                    os.chown(self.path, *owner)
                os.chmod(self.path, 0o700)
                return
            except OSError:
                self.path = None
                if attempt == 0 and cleanup is not None:
                    cleanup()

    def env(self, base: dict | None) -> dict:
        env = dict(base or {})
        folder = self.path or "/nonexistent"
        env.update(TMPDIR=folder, TMP=folder, TEMP=folder, HOME=folder)
        return env

    def close(self) -> None:
        if self.path:
            shutil.rmtree(self.path, ignore_errors=True)


def example_record(name: str, found: dict) -> tuple[dict, bool] | None:
    """A unit's record rebuilt from a runner's message, with the self-check that followed it; None
    when the message is not one, for this unit, of the runner's own form. Nothing else is taken."""
    if found.get("name") != name or found.get("status") not in STATUSES or not isinstance(found.get("trip"), bool):
        return None
    record = {"name": name, "status": found["status"]}
    for key in ("failed", "tried"):
        value = found.get(key)
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 10**7:
            return None
        record[key] = value
    seconds = found.get("sec")
    if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and 0 <= seconds < 10**7:
        record["sec"] = float(seconds)
    for key, limit in (("exc", 300), ("out", 2500)):
        if isinstance(found.get(key), str):
            record[key] = found[key][:limit]
    blocked = found.get("blocked_by")
    if isinstance(blocked, list):
        record["blocked_by"] = [b for b in blocked[:50] if isinstance(b, str) and UNIT_ID.fullmatch(b)]
    return record, found["trip"]


def run_doctests(cand_root, names_by_module, rdoctest_path, *, deadline, bound, load_bound, workers=4, prefix_cmd=None,
                 env=None, tmp_root=None, tmp_owner=None, cleanup=None, stats=None):
    """Run the docstring examples of the restored units, one module at a time per sandboxed process.

    The runner gets its module's units on standard input and answers over standard output (Child): it
    must import the module within `load_bound(module)` seconds, then report each unit's start and record,
    in order, each within `bound(name)` seconds (plus GRACE_SEC) of the one before. A unit that takes
    longer, or during which the runner ends or writes anything else, fails ("timeout" or "crash"), and
    the module's other units run in a new runner. A module whose import fails or does not finish fails
    as a whole. A record whose self-check failed (the runner could no longer tell a right example from a
    wrong one) fails every unit of its module, and the module is named. Units left when `deadline` (a
    time.monotonic() value) passes are not reached. `stats`, a dict, gets the phase's counts.

    Returns:
        ({dotted: record}, [modules whose runner failed its self-check], {dotted names not reached}).

    Raises:
        RunnerUnavailable: The runner could not be started.
    """
    cand_root = os.path.abspath(cand_root)
    results, bad, unreached = {}, [], set()
    lock = threading.Lock()
    counts = {"starts": 0, "timeouts": 0, "ended_or_stopped": 0, "malformed": 0, "over_half_bound": 0}
    near = set()   # units whose examples took more than half their time, as this process measured it

    def count(name):
        with lock:
            counts[name] += 1

    def one(item):
        mod, names = item
        out: dict = {}
        pending = list(names)
        while pending:
            if deadline - time.monotonic() <= 5:
                break
            count("starts")
            tmp = PrivateTmp(tmp_root, tmp_owner, cleanup)
            job = json.dumps({"names": pending}).encode()
            cmd = list(prefix_cmd or []) + [sys.executable, "-P", "-s", "-B", rdoctest_path, cand_root, mod]
            try:
                child = Child(cmd, cwd=cand_root, env=tmp.env(env), job=job, line_limit=1 << 20, total_limit=64 << 20)
            except OSError as exc:
                tmp.close()
                raise RunnerUnavailable(f"could not start the docstring runner: {exc}") from exc
            try:
                kind, found = child.message(min(deadline, time.monotonic() + load_bound(mod)))
                if kind == "message" and isinstance(found.get("module_error"), str):
                    why = "module import failed: " + found["module_error"][:600]
                    for n in pending:
                        out[n] = {"name": n, "status": "error", "exc": why}
                    pending = []
                    break
                if not (kind == "message" and found.get("loaded") is True):
                    if time.monotonic() >= deadline:
                        break   # the phase's time ran out: the units left are not reached
                    for n in pending:
                        out[n] = {"name": n, "status": "error", "exc": "module import did not finish"}
                    pending = []
                    break
                while pending:
                    name = pending[0]
                    until = min(deadline, time.monotonic() + bound(name) + GRACE_SEC)
                    kind, found = child.message(until)
                    started = kind == "message" and found.get("start") == name
                    began = time.monotonic()
                    if started:
                        kind, found = child.message(until)
                    rebuilt = example_record(name, found) if started and kind == "message" else None
                    if rebuilt is not None and time.monotonic() - began > bound(name) / 2:
                        count("over_half_bound")
                        with lock:
                            near.add(name)
                    if rebuilt is not None:
                        record, trip = rebuilt
                        if not trip:
                            # the runner could no longer tell a right example from a wrong one: nothing of
                            # this module counts
                            with lock:
                                bad.append(mod)
                            return mod, {n: {"name": n, "status": "error", "exc": "runner self-check failed"} for n in names}
                        out[name] = record
                        pending.pop(0)
                        continue
                    if kind == "timeout" and time.monotonic() >= deadline:
                        return mod, out   # the phase's time ran out during this unit: it and the rest are not reached
                    if kind == "timeout":
                        count("timeouts")
                        out[name] = {"name": name, "status": "timeout", "exc": "the unit's examples took longer than allowed"}
                    elif kind == "message":
                        count("malformed")
                        out[name] = {"name": name, "status": "error", "exc": "the runner wrote something other than this unit's record"}
                    else:
                        count("ended_or_stopped")
                        out[name] = {"name": name, "status": "crash",
                                     "exc": "the runner wrote too much" if kind == "bad" else "the runner ended during this unit"}
                    pending.pop(0)
                    break   # the module's other units run in a new runner
            finally:
                child.stop()
                tmp.close()
        return mod, out

    items = sorted(names_by_module.items())
    with ThreadPoolExecutor(max(1, workers)) as ex:
        for mod, out in ex.map(one, items):
            results.update(out)
    for mod, names in items:
        for n in names:
            if n not in results:
                unreached.add(n)
                results[n] = {"name": n, "status": "crash", "exc": "time budget for docstring examples used up"}
    if stats is not None:
        stats.update(counts)
        stats["over_half_bound_units"] = sorted(near)[:100]
    return results, bad, unreached


def job_bytes(units: dict, vectors: list) -> bytes:
    """A call runner's job: the units its calls belong to and the calls, as one pickle."""
    return pickle.dumps({"units": units, "vectors": vectors}, protocol=4)
