"""Which unit bodies the graded items run, traced on the original tree.

The graded items are the counted calls (recorded calls nothing visible answers: every recorded call
not on the documented list) and the docstring examples of the units in the set (units with a counted
call). Every counted call is replayed with the verifier's own resolution, revival and call (a returned
generator is read as far as the comparison reads it), and every example of a unit in the set is run with
SymPy's doctest runner, each with `sys.monitoring` watching the start of every unit's function body.
Build time only; it reads the original tree and the call data and never prints a result.

usage: graded_coverage.py <original_root> <units.json> <vectors_dir> <verifier_lib> <out.json> [--only VID,...]
Writes {"units": {uid: {"counted": n, "run_by_calls": n, "run_by_examples": n}}, "items": {uid: {"calls":
[vid, ...], "examples": [uid, ...]}} (for every unit without a counted call of its own, the counted calls and
the units in the set whose examples run it), "summary": {...}}.
A counted call that raises or runs out of its time here (one process replays them all, so one call can
leave state for the next) is replayed once more alone, in a process of its own with ten times the time,
and what it runs there is what counts; `--only` is that replay.
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
import subprocess
import sys
import time

CALL_SECONDS = 20.0
EXAMPLE_SECONDS = 30.0
TOOL = 4


class _Late(BaseException):
    pass


def _late(signum, frame):
    raise _Late()


def main():
    root, units_path, vectors, lib, out_path = sys.argv[1:6]
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    seconds = CALL_SECONDS * (10 if only else 1)
    root = os.path.realpath(root)
    sys.path[:] = [p for p in sys.path if p not in ("", os.getcwd())]
    sys.path.insert(0, root)
    sys.path.append(lib)
    os.chdir(root)
    import rvector  # the verifier's own resolution, revival and call
    from canon import MAX_ITER  # how many items of a returned iterator the comparison reads

    units = {u["uid"]: u for u in json.load(open(units_path, encoding="utf-8"))}
    gold = json.load(open(os.path.join(vectors, "gold.json"), encoding="utf-8"))
    documented = set(json.load(open(os.path.join(vectors, "documented.json"), encoding="utf-8"))["calls"])
    with open(os.path.join(vectors, "inputs.pkl"), "rb") as f:
        payload = pickle.load(f)  # noqa: S301 - the task's own build output: modules, unit facts and pickled bytes
    owner = {vid: uid for p in payload.values() for vid, uid, _blob in p["vectors"]}
    counted = {vid for vid in gold if vid not in documented}
    own = {}
    for vid in counted:
        own[owner[vid]] = own.get(owner[vid], 0) + 1
    in_set = set(own)

    from sympy.core.cache import clear_cache
    from sympy.testing.runtests import SymPyDocTestFinder, SymPyDocTestRunner, SymPyOutputChecker, setup_pprint
    import sympy.interactive.printing as interactive_printing
    from sympy.printing.pretty import stringpict
    from sympy.printing.pretty.pretty import pprint_use_unicode

    modules, codes, unresolved = {}, {}, []
    for uid, u in sorted(units.items()):
        if u["module"] not in modules:
            try:
                modules[u["module"]] = importlib.import_module(u["module"])
            except BaseException:  # noqa: BLE001
                modules[u["module"]] = None
        facts = {"file": u["file"], "qualname": u["qualname"], "name": u["qualname"].rsplit(".", 1)[-1],
                 "occ": u.get("occ", 0), "nocc": u.get("nocc", 1)}
        fn = None
        if modules[u["module"]] is not None:
            try:
                fn = rvector.resolve(modules[u["module"]], root, facts)
            except BaseException:  # noqa: BLE001
                fn = None
        if fn is None:
            unresolved.append(uid)
        else:
            codes[fn.__code__] = uid

    mon = sys.monitoring
    mon.use_tool_id(TOOL, "graded-coverage")
    hit = set()

    def on_start(code, offset):
        uid = codes.get(code)
        if uid is not None:
            hit.add(uid)
        return mon.DISABLE

    mon.register_callback(TOOL, mon.events.PY_START, on_start)
    for code in codes:
        mon.set_local_events(TOOL, code, mon.events.PY_START)
    signal.signal(signal.SIGALRM, _late)
    quiet = open(os.devnull, "w")
    by_calls, by_examples, runs, trouble, example_runs = {}, {}, {}, [], {}
    stats = {"calls": 0, "calls_raised": 0, "calls_raising_as_recorded": 0, "calls_out_of_time": 0, "examples": 0,
             "examples_missing": 0, "examples_out_of_time": 0}
    began = time.time()

    # the counted calls
    for mod_name, p in sorted(payload.items()):
        module = modules.get(mod_name)
        if module is None:
            try:
                module = importlib.import_module(mod_name)
            except BaseException:  # noqa: BLE001
                continue
        resolved = {}
        for vid, uid, blob in p["vectors"]:
            if vid not in counted or (only is not None and vid not in only):
                continue
            if uid not in resolved:
                try:
                    resolved[uid] = rvector.resolve(module, root, p["units"][uid])
                except BaseException:  # noqa: BLE001
                    resolved[uid] = None
            fn = resolved[uid]
            if fn is None:
                continue
            rvector.reseed(vid)
            hit.clear()
            mon.restart_events()
            signal.setitimer(signal.ITIMER_REAL, seconds)
            try:
                with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                    clear_cache()
                    res = rvector.call(fn, rvector.revive(pickle.loads(blob)))  # noqa: S301 - build output
                    if hasattr(res, "__next__"):   # a generator runs only as far as the comparison reads it
                        for _ in zip(range(MAX_ITER), res):
                            pass
            except _Late:
                stats["calls_out_of_time"] += 1
                trouble.append(vid)
            except BaseException:  # noqa: BLE001
                if isinstance(gold.get(vid), list) and gold[vid][:1] == ["EXC"]:
                    stats["calls_raising_as_recorded"] += 1   # a call whose recorded result is the error
                else:
                    stats["calls_raised"] += 1
                    trouble.append(vid)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            stats["calls"] += 1
            runs[vid] = sorted(hit - {uid})
    if only is not None:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"runs": runs, "trouble": trouble}, f)
        return
    # each call that raised or ran out of time, once more alone
    retried = {}
    for vid in trouble:
        alone = out_path + f".{vid}.json"
        done = subprocess.run([sys.executable, "-I", "-B", os.path.abspath(__file__), root, units_path, vectors, lib,
                               alone, "--only", vid], capture_output=True, text=True, timeout=seconds * 10 + 300)
        if done.returncode == 0 and os.path.exists(alone):
            again = json.load(open(alone, encoding="utf-8"))
            runs[vid] = sorted(set(runs[vid]) | set(again["runs"].get(vid, [])))
            retried[vid] = "still raised or ran out of time" if vid in again["trouble"] else "ran"
            os.remove(alone)
        else:
            retried[vid] = "the replay failed"
    for vid, ran in runs.items():
        for r in ran:
            by_calls[r] = by_calls.get(r, 0) + 1

    # the examples of the units in the set
    flags = pdoctest.ELLIPSIS | pdoctest.NORMALIZE_WHITESPACE | pdoctest.IGNORE_EXCEPTION_DETAIL
    by_module = {}
    for uid in sorted(in_set):
        by_module.setdefault(units[uid]["module"], []).append(uid)
    for mod_name, uids in sorted(by_module.items()):
        module = modules.get(mod_name)
        if module is None:
            continue
        try:
            tests = {t.name: t for t in SymPyDocTestFinder().find(module) if t.examples}
        except BaseException:  # noqa: BLE001
            continue
        for uid in uids:
            test = tests.get(units[uid]["dotted"])
            if test is None:
                stats["examples_missing"] += 1
                continue
            runner = SymPyDocTestRunner(verbose=False, optionflags=flags)
            runner._checker = SymPyOutputChecker()
            test.globs = {}
            hit.clear()
            mon.restart_events()
            old_stdout, old_hook = sys.stdout, sys.displayhook
            uu, wl = setup_pprint()
            signal.setitimer(signal.ITIMER_REAL, EXAMPLE_SECONDS)
            try:
                clear_cache()
                with contextlib.redirect_stderr(io.StringIO()):
                    sys.stdout = io.StringIO()
                    runner.run(test, out=lambda s: None, clear_globs=True)
            except _Late:
                stats["examples_out_of_time"] += 1
            except BaseException:  # noqa: BLE001
                pass
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                sys.stdout, sys.displayhook = old_stdout, old_hook
                interactive_printing.NO_GLOBAL = False
                pprint_use_unicode(uu)
                stringpict._GLOBAL_WRAP_LINE = wl
            stats["examples"] += 1
            example_runs[uid] = sorted(hit - {uid})
            for ran in hit - {uid}:
                by_examples[ran] = by_examples.get(ran, 0) + 1
    mon.set_events(TOOL, 0)
    for code in codes:
        mon.set_local_events(TOOL, code, 0)
    mon.free_tool_id(TOOL)

    facts = {uid: {"counted": own.get(uid, 0), "run_by_calls": by_calls.get(uid, 0),
                   "run_by_examples": by_examples.get(uid, 0)} for uid in sorted(units)}
    # for every unit without a counted call of its own: the graded items of other units that run it
    items = {uid: {"calls": [], "examples": []} for uid in units if not own.get(uid)}
    for vid, ran in runs.items():
        for r in ran:
            if r in items:
                items[r]["calls"].append(vid)
    for owner_uid, ran in example_runs.items():
        for r in ran:
            if r in items:
                items[r]["examples"].append(owner_uid)
    graded = [uid for uid, f in facts.items() if f["counted"] or f["run_by_calls"] or f["run_by_examples"]]
    summary = dict(stats, retried=retried, seconds=round(time.time() - began, 1), units=len(units), in_set=len(in_set),
                   counted_calls=len(counted), unresolved=unresolved, graded=len(graded),
                   ungraded=len(units) - len(graded))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"units": facts, "items": items, "summary": summary}, f)
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in summary.items()}))


if __name__ == "__main__":
    main()
