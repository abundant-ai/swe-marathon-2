"""Run the docstring examples of selected functions of ONE module.

usage: unitcheck.py <tree_root> <module> <names.json> [timeout_sec]

Prints one JSON object per unit. The examples run the way SymPy's own doctest runner
runs them: empty globals, plain-text printing,
ELLIPSIS | NORMALIZE_WHITESPACE | IGNORE_EXCEPTION_DETAIL. Every unit's random
generators are seeded from its name, so a unit gives the same result each time. After a
unit that runs out of time it exits with status 3; the units behind it are run again in
a fresh process.
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import signal
import sys
import time
import zlib

cand_root, module_name, names_path = sys.argv[1:4]
timeout = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0
names = json.load(open(names_path, encoding="utf-8"))
_real_stdout = sys.stdout


def emit(rec):
    _real_stdout.write(json.dumps(rec) + "\n")
    _real_stdout.flush()


cand_root = os.path.realpath(cand_root)
sys.path[:] = [p for p in sys.path if p not in ("", os.getcwd())]
sys.path.insert(0, cand_root)
os.chdir(cand_root)

import doctest as pdoctest  # noqa: E402
import importlib  # noqa: E402

RESTORE_RE = re.compile(r"NotImplementedError: RESTORE (U\d{4})")

try:
    from sympy.core.cache import clear_cache
    from sympy.testing.runtests import (
        SymPyDocTestFinder,
        SymPyDocTestRunner,
        SymPyOutputChecker,
        setup_pprint,
    )
    import sympy.interactive.printing as interactive_printing
    from sympy.printing.pretty import stringpict
    from sympy.printing.pretty.pretty import pprint_use_unicode

    module = importlib.import_module(module_name)
except BaseException as e:  # noqa: BLE001
    import traceback

    tb = traceback.format_exc()
    emit({"module_error": f"{type(e).__name__}: {e}"[:600], "blocked_by": sorted(set(RESTORE_RE.findall(tb))), "tb": tb[-1500:]})
    sys.exit(0)


class _Timeout(KeyboardInterrupt):
    """Raised by the alarm; the doctest runner re-raises KeyboardInterrupt, so a looping
    example ends the whole unit instead of being counted as one failed example."""


def _alarm(signum, frame):
    raise _Timeout()


signal.signal(signal.SIGALRM, _alarm)
FLAGS = pdoctest.ELLIPSIS | pdoctest.NORMALIZE_WHITESPACE | pdoctest.IGNORE_EXCEPTION_DETAIL


def reseed(name):
    """The same random numbers for a unit on every run: Python's and both of SymPy's generators."""
    value = zlib.crc32(name.encode("utf-8"))
    random.seed(value)
    try:
        from sympy.core import random as sympy_random

        sympy_random.rng.seed(value)
        sympy_random._assumptions_rng.seed(value)
    except BaseException:  # noqa: BLE001
        pass


def run_one(test):
    reseed(test.name)
    runner = SymPyDocTestRunner(verbose=False, optionflags=FLAGS)
    runner._checker = SymPyOutputChecker()
    test.globs = {}
    buf = io.StringIO()
    old_stdout, old_hook = sys.stdout, sys.displayhook
    clear_cache()
    uu, wl = setup_pprint()
    t0 = time.time()
    rec = {}
    status = "pass"
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout)
        sys.stdout = buf
        f, t = runner.run(test, out=buf.write, clear_globs=True)
        signal.setitimer(signal.ITIMER_REAL, 0)
        rec["failed"], rec["tried"] = f, t
        if f or not t:
            status = "fail"
    except _Timeout:
        status = "timeout"
    except KeyboardInterrupt:
        status = "error"
        rec["exc"] = "KeyboardInterrupt"
    except BaseException as e:  # noqa: BLE001
        status = "error"
        rec["exc"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        sys.stdout = old_stdout
        sys.displayhook = old_hook
        interactive_printing.NO_GLOBAL = False
        pprint_use_unicode(uu)
        stringpict._GLOBAL_WRAP_LINE = wl
    rec["sec"] = round(time.time() - t0, 3)
    rec["status"] = status
    out = buf.getvalue()
    if status != "pass":
        blocked = sorted(set(RESTORE_RE.findall(out)))
        if blocked:
            rec["blocked_by"] = blocked
            # is the first failing example the one that hit a missing unit?
            parts = [b for b in out.split("*" * 70) if b.strip()]
            rec["first_blocked"] = bool(parts and RESTORE_RE.search(parts[0]))
        rec["out"] = out[:2500]
    return rec


tests = {t.name: t for t in SymPyDocTestFinder().find(module) if t.examples}
for name in names:
    t = tests.get(name)
    if t is None:
        emit({"name": name, "status": "notfound"})
        continue
    rec = run_one(t)
    rec["name"] = name
    emit(rec)
    if rec["status"] == "timeout":
        # an interrupted body can leave global state behind: the units after it get a new process
        _real_stdout.flush()
        os._exit(3)
_real_stdout.flush()
os._exit(0)
