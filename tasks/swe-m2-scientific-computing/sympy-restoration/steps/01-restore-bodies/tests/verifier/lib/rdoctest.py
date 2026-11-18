"""Run the docstring examples of selected functions of ONE module of a candidate tree.

usage: rdoctest.py <cand_root> <module> <names.json> <out_path> <nonce> [timeout_sec]

Appends one line per unit to <out_path>:  <nonce> <json>
The examples run the way SymPy's own doctest runner runs them: empty globals,
plain-text printing, ELLIPSIS | NORMALIZE_WHITESPACE | IGNORE_EXCEPTION_DETAIL.
"""
from __future__ import annotations

import io
import json
import os
import re
import signal
import sys
import time

cand_root, module_name, names_path, out_path, nonce = sys.argv[1:6]
timeout = float(sys.argv[6]) if len(sys.argv) > 6 else 20.0
out_f = open(out_path, "a", encoding="utf-8")
names = json.load(open(names_path, encoding="utf-8"))


def emit(rec):
    out_f.write(nonce + " " + json.dumps(rec) + "\n")
    out_f.flush()


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


def run_one(test):
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

# tripwires: the runner must still be able to tell right from wrong
parser = pdoctest.DocTestParser()
bad = parser.get_doctest(">>> 1 + 1\n3\n", {}, "tripwire_bad", None, 0)
good = parser.get_doctest(">>> 1 + 1\n2\n", {}, "tripwire_good", None, 0)
rb, rg = run_one(bad), run_one(good)
emit({"tripwire": bool(rb["status"] == "fail" and rg["status"] == "pass")})
