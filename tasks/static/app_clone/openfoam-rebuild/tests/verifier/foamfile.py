"""Reads OpenFOAM files (ascii or binary, optionally gzipped) into a tree.

    Dict  ordered (key, value) entries; key None for a bare top-level list
    value list of Word, Str, Num, Seq, Dict, Arr
    Seq   bracketed items: '(' list, '[' dimensions, '{' uniform list
    Arr   a numeric list as a numpy array
Files it cannot read this way (binary records of undeclared type) raise ParseError; the
comparer then requires them to be identical byte for byte.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field

import numpy as np


class Word(str):
    pass


class Str(str):
    pass


@dataclass
class Num:
    value: float
    text: str

    @property
    def is_int(self) -> bool:
        return re.fullmatch(r"[-+]?\d+", self.text) is not None


@dataclass
class Seq:
    kind: str
    items: list


@dataclass
class Arr:
    data: np.ndarray  # shape (n,) or (n, k)
    is_int: bool  # every element was written as an integer
    texts: (
        np.ndarray | None
    )  # ascii only: digits after the point, per element (for rounding)


@dataclass
class Dict:
    entries: list = field(default_factory=list)

    def get(self, key, default=None):
        for k, v in self.entries:
            if k == key:
                return v
        return default

    def keys(self):
        return [k for k, _ in self.entries]


class ParseError(ValueError):
    pass


# Components per element of types written as raw binary.
_NCOMP = {
    "scalar": 1,
    "vector": 3,
    "tensor": 9,
    "symmTensor": 6,
    "sphericalTensor": 1,
    "label": 1,
    "point": 3,
    "vector2D": 2,
    "tensor2D": 4,
    "symmTensor2D": 3,
    "complex": 2,
    "bool": 1,
}
# Element type of the top-level list, by file class.
_CLASS_TYPE = {
    "vectorField": "vector",
    "pointField": "vector",
    "scalarField": "scalar",
    "labelList": "label",
    "labelField": "label",
    "faceCompactList": "label",
    "tensorField": "tensor",
    "symmTensorField": "symmTensor",
    "sphericalTensorField": "sphericalTensor",
    "boolList": "bool",
    "cellZone": "label",
    "faceZone": "label",
    "pointZone": "label",
    "cellSet": "label",
    "faceSet": "label",
    "pointSet": "label",
}

_SPACE = b" \t\r\n\f\v"
_NUM_RE = re.compile(rb"[-+]?(\d+\.?\d*([eE][-+]?\d+)?|\.\d+([eE][-+]?\d+)?)")


class _Reader:
    def __init__(self, data: bytes):
        self.b = data
        self.i = 0
        self.binary = False
        self.label_bytes = 4
        self.scalar_bytes = 8
        self.file_class = None

    # ---- lexing ----
    def skip(self):
        b, n = self.b, len(self.b)
        while self.i < n:
            c = b[self.i]
            if c in _SPACE:
                self.i += 1
            elif b.startswith(b"//", self.i):
                j = b.find(b"\n", self.i)
                self.i = n if j < 0 else j + 1
            elif b.startswith(b"/*", self.i):
                j = b.find(b"*/", self.i + 2)
                if j < 0:
                    raise ParseError("unterminated comment")
                self.i = j + 2
            else:
                return

    def peek(self) -> bytes:
        self.skip()
        return self.b[self.i : self.i + 1]

    def token(self):
        """Next scalar token or punctuation (bytes of length 1)."""
        self.skip()
        b, n = self.b, len(self.b)
        if self.i >= n:
            return None
        c = b[self.i : self.i + 1]
        if c in (b"(", b")", b"{", b"}", b"[", b"]", b";"):
            self.i += 1
            return c
        if c == b'"':
            j = self.i + 1
            out = bytearray()
            while j < n and b[j : j + 1] != b'"':
                if b[j : j + 1] == b"\\" and j + 1 < n:
                    out += (
                        b[j + 1 : j + 2]
                        if b[j + 1 : j + 2] in (b'"', b"\\")
                        else b[j : j + 2]
                    )
                    j += 2
                else:
                    out += b[j : j + 1]
                    j += 1
            if j >= n:
                raise ParseError("unterminated string")
            self.i = j + 1
            return Str(out.decode("utf-8", "replace"))
        m = _NUM_RE.match(b, self.i)
        if m and (
            m.end() >= n
            or b[m.end()] in _SPACE
            or b[m.end() : m.end() + 1] in (b"(", b")", b"{", b"}", b"[", b"]", b";")
        ):
            self.i = m.end()
            t = m.group().decode()
            return Num(float(t), t)
        # word: up to a delimiter; parentheses inside a word are kept while balanced
        j, depth = self.i, 0
        while j < n:
            ch = b[j : j + 1]
            if ch in (
                b" ",
                b"\t",
                b"\r",
                b"\n",
                b"\f",
                b"\v",
                b";",
                b"{",
                b"}",
                b"[",
                b"]",
                b'"',
            ):
                break
            if ch == b"(":
                if j == self.i:
                    break
                depth += 1
            elif ch == b")":
                if depth == 0:
                    break
                depth -= 1
            j += 1
        if j == self.i:
            raise ParseError(f"unexpected byte {b[self.i : self.i + 1]!r} at {self.i}")
        w = b[self.i : j]
        if any(c < 32 or c > 126 for c in w):
            raise ParseError(f"binary data where text was expected at {self.i}")
        self.i = j
        return Word(w.decode())

    # ---- structure ----
    def parse_file(self) -> Dict:
        top = Dict()
        while True:
            self.skip()
            if self.i >= len(self.b):
                return top
            if self.peek() in (b"(",) or _NUM_RE.match(self.b, self.i):
                # bare top-level list (mesh files, sets, zones)
                top.entries.append((None, self.value_until_end()))
                continue
            key = self.token()
            if isinstance(key, bytes):
                raise ParseError(f"unexpected {key!r} at top level")
            top.entries.append((key, self.entry_value(key)))
            if key == "FoamFile":
                self.read_header(top.entries[-1][1])
                if self.file_class == "decomposedBlockData":
                    top.entries.append((None, self.blocks()))
                    return top

    def blocks(self) -> list:
        """Collated file: one sized block per processor. Blocks without their own header take
        the format and class of the file's data.format and data.class."""
        out = []
        hdr = self.header
        ctx = {
            "binary": str((hdr.get(Word("data.format")) or ["ascii"])[0]) == "binary",
            "file_class": str((hdr.get(Word("data.class")) or [None])[0]),
            "label_bytes": self.label_bytes,
            "scalar_bytes": self.scalar_bytes,
        }
        while True:
            self.skip()
            if self.i >= len(self.b):
                return out
            n = self.token()
            if not isinstance(n, Num) or not n.is_int or self.peek() != b"(":
                raise ParseError("malformed collated block")
            self.i += 1
            size = int(n.value)
            raw = self.b[self.i : self.i + size]
            if len(raw) != size or self.b[self.i + size : self.i + size + 1] != b")":
                raise ParseError("collated block truncated")
            self.i += size + 1
            out.append(parse(raw, ctx))

    def read_header(self, value):
        d = value[0] if value and isinstance(value[0], Dict) else None
        if d is None:
            return
        self.header = d
        fmt = d.get(Word("format"))
        self.binary = bool(fmt) and str(fmt[0]) == "binary"
        cls = d.get(Word("class"))
        self.file_class = str(cls[0]) if cls else None
        arch = d.get(Word("arch"))
        if arch:
            m = re.search(r"label=(\d+)", str(arch[0]))
            if m:
                self.label_bytes = int(m.group(1)) // 8
            m = re.search(r"scalar=(\d+)", str(arch[0]))
            if m:
                self.scalar_bytes = int(m.group(1)) // 8

    def entry_value(self, key) -> list:
        """Value of a dictionary entry: a sub-dictionary, or items up to ';'."""
        if self.peek() == b"{":
            self.token()
            return [self.dict_body()]
        if isinstance(key, Word) and key.startswith("#"):
            t = self.token()  # directive: one argument, no ';'
            return [t]
        items = []
        hint = None
        while True:
            if self.peek() == b";":
                self.token()
                return items
            if self.peek() == b"}" or self.peek() == b"":
                raise ParseError(f"entry {key!r} not terminated by ';'")
            item = self.item(hint, items)
            if isinstance(item, Word) and item.startswith("List<"):
                hint = item[5:-1]
            items.append(item)

    def value_until_end(self) -> list:
        items = []
        while self.peek() not in (b"",):
            if self.peek() == b";":
                self.token()
                continue
            items.append(self.item(_class_type(self.file_class), items))
        return items

    def dict_body(self) -> Dict:
        d = Dict()
        while True:
            c = self.peek()
            if c == b"}":
                self.token()
                return d
            if c == b"":
                raise ParseError("unterminated dictionary")
            key = self.token()
            if isinstance(key, bytes):
                raise ParseError(f"unexpected {key!r} in dictionary")
            d.entries.append((key, self.entry_value(key)))

    def item(self, hint, prev):
        c = self.peek()
        if c == b"(":
            n = (
                prev[-1]
                if prev and isinstance(prev[-1], Num) and prev[-1].is_int
                else None
            )
            if self.binary and n is not None:
                a = self.binary_list(int(n.value), hint)
                if a is not None:
                    return a
            self.token()
            return self.seq_body(")", "(")
        if c == b"[":
            self.token()
            return self.seq_body("]", "[")
        if c == b"{":
            self.token()
            if prev and isinstance(prev[-1], Num):
                return self.seq_body("}", "{")  # uniform list N{value}
            return self.dict_body()
        t = self.token()
        if isinstance(t, bytes):
            raise ParseError(f"unexpected {t!r} at {self.i}")
        return t

    def seq_body(self, close: str, kind: str):
        items = []
        while True:
            c = self.peek()
            if c == close.encode():
                self.token()
                return _as_array(kind, items)
            if c == b"":
                raise ParseError(f"unterminated '{kind}'")
            if c == b"{" and items and isinstance(items[-1], (Word, Str)):
                self.token()
                items.append(
                    self.dict_body()
                )  # named dictionary inside a list (boundary)
                continue
            items.append(self.item(None, items))

    def _dtype(self, typ):
        if typ == "label":
            return np.dtype(f"<i{self.label_bytes}")
        if typ == "bool":
            return np.dtype("u1")
        return np.dtype(f"<f{self.scalar_bytes}")

    def binary_list(self, n: int, typ):
        """N values of a declared type as raw bytes, or None if the list is written as text
        (OpenFOAM writes some lists as text in binary files)."""
        if typ not in _NCOMP:
            return None
        self.skip()
        start = self.i + 1
        dt, k = self._dtype(typ), _NCOMP[typ]
        end = start + n * k * dt.itemsize
        if self.b[end : end + 1] != b")":
            return None
        self.i = end + 1
        a = np.frombuffer(self.b[start:end], dtype=dt).astype(
            np.int64 if dt.kind in "iu" else np.float64
        )
        return Arr(a.reshape(n, k) if k > 1 else a, dt.kind in "iu", None)


def _class_type(cls):
    """Element type of a file's top-level list, e.g. labelList, vectorIOField -> label, vector."""
    if cls in _CLASS_TYPE:
        return _CLASS_TYPE[cls]
    m = re.fullmatch(r"(\w+?)(?:IO)?(?:List|Field)", cls or "")
    return m.group(1) if m and m.group(1) in _NCOMP else None


def _decimals(t: str) -> int:
    """Digits after the point in a written number, counting the exponent (1.5e-3 -> 4)."""
    m = re.fullmatch(r"[-+]?(\d*)\.?(\d*)(?:[eE]([-+]?\d+))?", t)
    if not m:
        return 0
    return len(m.group(2)) - int(m.group(3) or 0)


def _as_array(kind: str, items: list):
    """Turns a list of numbers, or of equal-length number tuples, into an Arr."""
    if kind == "(" and items:
        if all(isinstance(x, Num) for x in items):
            return Arr(
                np.array([x.value for x in items]),
                all(x.is_int for x in items),
                np.array([_decimals(x.text) for x in items]),
            )
        if all(isinstance(x, Arr) and x.data.ndim == 1 for x in items):
            k = len(items[0].data)
            if k and all(len(x.data) == k for x in items):
                return Arr(
                    np.stack([x.data for x in items]),
                    all(x.is_int for x in items),
                    np.stack([x.texts for x in items]),
                )
    return Seq(kind, items)


def parse(data: bytes, context: dict | None = None) -> Dict:
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    r = _Reader(data)
    for k, v in (context or {}).items():
        setattr(r, k, v)
    return r.parse_file()


def read(path) -> Dict:
    with open(path, "rb") as f:
        return parse(f.read())
