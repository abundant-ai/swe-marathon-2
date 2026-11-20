"""Replay recorded calls of the functions of ONE module of a candidate tree.

usage: rvector.py <cand_root> <module> <vectors.pkl> <out.jsonl> [timeout_sec]

<vectors.pkl> holds {"units": {uid: {...}}, "vectors": [(vid, uid, blob), ...]} where blob is
the pickled argument mapping of one call.  For every vector the function is called
directly with those arguments and one line  {"v": vid, "c": <canonical result>}  is
appended to <out.jsonl>, after a line {"loaded": true} once the module is imported.  A call
that returns None is represented by the state of its arguments after the call; a call that
returns a value and changes an argument (as the comparison tells states apart, so a memo
slot filled is no change) by both.  The Dummies that came with the arguments keep their names in the
result's form; the ones the call made are marked as such (canon.py).  No expected result is
available to this process.  After a call that runs out of time the runner exits with status
3, so that the calls behind it run in a fresh process.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import json
import os
import pickle
import random
import signal
import sys
import time
import types
import zlib

cand_root, module_name, vec_path, out_path = sys.argv[1:5]
timeout = float(sys.argv[5]) if len(sys.argv) > 5 else 5.0
HERE = os.path.dirname(os.path.abspath(__file__))
data = pickle.load(open(vec_path, "rb"))
out_f = open(out_path, "a", encoding="utf-8")

cand_root = os.path.realpath(cand_root)
sys.path[:] = [p for p in sys.path if p not in ("", os.getcwd(), HERE)]
sys.path.insert(0, cand_root)
sys.path.append(HERE)
os.chdir(cand_root)

from canon import Uncanonical, canon, dummies, same  # noqa: E402

MAX_LINE = 2_000_000   # a result together with the arguments it changed can be large (a mechanics system)


def emit(vid, c, ms=0):
    line = json.dumps({"v": vid, "c": c, "ms": ms})
    if len(line) > MAX_LINE:
        line = json.dumps({"v": vid, "c": ["TOOBIG"], "ms": ms})
    out_f.write(line + "\n")
    out_f.flush()


try:
    from sympy.core.cache import clear_cache

    module = importlib.import_module(module_name)
except BaseException as e:  # noqa: BLE001
    for vid, uid, blob in data["vectors"]:
        emit(vid, ["EXC", "ImportFailure"])
    sys.exit(0)
out_f.write(json.dumps({"loaded": True}) + "\n")
out_f.flush()


def def_lines(u):
    """Lines (def and first decorator) of the unit's function in the candidate file."""
    path = os.path.join(cand_root, u["file"])
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = {}

    def visit(node, prefix):
        for ch in node.body:
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.setdefault(prefix + ch.name, []).append(ch)
            elif isinstance(ch, ast.ClassDef):
                visit(ch, prefix + ch.name + ".")

    visit(tree, "")
    nodes = out.get(u["qualname"]) or []
    if len(nodes) != u.get("nocc", 1):
        return path, set()
    n = nodes[u.get("occ", 0)]
    return path, {n.lineno, min([d.lineno for d in n.decorator_list] + [n.lineno])}


def resolve(u):
    """The undecorated function object of the unit, or None."""
    path, lines = def_lines(u)
    if not lines:
        return None
    parts = u["qualname"].split(".")
    holder = module
    for p in parts[:-1]:
        holder = vars(holder).get(p) if isinstance(holder, (type, types.ModuleType)) else None
        if holder is None:
            return None
    start = vars(holder).get(parts[-1])
    seen = set()
    stack = [(start, 0)]
    while stack:
        o, d = stack.pop()
        if o is None or id(o) in seen or d > 8:
            continue
        seen.add(id(o))
        if isinstance(o, types.FunctionType):
            c = o.__code__
            if c.co_name == u["name"] and os.path.realpath(c.co_filename) == path and c.co_firstlineno in lines:
                return o
            for cell in o.__closure__ or ():
                try:
                    stack.append((cell.cell_contents, d + 1))
                except ValueError:
                    pass
            stack.append((getattr(o, "__wrapped__", None), d + 1))
        elif isinstance(o, property):
            stack += [(o.fget, d + 1), (o.fset, d + 1), (o.fdel, d + 1)]
        elif isinstance(o, (classmethod, staticmethod)):
            stack.append((o.__func__, d + 1))
        else:
            for attr in ("__wrapped__", "__func__", "func", "fget", "f", "_func", "function"):
                try:
                    stack.append((inspect.getattr_static(o, attr, None), d + 1))
                except Exception:  # noqa: BLE001
                    pass
            try:
                for v in list(vars(o).values())[:20]:
                    if isinstance(v, (types.FunctionType, property, classmethod, staticmethod)):
                        stack.append((v, d + 1))
            except TypeError:
                pass
    return None


def revive(args):
    """SymPy objects are unpickled from their arguments without running __init__; rebuild
    the ones whose class sets state there, so that the call sees a complete object."""
    from sympy.core.basic import Basic

    for k, v in list(args.items()):
        if isinstance(v, Basic) and any(
            "__init__" in vars(c) for c in type(v).__mro__
            if (c.__module__ or "").startswith("sympy") and c is not Basic
        ):
            args[k] = type(v)(*v.args)
    return args


class _Timeout(BaseException):
    pass


class _Unusable(Exception):
    """The recorded arguments could not be rebuilt in this tree."""


def _alarm(signum, frame):
    raise _Timeout()


signal.signal(signal.SIGALRM, _alarm)
funcs = {}


def reseed(vid):
    """Give a call the same random numbers on every run, so that grading one tree twice
    gives one result: Python's generator and both of SymPy's (the one its assumption
    system shuffles with included).  Recorded results do not depend on the random state."""
    value = zlib.crc32(str(vid).encode("utf-8"))
    random.seed(value)
    try:
        from sympy.core import random as sympy_random

        sympy_random.rng.seed(value)
        sympy_random._assumptions_rng.seed(value)
    except BaseException:  # noqa: BLE001
        pass


def call(fn, args):
    code = fn.__code__
    names = code.co_varnames
    npos, nkw = code.co_argcount, code.co_kwonlyargcount
    pos = [args[names[i]] for i in range(npos)]
    kwonly = {names[i]: args[names[i]] for i in range(npos, npos + nkw)}
    idx = npos + nkw
    varargs, varkw = (), {}
    if code.co_flags & 0x04:
        varargs = args[names[idx]]
        idx += 1
    if code.co_flags & 0x08:
        varkw = args[names[idx]]
    return fn(*pos, *varargs, **kwonly, **varkw)


for vid, uid, blob in data["vectors"]:
    timed_out = False
    u = data["units"][uid]
    if uid not in funcs:
        try:
            funcs[uid] = resolve(u)
        except BaseException:  # noqa: BLE001
            funcs[uid] = None
    fn = funcs[uid]
    if fn is None:
        emit(vid, ["EXC", "Unresolved"])
        continue
    reseed(vid)
    t0 = time.time()
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout)
        clear_cache()
        try:
            args = revive(pickle.loads(blob))
            # the Dummies the call is given, read from a copy so that nothing touches the arguments
            fixed = dummies(revive(pickle.loads(blob)))
        except _Timeout:
            raise
        except BaseException:  # noqa: BLE001
            raise _Unusable()
        res = call(fn, args)
        if res is None:
            # nothing returned: what the call did to its arguments is the result
            after = canon(args, fixed)
            before = canon(revive(pickle.loads(blob)), fixed)
            c = ["N"] if after == before else ["NS", after]
        else:
            c = canon(res, fixed)
            # a value returned and an argument changed: both are the result
            try:
                after = canon(args, fixed)
                before = canon(revive(pickle.loads(blob)), fixed)
            except Uncanonical:
                after = before = None
            if after is not None and not same(before, after):
                c = ["RS", c, after]
        signal.setitimer(signal.ITIMER_REAL, 0)
    except _Timeout:
        c = ["EXC", "Timeout", []]
        timed_out = True
    except _Unusable:
        c = ["EXC", "Unusable", []]
    except Uncanonical:
        c = ["EXC", "Uncanonical", []]
    except BaseException as e:  # noqa: BLE001
        chain = [k.__name__ for k in type(e).__mro__ if k.__name__ not in ("Exception", "BaseException", "object")]
        c = ["EXC", type(e).__name__, chain[:12]]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    emit(vid, c, int((time.time() - t0) * 1000))
    if timed_out:
        # an interrupted body can leave global state behind (a working precision, say)
        out_f.close()
        os._exit(3)
out_f.close()
os._exit(0)
