"""Structural canonical form of a Python / SymPy value, as JSON-able nested lists.

Two values that are equal in the sense used by this comparison have the same canonical
form, except that floating-point leaves are compared with a tolerance by `same()`.

  None -> ["N"]           bool -> ["B", v]         integer -> ["I", "<decimal>"]
  rational -> ["Q", p, q] float -> ["F", "<repr>"] complex -> ["C", re, im]
  str -> ["S", s]         bytes -> ["Y", hex]
  tuple -> ["T", [..]]    list -> ["L", [..]]      set -> ["E", [sorted..]]
  dict -> ["D", [[k, v] sorted..]]                 iterator -> ["G", [first items..]]
  SymPy expression -> ["X", class, [args..]]  (atoms carry their defining data)
  matrix -> ["M", rows, cols, [entries..]]    class -> ["K", "module.qualname"]
  other SymPy object -> ["O", class, [[attribute, value]..]], or ["R", class, repr] when its
  state cannot be expressed                     named function -> ["FN", name]
  exception raised by the call -> ["EXC", class name, [class chain..]]
  call that returned None -> ["NS", <arguments after the call>], or ["N"] if unchanged
"""
from __future__ import annotations

import itertools
import json
import math

MAX_NODES = 40000
MAX_DEPTH = 80
MAX_ITER = 200


class Uncanonical(Exception):
    pass


def canon(obj):
    budget = [MAX_NODES]
    _ACTIVE.clear()
    return _c(obj, 0, budget)


def _key(node):
    return json.dumps(node, sort_keys=True)


def _c(o, depth, budget):
    budget[0] -= 1
    if budget[0] < 0 or depth > MAX_DEPTH:
        raise Uncanonical("too large")
    if o is None:
        return ["N"]
    t = type(o)
    if t is bool:
        return ["B", bool(o)]
    if isinstance(o, int):
        return ["I", str(int(o))]
    if isinstance(o, float):
        return _f(o)
    if isinstance(o, complex):
        return ["C", _f(o.real), _f(o.imag)]
    if isinstance(o, str):
        return ["S", str(o)]
    if t in (bytes, bytearray):
        return ["Y", bytes(o).hex()]
    if isinstance(o, type):
        return ["K", f"{o.__module__}.{o.__qualname__}"]

    import fractions

    if isinstance(o, fractions.Fraction):
        return ["Q", str(o.numerator), str(o.denominator)]

    import sympy
    from sympy.core.basic import Basic
    from sympy.matrices.matrixbase import MatrixBase

    # every matrix kind (mutable, immutable, sparse) by shape and entries
    if isinstance(o, MatrixBase):
        r, c = int(o.rows), int(o.cols)
        return ["M", r, c, [_c(o[i, j], depth + 1, budget) for i in range(r) for j in range(c)]]
    if isinstance(o, Basic):
        return _basic(o, depth, budget, sympy)

    mod = t.__module__ or ""
    # numeric helper types used by the polynomial domains
    if mod.startswith(("sympy.external.pythonmpq", "sympy.polys.domains")) and hasattr(o, "numerator") and hasattr(o, "denominator") and not hasattr(o, "ex"):
        return ["Q", str(int(o.numerator)), str(int(o.denominator))]
    if mod.startswith("mpmath"):
        import mpmath

        if isinstance(o, mpmath.mpf):
            return _f(float(o)) if abs(o) < 1e300 else ["F", mpmath.nstr(o, 15)]
        if isinstance(o, mpmath.mpc):
            return ["C", _f(float(o.real)), _f(float(o.imag))]
        if isinstance(o, mpmath.matrix):
            return ["M", int(o.rows), int(o.cols), [_c(o[i, j], depth + 1, budget) for i in range(o.rows) for j in range(o.cols)]]
        raise Uncanonical(f"mpmath type {t.__name__}")

    if isinstance(o, tuple):
        tag = "T" if t is tuple else "T:" + t.__name__
        return [tag, [_c(x, depth + 1, budget) for x in o]]
    if isinstance(o, list):
        tag = "L" if t is list else "L:" + t.__name__
        return [tag, [_c(x, depth + 1, budget) for x in o]]
    if isinstance(o, (set, frozenset)):
        items = [_c(x, depth + 1, budget) for x in o]
        return ["E", sorted(items, key=_key)]
    if isinstance(o, dict):
        # dict and the standard dict flavours (defaultdict, OrderedDict, Counter) alike
        tag = "D" if (t is dict or mod == "collections") else "D:" + t.__name__
        items = [[_c(k, depth + 1, budget), _c(v, depth + 1, budget)] for k, v in o.items()]
        return [tag, sorted(items, key=_key)]
    if isinstance(o, range):
        return ["L", [["I", str(x)] for x in itertools.islice(o, MAX_ITER)]]

    import collections
    import collections.abc as cabc

    if isinstance(o, collections.deque):
        return ["L:deque", [_c(x, depth + 1, budget) for x in o]]
    if isinstance(o, (cabc.KeysView, cabc.ValuesView, cabc.ItemsView)):
        return ["L", [_c(x, depth + 1, budget) for x in o]]
    if hasattr(o, "__next__") and hasattr(o, "__iter__"):
        return ["G", [_c(x, depth + 1, budget) for x in itertools.islice(o, MAX_ITER)]]

    import types

    if isinstance(o, (types.FunctionType, types.BuiltinFunctionType, types.MethodType)):
        name = getattr(o, "__qualname__", None)
        if not name or "<lambda>" in name or "<locals>" in name:
            raise Uncanonical("anonymous function")
        return ["FN", f"{getattr(o, '__module__', '')}.{name}"]
    # other SymPy objects: class name plus stored state; if the state cannot be expressed,
    # class name plus printed form
    if mod.startswith("sympy."):
        cls = f"{mod}.{t.__qualname__}"
        if id(o) in _ACTIVE:
            return ["REF", cls]
        _ACTIVE.add(id(o))
        try:
            saved = budget[0]
            try:
                state = _state(o, t, depth, budget)
                if state:
                    return ["O", cls, state]
            except Uncanonical:
                budget[0] = saved
        finally:
            _ACTIVE.discard(id(o))
        try:
            r = repr(o)
        except Exception:  # noqa: BLE001
            r = None
        if isinstance(r, str) and " at 0x" not in r and 0 < len(r) <= 20000:
            return ["R", cls, r]
    raise Uncanonical(f"unsupported type {mod}.{t.__qualname__}")


_ACTIVE = set()


def _state(o, t, depth, budget):
    names = []
    for klass in t.__mro__:
        slots = klass.__dict__.get("__slots__", ())
        names += [slots] if isinstance(slots, str) else list(slots)
    state = []
    for n in sorted(set(names)):
        if n in ("__dict__", "__weakref__") or n.startswith("__") or "cache" in n or n == "_hash":
            continue
        try:
            state.append([["S", n], _c(object.__getattribute__(o, n), depth + 1, budget)])
        except AttributeError:
            continue
    d = getattr(o, "__dict__", None)
    if isinstance(d, dict):
        for n in sorted(k for k in d if isinstance(k, str)):
            if n.startswith("__") or "cache" in n or n == "_hash":
                continue
            state.append([["S", n], _c(d[n], depth + 1, budget)])
    return state


def _f(x):
    x = float(x)
    if math.isnan(x):
        return ["F", "nan"]
    if math.isinf(x):
        return ["F", "inf" if x > 0 else "-inf"]
    return ["F", repr(x)]


def _basic(o, depth, budget, sympy):
    from sympy.core.containers import Tuple
    from sympy.core.numbers import Float, Integer, Rational
    from sympy.core.symbol import Dummy, Symbol, Wild
    from sympy.logic.boolalg import BooleanFalse, BooleanTrue

    if isinstance(o, BooleanTrue):
        return ["B", True]
    if isinstance(o, BooleanFalse):
        return ["B", False]
    if isinstance(o, Tuple):
        return ["T", [_c(a, depth + 1, budget) for a in o.args]]
    if isinstance(o, Integer):
        return ["I", str(int(o.p))]
    if isinstance(o, Rational):
        return ["Q", str(int(o.p)), str(int(o.q))]
    if isinstance(o, Float):
        return _f(float(o)) if abs(o) < 1e300 else ["F", str(o)]
    name = type(o).__name__
    if isinstance(o, Dummy):
        return ["X", "Dummy", [["S", o.name]]]
    if isinstance(o, (Symbol, Wild)):
        try:
            ass = sorted((str(k), bool(v)) for k, v in (getattr(o, "_assumptions_orig", None) or {}).items())
        except Exception:  # noqa: BLE001
            ass = []
        return ["X", name, [["S", o.name], ["S", json.dumps(ass)]]]
    # objects whose defining data is not in .args
    af = getattr(o, "_array_form", None)
    if name == "Permutation" and isinstance(af, list):
        return ["X", name, [["L", [["I", str(int(i))] for i in af]]]]
    args = o.args
    if name in ("Poly", "PurePoly"):
        dom = getattr(getattr(o, "rep", None), "dom", None)
        return ["X", name, [_c(a, depth + 1, budget) for a in args] + [["S", str(dom)]]]
    if not args:
        # an atom without args: its printed name identifies it (constants, singletons, strings)
        extra = getattr(o, "name", None)
        if isinstance(extra, str):
            return ["X", name, [["S", extra]]]
        return ["X", name, []]
    return ["X", name, [_c(a, depth + 1, budget) for a in args]]


def same(a, b, rel=1e-9, abs_=1e-12):
    """Compare two canonical forms; float leaves within tolerance."""
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        if a and b and a[0] == "EXC" and b[0] == "EXC":
            # same exception class, or one is a subclass of the other
            ca = set(a[2]) if len(a) > 2 and isinstance(a[2], list) else {a[1] if len(a) > 1 else None}
            cb = set(b[2]) if len(b) > 2 and isinstance(b[2], list) else {b[1] if len(b) > 1 else None}
            na, nb = (a[1] if len(a) > 1 else None), (b[1] if len(b) > 1 else None)
            return na is not None and nb is not None and (na in cb or nb in ca)
        if len(a) != len(b):
            return False
        if len(a) == 2 and a[0] == "F" and b[0] == "F":
            try:
                x, y = float(a[1]), float(b[1])
            except (TypeError, ValueError):
                return a[1] == b[1]
            if math.isnan(x) or math.isnan(y):
                return math.isnan(x) and math.isnan(y)
            if math.isinf(x) or math.isinf(y):
                return x == y
            return abs(x - y) <= max(abs_, rel * max(abs(x), abs(y)))
        return all(same(x, y, rel, abs_) for x, y in zip(a, b))
    return a == b
