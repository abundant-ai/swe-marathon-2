"""Structural canonical form of a Python / SymPy value, as JSON-able nested lists, and the
comparison of two such forms.

  None -> ["N"]           bool -> ["B", v]         integer -> ["I", "<decimal>"]
  rational -> ["Q", p, q] float -> ["F", "<repr>"] complex -> ["C", re, im]
  str -> ["S", s]         bytes -> ["Y", hex]
  tuple -> ["T", [..]]    list -> ["L", [..]]      set -> ["E", [sorted..]]
  dict -> ["D", [[k, v] sorted..]]                 iterator -> ["G", [first items..]]
  SymPy expression -> ["X", class, [args..]]  (atoms carry their defining data)
  symbol -> ["X", class, [name, assumptions]]
  Dummy that came with the call's arguments -> ["X", "Dummy", [name, assumptions, index]]
  Dummy the call made -> ["X", "Dummy~", [name ("" when unnamed), assumptions, identity]]
  matrix -> ["M", rows, cols, [entries..]]    class -> ["K", "module.qualname"]
  domain matrix storage -> ["DM", rows, cols, domain, [entries..], "dense" | "sparse" | "sparse with zeros"]
  other SymPy object -> ["O", class, [[attribute, value]..]] (an attribute filled lazily is "~name";
  a value that cannot be expressed is ["?"]; a creation counter is ["#", "given" | "made", value]),
  or ["R", class, repr] when its state cannot be expressed      named function -> ["FN", name]
  exception raised by the call -> ["EXC", class name, [class chain..]]
  call that returned None -> ["NS", <arguments after the call>], or ["N"] if unchanged

`same()` compares behaviour, not bookkeeping, and nothing looser than that:
- a symbol is its name plus the assumptions SymPy's own equality uses; so is a Dummy;
- a Dummy the call made is named and numbered from a process-wide counter, so those compare up
  to one consistent renaming (a bijection over the whole result); a Dummy that came with the
  call's arguments keeps its name and index, so two of them cannot trade places;
- a value an object fills lazily from its other state (a memo slot) counts when both sides hold
  one, for a dict of such values on the keys both hold; an empty one is never wrong;
- a process-wide creation counter (`ReferenceFrame.index`, which orders a vector's printed
  components) is exact for an object that came with the arguments, so a copy cannot stand in
  for it, and compares up to one order-preserving renaming for the objects the call made;
- strings compare exactly, except the LaTeX of LATEX_UNITS, compared without the whitespace
  LaTeX ignores;
- domain-matrix storage, dense or sparse, counts for STORAGE_UNITS, whose result is that storage,
  and zeros stored in sparse storage always count;
- Truss's coordinate lists kept in parallel with its nodes count, except in the result of
  `Truss.remove_node`, whose upstream body keeps them inconsistently;
- floats compare within a relative tolerance of 1e-9.
"""
from __future__ import annotations

import itertools
import json
import math
import re
from typing import NamedTuple

MAX_NODES = 40000
MAX_DEPTH = 80
MAX_ITER = 200
# attributes that hold a value computed lazily from the object's other state
MEMO_SLOTS = frozenset({
    "_img", "_ker", "_starts_with_unity", "_is_sq_maxrank_HNF", "_QQ_matrix", "_QQ_col",
    "_mult_tab", "_test_factor", "_maximal_order", "_discriminant", "_nilradicals_mod_p",
    "_gb", "_gbe", "_is_confluent", "_var_dict",
})
AUTO_DUMMY = re.compile(r"Dummy_\d+")
# per class: the attribute that holds a process-wide creation counter
COUNTERS = {"sympy.physics.vector.frame.ReferenceFrame": "index"}
STATE_SKIP: dict = {}
# per class: lists kept in parallel with another attribute, left out for PARALLEL_LIST_UNITS only
PARALLEL_LISTS = {
    "sympy.physics.continuum_mechanics.truss.Truss": frozenset({"_node_position_x", "_node_position_y"}),
}
PARALLEL_LIST_UNITS = frozenset({"sympy/physics/continuum_mechanics/truss.py::Truss.remove_node"})
# units ("file::qualname") whose result is LaTeX, in which whitespace carries no meaning
LATEX_UNITS = frozenset({"sympy/printing/latex.py::multiline_latex", "sympy/physics/vector/printing.py::vlatex"})
# units whose result is a domain matrix in a given storage: the storage is the contract
STORAGE_UNITS = frozenset({
    "sympy/matrices/repmatrix.py::RepMatrix.to_DM",
    "sympy/polys/matrices/ddm.py::DDM.from_list_flat", "sympy/polys/matrices/ddm.py::DDM.from_flat_nz",
    "sympy/polys/matrices/ddm.py::DDM.from_dod", "sympy/polys/matrices/ddm.py::DDM.from_dok",
    "sympy/polys/matrices/ddm.py::DDM.to_sdm", "sympy/polys/matrices/ddm.py::DDM.diag",
    "sympy/polys/matrices/domainmatrix.py::DM", "sympy/polys/matrices/domainmatrix.py::DomainMatrix.from_list_sympy",
    "sympy/polys/matrices/domainmatrix.py::DomainMatrix.from_dict_sympy",
    "sympy/polys/matrices/domainmatrix.py::DomainMatrix.from_Matrix",
    "sympy/polys/matrices/domainmatrix.py::DomainMatrix.to_sparse", "sympy/polys/matrices/domainmatrix.py::DomainMatrix.to_dense",
    "sympy/polys/matrices/domainmatrix.py::DomainMatrix.to_ddm", "sympy/polys/matrices/domainmatrix.py::DomainMatrix.to_sdm",
    "sympy/polys/matrices/domainmatrix.py::DomainMatrix.from_list_flat",
    "sympy/polys/matrices/domainmatrix.py::DomainMatrix.diag", "sympy/polys/matrices/domainmatrix.py::DomainMatrix.ones",
    "sympy/polys/matrices/sdm.py::SDM.from_list", "sympy/polys/matrices/sdm.py::SDM.from_ddm",
    "sympy/polys/matrices/sdm.py::SDM.from_list_flat", "sympy/polys/matrices/sdm.py::SDM.from_dod",
    "sympy/polys/matrices/sdm.py::SDM.from_dok", "sympy/polys/matrices/sdm.py::SDM.to_ddm",
})


class Profile(NamedTuple):
    """What of a unit's result is compared beyond the default."""

    latex: bool = False            # whitespace LaTeX ignores is ignored
    storage: bool = False          # dense versus sparse storage counts
    parallel_lists: bool = True    # Truss's parallel coordinate lists count


STRICT = Profile()


def profile_of(unit_key: str) -> Profile:
    """The comparison profile of a unit, by "file::qualname"."""
    return Profile(latex=unit_key in LATEX_UNITS, storage=unit_key in STORAGE_UNITS,
                   parallel_lists=unit_key not in PARALLEL_LIST_UNITS)


class Uncanonical(Exception):
    pass


_ACTIVE = set()
_FIXED = set()        # identities of the Dummies and counted objects that came with the call's arguments
_COLLECT = None       # a set while dummies() collects, else None


def canon(obj, fixed=frozenset()):
    """The canonical form of `obj`; `fixed` holds the Dummies of the call's arguments (dummies())."""
    budget = [MAX_NODES]
    _ACTIVE.clear()
    _FIXED.clear()
    _FIXED.update(fixed)
    try:
        return _c(obj, 0, budget)
    finally:
        _FIXED.clear()


def dummies(obj) -> frozenset:
    """Identities of every Dummy and counted object (COUNTERS) the canonical form of `obj` reaches."""
    global _COLLECT
    _COLLECT = set()
    try:
        canon(obj)
    except Exception:  # noqa: BLE001 - what was reached before the form gave up still counts
        pass
    finally:
        found, _COLLECT = frozenset(_COLLECT), None
    return found


_RENAMABLE = re.compile(r'("Dummy~", \[\["S", "(?:[^"\\]|\\.)*"\], \["S", "(?:[^"\\]|\\.)*"\], \["S", ")[^"]*"'
                        r'|(\["#", "made", ")[^"]*"')


def _key(node):
    """Sort key of a node; the identity of what the call made does not decide an order."""
    text = json.dumps(node, sort_keys=True)
    if '"Dummy~"' not in text and '"made"' not in text:
        return text
    return _RENAMABLE.sub(lambda m: (m.group(1) or m.group(2)) + '"', text)


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

    if mod.startswith("sympy.polys.matrices.") and t.__name__ in ("DDM", "SDM"):
        return _domain_matrix(o, t, depth, budget)
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


def _skipped(n, skip):
    return n.startswith("__") or "cache" in n or n == "_hash" or n in skip


def _counter(cls, value):
    """A creation counter's value: exact when the object came with the arguments."""
    ident = ("counter", cls, repr(value))
    if _COLLECT is not None:
        _COLLECT.add(ident)
    return ["#", "given" if _COLLECT is not None or ident in _FIXED else "made", repr(value)]


def _entry(n, value, depth, budget, counter=None):
    """One attribute of an object's state; a memo slot is marked, and kept when it can be expressed."""
    if n == counter:
        return [["S", n], _counter(counter, value)]
    if n not in MEMO_SLOTS:
        return [["S", n], _c(value, depth + 1, budget)]
    saved = budget[0]
    try:
        return [["S", "~" + n], _c(value, depth + 1, budget)]
    except Uncanonical:
        budget[0] = saved
        return [["S", "~" + n], ["?"]]


def _state(o, t, depth, budget):
    names = []
    for klass in t.__mro__:
        slots = klass.__dict__.get("__slots__", ())
        names += [slots] if isinstance(slots, str) else list(slots)
    cls = f"{t.__module__}.{t.__qualname__}"
    skip = STATE_SKIP.get(cls, frozenset())
    counter = COUNTERS.get(cls)
    state = []
    for n in sorted(set(names)):
        if n in ("__dict__", "__weakref__") or _skipped(n, skip):
            continue
        try:
            value = object.__getattribute__(o, n)
        except AttributeError:
            continue
        state.append(_entry(n, value, depth, budget, counter))
    d = getattr(o, "__dict__", None)
    if isinstance(d, dict):
        for n in sorted(k for k in d if isinstance(k, str)):
            if _skipped(n, skip):
                continue
            state.append(_entry(n, d[n], depth, budget, counter))
    return state


def _domain_matrix(o, t, depth, budget):
    """Shape, domain, every entry and the storage, read from the storage itself (no method of the
    object is called): "dense" (a list of rows), "sparse" (a dict of row dicts without zeros) or
    "sparse with zeros" (one that stores a zero, which no sparse matrix of SymPy's own does)."""
    d = vars(o)
    shape = d.get("shape")
    if not (isinstance(shape, tuple) and len(shape) == 2 and all(type(k) is int and k >= 0 for k in shape)):
        raise Uncanonical("domain matrix without a shape")
    rows, cols = shape
    if rows * cols > MAX_NODES:
        raise Uncanonical("too large")
    domain = d.get("domain")
    zero = getattr(domain, "zero", 0)
    if t.__name__ == "DDM":
        grid = list.__iter__(o)
        entries = [row[j] for row in grid for j in range(cols)]
        kind = "dense"
    else:
        entries, kind = [], "sparse"
        for i in range(rows):
            row = dict.get(o, i) or {}
            try:
                if any(v == zero for v in row.values()):
                    kind = "sparse with zeros"
            except Exception:  # noqa: BLE001 - an element that cannot be compared with zero is not one
                pass
            entries.extend(row.get(j, zero) for j in range(cols))
    return ["DM", rows, cols, _c(domain, depth + 1, budget), [_c(x, depth + 1, budget) for x in entries], kind]


def _f(x):
    x = float(x)
    if math.isnan(x):
        return ["F", "nan"]
    if math.isinf(x):
        return ["F", "inf" if x > 0 else "-inf"]
    return ["F", repr(x)]


def _assumptions(o):
    """The assumptions SymPy's equality and hash use, not the keywords the symbol was made with."""
    try:
        return json.dumps(sorted((str(k), bool(v)) for k, v in (object.__getattribute__(o, "_assumptions0") or ())))
    except Exception:  # noqa: BLE001
        return "[]"


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
        ident = ("dummy", o.name, getattr(o, "dummy_index", None))
        if _COLLECT is not None:
            _COLLECT.add(ident)
        if _COLLECT is not None or ident in _FIXED:
            # came with the arguments, which carry its name and index into every replay
            return ["X", "Dummy", [["S", o.name], ["S", _assumptions(o)], ["S", str(ident[2])]]]
        # made by the call: its name, if it was given one, and its identity within this result
        own = "" if AUTO_DUMMY.fullmatch(o.name or "") else o.name
        return ["X", "Dummy~", [["S", own], ["S", _assumptions(o)], ["S", str(ident[2])]]]
    if isinstance(o, (Symbol, Wild)):
        return ["X", name, [["S", o.name], ["S", _assumptions(o)]]]
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


_LATEX_SPACE = re.compile(r"\s+")
_LATEX_KEEP = re.compile(r"(\\[A-Za-z]+) (?=[A-Za-z])|(\\) ")


def latex_form(text: str) -> str:
    """LaTeX without the whitespace it ignores: a space is kept only where it ends a control word
    before a letter, or follows a lone backslash."""
    text = _LATEX_SPACE.sub(" ", text.strip())
    text = _LATEX_KEEP.sub(lambda m: (m.group(1) or m.group(2)) + "\0", text)
    return text.replace(" ", "").replace("\0", " ")


class _Context:
    __slots__ = ("rel", "abs_", "profile", "forward", "backward", "counted")

    def __init__(self, rel, abs_, profile):
        self.rel, self.abs_, self.profile = rel, abs_, profile
        self.forward, self.backward = {}, {}
        self.counted = {}   # counter value on one side -> on the other, for the objects the call made

    def in_order(self):
        """The objects the call made were made in the same order on both sides."""
        pairs = sorted(self.counted.items(), key=lambda kv: _number(kv[0]))
        return all(_number(a[1]) < _number(b[1]) for a, b in zip(pairs, pairs[1:]))

    def bind(self, x, y):
        """One renaming for the whole comparison: x and y stand for each other, and nothing else."""
        if self.forward.get(x, y) != y or self.backward.get(y, x) != x:
            return False
        self.forward[x], self.backward[y] = y, x
        return True


def _number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return float("nan")


def same(a, b, rel=1e-9, abs_=1e-12, profile=None):
    """Compare two canonical forms (see the module docstring); `profile` is the unit's (profile_of)."""
    ctx = _Context(rel, abs_, profile or STRICT)
    return _same(a, b, ctx) and ctx.in_order()


def _filled(node):
    return isinstance(node, list) and node not in (["N"], ["?"]) and not (
        len(node) == 2 and node[0] in ("D", "L", "T", "E") and node[1] == [])


def _same_state(a, b, ctx, cls):
    """Two objects' states: every attribute alike, a memo slot only where both hold a value."""
    if not (isinstance(a, list) and isinstance(b, list)):
        return False
    skip = PARALLEL_LISTS.get(cls, frozenset()) if not ctx.profile.parallel_lists else frozenset()
    left, right = {}, {}
    for side, out in ((a, left), (b, right)):
        for item in side:
            if not (isinstance(item, list) and len(item) == 2 and isinstance(item[0], list) and len(item[0]) == 2):
                return False
            name = item[0][1]
            if isinstance(name, str) and name not in skip:
                out[name] = item[1]
    plain = {n for n in left if not n.startswith("~")} | {n for n in right if not n.startswith("~")}
    for name in sorted(plain):
        if name not in left or name not in right or not _same(left[name], right[name], ctx):
            return False
    for name in sorted({n for n in left if n.startswith("~")} & {n for n in right if n.startswith("~")}):
        x, y = left[name], right[name]
        if not (_filled(x) and _filled(y)):
            continue
        if x[0] == "D" and y[0] == "D" and len(x) == 2 and len(y) == 2:
            # a dict of lazily filled values: the entries both sides hold
            xs, ys = {_key(k): v for k, v in x[1]}, {_key(k): v for k, v in y[1]}
            for k in sorted(set(xs) & set(ys)):
                if not _same(xs[k], ys[k], ctx):
                    return False
            continue
        if not _same(x, y, ctx):
            return False
    return True


def _same(a, b, ctx):
    if type(a) is not type(b):
        return False
    if isinstance(a, str):
        return a == b or (ctx.profile.latex and latex_form(a) == latex_form(b))
    if not isinstance(a, list):
        return a == b
    if a and b and a[0] == "EXC" and b[0] == "EXC":
        # same exception class, or one is a subclass of the other
        ca = set(a[2]) if len(a) > 2 and isinstance(a[2], list) else {a[1] if len(a) > 1 else None}
        cb = set(b[2]) if len(b) > 2 and isinstance(b[2], list) else {b[1] if len(b) > 1 else None}
        na, nb = (a[1] if len(a) > 1 else None), (b[1] if len(b) > 1 else None)
        return na is not None and nb is not None and (na in cb or nb in ca)
    if len(a) != len(b):
        return False
    head = a[0] if a and isinstance(a[0], str) else None
    if head is not None and b[0] != head:
        return False
    if head == "F" and len(a) == 2:
        try:
            x, y = float(a[1]), float(b[1])
        except (TypeError, ValueError):
            return a[1] == b[1]
        if math.isnan(x) or math.isnan(y):
            return math.isnan(x) and math.isnan(y)
        if math.isinf(x) or math.isinf(y):
            return x == y
        return abs(x - y) <= max(ctx.abs_, ctx.rel * max(abs(x), abs(y)))
    if head == "X" and len(a) == 3 and a[1] == "Dummy~" and b[1] == "Dummy~":
        try:
            (_, name_a), (_, ass_a), (_, id_a) = a[2]
            (_, name_b), (_, ass_b), (_, id_b) = b[2]
        except (TypeError, ValueError):
            return False
        return name_a == name_b and ass_a == ass_b and ctx.bind(id_a, id_b)
    if head == "#" and len(a) == 3:
        if a[1] != b[1]:
            return False
        if a[1] == "given":
            return a[2] == b[2]
        if not ctx.bind(("#", a[2]), ("#", b[2])):
            return False
        ctx.counted[a[2]] = b[2]
        return True
    if head == "DM" and len(a) == 6:
        if not all(_same(x, y, ctx) for x, y in zip(a[1:5], b[1:5])):
            return False
        if "sparse with zeros" in (a[5], b[5]) or ctx.profile.storage:
            return a[5] == b[5]
        return True
    if head == "O" and len(a) == 3:
        return a[1] == b[1] and _same_state(a[2], b[2], ctx, a[1])
    return all(_same(x, y, ctx) for x, y in zip(a, b))
