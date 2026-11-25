"""Record the calls that docstring examples make directly into restorable units.

usage:
  rec_doctests.py drive <tree_root> <units.json> <out_dir> [--workers N]
  rec_doctests.py one <tree_root> <module> <units.json> <out.pkl>

Run on the ORIGINAL tree. Output records have the shape of rec_plugin's:
(uid, True, "doctest::<name>", pickled arguments).  These are used only for units that the
test suite never calls with replayable arguments.
"""

from __future__ import annotations

import collections
import hashlib
import io
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

CAP = 12


def one(root, module_name, units_path, out_path):
    root = os.path.realpath(root)
    sys.path.insert(0, root)
    os.chdir(root)
    units = [u for u in json.loads(Path(units_path).read_text())]
    codemap = {}
    for u in units:
        fn = os.path.join(root, u["file"])
        codemap[(fn, u["def_line"])] = u
        codemap[(fn, u["deco_line"])] = u
    state = {"test": None, "busy": False}
    counts, seen, records = collections.Counter(), collections.defaultdict(set), []
    mon = sys.monitoring
    TOOL = 4

    def on_start(code, offset):
        u = codemap.get((code.co_filename, code.co_firstlineno))
        if u is None or code.co_name != u["name"]:
            return mon.DISABLE
        if state["busy"] or state["test"] is None or counts[u["uid"]] >= CAP:
            return None
        state["busy"] = True
        try:
            frame = sys._getframe(1)
            caller = frame.f_back
            direct = caller is not None and caller.f_code.co_filename.startswith(
                "<doctest"
            )
            if not direct and state["test"] != u["dotted"]:
                return None  # inner calls only while the unit's own examples run
            n = (
                code.co_argcount
                + code.co_kwonlyargcount
                + bool(code.co_flags & 0x04)
                + bool(code.co_flags & 0x08)
            )
            try:
                blob = pickle.dumps(
                    {k: frame.f_locals[k] for k in code.co_varnames[:n]}, protocol=4
                )
            except BaseException:  # noqa: BLE001
                return None
            if len(blob) > 30000:
                return None
            h = hashlib.sha1(blob).digest()
            if h in seen[u["uid"]]:
                return None
            seen[u["uid"]].add(h)
            counts[u["uid"]] += 1
            records.append((u["uid"], direct, "doctest::" + state["test"], blob))
        finally:
            state["busy"] = False
        return None

    mon.use_tool_id(TOOL, "recdt")
    mon.register_callback(TOOL, mon.events.PY_START, on_start)
    mon.set_events(TOOL, mon.events.PY_START)

    import doctest as pdoctest
    import importlib

    from sympy.core.cache import clear_cache
    from sympy.testing.runtests import (
        SymPyDocTestFinder,
        SymPyDocTestRunner,
        SymPyOutputChecker,
        setup_pprint,
    )

    module = importlib.import_module(module_name)
    want = {u["dotted"] for u in units if u["module"] == module_name}
    for test in SymPyDocTestFinder().find(module):
        if not test.examples or test.name not in want:
            continue
        runner = SymPyDocTestRunner(
            verbose=False,
            optionflags=pdoctest.ELLIPSIS
            | pdoctest.NORMALIZE_WHITESPACE
            | pdoctest.IGNORE_EXCEPTION_DETAIL,
        )
        runner._checker = SymPyOutputChecker()
        test.globs = {}
        buf = io.StringIO()
        old = sys.stdout
        clear_cache()
        setup_pprint()
        state["test"] = test.name
        mon.restart_events()
        try:
            sys.stdout = buf
            runner.run(test, out=buf.write, clear_globs=True)
        except BaseException:  # noqa: BLE001, S110
            pass
        finally:
            sys.stdout = old
            state["test"] = None
    with open(out_path, "wb") as f:
        pickle.dump(records, f, protocol=4)


def drive(root, units_path, out_dir, workers):
    from concurrent.futures import ThreadPoolExecutor

    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    units = json.loads(Path(units_path).read_text())
    mods = sorted({u["module"] for u in units})

    def run(item):
        k, mod = item
        out = os.path.join(out_dir, f"recdt_{k:04d}.pkl")
        env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    os.path.abspath(__file__),
                    "one",
                    root,
                    mod,
                    os.path.abspath(units_path),
                    out,
                ],
                check=False,
                env=env,
                timeout=900,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            pass
        try:
            return len(pickle.load(open(out, "rb")))
        except Exception:  # noqa: BLE001
            return 0

    with ThreadPoolExecutor(workers) as ex:
        total = sum(ex.map(run, list(enumerate(mods))))
    print("doctest call records:", total, "from", len(mods), "modules")


if __name__ == "__main__":
    if sys.argv[1] == "one":
        one(*sys.argv[2:6])
    else:
        w = (
            int(sys.argv[sys.argv.index("--workers") + 1])
            if "--workers" in sys.argv
            else 8
        )
        drive(sys.argv[2], sys.argv[3], sys.argv[4], w)
