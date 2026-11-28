"""How a work tree is turned into the form the build takes.

That tree is built from the blanked copy, as the recovery tooling marked it, by
replacing, for every restorable unit, its placeholder statement with the body
found in the work tree for the function of the same qualified name in the same
file.  Nothing else from the work tree is used.
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

PLACEHOLDER_RE = re.compile(
    r'^(\s*)raise NotImplementedError\("RESTORE (U\d{4})"\)\s*$'
)

DENY_MODULES = {
    "os",
    "sys",
    "subprocess",
    "importlib",
    "builtins",
    "ctypes",
    "gc",
    "inspect",
    "doctest",
    "pytest",
    "_pytest",
    "unittest",
    "traceback",
    "io",
    "pathlib",
    "shutil",
    "socket",
    "pickle",
    "marshal",
    "code",
    "codeop",
    "runpy",
    "pkgutil",
    "site",
    "atexit",
    "signal",
    "threading",
    "multiprocessing",
    "tempfile",
    "glob",
    "linecache",
    "pdb",
    "faulthandler",
    "resource",
    "mmap",
    "select",
    "asyncio",
    "concurrent",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "zipfile",
    "tarfile",
    "zipimport",
    "imp",
    "hypothesis",
    "xdist",
    "coverage",
    "trace",
    "tracemalloc",
    "sysconfig",
    "platform",
    "__main__",
    "posix",
    "nt",
    "pwd",
    "grp",
    "fcntl",
    "termios",
    "pty",
    "tty",
    "selectors",
    "ssl",
    # the same reach by another name, files by another door, and the means to rewrite or watch the interpreter
    "posixpath",
    "ntpath",
    "genericpath",
    "codecs",
    "fileinput",
    "logging",
    "gzip",
    "bz2",
    "lzma",
    "shelve",
    "dbm",
    "sqlite3",
    "webbrowser",
    "pydoc",
    "zipapp",
    "tkinter",
    "readline",
    "rlcompleter",
    "cProfile",
    "profile",
    "pstats",
    "timeit",
    "copyreg",
    "json",
    "hashlib",
    "hmac",
    "secrets",
}
# and every module whose top-level name starts with an underscore (the C cores of the modules above,
# such as _io, _thread or _posixsubprocess), but __future__
DENY_MODULE_PREFIXES = (
    "sympy.testing",
    "sympy.conftest",
    "sympy.utilities.pytest",
    "sympy.utilities.runtests",
    "sympy.utilities.benchmarking",
    "sympy.utilities.randtest",
    "sympy.utilities.tmpfiles",
    # SymPy's own ways to reach modules by name, to write files, to compile and to open viewers
    "sympy.external.importtools",
    "sympy.printing.preview",
    "sympy.printing.gtk",
    "sympy.utilities.autowrap",
    "sympy.utilities._compilation",
    "sympy.utilities.codegen",
    "sympy.plotting",
    "sympy.interactive",
)
DENY_NAMES = {
    "eval",
    "exec",
    "compile",
    "open",
    "__import__",
    "globals",
    "locals",
    "vars",
    "breakpoint",
    "input",
    "exit",
    "quit",
    "__builtins__",
    "__loader__",
    "__spec__",
    "preview",
    "autowrap",
    "ufuncify",
    "binary_function",
    "print_gtk",
    "attrgetter",
    "methodcaller",
}
# module names that are also refused when a body uses them as globals of its module
DENY_GLOBAL_MODULES = {
    "os",
    "sys",
    "subprocess",
    "importlib",
    "inspect",
    "builtins",
    "ctypes",
    "gc",
    "shutil",
    "socket",
    "pathlib",
    "pickle",
    "marshal",
    "signal",
    "threading",
    "multiprocessing",
    "tempfile",
    "atexit",
    "pdb",
    "io",
    "doctest",
    "pytest",
    "unittest",
    "traceback",
    "posix",
    "posixpath",
    "ntpath",
    "genericpath",
    "codecs",
    "logging",
    "json",
    "hashlib",
    "hmac",
}


def _denied_module(name: str) -> bool:
    root = name.split(".")[0]
    return (
        root in DENY_MODULES
        or (root.startswith("_") and root != "__future__")
        or name.startswith(DENY_MODULE_PREFIXES)
    )


DENY_IMPORTED_NAMES = {
    "testing",
    "pytest",
    "runtests",
    "conftest",
    "benchmarking",
    "randtest",
    "tmpfiles",
    "preview",
    "autowrap",
    "ufuncify",
    "binary_function",
    "print_gtk",
    "attrgetter",
    "methodcaller",
    "importtools",
    "plotting",
    "interactive",
}
DENY_ATTRS = {
    "__globals__",
    "__builtins__",
    "__code__",
    "__closure__",
    "__subclasses__",
    "__loader__",
    "__spec__",
    "__getattribute__",
    "f_back",
    "f_globals",
    "f_locals",
    "f_builtins",
    "f_code",
    "tb_frame",
    "tb_next",
    "gi_frame",
    "cr_frame",
    "ag_frame",
    "_getframe",
    "settrace",
    "setprofile",
    "__stdout__",
    "__stderr__",
    "stdout",
    "stderr",
    "displayhook",
    "excepthook",
    "meta_path",
    "path_hooks",
    # a module's own handle on the process, the interpreter or the files: no body of SymPy 1.14.0 needs one
    "os",
    "_os",
    "sys",
    "modules",
    "__traceback__",
    "tb_lineno",
    "f_trace",
    "testing",
    "runtests",
    "importtools",
    "_compilation",
    "autowrap",
    "plotting",
    "interactive",
    "gtk",
    "pytest",
    "conftest",
    "preview",
    "attrgetter",
    "methodcaller",
    "open",
    "write",
    "writelines",
    "popen",
    "fork",
    "kill",
    "unlink",
    "rmtree",
    "mkdir",
    "makedirs",
    "rename",
    "chmod",
    "chdir",
    "putenv",
    "environ",
    "_exit",
    "abort",
}
# functions that reach an attribute or a module by a name given as a string: a literal name on the
# lists above is refused there too
NAME_CALLS = {"getattr", "setattr", "delattr", "hasattr", "attrgetter", "methodcaller"}
MODULE_CALLS = {"import_module", "__import__"}
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
                    if _denied_module(a.name):
                        return f"import of '{a.name}'"
            elif isinstance(n, ast.ImportFrom):
                mod = n.module or ""
                if n.level == 0 and _denied_module(mod):
                    return f"import from '{mod}'"
                if n.level and mod.split(".")[0] in ("testing", "conftest"):
                    return f"relative import from '{mod}'"
                for a in n.names:
                    if a.name in DENY_MODULES or a.name in DENY_IMPORTED_NAMES:
                        return f"import of '{a.name}' from '{mod}'"
            elif (
                isinstance(n, ast.Name)
                and isinstance(n.ctx, ast.Load)
                and n.id not in bound
            ):
                if n.id in DENY_NAMES:
                    return f"use of builtin '{n.id}'"
                if n.id in DENY_GLOBAL_MODULES:
                    return f"use of module '{n.id}'"
            elif isinstance(n, ast.Attribute) and n.attr in DENY_ATTRS:
                return f"attribute '.{n.attr}'"
            elif isinstance(n, ast.Subscript) and _denied_entry(n.slice):
                return f"literal key '{n.slice.value}'"
            elif isinstance(n, ast.Call):
                called = (
                    n.func.id
                    if isinstance(n.func, ast.Name)
                    else n.func.attr
                    if isinstance(n.func, ast.Attribute)
                    else None
                )
                literals = [
                    a.value
                    for a in n.args
                    if isinstance(a, ast.Constant) and isinstance(a.value, str)
                ]
                if (
                    called in KEY_CALLS
                    and isinstance(n.func, ast.Attribute)
                    and n.args
                    and _denied_entry(n.args[0])
                ):
                    return f"literal key '{n.args[0].value}'"
                if called in NAME_CALLS:
                    for name in literals:
                        if any(part in DENY_ATTRS for part in name.split(".")):
                            return f"attribute '.{name}'"
                elif (
                    called in MODULE_CALLS and literals and _denied_module(literals[0])
                ):
                    return f"import of '{literals[0]}'"
    return None


# methods that take a key: a literal name on the lists above given to one is refused, whatever holds it
# (a namespace from `x.__dict__`, from `getattr(x, '__dict__')` or kept in a variable, or any mapping)
KEY_CALLS = {"get", "pop", "setdefault", "__getitem__", "__setitem__", "__delitem__"}


def _denied_entry(node) -> bool:
    """A literal key that names something on the lists: a module, a builtin, an attribute (`x['os']`,
    `d.get('__builtins__')`, `getattr(m, '__dict__')['open']`), whatever holds it."""
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return False
    name = node.value
    return (
        name in DENY_ATTRS
        or name in DENY_NAMES
        or name in DENY_MODULES
        or name in DENY_IMPORTED_NAMES
    )


def rules_text() -> str:
    """The complete list of constructs a restored body may not use."""
    return "\n".join(
        [
            "The build does not take a restored body that contains any of the following.",
            "",
            "Imports (also `from X import ...`):",
            "  " + ", ".join(sorted(DENY_MODULES)),
            "  and every module whose name starts with an underscore (but __future__)",
            "The same modules when they are already globals of the unit's module:",
            "  " + ", ".join(sorted(DENY_GLOBAL_MODULES)),
            "Imports of SymPy's testing code:",
            "  "
            + ", ".join(DENY_MODULE_PREFIXES)
            + "  (and the names "
            + ", ".join(sorted(DENY_IMPORTED_NAMES))
            + ")",
            "Builtins, unless the body binds the name itself:",
            "  " + ", ".join(sorted(DENY_NAMES)),
            "Attributes (also when getattr, setattr, delattr, hasattr, attrgetter or methodcaller is given the name",
            "as a literal):",
            "  " + ", ".join(sorted(DENY_ATTRS)),
            "Modules named as a literal to import_module or __import__, as for imports.",
            "Any of the names above as a literal key, whatever holds it (`x['os']`, `d.get('sys')`, `x.__dict__.pop('open')`).",
        ]
    )


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
    return (
        isinstance(a, ast.Constant)
        and isinstance(a.value, str)
        and a.value.startswith("RESTORE U")
    )


def _body_lines(src_lines, fn, doc, rest, target_indent: str):
    first = rest[0]
    line = src_lines[first.lineno - 1]
    prefix = line[: len(line) - len(line.lstrip())]
    own_line = first.col_offset == len(
        prefix.encode("utf-8")
    ) or first.col_offset == len(prefix)
    # the body starts right after the docstring, so comments and decorators that precede
    # the first statement belong to it
    start = min(
        [d.lineno for d in getattr(first, "decorator_list", [])] + [first.lineno]
    )
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
            out.append(target_indent + ln[len(prefix) :])
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

    state is one of: 'restored', 'todo', 'missing', 'syntax', 'not allowed: <why>'.
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
                states[uid] = "not allowed: " + why
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
            ref if ref is not None else _masked_dump(skel_src, uids_by_qualname)
        )
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
    units = json.loads(Path(path).read_text(encoding="utf-8"))
    byfile: dict = {}
    for u in units:
        key = u["qualname"]
        if u.get("nocc", 1) != 1:
            key = f"{key}#{u.get('occ', 0)}/{u['nocc']}"
        byfile.setdefault(u["file"], {})[key] = u["uid"]
    return units, byfile


def build_candidate(
    skel_root: str,
    work_root: str,
    cand_root: str,
    byfile: dict,
    cache: dict | None = None,
):
    """Refresh candidate files for all unit-bearing files. Returns {uid: state}.

    work_root/<file> is read, unless it or a directory on its way is a link (then it counts as
    missing); skel_root/<file> is the blanked skeleton; the result is written to
    cand_root/<file>.  `cache` (mutable dict) memoises per-file results on (mtime_ns, size).
    """
    states = {}
    notes = []
    real_root = os.path.realpath(work_root)
    for rel, qmap in byfile.items():
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
        skel_src = Path(os.path.join(skel_root, rel)).read_text(encoding="utf-8")
        work_src = None
        direct = os.path.realpath(wp) == os.path.join(real_root, os.path.normpath(rel))
        if (
            st is not None
            and direct
            and not os.path.islink(wp)
            and os.path.isfile(wp)
            and st.st_size <= MAX_SOURCE_BYTES
        ):
            try:
                work_src = Path(wp).read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                work_src = None
        cand, fstates = transplant_file(skel_src, work_src, qmap)
        outside = bool(fstates.pop("__outside__", False))
        cp = os.path.join(cand_root, rel)
        try:
            old = Path(cp).read_text(encoding="utf-8")
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
