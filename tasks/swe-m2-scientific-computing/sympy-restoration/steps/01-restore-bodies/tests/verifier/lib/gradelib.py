"""Verifier-side driver for the docstring examples (one sandboxed process per module)."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor


def run_doctests(cand_root, names_by_module, rdoctest_path, workers=4, timeout=20.0, prefix_cmd=None,
                 scratch="/tmp", env=None, budget_sec=1800.0):
    """Returns ({dotted: record}, [modules whose runner failed its self-check], n_not_reached).

    A runner stopped by a time limit keeps what it reported and fails the rest.  A runner
    that ends on its own without its closing self-check, or reports a unit twice, fails
    every unit of its module.
    """
    cand_root = os.path.abspath(cand_root)
    deadline = time.time() + budget_sec
    results, bad = {}, []

    def one(item):
        k, (mod, names) = item
        left = deadline - time.time()
        if left <= 5:
            return mod, names, {}, None, None, "time budget for docstring examples used up"
        nonce = secrets.token_hex(12)
        npath = os.path.join(scratch, f"n{k}.json")
        opath = os.path.join(scratch, f"o{k}.jsonl")
        with open(npath, "w", encoding="utf-8") as f:
            json.dump(names, f)
        open(opath, "w").close()
        os.chmod(opath, 0o666)
        os.chmod(npath, 0o644)
        cmd = list(prefix_cmd or []) + [sys.executable, "-P", "-s", "-B", rdoctest_path, cand_root, mod, npath,
                                         opath, nonce, str(timeout)]
        err, cut = "", False
        try:
            p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env, cwd=cand_root,
                               timeout=max(5.0, min(timeout * (len(names) + 2) + 60, left)))
            err = (p.stderr or b"").decode("utf-8", "replace")[-300:]
        except subprocess.TimeoutExpired:
            err, cut = "module run exceeded its time budget", True
        except OSError as e:
            err = f"could not start runner: {e}"
        got, trip, merr, dup = {}, None, None, False
        try:
            with open(opath, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if not line.startswith(nonce + " "):
                        continue
                    try:
                        rec = json.loads(line[len(nonce) + 1:])
                    except ValueError:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    if "name" in rec:
                        if rec["name"] in got:
                            dup = True
                        got.setdefault(rec["name"], rec)
                    elif "tripwire" in rec:
                        trip = rec["tripwire"]
                    elif "module_error" in rec:
                        merr = rec
        except OSError:
            pass
        return mod, names, got, trip, merr, err, cut, dup

    items = list(enumerate(sorted(names_by_module.items())))
    not_reached = 0
    with ThreadPoolExecutor(max(1, workers)) as ex:
        for mod, names, got, trip, merr, err, cut, dup in ex.map(one, items):
            if merr is not None:
                for n in names:
                    results[n] = {"name": n, "status": "error", "exc": "module import failed: " + str(merr.get("module_error"))}
                continue
            if trip is False or dup:
                # the runner could no longer tell a right example from a wrong one, or a
                # unit was reported more than once
                bad.append(mod)
                for n in names:
                    results[n] = {"name": n, "status": "error", "exc": "runner self-check failed"}
                continue
            if trip is None and not cut and got:
                # ended by itself without the closing self-check: nothing it said counts
                for n in names:
                    results[n] = {"name": n, "status": "crash", "exc": "runner ended without its closing self-check"}
                continue
            for n in names:
                if n not in got:
                    not_reached += 1
                results[n] = got.get(n) or {"name": n, "status": "crash", "exc": err or "runner stopped before this unit"}
    return results, bad, not_reached
