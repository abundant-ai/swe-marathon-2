"""Run the docstring examples of selected functions of ONE module of a candidate tree.

usage: rdoctest.py <cand_root> <module>

The units arrive on standard input as one JSON object, {"names": [...]}, read whole before anything of
the tree is imported. The answers go to standard output, one JSON object per line: {"loaded": true,
"load_sec": s} once the module is imported (or {"module_error": why}), then for every unit {"start":
name} before its examples and its record after them ({"name", "status", "failed", "tried", "sec", and
"exc", "out", "blocked_by" when it did not pass}, with "trip": whether the runner could still tell a
right example from a wrong one right after it), and {"done": true} at the end. What the examples
print goes elsewhere. The examples run the way SymPy's own doctest runner runs them: empty globals,
plain-text printing, ELLIPSIS | NORMALIZE_WHITESPACE | IGNORE_EXCEPTION_DETAIL. Every unit's random
generators are seeded from its name, so one tree gives the same result each time. This process holds
no key and is trusted with nothing: the process that started it reads each line within its own
limits, expects the lines in this order, and ends it when a unit takes longer than it allows.
"""

from __future__ import annotations

import io
import json
import os
import random
import re
import sys
import time
import zlib

RESTORE_RE = re.compile(r"NotImplementedError: RESTORE (U\d{4})")


def reseed(name):
    """The same random numbers for a unit on every run: Python's and both of SymPy's generators."""
    value = zlib.crc32(name.encode("utf-8"))
    random.seed(value)
    try:
        from sympy.core import random as sympy_random

        sympy_random.rng.seed(value)
        sympy_random._assumptions_rng.seed(value)
    except BaseException:  # noqa: BLE001, S110
        pass


def main():
    began = time.time()
    cand_root, module_name = sys.argv[1:3]
    names = json.loads(sys.stdin.buffer.read())["names"]
    # the answers go to a descriptor of their own; whatever else writes to the standard streams is lost
    channel = os.fdopen(os.dup(1), "wb", buffering=0)
    quiet = os.open(os.devnull, os.O_RDWR)
    for descriptor in (0, 1, 2):
        os.dup2(quiet, descriptor)
    sys.stdin, sys.stdout, sys.stderr = (
        open(os.devnull),  # noqa: SIM115 - The stream stays open for the owning process.
        open(os.devnull, "w"),  # noqa: SIM115 - The stream stays open for the owning process.
        open(os.devnull, "w"),  # noqa: SIM115 - The stream stays open for the owning process.
    )
    dumps = json.dumps

    def send(record):
        channel.write(dumps(record).encode("ascii") + b"\n")

    cand_root = os.path.realpath(cand_root)
    sys.path[:] = [p for p in sys.path if p not in ("", os.getcwd())]
    sys.path.insert(0, cand_root)
    os.chdir(cand_root)

    import doctest as pdoctest
    import importlib

    try:
        import sympy.interactive.printing as interactive_printing
        from sympy.core.cache import clear_cache
        from sympy.printing.pretty import stringpict
        from sympy.printing.pretty.pretty import pprint_use_unicode
        from sympy.testing.runtests import (
            SymPyDocTestFinder,
            SymPyDocTestRunner,
            SymPyOutputChecker,
            setup_pprint,
        )

        module = importlib.import_module(module_name)
        tests = {t.name: t for t in SymPyDocTestFinder().find(module) if t.examples}
    except BaseException as e:  # noqa: BLE001
        send({"module_error": f"{type(e).__name__}: {e}"[:600]})
        channel.close()
        os._exit(0)
    send({"loaded": True, "load_sec": round(time.time() - began, 3)})
    flags = (
        pdoctest.ELLIPSIS
        | pdoctest.NORMALIZE_WHITESPACE
        | pdoctest.IGNORE_EXCEPTION_DETAIL
    )
    parser = pdoctest.DocTestParser()

    def run_one(test):
        reseed(test.name)
        runner = SymPyDocTestRunner(verbose=False, optionflags=flags)
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
            sys.stdout = buf
            f, t = runner.run(test, out=buf.write, clear_globs=True)
            rec["failed"], rec["tried"] = f, t
            if f or not t:
                status = "fail"
        except BaseException as e:  # noqa: BLE001
            status = "error"
            rec["exc"] = f"{type(e).__name__}: {e}"[:300]
        finally:
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
                rec["blocked_by"] = blocked[:50]
            rec["out"] = out[:2500]
        return rec

    def tripwire():
        """Whether the runner still fails a wrong example and passes a right one."""
        bad = parser.get_doctest(">>> 1 + 1\n3\n", {}, "tripwire_bad", None, 0)
        good = parser.get_doctest(">>> 1 + 1\n2\n", {}, "tripwire_good", None, 0)
        try:
            return (
                run_one(bad)["status"] == "fail" and run_one(good)["status"] == "pass"
            )
        except BaseException:  # noqa: BLE001
            return False

    for name in names:
        send({"start": name})
        test = tests.get(name)
        if test is None:
            send({"name": name, "status": "notfound", "trip": True})
            continue
        rec = run_one(test)
        rec["name"] = name
        rec["trip"] = tripwire()
        send(rec)
    send({"done": True})
    channel.close()
    os._exit(0)


if __name__ == "__main__":
    main()
