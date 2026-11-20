"""Record the arguments of calls into chosen units while the withheld test functions run.

Build time only, on the ORIGINAL tree with the full test suite (withheld tests included).

usage:
  rec_withheld.py <tree> <units.json> <uids.json> <functions.json> <out.pkl> [--cap 40]

<uids.json> lists the units to record, <functions.json> the withheld test functions
("file::function"). Only those functions run (every parametrisation), one pytest process.
For every call into a listed unit the argument values at function entry are pickled with the
test that was running and whether the test itself made the call; at most --cap distinct calls
per unit and kind, none larger than 30,000 bytes. <out.pkl> holds [(uid, direct, nodeid, blob)].
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

PLUGIN = '''
import hashlib, json, os, pickle, sys
import pytest
sys.path.insert(0, os.environ["REC_BUILDER"])
import documented
_FUNCS = set(json.load(open(os.environ["REC_FUNCS"])))
_UIDS = set(json.load(open(os.environ["REC_UIDS"])))
_UNITS = [u for u in json.load(open(os.environ["REC_UNITSJSON"])) if u["uid"] in _UIDS]
_CODEMAP = documented.unit_code_map(os.environ["REC_TREE"], _UNITS)
_CAP = int(os.environ.get("REC_CAP", "40"))
_state = {"test": None, "busy": False}
_counts, _seen, _records = {}, {}, []
_mon = sys.monitoring


def _key(nodeid):
    f, rest = nodeid.split("::", 1)
    return f + "::" + rest.split("[")[0]


def pytest_collection_modifyitems(config, items):
    keep = [it for it in items if _key(it.nodeid) in _FUNCS]
    drop = [it for it in items if _key(it.nodeid) not in _FUNCS]
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = keep


def _on_start(code, offset):
    u = _CODEMAP.get((code.co_filename, code.co_firstlineno))
    if u is None or code.co_name != u["name"]:
        return _mon.DISABLE
    if _state["busy"] or _state["test"] is None:
        return None
    uid = u["uid"]
    c = _counts.setdefault(uid, [0, 0])
    if c[0] >= _CAP and c[1] >= _CAP:
        return _mon.DISABLE
    _state["busy"] = True
    try:
        frame = sys._getframe(1)
        caller = frame.f_back
        fn = caller.f_code.co_filename if caller is not None else ""
        direct = ("/tests/" in fn and os.path.basename(fn).startswith("test_")) or fn.startswith("<doctest")
        if c[0 if direct else 1] >= _CAP:
            return None
        n = code.co_argcount + code.co_kwonlyargcount + bool(code.co_flags & 0x04) + bool(code.co_flags & 0x08)
        try:
            blob = pickle.dumps({k: frame.f_locals[k] for k in code.co_varnames[:n]}, protocol=4)
        except BaseException:
            return None
        if len(blob) > 30000:
            return None
        h = hashlib.sha1(blob).digest()
        seen = _seen.setdefault(uid, set())
        if h in seen:
            return None
        seen.add(h)
        c[0 if direct else 1] += 1
        _records.append((uid, direct, _state["test"], blob))
    finally:
        _state["busy"] = False
    return None


def pytest_configure(config):
    _mon.use_tool_id(4, "rec")
    _mon.register_callback(4, _mon.events.PY_START, _on_start)
    _mon.set_events(4, _mon.events.PY_START)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    _state["test"] = item.nodeid
    try:
        yield
    finally:
        _state["test"] = None


def pytest_sessionfinish(session, exitstatus):
    with open(os.environ["REC_OUT"], "wb") as f:
        pickle.dump(_records, f, protocol=4)
'''


def main():
    tree, units_json, uids_json, funcs_json, out = (os.path.abspath(p) for p in sys.argv[1:6])
    cap = sys.argv[sys.argv.index("--cap") + 1] if "--cap" in sys.argv else "40"
    plugin_dir = os.path.join(os.path.dirname(out), "rec_plugin")
    os.makedirs(plugin_dir, exist_ok=True)
    with open(os.path.join(plugin_dir, "rec_withheld_plugin.py"), "w", encoding="utf-8") as f:
        f.write(PLUGIN)
    funcs = json.load(open(funcs_json, encoding="utf-8"))
    files = sorted({f.split("::")[0] for f in funcs})
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=plugin_dir, REC_BUILDER=HERE,
               REC_TREE=tree, REC_UNITSJSON=units_json, REC_UIDS=uids_json, REC_FUNCS=funcs_json, REC_OUT=out, REC_CAP=cap)
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "rec_withheld_plugin", "-p", "no:cacheprovider", "-q", "-o", "addopts=",
           "-m", "not slow and not tooslow", "--timeout", "180", "--no-header", "-rN", *files]
    started = time.time()
    with open(out + ".log", "w") as log:
        done = subprocess.run(cmd, cwd=tree, env=env, stdout=log, stderr=subprocess.STDOUT)
    print(f"pytest exit {done.returncode} in {time.time() - started:.0f}s over {len(files)} files", flush=True)


if __name__ == "__main__":
    main()
