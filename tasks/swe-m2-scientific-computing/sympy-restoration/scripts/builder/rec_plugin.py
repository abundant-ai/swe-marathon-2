"""pytest plugin (build time only): record the arguments of calls into restorable units.

Run on the ORIGINAL tree:
  REC_UNITS=units.json REC_OUT=dir pytest -p rec_plugin ...   (PYTHONPATH must contain this dir)

For every call whose callee is a unit, the argument values at function entry are pickled
together with the test that was running and whether the caller was the test itself.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import pickle
import sys

import pytest

_UNITS = json.load(open(os.environ["REC_UNITS"]))
_ROOT = os.path.realpath(os.environ.get("REC_ROOT", os.getcwd()))
_OUT = os.environ["REC_OUT"]
_CAP_DIRECT = int(os.environ.get("REC_CAP_DIRECT", "80"))
_CAP_INNER = int(os.environ.get("REC_CAP_INNER", "40"))

_codemap = {}
for u in _UNITS:
    fn = os.path.join(_ROOT, u["file"])
    _codemap[(fn, u["def_line"])] = u
    _codemap[(fn, u["deco_line"])] = u

_state = {"test": None, "busy": False}
_counts = {}
_seen = {}
_records = []
_TOOL = 4
_mon = sys.monitoring


def _is_test_frame(frame):
    if frame is None:
        return False
    fn = frame.f_code.co_filename
    base = os.path.basename(fn)
    return ("/tests/" in fn and base.startswith("test_")) or fn.startswith("<doctest")


def _on_start(code, offset):
    u = _codemap.get((code.co_filename, code.co_firstlineno))
    if u is None or code.co_name != u["name"]:
        return _mon.DISABLE
    if _state["busy"] or _state["test"] is None:
        return None
    uid = u["uid"]
    c = _counts.setdefault(uid, [0, 0])
    if c[0] >= _CAP_DIRECT and c[1] >= _CAP_INNER:
        return _mon.DISABLE
    _state["busy"] = True
    try:
        frame = sys._getframe(1)
        direct = _is_test_frame(frame.f_back)
        if (direct and c[0] >= _CAP_DIRECT) or (not direct and c[1] >= _CAP_INNER):
            return None
        n = code.co_argcount + code.co_kwonlyargcount
        if code.co_flags & 0x04:
            n += 1
        if code.co_flags & 0x08:
            n += 1
        names = code.co_varnames[:n]
        loc = frame.f_locals
        try:
            args = {k: loc[k] for k in names}
            blob = pickle.dumps(args, protocol=4)
        except BaseException:  # noqa: BLE001
            return None
        if len(blob) > 30000:
            return None
        h = hashlib.sha1(blob).digest()
        s = _seen.setdefault(uid, set())
        if h in s:
            return None
        s.add(h)
        c[0 if direct else 1] += 1
        _records.append((uid, direct, _state["test"], blob))
    finally:
        _state["busy"] = False
    return None


def _flush():
    if not _records:
        return
    os.makedirs(_OUT, exist_ok=True)
    path = os.path.join(_OUT, f"rec_{os.environ.get('PYTEST_XDIST_WORKER', 'main')}_{os.getpid()}.pkl")
    with open(path, "wb") as f:
        pickle.dump(_records, f, protocol=4)


def pytest_configure(config):
    if getattr(config, "workerinput", None) is None and config.pluginmanager.hasplugin("xdist") and config.getoption("numprocesses", None):
        return  # controller process of an xdist run: workers do the recording
    _mon.use_tool_id(_TOOL, "rec")
    _mon.register_callback(_TOOL, _mon.events.PY_START, _on_start)
    _mon.set_events(_TOOL, _mon.events.PY_START)
    atexit.register(_flush)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    _state["test"] = item.nodeid
    try:
        yield
    finally:
        _state["test"] = None


def pytest_sessionfinish(session, exitstatus):
    _flush()
    _records.clear()
