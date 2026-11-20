"""The recorded-call comparison grades behaviour, and nothing looser: what is left out cannot
hide a wrong answer, and a value keeps its type and its container.

The verifier's own `canon.py` (and, for a call that changes an argument, its own `rvector.py`) runs
here against a stand-in `sympy` package that supplies the classes it imports; objects are plain
Python classes placed in SymPy's module names.
"""

from __future__ import annotations

import json
import pickle
import subprocess
import sys

STANDIN = {
    "sympy/__init__.py": "",
    "sympy/core/__init__.py": "",
    "sympy/core/basic.py": "class Basic:\n    args = ()\n",
    "sympy/core/cache.py": "def clear_cache():\n    pass\n",
    "sympy/core/containers.py": ("from sympy.core.basic import Basic\n\n\nclass Tuple(Basic):\n"
                                 "    def __init__(self, *args):\n        self.args = args\n"),
    "sympy/core/numbers.py": (
        "from sympy.core.basic import Basic\n\n\n"
        "class Rational(Basic):\n"
        "    def __init__(self, p, q=1):\n        self.p, self.q = p, q\n\n\n"
        "class Integer(Rational):\n"
        "    def __init__(self, p):\n        super().__init__(p, 1)\n\n\n"
        "class Float(Basic):\n"
        "    def __init__(self, mpf, prec):\n        self._mpf_, self._prec = mpf, prec\n"),
    "sympy/core/symbol.py": (
        "from sympy.core.basic import Basic\n\n\n"
        "class Symbol(Basic):\n"
        "    def __init__(self, name, **assumptions):\n"
        "        self.name = name\n"
        "        self._assumptions0 = tuple(sorted(dict(assumptions, commutative=True).items()))\n\n\n"
        "class Dummy(Symbol):\n"
        "    _count = 0\n\n"
        "    def __init__(self, name=None, dummy_index=None, **assumptions):\n"
        "        if name is None:\n"
        "            name = 'Dummy_' + str(Dummy._count)\n"
        "        if dummy_index is None:\n"
        "            dummy_index = 5000 + Dummy._count\n"
        "            Dummy._count += 1\n"
        "        super().__init__(name, **assumptions)\n"
        "        self.dummy_index = dummy_index\n\n\n"
        "class Wild(Symbol):\n    pass\n"),
    "sympy/external/__init__.py": "",
    "sympy/external/pythonmpq.py": ("class PythonMPQ:\n"
                                    "    def __init__(self, p, q):\n        self.numerator, self.denominator = p, q\n"),
    "sympy/logic/__init__.py": "",
    "sympy/logic/boolalg.py": ("from sympy.core.basic import Basic\n\n\nclass BooleanTrue(Basic):\n    pass\n\n\n"
                               "class BooleanFalse(Basic):\n    pass\n"),
    "sympy/matrices/__init__.py": "",
    "sympy/matrices/matrixbase.py": (
        "class MatrixBase:\n"
        "    def __init__(self, rows, cols, entries):\n        self.rows, self.cols, self._entries = rows, cols, entries\n\n"
        "    def __getitem__(self, key):\n        return self._entries[key[0] * self.cols + key[1]]\n\n\n"
        "class MutableDenseMatrix(MatrixBase):\n    pass\n\n\n"
        "class ImmutableDenseMatrix(MatrixBase):\n    pass\n\n\n"
        "class MutableSparseMatrix(MatrixBase):\n    pass\n"),
}

PROBE = r"""
import collections, fractions, json, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from canon import canon, dummies, profile_of, same, same_loose
from sympy.core.basic import Basic
from sympy.core.containers import Tuple
from sympy.core.numbers import Float, Integer, Rational
from sympy.core.symbol import Dummy, Symbol
from sympy.external.pythonmpq import PythonMPQ
from sympy.logic.boolalg import BooleanFalse, BooleanTrue
from sympy.matrices.matrixbase import ImmutableDenseMatrix, MutableDenseMatrix, MutableSparseMatrix

def place(cls, module):
    cls.__module__ = module
    return cls

class Add(Basic):
    def __init__(self, *args):
        self.args = args
class Mul(Add):
    pass

class Homomorphism:
    def __init__(self, matrix, img=None, ker=None):
        self.matrix, self._img, self._ker = matrix, img, ker
place(Homomorphism, "sympy.polys.agca.homomorphisms")

class ReferenceFrame:
    def __init__(self, name, index, var_dict=None):
        self.name, self.index, self._var_dict = name, index, var_dict or {}
place(ReferenceFrame, "sympy.physics.vector.frame")

class Truss:
    def __init__(self, positions, ys):
        self._node_positions, self._node_position_y = positions, ys
place(Truss, "sympy.physics.continuum_mechanics.truss")

class DDM(list):
    def __init__(self, rows, shape, domain):
        super().__init__(rows)
        self.shape, self.rows, self.cols, self.domain = shape, shape[0], shape[1], domain
place(DDM, "sympy.polys.matrices.ddm")

class SDM(dict):
    def __init__(self, elems, shape, domain):
        super().__init__(elems)
        self.shape, self.rows, self.cols, self.domain = shape, shape[0], shape[1], domain
place(SDM, "sympy.polys.matrices.sdm")

class DiophantineSolutionSet(set):
    pass

def unit(name):
    return profile_of(name)

TRUSS_REMOVE = unit("sympy/physics/continuum_mechanics/truss.py::Truss.remove_node")
LATEX = unit("sympy/printing/latex.py::multiline_latex")
dense, sparse = DDM([[1, 0], [0, 3]], (2, 2), "ZZ"), SDM({0: {0: 1}, 1: {1: 3}}, (2, 2), "ZZ")
zeros_stored = SDM({0: {0: 1, 1: 0}, 1: {1: 3}}, (2, 2), "ZZ")
I1, I2, I3, I4 = Integer(1), Integer(2), Integer(3), Integer(4)
cells = [I1, I2, I3, I4]
true, false = BooleanTrue(), BooleanFalse()
# 1.25 at 66 bits (20 digits) and at 53 bits; a 53-bit value one unit in the 40th bit away
f66, f53 = Float((0, 5, -2, 3), 66), Float((0, 5, -2, 3), 53)
f53_close = Float((0, (5 << 40) + 1, -42, 43), 53)
f53_far = Float((0, (5 << 20) + 1, -22, 23), 53)

# Dummies that came with the call's arguments keep their names; those the call made compare up to
# one consistent renaming
x, y = Dummy("Dummy_1", 101), Dummy("Dummy_2", 102)
given = dummies([x, y])
u, v = Dummy("t", 201), Dummy("t", 202)   # two given Dummies of one name
given_same = dummies([u, v])
d1, d2, e1, e2 = Dummy(), Dummy(), Dummy(), Dummy()
out = {
    "given_dummies_trade_places": same(canon(Add(x, Mul(-1, y)), given), canon(Add(y, Mul(-1, x)), given)),
    "given_dummies_alike": same(canon(Add(x, Mul(-1, y)), given), canon(Add(x, Mul(-1, y)), given)),
    "given_namesakes_trade_places": same(canon(Add(u, Mul(-1, v)), given_same), canon(Add(v, Mul(-1, u)), given_same)),
    "made_dummies_renamed": same(canon((d1, Add(d1, d2), d2)), canon((e1, Add(e1, e2), e2))),
    "made_dummies_merged": same(canon((d1, d2, d1)), canon((e1, e1, e1))),
    "made_dummy_for_given": same(canon(Add(x, 1), given), canon(Add(d1, 1), given)),
    "made_dummies_in_a_set": same(canon({Add(d1, 1), Mul(2, d2)}), canon({Add(e1, 1), Mul(2, e2)})),
    "named_made_dummy": same(canon(Dummy("u")), canon(Dummy("u"))),
    "named_made_dummy_renamed": same(canon(Dummy("u")), canon(Dummy("v"))),
    "dummy_assumptions": same(canon(Dummy(positive=True)), canon(Dummy())),
    "symbol_keywords": same(canon(Symbol("x", commutative=True)), canon(Symbol("x"))),
    "symbol_assumptions": same(canon(Symbol("x", real=True)), canon(Symbol("x"))),
    "float_in_a_child": same(canon((0.1, 0.2)), canon((0.1 + 1e-12, 0.2))),
    # a memo slot counts where both sides hold a value; an empty one is never wrong
    "memo_left_empty": same(canon(Homomorphism([1, 2], img="filled", ker="filled")), canon(Homomorphism([1, 2]))),
    "memo_wrong": same(canon(Homomorphism([1, 2], img="right")), canon(Homomorphism([1, 2], img="wrong"))),
    "memo_dict_more_keys": same(canon(ReferenceFrame("A", 1, {"a": 1})), canon(ReferenceFrame("A", 1, {"a": 1, "b": 2}))),
    "memo_dict_wrong_value": same(canon(ReferenceFrame("A", 1, {"a": 1})), canon(ReferenceFrame("A", 1, {"a": 2}))),
    "memo_real_state": same(canon(Homomorphism([1, 2])), canon(Homomorphism([1, 3]))),
    "counter": same(canon(ReferenceFrame("A", 7)), canon(ReferenceFrame("A", 9))),
    # frames the call made, numbered in the same order or swapped; a made copy for a given frame
    "counter_made_renumbered": same(canon([ReferenceFrame("A", 7), ReferenceFrame("B", 8)]),
                                    canon([ReferenceFrame("A", 17), ReferenceFrame("B", 18)])),
    "counter_made_swapped": same(canon([ReferenceFrame("A", 7), ReferenceFrame("B", 8)]),
                                 canon([ReferenceFrame("A", 18), ReferenceFrame("B", 17)])),
    "counter_given_copy": same(canon(ReferenceFrame("A", 7), dummies(ReferenceFrame("A", 7))),
                               canon(ReferenceFrame("A", 9), dummies(ReferenceFrame("A", 7)))),
    "parallel_list": same(canon(Truss([(0, 0), (2, 2)], [2, 0])), canon(Truss([(0, 0), (2, 2)], [0, 2]))),
    "parallel_list_remove_node": same(canon(Truss([(0, 0), (2, 2)], [2, 0])), canon(Truss([(0, 0), (2, 2)], [0, 2])), profile=TRUSS_REMOVE),
    "positions_differ_remove_node": same(canon(Truss([(0, 0), (2, 2)], [0])), canon(Truss([(0, 0), (2, 3)], [0])), profile=TRUSS_REMOVE),
    # domain-matrix storage counts for every unit (DomainMatrix.nullspace returning dense storage for sparse input)
    "storage_everywhere": same(canon(dense), canon(sparse)),
    "storage_alike": same(canon(sparse), canon(SDM({0: {0: 1}, 1: {1: 3}}, (2, 2), "ZZ"))),
    "zeros_stored": same(canon(sparse), canon(zeros_stored)),
    "zeros_stored_dense": same(canon(dense), canon(zeros_stored)),
    "entries_differ": same(canon(dense), canon(SDM({0: {0: 1}, 1: {1: 4}}, (2, 2), "ZZ"))),
    "whitespace_runs": same(canon("a  b \n"), canon("a b")),
    "trailing_newline": same(canon("tree\n"), canon("tree")),
    "latex_spacing": same(canon("x &- a"), canon("x & - a"), profile=LATEX),
    "latex_lines": same(canon("\\begin{align*}\nx &= y\n\\end{align*}"), canon("\\begin{align*} x &= y \\end{align*}"), profile=LATEX),
    "latex_control_word": same(canon("\\alpha x"), canon("\\alphax"), profile=LATEX),
    "latex_sign": same(canon("x = a + b"), canon("x = a - b"), profile=LATEX),
    "latex_elsewhere": same(canon("x &- a"), canon("x & - a")),
    # a blank line is a paragraph break, which LaTeX rejects inside align* (multiline_latex with blank lines)
    "latex_paragraph": same(canon("x &= a \\\\\ny &= b"), canon("x &= a \\\\\n\ny &= b"), profile=LATEX),
    "list_vs_tuple": same(canon([1, 2]), canon((1, 2))),
    # a value keeps its type: nP returning an int, right_open a bool, a list of Tuple for tuple ...
    "int_vs_Integer": same(canon(20), canon(Integer(20))),
    "Integer_alike": same(canon(Integer(20)), canon(Integer(20))),
    "bool_vs_true": same(canon(True), canon(true)),
    "false_vs_true": same(canon(false), canon(true)),
    "tuple_vs_Tuple": same(canon((I1, I2)), canon(Tuple(I1, I2))),
    "Fraction_vs_Rational": same(canon(fractions.Fraction(1, 3)), canon(Rational(1, 3))),
    "PythonMPQ_vs_Rational": same(canon(PythonMPQ(1, 3)), canon(Rational(1, 3))),
    "PythonMPQ_vs_Fraction": same(canon(PythonMPQ(1, 3)), canon(fractions.Fraction(1, 3))),
    "float_vs_Float": same(canon(1.25), canon(f53)),
    # ... banded returning a dense Matrix where upstream returns a SparseMatrix, to_matrix a mutable one
    "dense_vs_sparse_matrix": same(canon(MutableSparseMatrix(2, 2, cells)), canon(MutableDenseMatrix(2, 2, cells))),
    "mutable_vs_immutable_matrix": same(canon(ImmutableDenseMatrix(2, 2, cells)), canon(MutableDenseMatrix(2, 2, cells))),
    "matrix_alike": same(canon(ImmutableDenseMatrix(2, 2, cells)), canon(ImmutableDenseMatrix(2, 2, list(cells)))),
    # ... gauss_laguerre evaluating at the default precision whatever n_digits asks for
    "float_precision": same(canon(f66), canon(f53)),
    "float_close_at_its_precision": same(canon(f53), canon(f53_close)),
    "float_far_at_its_precision": same(canon(f53), canon(f53_far)),
    # ... diop_solve returning a set subclass, as_coefficients_dict a dict, multiset a Counter
    "set_vs_frozenset": same(canon({1, 2}), canon(frozenset({1, 2}))),
    "set_vs_set_subclass": same(canon({1, 2}), canon(DiophantineSolutionSet({1, 2}))),
    "defaultdict_vs_dict": same(canon(collections.defaultdict(int, {1: 2})), canon({1: 2})),
    "defaultdict_factory": same(canon(collections.defaultdict(int, {1: 2})), canon(collections.defaultdict(list, {1: 2}))),
    "dict_vs_Counter": same(canon({1: 2}), canon(collections.Counter({1: 2}))),
    "dict_vs_OrderedDict": same(canon({1: 2}), canon(collections.OrderedDict({1: 2}))),
    "OrderedDict_order": same(canon(collections.OrderedDict([(1, 2), (3, 4)])), canon(collections.OrderedDict([(3, 4), (1, 2)]))),
    "dict_order": same(canon({1: 2, 3: 4}), canon({3: 4, 1: 2})),
    "list_vs_range": same(canon([0, 1]), canon(range(2))),
    "list_vs_dict_keys": same(canon([1]), canon({1: 2}.keys())),
    "generator_vs_iterator": same(canon(i for i in [1, 2]), canon(iter([1, 2]))),
    # what a table could answer is judged with the type left out (the build's documented results)
    "loose_int_Integer": same_loose(canon(20), canon(Integer(20))),
    "loose_matrices": same_loose(canon(MutableSparseMatrix(2, 2, cells)), canon(ImmutableDenseMatrix(2, 2, cells))),
    "loose_floats": same_loose(canon(1.25), canon(f66)),
    "loose_values_still_differ": same_loose(canon(20), canon(Integer(21))),
}
print(json.dumps(out))
"""

KEPT = ("given_dummies_alike", "made_dummies_renamed", "made_dummies_in_a_set", "named_made_dummy", "symbol_keywords",
        "float_in_a_child", "memo_left_empty", "memo_dict_more_keys", "counter", "counter_made_renumbered", "parallel_list_remove_node",
        "storage_alike", "latex_spacing", "latex_lines", "Integer_alike", "matrix_alike", "float_close_at_its_precision", "dict_order",
        "loose_int_Integer", "loose_matrices", "loose_floats")
TOLD_APART = ("given_dummies_trade_places", "given_namesakes_trade_places", "made_dummies_merged", "made_dummy_for_given", "named_made_dummy_renamed",
              "dummy_assumptions", "symbol_assumptions", "memo_wrong", "memo_dict_wrong_value", "memo_real_state", "counter_made_swapped", "counter_given_copy", "parallel_list",
              "positions_differ_remove_node", "storage_everywhere", "zeros_stored", "zeros_stored_dense", "entries_differ",
              "whitespace_runs", "trailing_newline", "latex_control_word", "latex_sign", "latex_elsewhere", "latex_paragraph", "list_vs_tuple",
              "int_vs_Integer", "bool_vs_true", "false_vs_true", "tuple_vs_Tuple", "Fraction_vs_Rational", "PythonMPQ_vs_Rational",
              "PythonMPQ_vs_Fraction", "float_vs_Float", "dense_vs_sparse_matrix", "mutable_vs_immutable_matrix", "float_precision",
              "float_far_at_its_precision", "set_vs_frozenset", "set_vs_set_subclass", "defaultdict_vs_dict", "defaultdict_factory",
              "dict_vs_Counter", "dict_vs_OrderedDict", "OrderedDict_order", "list_vs_range", "list_vs_dict_keys", "generator_vs_iterator",
              "loose_values_still_differ")


def standin(tmp_path):
    for rel, text in STANDIN.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    return tmp_path


def test_what_is_left_out_is_not_behaviour_and_hides_no_wrong_answer(tmp_path, task_root):
    standin(tmp_path)
    lib = task_root / "steps" / "01-restore-bodies" / "tests" / "verifier" / "lib"
    done = subprocess.run([sys.executable, "-I", "-B", "-c", PROBE, str(tmp_path), str(lib)], capture_output=True, text=True,
                          timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    got = json.loads(done.stdout)
    assert sorted(KEPT + TOLD_APART) == sorted(got), "every case is decided here"
    # alike: Dummies the call made under another name, keywords SymPy's equality ignores, a float
    # within tolerance, an empty cache, a creation counter renumbered in order, upstream's inconsistent lists in what
    # remove_node leaves, LaTeX whitespace, a dict's order; and, for the build, a type a printed result does not show
    assert all(got[name] for name in KEPT), {name: got[name] for name in KEPT}
    # told apart: given Dummies trading places, a renaming that merges two, assumptions, a wrong or
    # real value, objects made in another order or a copy for a given one, parallel lists elsewhere, storage, stored zeros, every
    # other whitespace, a LaTeX control word run into a letter or a paragraph break, and every type and container:
    # Python against SymPy numbers, booleans and tuples, the rationals, a matrix's class, a Float's precision,
    # the flavours of a set, a dict, a view, a range and an iterator
    assert not any(got[name] for name in TOLD_APART), {name: got[name] for name in TOLD_APART}


DEMO = '''class Holder:
    def __init__(self):
        self.matrix, self._img = [1], None


def counts(a):
    """ddm_irref's shape: works on its argument in place and returns what it found"""
    a.append(1)
    return len(a)


def counts_on_a_copy(a):
    a = list(a)
    a.append(1)
    return len(a)


def pure(a):
    return len(a) + 1


def fills(h):
    h._img = "filled"
    return 1
'''

PAYLOAD = """import pickle, sys
sys.path[:0] = [sys.argv[1]]
from sympy.demo import Holder
units = {name: {"file": "sympy/demo.py", "qualname": name, "name": name, "occ": 0, "nocc": 1}
         for name in ("counts", "counts_on_a_copy", "pure", "fills")}
vectors = [("V1", "counts", pickle.dumps({"a": [5]})), ("V2", "counts_on_a_copy", pickle.dumps({"a": [5]})),
           ("V3", "pure", pickle.dumps({"a": [5]})), ("V4", "fills", pickle.dumps({"h": Holder()}))]
with open(sys.argv[2], "wb") as handle:
    pickle.dump({"units": units, "vectors": vectors}, handle)
"""


def test_a_call_that_changes_an_argument_is_compared_with_its_result(tmp_path, task_root):
    tree = standin(tmp_path / "tree")
    (tree / "sympy" / "demo.py").write_text(DEMO)
    lib = task_root / "steps" / "01-restore-bodies" / "tests" / "verifier" / "lib"
    made = subprocess.run([sys.executable, "-I", "-B", "-c", PAYLOAD, str(tree), str(tmp_path / "in.pkl")], capture_output=True,
                          text=True, timeout=60)
    assert made.returncode == 0, made.stderr[-2000:]
    done = subprocess.run([sys.executable, "-I", "-B", str(lib / "rvector.py"), str(tree), "sympy.demo", str(tmp_path / "in.pkl"),
                           str(tmp_path / "out.jsonl"), "5"], capture_output=True, text=True, timeout=120, cwd=tree)
    assert done.returncode == 0, done.stderr[-2000:]
    got = {rec["v"]: rec["c"] for rec in map(json.loads, (tmp_path / "out.jsonl").read_text().splitlines()) if "v" in rec}
    assert got["V1"] == ["RS", ["I", "2"], ["D", [[["S", "a"], ["L", [["I", "5"], ["I", "1"]]]]]]], got["V1"]
    # a body that leaves the argument alone returns the same value, and is told apart by the state
    assert got["V2"] == got["V3"] == ["I", "2"] and got["V2"] != got["V1"]
    # a memo slot filled is no change: values kept only as a cache do not count
    assert got["V4"] == ["I", "1"], got["V4"]
