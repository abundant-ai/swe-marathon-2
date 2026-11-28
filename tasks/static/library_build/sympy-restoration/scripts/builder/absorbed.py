"""Which units without a counted call of their own a graded item fails without, on the original tree.

For every unit that has no counted call of its own and runs inside other units' graded items
(`graded_coverage.py`'s `items`), its body is made to raise NotImplementedError on entry, as its
placeholder does (a `sys.monitoring` callback at the start of its code, in this process only), and the
graded items that run it are replayed until one fails: a counted call compared with its reference
result as the verifier compares it (the verifier's own resolution, revival, call and comparison), or
the examples of a unit in the set run with SymPy's doctest runner and the verifier's flags. An item that
fails on the original too, here, is not taken as evidence either way. A unit is graded through others
when some item fails without its body; it is absorbed when every item that reached it still passes
(SymPy catches NotImplementedError where it tries another method). Build time only; prints counts only.

usage: absorbed.py <original_root> <units.json> <vectors_dir> <verifier_lib> <coverage.json> <out.json>
Writes {"graded": {uid: the first item that fails without it}, "absorbed": [uid, ...], "untested": [...],
"summary": {...}}; an item is ["call", vid] or ["examples", uid].
"""

from __future__ import annotations

import contextlib
import doctest as pdoctest
import importlib
import io
import json
import os
import pickle
import signal
import sys
import time
from pathlib import Path

ITEM_SECONDS = 30.0
TOOL = 4


class _Late(BaseException):
    pass


def _late(signum, frame):
    raise _Late()


def main():
    root, units_path, vectors, lib, coverage_path, out_path = sys.argv[1:7]
    root = os.path.realpath(root)
    sys.path[:] = [p for p in sys.path if p not in ("", os.getcwd())]
    sys.path.insert(0, root)
    sys.path.append(lib)
    os.chdir(root)
    import rvector
    from canon import MAX_ITER, Uncanonical, canon, dummies, profile_of, same  # noqa: F401

    units = {
        u["uid"]: u for u in json.loads(Path(units_path).read_text(encoding="utf-8"))
    }
    gold = json.loads(
        Path(os.path.join(vectors, "gold.json")).read_text(encoding="utf-8")
    )
    with open(os.path.join(vectors, "inputs.pkl"), "rb") as f:
        payload = pickle.load(f)
    where = {
        vid: (mod, uid, blob)
        for mod, p in payload.items()
        for vid, uid, blob in p["vectors"]
    }
    facts = {uid: m for p in payload.values() for uid, m in p["units"].items()}
    items = json.loads(Path(coverage_path).read_text(encoding="utf-8"))["items"]
    targets = sorted(uid for uid, it in items.items() if it["calls"] or it["examples"])

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

    modules, functions, tests_of = {}, {}, {}

    def module_of(name):
        if name not in modules:
            try:
                modules[name] = importlib.import_module(name)
            except BaseException:  # noqa: BLE001
                modules[name] = None
        return modules[name]

    def function_of(uid):
        if uid not in functions:
            u = units[uid]
            m = module_of(u["module"])
            meta = facts.get(uid) or {
                "file": u["file"],
                "qualname": u["qualname"],
                "name": u["qualname"].rsplit(".", 1)[-1],
                "occ": u.get("occ", 0),
                "nocc": u.get("nocc", 1),
            }
            try:
                functions[uid] = (
                    rvector.resolve(m, root, meta) if m is not None else None
                )
            except BaseException:  # noqa: BLE001
                functions[uid] = None
        return functions[uid]

    signal.signal(signal.SIGALRM, _late)
    quiet = open(os.devnull, "w")  # noqa: SIM115 - The stream stays open for the owning process.
    flags = (
        pdoctest.ELLIPSIS
        | pdoctest.NORMALIZE_WHITESPACE
        | pdoctest.IGNORE_EXCEPTION_DETAIL
    )

    def call_passes(vid):
        _mod, uid, blob = where[vid]
        fn = function_of(uid)
        if fn is None:
            return None
        rvector.reseed(vid)
        signal.setitimer(signal.ITIMER_REAL, ITEM_SECONDS)
        try:
            with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                clear_cache()
                args = rvector.revive(pickle.loads(blob))
                fixed = dummies(rvector.revive(pickle.loads(blob)))
                res = rvector.call(fn, args)
                if res is None:
                    after, before = (
                        canon(args, fixed),
                        canon(rvector.revive(pickle.loads(blob)), fixed),
                    )
                    c = ["N"] if after == before else ["NS", after]
                else:
                    c = canon(res, fixed)
                    try:
                        after, before = (
                            canon(args, fixed),
                            canon(rvector.revive(pickle.loads(blob)), fixed),
                        )
                    except Uncanonical:
                        after = before = None
                    if after is not None and not same(before, after):
                        c = ["RS", c, after]
        except _Late:
            return False
        except BaseException as e:  # noqa: BLE001
            chain = [
                k.__name__
                for k in type(e).__mro__
                if k.__name__ not in ("Exception", "BaseException", "object")
            ]
            c = ["EXC", type(e).__name__, chain[:12]]
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        u = units[uid]
        try:
            return bool(
                same(c, gold[vid], profile=profile_of(f"{u['file']}::{u['qualname']}"))
            )
        except BaseException:  # noqa: BLE001
            return False

    def examples_pass(uid):
        u = units[uid]
        if u["module"] not in tests_of:
            m = module_of(u["module"])
            try:
                tests_of[u["module"]] = (
                    {t.name: t for t in SymPyDocTestFinder().find(m) if t.examples}
                    if m
                    else {}
                )
            except BaseException:  # noqa: BLE001
                tests_of[u["module"]] = {}
        test = tests_of[u["module"]].get(u["dotted"])
        if test is None:
            return None
        rvector.reseed(test.name)
        runner = SymPyDocTestRunner(verbose=False, optionflags=flags)
        runner._checker = SymPyOutputChecker()
        test.globs = {}
        old_stdout, old_hook = sys.stdout, sys.displayhook
        uu, wl = setup_pprint()
        signal.setitimer(signal.ITIMER_REAL, ITEM_SECONDS)
        try:
            clear_cache()
            with contextlib.redirect_stderr(io.StringIO()):
                sys.stdout = io.StringIO()
                failed, tried = runner.run(test, out=lambda s: None, clear_globs=True)
            return failed == 0 and tried > 0
        except BaseException:  # noqa: BLE001
            return False
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            sys.stdout, sys.displayhook = old_stdout, old_hook
            interactive_printing.NO_GLOBAL = False
            pprint_use_unicode(uu)
            stringpict._GLOBAL_WRAP_LINE = wl

    def passes(item):
        kind, key = item
        return call_passes(key) if kind == "call" else examples_pass(key)

    mon = sys.monitoring
    mon.use_tool_id(TOOL, "absorbed")
    current = {"code": None, "reached": False}

    def on_start(code, offset):
        if code is current["code"]:
            current["reached"] = True
            raise NotImplementedError("RESTORE")
        return mon.DISABLE

    mon.register_callback(TOOL, mon.events.PY_START, on_start)
    baseline = {}
    graded, absorbed, untested = {}, [], []
    began = time.time()
    for uid in targets:
        fn = function_of(uid)
        if fn is None:
            untested.append(uid)
            continue
        found, tried = None, 0
        for item in [["call", v] for v in items[uid]["calls"]] + [
            ["examples", o] for o in items[uid]["examples"]
        ]:
            key = tuple(item)
            if key not in baseline:
                baseline[key] = passes(item)
            if baseline[key] is not True:
                continue
            current.update(code=fn.__code__, reached=False)
            mon.set_local_events(TOOL, fn.__code__, mon.events.PY_START)
            mon.restart_events()
            try:
                result = passes(item)
            finally:
                mon.set_local_events(TOOL, fn.__code__, 0)
                current.update(code=None)
            tried += 1
            if result is not True:
                found = item
                break
        if found is not None:
            graded[uid] = found
        elif tried:
            absorbed.append(uid)
        else:
            untested.append(uid)
    mon.free_tool_id(TOOL)
    summary = {
        "targets": len(targets),
        "graded_through_others": len(graded),
        "absorbed": len(absorbed),
        "untested": len(untested),
        "items_checked_on_the_original": len(baseline),
        "items_failing_on_the_original": sum(
            1 for v in baseline.values() if v is not True
        ),
        "seconds": round(time.time() - began, 1),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "graded": graded,
                "absorbed": absorbed,
                "untested": untested,
                "summary": summary,
            },
            f,
        )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
