"""Verifier-side driver for the docstring examples (one sandboxed process per module)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor


class RunnerUnavailable(Exception):
    """The runner could not be started at all."""


def signed_text(line, key):
    """The JSON text of a runner's line when its tag is the HMAC-SHA256 of that text with `key`
    (the run's key, which only the runner was given); None for any other line."""
    tag, _, text = line.rstrip("\n").partition(" ")
    if len(tag) != 64 or not text:
        return None
    try:
        expected = hmac.new(key.encode("ascii"), text.encode("utf-8", "surrogatepass"), hashlib.sha256).hexdigest()
    except (UnicodeError, ValueError):
        return None
    return text if hmac.compare_digest(tag, expected) else None


def read_runner_records(path, key, limit=200_000_000):
    """The records of one run: units by name, the self-check, a module error, and whether a unit
    was reported twice. Lines not signed with the run's key, malformed lines and records of the
    wrong shape are skipped."""
    got, trip, merr, dup = {}, None, None, False
    try:
        if os.path.getsize(path) > limit:
            return got, trip, merr, dup
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if len(line) > 500_000:
                    continue
                text = signed_text(line, key)
                if text is None:
                    continue
                try:
                    rec = json.loads(text)
                except (ValueError, RecursionError):
                    continue
                if not isinstance(rec, dict):
                    continue
                if isinstance(rec.get("name"), str) and isinstance(rec.get("status"), str):
                    if rec["name"] in got:
                        dup = True
                    got.setdefault(rec["name"], rec)
                elif "tripwire" in rec:
                    trip = rec["tripwire"] is True if trip is None else (trip and rec["tripwire"] is True)
                elif "module_error" in rec:
                    merr = rec
    except OSError:
        pass
    return got, trip, merr, dup


def run_doctests(cand_root, names_by_module, rdoctest_path, *, watch, deadline, workers=4, timeout=20.0,
                 prefix_cmd=None, scratch="/tmp", env=None, load_sec=120.0, stall_margin_sec=30.0, restart_limit=8,
                 stats=None):
    """Run the docstring examples of the restored units, one module per sandboxed process.

    Each run is watched: it gets `load_sec` to import the module (the runner says when it has),
    then may stay silent for at most one unit's `timeout` plus `stall_margin_sec`. A unit's
    record counts only when its run reached its own closing self-check. When a run ends, or
    stops, without it, the first unit of that run without a record fails ("crash", or
    "timeout" when it stopped) and the module starts again without that unit, at most
    `restart_limit` times; a runner that checks itself and exits after a unit that ran out of
    time is simply started again behind it. A module whose import does not finish fails as a
    whole, as one whose import raises does, and so do the units left after its restarts run
    out. Units left when `deadline` (a time.monotonic() value) passes are not reached. `stats`, a
    dict, gets the phase's counts: starts, units that ran out of time, runs that ended or stopped.

    Returns:
        ({dotted: record}, [modules whose runner failed its self-check], number of units not
        reached). Every unit of `names_by_module` has a record.

    Raises:
        RunnerUnavailable: The runner could not be started.
    """
    cand_root = os.path.abspath(cand_root)
    results, bad = {}, []
    lock = threading.Lock()
    counts = {"starts": 0, "timeouts": 0, "ended_or_stopped": 0}

    def count(name):
        with lock:
            counts[name] += 1

    def one(item):
        k, (mod, names) = item
        out = {}
        pending, crashes, starts = list(names), 0, 0
        note = "time budget for docstring examples used up"
        while pending:
            left = deadline - time.monotonic()
            if left <= 5:
                break
            key = secrets.token_hex(16)
            npath = os.path.join(scratch, f"n{k}.{starts}.json")
            opath = os.path.join(scratch, f"o{k}.{starts}.jsonl")
            starts += 1
            count("starts")
            with open(npath, "w", encoding="utf-8") as f:
                json.dump(pending, f)
            open(opath, "w").close()
            os.chmod(opath, 0o666)
            os.chmod(npath, 0o644)
            cmd = list(prefix_cmd or []) + [sys.executable, "-P", "-s", "-B", rdoctest_path, cand_root, mod, npath, opath, str(timeout)]
            try:
                state, first, code = watch(cmd, cwd=cand_root, env=env, log_path=os.devnull, res_path=opath,
                                           deadline=deadline, collect_sec=load_sec, stall_sec=timeout + stall_margin_sec,
                                           marker=None, stdin_data=(key + "\n").encode("ascii"))
            except OSError as exc:
                raise RunnerUnavailable(f"could not start the docstring runner: {exc}") from exc
            got, trip, merr, dup = read_runner_records(opath, key)
            if trip is False or dup:
                # the runner could no longer tell a right example from a wrong one, or a unit was
                # reported more than once: nothing of this module counts
                return mod, {n: {"name": n, "status": "error", "exc": "runner self-check failed"} for n in names}, True, 0
            if merr is not None or (first is None and state != "budget"):
                # the module could not be imported, or its import never finished
                why = ("module import failed: " + str(merr.get("module_error"))[:600] if merr is not None
                       else "module import did not finish")
                for n in pending:
                    out[n] = {"name": n, "status": "error", "exc": why}
                pending = []
                break
            if state == "budget" and trip is not True:
                break
            progressed = any(n in got for n in pending)
            if trip is True:
                out.update({n: rec for n, rec in got.items() if n in pending})
                pending = [n for n in pending if n not in got]
                if not pending or state == "budget":
                    break
                if code == 3 and progressed:
                    count("timeouts")
                    continue   # a unit ran out of time; the rest run in a fresh process
            culprit = next((n for n in pending if n not in got), None)
            if culprit is None:
                # every unit reported, yet the run ended before its closing self-check: nothing of
                # it counts, and running it again would end the same way
                for n in pending:
                    out[n] = {"name": n, "status": "crash", "exc": "runner ended before its closing self-check"}
                pending = []
                break
            # ended or stopped without its self-check (or checked itself with units left over):
            # the first unit without a record fails, and the rest of the module runs again
            count("ended_or_stopped")
            out[culprit] = {"name": culprit, "status": "timeout" if state == "stalled" else "crash",
                            "exc": "runner stopped during this unit" if state == "stalled" else "runner ended during this unit"}
            pending = [n for n in pending if n != culprit]
            crashes += 1
            if crashes > restart_limit:
                # the module's own bodies keep ending its runner: what is left fails, as the rest
                # of a module that cannot be imported does
                for n in pending:
                    out[n] = {"name": n, "status": "crash", "exc": "runner restarted too often"}
                pending = []
                break
        missing = 0
        for n in names:
            if n not in out:
                out[n] = {"name": n, "status": "crash", "exc": note, "not_reached": True}
                missing += 1
        return mod, out, False, missing

    items = list(enumerate(sorted(names_by_module.items())))
    not_reached = 0
    with ThreadPoolExecutor(max(1, workers)) as ex:
        for mod, out, tampered, missing in ex.map(one, items):
            if tampered:
                bad.append(mod)
            results.update(out)
            not_reached += missing
    if stats is not None:
        stats.update(counts)
    return results, bad, not_reached
