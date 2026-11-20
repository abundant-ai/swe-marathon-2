"""The recorded-call comparison grades behaviour: memo slots, a creation counter, parallel
bookkeeping lists, domain-matrix storage and whitespace runs do not decide a match.

The verifier's own `canon.py` runs here against a stand-in `sympy` package that supplies the two
base classes it imports; objects are plain Python classes placed in SymPy's module names.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

STANDIN = {
    "sympy/__init__.py": "",
    "sympy/core/__init__.py": "",
    "sympy/core/basic.py": "class Basic:\n    pass\n",
    "sympy/matrices/__init__.py": "",
    "sympy/matrices/matrixbase.py": "class MatrixBase:\n    pass\n",
}

PROBE = r"""
import json, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from canon import canon, same

def place(cls, module):
    cls.__module__ = module
    return cls

class Homomorphism:
    def __init__(self, matrix, img=None, ker=None):
        self.matrix, self._img, self._ker = matrix, img, ker
place(Homomorphism, "sympy.polys.agca.homomorphisms")

class ReferenceFrame:
    def __init__(self, name, index):
        self.name, self.index = name, index
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

out = {
    "memo": same(canon(Homomorphism([1, 2], img="filled", ker="filled")), canon(Homomorphism([1, 2]))),
    "memo_real_state": same(canon(Homomorphism([1, 2])), canon(Homomorphism([1, 3]))),
    "counter": same(canon(ReferenceFrame("A", 7)), canon(ReferenceFrame("A", 9))),
    "parallel_list": same(canon(Truss([(0, 0), (2, 2)], [2, 0])), canon(Truss([(0, 0), (2, 2)], [0, 2]))),
    "positions_differ": same(canon(Truss([(0, 0), (2, 2)], [0])), canon(Truss([(0, 0), (2, 3)], [0]))),
    "dense_sparse": same(canon(DDM([[1, 0], [0, 3]], (2, 2), "ZZ")), canon(SDM({0: {0: 1}, 1: {1: 3}}, (2, 2), "ZZ"))),
    "entries_differ": same(canon(DDM([[1, 0], [0, 3]], (2, 2), "ZZ")), canon(SDM({0: {0: 1}, 1: {1: 4}}, (2, 2), "ZZ"))),
    "whitespace_runs": same(canon("a  b \n"), canon("a b")),
    "token_spacing": same(canon("&- a"), canon("& - a")),
    "list_vs_tuple": same(canon([1, 2]), canon((1, 2))),
}
print(json.dumps(out))
"""


def test_state_that_is_not_behaviour_does_not_decide_a_match(tmp_path, task_root):
    for rel, text in STANDIN.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    lib = task_root / "steps" / "01-restore-bodies" / "tests" / "verifier" / "lib"
    done = subprocess.run([sys.executable, "-I", "-B", "-c", PROBE, str(tmp_path), str(lib)], capture_output=True, text=True,
                          timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    got = json.loads(done.stdout)
    # left out: lazily filled caches, a creation counter, a list kept beside the real positions,
    # the storage of a domain matrix, the length of a whitespace run
    assert got["memo"] and got["counter"] and got["parallel_list"] and got["dense_sparse"] and got["whitespace_runs"], got
    # still compared: real state, entries, the presence of a space between tokens, the container
    assert not (got["memo_real_state"] or got["positions_differ"] or got["entries_differ"] or got["token_spacing"]
                or got["list_vs_tuple"]), got
