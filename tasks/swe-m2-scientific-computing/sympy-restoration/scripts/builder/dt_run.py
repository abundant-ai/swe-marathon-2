"""Run the docstring examples of selected functions of ONE module, sympy-style.

usage: dt_run.py <tree_root> <module> [--names names.json] [--trace candidates.json]
                 [--timeout SEC] [--import-trace]
Prints one JSON object per line: {"name":..., "status":..., ...}
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import signal
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("module")
ap.add_argument("--names")
ap.add_argument("--trace")
ap.add_argument("--timeout", type=float, default=20.0)
ap.add_argument("--import-trace", action="store_true")
args = ap.parse_args()

root = os.path.realpath(args.root)
sys.path.insert(0, root)
os.chdir(root)

code_map = {}
called = set()
TOOL = 3
if args.trace:
    cands = json.load(open(args.trace))
    for i, u in enumerate(cands):
        fn = os.path.join(root, u["file"])
        code_map[(fn, u["def_line"])] = i
        code_map[(fn, u["deco_line"])] = i
    mon = sys.monitoring
    mon.use_tool_id(TOOL, "units")

    def on_start(code, off):
        k = (code.co_filename, code.co_firstlineno)
        i = code_map.get(k)
        if i is not None and code.co_name == cands[i]["name"]:
            called.add(i)
        return mon.DISABLE

    mon.register_callback(TOOL, mon.events.PY_START, on_start)
    mon.set_events(TOOL, mon.events.PY_START)

import importlib  # noqa: E402

if args.import_trace:
    import sympy  # noqa: F401

    mods = sorted({u["module"] for u in cands})
    bad = []
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as e:  # noqa: BLE001
            bad.append((m, repr(e)[:200]))
    print(json.dumps({"import_called": sorted(called), "import_errors": bad}))
    sys.exit(0)

import doctest as pdoctest  # noqa: E402

from sympy.core.cache import clear_cache  # noqa: E402
from sympy.testing.runtests import (  # noqa: E402
    SymPyDocTestFinder,
    SymPyDocTestRunner,
    SymPyOutputChecker,
    setup_pprint,
)

try:
    module = importlib.import_module(args.module)
except BaseException as e:  # noqa: BLE001
    print(json.dumps({"module_error": f"{type(e).__name__}: {e}"[:2000]}))
    sys.exit(0)

want = None
if args.names:
    want = set(json.load(open(args.names)))

tests = SymPyDocTestFinder().find(module)
tests = [t for t in tests if t.examples]
tests.sort(key=lambda t: (t.lineno or 0, t.name))


class _Timeout(BaseException):
    pass


def _alarm(signum, frame):
    raise _Timeout()


signal.signal(signal.SIGALRM, _alarm)
RESTORE_RE = re.compile(r"NotImplementedError: RESTORE (U\d+)")

import sympy.interactive.printing as interactive_printing  # noqa: E402
from sympy.printing.pretty import stringpict  # noqa: E402
from sympy.printing.pretty.pretty import pprint_use_unicode  # noqa: E402

for test in tests:
    if want is not None and test.name not in want:
        continue
    rec = {"name": test.name, "lineno": test.lineno, "n": len(test.examples)}
    dep = test.globs.get("_doctest_depends_on") or {}
    if dep:
        rec["status"] = "skip"
        rec["why"] = "depends:" + ",".join(sorted(dep))
        print(json.dumps(rec), flush=True)
        continue
    n_real = sum(1 for ex in test.examples if not ex.options.get(pdoctest.SKIP))
    rec["n_real"] = n_real
    runner = SymPyDocTestRunner(
        verbose=False,
        optionflags=pdoctest.ELLIPSIS | pdoctest.NORMALIZE_WHITESPACE | pdoctest.IGNORE_EXCEPTION_DETAIL,
    )
    runner._checker = SymPyOutputChecker()
    test.globs = {}
    buf = io.StringIO()
    old_stdout = sys.stdout
    old_hook = sys.displayhook
    clear_cache()
    uu, wl = setup_pprint()
    if args.trace:
        called.clear()
        sys.monitoring.restart_events()
    t0 = time.time()
    status = "pass"
    try:
        signal.setitimer(signal.ITIMER_REAL, args.timeout)
        sys.stdout = buf
        f, t = runner.run(test, out=buf.write, clear_globs=True)
        signal.setitimer(signal.ITIMER_REAL, 0)
        rec["failed"], rec["tried"] = f, t
        if f:
            status = "fail"
    except _Timeout:
        status = "timeout"
    except BaseException as e:  # noqa: BLE001
        status = "error"
        rec["exc"] = f"{type(e).__name__}: {e}"[:500]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        sys.stdout = old_stdout
        sys.displayhook = old_hook
        interactive_printing.NO_GLOBAL = False
        pprint_use_unicode(uu)
        stringpict._GLOBAL_WRAP_LINE = wl
    rec["sec"] = round(time.time() - t0, 3)
    out = buf.getvalue()
    if status != "pass":
        blocked = sorted(set(RESTORE_RE.findall(out)))
        if blocked:
            rec["blocked_by"] = blocked
        rec["out"] = out[:3000]
    rec["status"] = status
    if args.trace:
        rec["called"] = sorted(called)
    print(json.dumps(rec), flush=True)
