"""Find the recorded calls whose arguments a docstring example or a visible test also uses.

Build time only, on the ORIGINAL tree whose test directories hold the visible tests only
(the working copy with the original bodies put back).

usage:
  documented.py doctests <tree> <units.json> <inputs.pkl> <lib_dir> <out.json> [<package> ...]
  documented.py tests <tree> <units.json> <inputs.pkl> <lib_dir> <out.json> <package> [<package> ...]
  documented.py merge <out.json> <part.json> [<part.json> ...]

While the examples of every docstring of the named packages run (`doctests`), or while the
visible tests under them run (`tests`, one pytest process per package, one at a time), every
call into a unit is compared with that unit's recorded calls: a recorded call whose pickled
arguments are byte-identical to the call's, or whose arguments have the same canonical form
(the comparison's own `canon`, after a pickle round trip as the recorded calls had), is marked
documented. Calls made directly by an example or a test and calls made inside the library while
one runs count alike. The output maps each documented call id to where it was seen first.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import io
import json
import os
import pickle
import signal
import subprocess
import sys
import time

CAP_PICKLES = 20_000   # calls into one unit that are pickled and compared, per process
MAX_BLOB = 30_000      # recorded arguments are never larger than this


def unit_code_map(tree, units):
    """(absolute file, first line of the code object) -> unit, from the original source."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common"))
    import restorelib  # noqa: PLC0415

    out, parsed = {}, {}
    for u in units:
        path = os.path.join(tree, u["file"])
        if path not in parsed:
            parsed[path] = restorelib.index_functions(ast.parse(open(path, encoding="utf-8").read()))
        nodes = parsed[path].get(u["qualname"]) or []
        if len(nodes) != u.get("nocc", 1):
            continue
        fn = nodes[u.get("occ", 0)]
        for line in {fn.lineno, min([d.lineno for d in fn.decorator_list] + [fn.lineno])}:
            out[(os.path.realpath(path), line)] = dict(u, name=u["qualname"].rsplit(".", 1)[-1])
    return out


class Matcher:
    """Marks recorded calls that a call seen at run time repeats."""

    def __init__(self, tree, units_path, inputs_path, lib_dir):
        self.tree = os.path.realpath(tree)
        units = json.load(open(units_path, encoding="utf-8"))
        payload = pickle.load(open(inputs_path, "rb"))
        self.vectors = {}
        for p in payload.values():
            for vid, uid, blob in p["vectors"]:
                self.vectors.setdefault(uid, []).append((vid, blob))
        self.by_sha = {uid: {hashlib.sha1(b).digest(): vid for vid, b in vs} for uid, vs in self.vectors.items()}
        self.keys = {}            # uid -> {canonical key: vid}, built on first use
        self.codemap = unit_code_map(self.tree, [u for u in units if u["uid"] in self.vectors])
        self.found = {}           # vid -> {"by", "source", "direct"}
        self.left = {uid: len(vs) for uid, vs in self.vectors.items()}
        self.pickled = {}
        self.capped = set()
        self.context = None
        self.busy = False
        sys.path.insert(0, lib_dir)
        import canon  # noqa: PLC0415

        self.canon = canon

    def key(self, args):
        try:
            return json.dumps(self.canon.canon(args), sort_keys=True, separators=(",", ":"))
        except Exception:  # noqa: BLE001 - arguments without a canonical form are matched by bytes only
            return None

    def unit_keys(self, uid):
        if uid not in self.keys:
            table = {}
            for vid, blob in self.vectors[uid]:
                try:
                    k = self.key(revive(pickle.loads(blob)))
                except Exception:  # noqa: BLE001
                    k = None
                if k is not None:
                    table.setdefault(k, []).append(vid)
            self.keys[uid] = table
        return self.keys[uid]

    def mark(self, vids, uid, direct):
        for vid in vids:
            if vid not in self.found:
                self.found[vid] = {"by": self.context[0], "source": self.context[1], "direct": direct}
                self.left[uid] -= 1

    def on_start(self, code, offset):
        u = self.codemap.get((code.co_filename, code.co_firstlineno))
        mon = sys.monitoring
        if u is None or code.co_name != u["name"]:
            return mon.DISABLE
        uid = u["uid"]
        if self.left.get(uid, 0) <= 0:
            return mon.DISABLE
        if self.busy or self.context is None:
            return None
        if self.pickled.get(uid, 0) >= CAP_PICKLES:
            self.capped.add(uid)
            return None
        self.busy = True
        try:
            frame = sys._getframe(1)
            caller = frame.f_back
            fn = caller.f_code.co_filename if caller is not None else ""
            direct = fn.startswith("<doctest") or ("/tests/" in fn and os.path.basename(fn).startswith("test_"))
            n = code.co_argcount + code.co_kwonlyargcount + bool(code.co_flags & 0x04) + bool(code.co_flags & 0x08)
            try:
                blob = pickle.dumps({k: frame.f_locals[k] for k in code.co_varnames[:n]}, protocol=4)
            except BaseException:  # noqa: BLE001
                return None
            self.pickled[uid] = self.pickled.get(uid, 0) + 1
            if len(blob) > MAX_BLOB:
                return None
            hit = self.by_sha[uid].get(hashlib.sha1(blob).digest())
            if hit is not None:
                self.mark([hit], uid, direct)
                return None
            try:
                k = self.key(revive(pickle.loads(blob)))
            except Exception:  # noqa: BLE001
                k = None
            if k is not None and k in self.unit_keys(uid):
                self.mark(self.unit_keys(uid)[k], uid, direct)
        finally:
            self.busy = False
        return None

    def install(self):
        mon = sys.monitoring
        mon.use_tool_id(4, "documented")
        mon.register_callback(4, mon.events.PY_START, self.on_start)
        mon.set_events(4, mon.events.PY_START)

    def write(self, path, extra):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"documented": self.found, "capped_units": sorted(self.capped), **extra}, f)


def revive(args):
    """As the call runner does: rebuild SymPy objects whose class sets state in __init__."""
    from sympy.core.basic import Basic  # noqa: PLC0415

    for k, v in list(args.items()):
        if isinstance(v, Basic) and any("__init__" in vars(c) for c in type(v).__mro__
                                        if (c.__module__ or "").startswith("sympy") and c is not Basic):
            args[k] = type(v)(*v.args)
    return args


def modules_of(tree, package):
    base = os.path.join(tree, *package.split("."))
    out = []
    for folder, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in ("tests", "__pycache__", "benchmarks"))
        for name in sorted(files):
            if name.endswith(".py") and not name.startswith(("test_", "conftest")):
                rel = os.path.relpath(os.path.join(folder, name), tree)[:-3].replace(os.sep, ".")
                out.append(rel[: -len(".__init__")] if rel.endswith(".__init__") else rel)
    return out


class _Timeout(KeyboardInterrupt):
    pass


def run_doctests(matcher, modules, timeout=20.0):
    import doctest as pdoctest  # noqa: PLC0415

    from sympy.core.cache import clear_cache  # noqa: PLC0415
    from sympy.testing.runtests import SymPyDocTestFinder, SymPyDocTestRunner, SymPyOutputChecker, setup_pprint  # noqa: PLC0415

    def alarm(signum, frame):
        raise _Timeout()

    signal.signal(signal.SIGALRM, alarm)
    flags = pdoctest.ELLIPSIS | pdoctest.NORMALIZE_WHITESPACE | pdoctest.IGNORE_EXCEPTION_DETAIL
    ran = failed_imports = 0
    for name in modules:
        try:
            module = importlib.import_module(name)
            tests = [t for t in SymPyDocTestFinder().find(module) if t.examples]
        except BaseException:  # noqa: BLE001
            failed_imports += 1
            continue
        for test in tests:
            runner = SymPyDocTestRunner(verbose=False, optionflags=flags)
            runner._checker = SymPyOutputChecker()
            test.globs = {}
            buf, old = io.StringIO(), sys.stdout
            clear_cache()
            setup_pprint()
            matcher.context = ("doctest", test.name)
            try:
                signal.setitimer(signal.ITIMER_REAL, timeout)
                sys.stdout = buf
                runner.run(test, out=buf.write, clear_globs=True)
            except BaseException:  # noqa: BLE001
                pass
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                sys.stdout = old
                matcher.context = None
            ran += 1
    return {"docstrings_run": ran, "modules_not_imported": failed_imports}


PLUGIN = '''
import json, os, sys
import pytest
sys.path.insert(0, os.environ["DOC_BUILDER"])
import documented
M = documented.Matcher(os.environ["DOC_TREE"], os.environ["DOC_UNITS"], os.environ["DOC_INPUTS"], os.environ["DOC_LIB"])
M.install()
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    M.context = ("test", item.nodeid)
    try:
        yield
    finally:
        M.context = None
def pytest_sessionfinish(session, exitstatus):
    M.write(os.environ["DOC_OUT"], {"exitstatus": int(exitstatus)})
'''


def main():
    mode = sys.argv[1]
    if mode == "merge":
        out, parts = sys.argv[2], sys.argv[3:]
        merged, capped, notes = {}, set(), []
        for part in parts:
            try:
                data = json.load(open(part, encoding="utf-8"))
            except (OSError, ValueError):
                notes.append(f"missing or unreadable part {os.path.basename(part)}")
                continue
            for vid, where in data["documented"].items():
                merged.setdefault(vid, where)
            capped.update(data.get("capped_units", []))
        json.dump({"documented": dict(sorted(merged.items())), "capped_units": sorted(capped), "notes": notes},
                  open(out, "w", encoding="utf-8"), indent=0)
        print(f"documented calls: {len(merged)} | units with capped comparison: {len(capped)} | {notes}")
        return
    tree, units_path, inputs_path, lib_dir, out = (os.path.abspath(p) for p in sys.argv[2:7])
    packages = sys.argv[7:] or ["sympy"]
    if mode == "doctests":
        os.chdir(tree)
        sys.path[:0] = [tree]
        matcher = Matcher(tree, units_path, inputs_path, lib_dir)
        matcher.install()
        mods = [m for p in packages for m in modules_of(tree, p)]
        started = time.time()
        stats = run_doctests(matcher, mods)
        matcher.write(out, dict(stats, modules=len(mods), seconds=round(time.time() - started, 1)))
        print(json.dumps({"documented": len(matcher.found), **stats}))
        return
    plugin_dir = os.path.join(os.path.dirname(out), "plugin")
    os.makedirs(plugin_dir, exist_ok=True)
    with open(os.path.join(plugin_dir, "documented_plugin.py"), "w", encoding="utf-8") as f:
        f.write(PLUGIN)
    parts = []
    for package in packages:
        part = f"{out}.{package}.json"
        env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1",
                   PYTHONPATH=plugin_dir, DOC_BUILDER=os.path.dirname(os.path.abspath(__file__)), DOC_TREE=tree,
                   DOC_UNITS=units_path, DOC_INPUTS=inputs_path, DOC_LIB=lib_dir, DOC_OUT=part)
        cmd = [sys.executable, "-B", "-m", "pytest", "-p", "documented_plugin", "-p", "no:cacheprovider", "-q",
               "-o", "addopts=", "-m", "not slow and not tooslow", "--timeout", "180",
               "--no-header", "-rN", package.replace(".", "/")]
        started = time.time()
        with open(part + ".log", "w") as log:
            done = subprocess.run(cmd, cwd=tree, env=env, stdout=log, stderr=subprocess.STDOUT)
        print(f"{package}: exit {done.returncode} in {time.time() - started:.0f}s", flush=True)
        parts.append(part)
    sys.argv = [sys.argv[0], "merge", out, *parts]
    main()


if __name__ == "__main__":
    main()
