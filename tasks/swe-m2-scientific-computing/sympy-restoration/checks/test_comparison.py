"""The recorded-call comparison grades behaviour, and nothing looser: what is left out cannot
hide a wrong answer.

The verifier's own `canon.py` runs here against a stand-in `sympy` package that supplies the
classes it imports; objects are plain Python classes placed in SymPy's module names.
"""

from __future__ import annotations

import json
import subprocess
import sys

STANDIN = {
    "sympy/__init__.py": "",
    "sympy/core/__init__.py": "",
    "sympy/core/basic.py": "class Basic:\n    args = ()\n",
    "sympy/core/containers.py": "from sympy.core.basic import Basic\n\n\nclass Tuple(Basic):\n    pass\n",
    "sympy/core/numbers.py": ("from sympy.core.basic import Basic\n\n\nclass Rational(Basic):\n    pass\n\n\n"
                              "class Integer(Rational):\n    pass\n\n\nclass Float(Basic):\n    pass\n"),
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
    "sympy/logic/__init__.py": "",
    "sympy/logic/boolalg.py": "class BooleanTrue:\n    pass\n\n\nclass BooleanFalse:\n    pass\n",
    "sympy/matrices/__init__.py": "",
    "sympy/matrices/matrixbase.py": "class MatrixBase:\n    pass\n",
}

PROBE = r"""
import json, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from canon import canon, dummies, profile_of, same
from sympy.core.basic import Basic
from sympy.core.symbol import Dummy, Symbol

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

def unit(name):
    return profile_of(name)

TRUSS_REMOVE = unit("sympy/physics/continuum_mechanics/truss.py::Truss.remove_node")
TO_SDM = unit("sympy/polys/matrices/ddm.py::DDM.to_sdm")
LATEX = unit("sympy/printing/latex.py::multiline_latex")
dense, sparse = DDM([[1, 0], [0, 3]], (2, 2), "ZZ"), SDM({0: {0: 1}, 1: {1: 3}}, (2, 2), "ZZ")
zeros_stored = SDM({0: {0: 1, 1: 0}, 1: {1: 3}}, (2, 2), "ZZ")

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
    "dense_sparse": same(canon(dense), canon(sparse)),
    "dense_sparse_converter": same(canon(dense), canon(sparse), profile=TO_SDM),
    "sparse_converter": same(canon(sparse), canon(SDM({0: {0: 1}, 1: {1: 3}}, (2, 2), "ZZ")), profile=TO_SDM),
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
    "list_vs_tuple": same(canon([1, 2]), canon((1, 2))),
}
print(json.dumps(out))
"""

KEPT = ("given_dummies_alike", "made_dummies_renamed", "made_dummies_in_a_set", "named_made_dummy", "symbol_keywords",
        "float_in_a_child", "memo_left_empty", "memo_dict_more_keys", "counter", "counter_made_renumbered", "parallel_list_remove_node", "dense_sparse",
        "sparse_converter", "latex_spacing", "latex_lines")
TOLD_APART = ("given_dummies_trade_places", "given_namesakes_trade_places", "made_dummies_merged", "made_dummy_for_given", "named_made_dummy_renamed",
              "dummy_assumptions", "symbol_assumptions", "memo_wrong", "memo_dict_wrong_value", "memo_real_state", "counter_made_swapped", "counter_given_copy", "parallel_list",
              "positions_differ_remove_node", "dense_sparse_converter", "zeros_stored", "zeros_stored_dense", "entries_differ",
              "whitespace_runs", "trailing_newline", "latex_control_word", "latex_sign", "latex_elsewhere", "list_vs_tuple")


def test_what_is_left_out_is_not_behaviour_and_hides_no_wrong_answer(tmp_path, task_root):
    for rel, text in STANDIN.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    lib = task_root / "steps" / "01-restore-bodies" / "tests" / "verifier" / "lib"
    done = subprocess.run([sys.executable, "-I", "-B", "-c", PROBE, str(tmp_path), str(lib)], capture_output=True, text=True,
                          timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    got = json.loads(done.stdout)
    assert sorted(KEPT + TOLD_APART) == sorted(got), "every case is decided here"
    # alike: Dummies the call made under another name, keywords SymPy's equality ignores, a float
    # within tolerance, an empty cache, a creation counter renumbered in order, upstream's inconsistent lists in what
    # remove_node leaves, storage where it is not the contract, LaTeX whitespace
    assert all(got[name] for name in KEPT), {name: got[name] for name in KEPT}
    # told apart: given Dummies trading places, a renaming that merges two, assumptions, a wrong or
    # real value, objects made in another order or a copy for a given one, parallel lists elsewhere, storage where it is the contract, stored zeros, every
    # other whitespace, a LaTeX control word run into a letter, a container
    assert not any(got[name] for name in TOLD_APART), {name: got[name] for name in TOLD_APART}
