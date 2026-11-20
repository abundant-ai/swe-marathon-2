"""How a work tree is turned into its delivered form.

The delivered tree is built from the original skeleton by replacing, for every
restorable unit, the placeholder statement with the body found in the work tree
for the function of the same qualified name in the same file.  Nothing else
from the work tree is used.
"""
from __future__ import annotations

import ast
import json
import os
import re

PLACEHOLDER_RE = re.compile(r'^(\s*)raise NotImplementedError\("RESTORE (U\d{4})"\)\s*$')

DENY_MODULES = {
    "os", "sys", "subprocess", "importlib", "builtins", "ctypes", "gc", "inspect",
    "doctest", "pytest", "_pytest", "unittest", "traceback", "io", "pathlib", "shutil",
    "socket", "pickle", "marshal", "code", "codeop", "runpy", "pkgutil", "site",
    "atexit", "signal", "threading", "multiprocessing", "tempfile", "glob", "linecache",
    "pdb", "faulthandler", "resource", "mmap", "select", "asyncio", "concurrent",
    "urllib", "http", "ftplib", "smtplib", "zipfile", "tarfile", "zipimport", "imp",
    "hypothesis", "xdist", "coverage", "trace", "tracemalloc", "sysconfig", "platform",
}
DENY_MODULE_PREFIXES = (
    "sympy.testing", "sympy.conftest", "sympy.utilities.pytest", "sympy.utilities.runtests",
    "sympy.utilities.benchmarking", "sympy.utilities.randtest", "sympy.utilities.tmpfiles",
)
DENY_NAMES = {
    "eval", "exec", "compile", "open", "__import__", "globals", "locals", "vars",
    "breakpoint", "input", "exit", "quit", "__builtins__", "__loader__", "__spec__",
}
# module names that are also rejected when a body uses them as globals of its module
DENY_GLOBAL_MODULES = {
    "os", "sys", "subprocess", "importlib", "inspect", "builtins", "ctypes", "gc", "shutil",
    "socket", "pathlib", "pickle", "marshal", "signal", "threading", "multiprocessing",
    "tempfile", "atexit", "pdb", "io", "doctest", "pytest", "unittest", "traceback",
}
DENY_IMPORTED_NAMES = {"testing", "pytest", "runtests", "conftest", "benchmarking", "randtest", "tmpfiles"}
DENY_ATTRS = {
    "__globals__", "__builtins__", "__code__", "__closure__", "__subclasses__",
    "__loader__", "__spec__", "__getattribute__", "f_back", "f_globals", "f_locals",
    "f_builtins", "f_code", "tb_frame", "tb_next", "gi_frame", "cr_frame", "ag_frame",
    "_getframe", "settrace", "setprofile", "__stdout__", "__stderr__", "stdout", "stderr",
    "displayhook", "excepthook", "meta_path", "path_hooks",
}
MAX_SOURCE_BYTES = 4_000_000


def _bound_names(fn, nodes) -> set:
    bound = set()
    if fn is not None:
        for a in ast.walk(fn.args):
            if isinstance(a, ast.arg):
                bound.add(a.arg)
    for top in nodes:
        for n in ast.walk(top):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                bound.add(n.id)
            elif isinstance(n, ast.arg):
                bound.add(n.arg)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    bound.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, ast.ExceptHandler) and n.name:
                bound.add(n.name)
    return bound


def scan_body(nodes, fn=None) -> str | None:
    """Return a short reason if the body uses a construct that is never needed here."""
    bound = _bound_names(fn, nodes)
    for top in nodes:
        for n in ast.walk(top):
            if isinstance(n, ast.Import):
                for a in n.names:
                    root = a.name.split(".")[0]
                    if root in DENY_MODULES or a.name.startswith(DENY_MODULE_PREFIXES):
                        return f"import of '{a.name}'"
            elif isinstance(n, ast.ImportFrom):
                mod = n.module or ""
                root = mod.split(".")[0]
                if n.level == 0 and (root in DENY_MODULES or mod.startswith(DENY_MODULE_PREFIXES)):
                    return f"import from '{mod}'"
                if n.level and mod.split(".")[0] in ("testing", "conftest"):
                    return f"relative import from '{mod}'"
                for a in n.names:
                    if a.name in DENY_MODULES or a.name in DENY_IMPORTED_NAMES:
                        return f"import of '{a.name}' from '{mod}'"
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in bound:
                if n.id in DENY_NAMES:
                    return f"use of builtin '{n.id}'"
                if n.id in DENY_GLOBAL_MODULES:
                    return f"use of module '{n.id}'"
            elif isinstance(n, ast.Attribute) and n.attr in DENY_ATTRS:
                return f"attribute '.{n.attr}'"
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id in ("getattr", "setattr", "delattr", "hasattr") and len(n.args) >= 2
                  and isinstance(n.args[1], ast.Constant) and n.args[1].value in DENY_ATTRS):
                return f"attribute '.{n.args[1].value}'"
    return None


def rules_text() -> str:
    """The complete list of constructs a restored body may not use."""
    return "\n".join([
        "A restored body is rejected when it contains any of the following.",
        "",
        "Imports (also `from X import ...`):",
        "  " + ", ".join(sorted(DENY_MODULES)),
        "The same modules when they are already globals of the unit's module:",
        "  " + ", ".join(sorted(DENY_GLOBAL_MODULES)),
        "Imports of SymPy's testing code:",
        "  " + ", ".join(DENY_MODULE_PREFIXES) + "  (and the names " + ", ".join(sorted(DENY_IMPORTED_NAMES)) + ")",
        "Builtins, unless the body binds the name itself:",
        "  " + ", ".join(sorted(DENY_NAMES)),
        "Attributes (also through getattr/setattr/hasattr with a literal name):",
        "  " + ", ".join(sorted(DENY_ATTRS)),
    ])


def _doc_and_rest(fn):
    b = fn.body
    if (
        b
        and isinstance(b[0], ast.Expr)
        and isinstance(getattr(b[0], "value", None), ast.Constant)
        and isinstance(b[0].value.value, str)
    ):
        return b[0], b[1:]
    return None, b


def index_functions(tree) -> dict:
    """qualname -> list of FunctionDef nodes (module level and class level only)."""
    out: dict = {}

    def visit(node, prefix):
        for ch in node.body:
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.setdefault(prefix + ch.name, []).append(ch)
            elif isinstance(ch, ast.ClassDef):
                visit(ch, prefix + ch.name + ".")

    visit(tree, "")
    return out


def _is_placeholder(rest) -> bool:
    if len(rest) != 1 or not isinstance(rest[0], ast.Raise):
        return False
    exc = rest[0].exc
    if not isinstance(exc, ast.Call) or not isinstance(exc.func, ast.Name):
        return False
    if exc.func.id != "NotImplementedError" or len(exc.args) != 1:
        return False
    a = exc.args[0]
    return isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.startswith("RESTORE U")


def _body_lines(src_lines, fn, doc, rest, target_indent: str):
    first = rest[0]
    line = src_lines[first.lineno - 1]
    prefix = line[: len(line) - len(line.lstrip())]
    own_line = first.col_offset == len(prefix.encode("utf-8")) or first.col_offset == len(prefix)
    # the body starts right after the docstring, so comments and decorators that precede
    # the first statement belong to it
    start = min([d.lineno for d in getattr(first, "decorator_list", [])] + [first.lineno])
    if doc is not None and doc.end_lineno < start:
        start = doc.end_lineno + 1
    if own_line and start > fn.lineno:
        raw = src_lines[start - 1 : fn.end_lineno]
    else:
        # body shares a line with something else: rebuild from statement segments
        raw = []
        text = "\n".join(src_lines)
        prefix = ""
        for st in rest:
            seg = ast.get_source_segment(text, st)
            raw.extend((seg or "pass").split("\n"))
    if prefix == target_indent:
        return raw
    out = []
    for i, ln in enumerate(raw):
        if not ln.strip():
            out.append(ln)
        elif prefix and ln.startswith(prefix):
            out.append(target_indent + ln[len(prefix):])
        elif not prefix:
            out.append(target_indent + ln)
        else:
            out.append(ln)  # continuation inside a multi-line token; keep as is
    return out


def _split_key(q):
    occ, nocc = 0, 1
    if "#" in q:
        occ, nocc = (int(x) for x in q.split("#")[1].split("/"))
    return q.split("#")[0], occ, nocc


def _masked_dump(src: str, keys):
    """AST dump of `src` with the body of every unit replaced by `pass` (docstring kept)."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    funcs = index_functions(tree)
    for q in keys:
        name, occ, nocc = _split_key(q)
        nodes = funcs.get(name) or []
        if len(nodes) != nocc:
            return None
        fn = nodes[occ]
        doc, _rest = _doc_and_rest(fn)
        fn.body = ([doc] if doc is not None else []) + [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def transplant_file(skel_src: str, work_src: str | None, uids_by_qualname: dict):
    """Return (candidate_src, {uid: state}).

    state is one of: 'restored', 'todo', 'missing', 'syntax', 'rejected: <why>'.
    The candidate is guaranteed to differ from the skeleton only inside unit bodies.
    """
    states = {}
    bodies = {}
    tree = None
    if work_src is not None:
        # the same line model as the parser: CRLF and bare CR are line ends
        work_src = work_src.replace("\r\n", "\n").replace("\r", "\n")
    if work_src is None:
        for q, uid in uids_by_qualname.items():
            states[uid] = "missing"
    else:
        try:
            tree = ast.parse(work_src)
        except (SyntaxError, ValueError, RecursionError, MemoryError) as e:
            ln = getattr(e, "lineno", "?")
            for q, uid in uids_by_qualname.items():
                states[uid] = f"syntax: file does not parse (line {ln})"
    skel_lines = skel_src.split("\n")
    ph = {}
    for i, ln in enumerate(skel_lines):
        m = PLACEHOLDER_RE.match(ln)
        if m:
            ph[m.group(2)] = (i, m.group(1))
    if tree is not None:
        funcs = index_functions(tree)
        work_lines = work_src.split("\n")
        for q, uid in uids_by_qualname.items():
            name, occ, nocc = _split_key(q)
            nodes = funcs.get(name)
            if not nodes or len(nodes) != nocc:
                states[uid] = "missing"
                continue
            fn = nodes[occ]
            doc, rest = _doc_and_rest(fn)
            if not rest or _is_placeholder(rest):
                states[uid] = "todo"
                continue
            why = scan_body(rest, fn)
            if why:
                states[uid] = "rejected: " + why
                continue
            if uid not in ph:
                states[uid] = "missing"
                continue
            bodies[uid] = _body_lines(work_lines, fn, doc, rest, ph[uid][1])
            states[uid] = "restored"
    def splice(use):
        lines = list(skel_lines)
        for uid, (i, _ind) in sorted(ph.items(), key=lambda kv: -kv[1][0]):
            if uid in use:
                lines[i : i + 1] = bodies[uid]
        return "\n".join(lines)

    ref = _masked_dump(skel_src, uids_by_qualname) if bodies else None

    def sound(text):
        # compiles, and is the skeleton everywhere outside the unit bodies
        if ref is None or _masked_dump(text, uids_by_qualname) != ref:
            return False
        try:
            compile(text, "<candidate>", "exec", dont_inherit=True)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            return False
        return True

    if tree is not None:
        # edits outside the unit bodies do not reach the candidate; remember that there are some
        states["__outside__"] = _masked_dump(work_src, uids_by_qualname) != (
            ref if ref is not None else _masked_dump(skel_src, uids_by_qualname))
    cand = splice(bodies)
    if bodies and not sound(cand):
        # some transplanted body does not stay inside its function: keep the ones that do
        good = set()
        for uid in sorted(bodies):
            if sound(splice(good | {uid})):
                good.add(uid)
            else:
                states[uid] = "syntax: restored body does not fit in place"
        cand = splice(good)
    return cand, states


def load_units(path: str):
    units = json.load(open(path, encoding="utf-8"))
    byfile: dict = {}
    for u in units:
        key = u["qualname"]
        if u.get("nocc", 1) != 1:
            key = f'{key}#{u.get("occ", 0)}/{u["nocc"]}'
        byfile.setdefault(u["file"], {})[key] = u["uid"]
    return units, byfile


def build_candidate(skel_root: str, work_root: str, cand_root: str, byfile: dict, cache: dict | None = None,
                    withheld: dict | None = None):
    """Refresh candidate files for all unit-bearing files. Returns {uid: state}.

    work_root/<file> is read; skel_root/<file> is the original skeleton; the result is written to
    cand_root/<file>.  `cache` (mutable dict) memoises per-file results on (mtime_ns, size).
    A file named in `withheld` is not read: it keeps the skeleton, and its units get the state
    given there.
    """
    states = {}
    notes = []
    withheld = withheld or {}
    for rel, qmap in byfile.items():
        if rel in withheld:
            skel_src = open(os.path.join(skel_root, rel), encoding="utf-8").read()
            cp = os.path.join(cand_root, rel)
            os.makedirs(os.path.dirname(cp), exist_ok=True)
            with open(cp, "w", encoding="utf-8") as f:
                f.write(skel_src)
            states.update({uid: withheld[rel] for uid in qmap.values()})
            continue
        wp = os.path.join(work_root, rel)
        try:
            st = os.stat(wp)
            key = [st.st_mtime_ns, st.st_size]
        except OSError:
            st, key = None, None
        if cache is not None and key is not None:
            c = cache.get(rel)
            if c and c.get("key") == key:
                states.update(c["states"])
                if c.get("note"):
                    notes.append(c["note"])
                continue
        skel_src = open(os.path.join(skel_root, rel), encoding="utf-8").read()
        work_src = None
        if st is not None and not os.path.islink(wp) and os.path.isfile(wp) and st.st_size <= MAX_SOURCE_BYTES:
            try:
                work_src = open(wp, encoding="utf-8-sig").read()
            except (OSError, UnicodeDecodeError):
                work_src = None
        cand, fstates = transplant_file(skel_src, work_src, qmap)
        outside = bool(fstates.pop("__outside__", False))
        cp = os.path.join(cand_root, rel)
        try:
            old = open(cp, encoding="utf-8").read()
        except OSError:
            old = None
        if old != cand:
            os.makedirs(os.path.dirname(cp), exist_ok=True)
            tmp = cp + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(cand)
            os.replace(tmp, cp)
        note = None
        if outside:
            note = rel
            notes.append(rel)
        states.update(fstates)
        if cache is not None and key is not None:
            cache[rel] = {"key": key, "states": fstates, "note": note}
    return states, notes
