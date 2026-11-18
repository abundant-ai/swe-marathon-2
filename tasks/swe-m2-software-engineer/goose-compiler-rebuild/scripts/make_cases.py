"""Generate the cases for the Goose compiler rebuild: one or a few Goose files, a command line and
optional standard input.

Programs come from a checkout of aardappel/goose: its test suite and benchmark programs (never
shipped to the candidate), its samples and the complete programs in its documentation (both
shipped). Visible cases use the samples, the documentation's programs and a fixed 15% of the
test and benchmark programs. Private cases use only the others, and leave out any of them that a
shipped file already holds (comments and whitespace aside) or that equals a visible program; the
generator refuses to write a private case whose input an agent could know.

Comments are removed from a program before it runs or is checked: the error tests name the error
they expect in comments, and many run tests write their output after each `print`. Every case is
then changed in ways that keep its meaning and change its answer: identifiers renamed
consistently, blank lines and indentation added so that positions move, and for most run cases
literals changed so that the output follows. A format input keeps every token of its program
and gets comments back: the program's own where no other case is built on that program, neutral
ones otherwise. Expected outputs are NOT produced here: they are recorded from the original
compiler on Linux when the images are built.

usage: make_cases.py <goose checkout> --count 1800 --seed N --visible 300 --out-private P --out-visible V
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from package_step import agent_visible

RUN_DIRS = ("codegen", "lifetimes", "typing", "optimizer", "stdlib", "runtime", "storage", "syntax")
ERROR_DIRS = ("errors_tc", "errors")
# Modules a program may import: the standard library, less what touches the machine (os, ffi).
MODULES = {"std", "vec", "slot_pool", "slice_pool", "slice_pool_internal", "math", "exception", "dictionary", "json",
           "mat", "quat", "base64", "binary", "csv", "regex"}
# The modules written in Goose beyond std and math, which a library case exercises.
LIBRARY = {"json", "regex", "csv", "base64", "binary", "dictionary", "exception", "mat", "quat"}
MARKER = re.compile(r"//\s*(no-jit|parse-only)\b")  # first-line markers: refused by the JIT, or not a program
THREADS = {"thread_fn", "thread_spawn", "thread_spawn_contained", "thread_wait", "qput", "qget", "qpoll", "qlimit",
           "hardware_threads"}
BENCH_N = re.compile(r"^(\s*let\s+(\w+)\s*=\s*)(\d+)(\s*;\s*//\s*BENCH_N.*)$", re.M)
VISIBLE_SHARE = 0.15
# Draws per case, both sides alike; the command line has a fixed list of its own (CLI_*).
KINDS = (("run", 0.315), ("library", 0.04), ("modules", 0.03), ("rejected", 0.08), ("check", 0.375), ("format", 0.16))
COMMANDS = ["run", "build", "check", "fetch", "format", "toolchain", "version", "lsp", "completion", "help"]
# One case for each command-line behaviour, on the private side; the visible side shows a few.
CLI_PRIVATE = [["version"], ["--version"], ["help"], *[["help", c] for c in COMMANDS], ["help", "c"], ["help", "internals"],
               ["run", "--help"], ["check", "-h"], ["format", "--help"],
               ["completion", "bash"], ["completion", "zsh"], ["completion", "fish"], ["completion", "powershell"],
               ["completion"], ["completion", "tcsh"], ["biuld", "main.goose"], ["chekc", "main.goose"], ["frobnicate"],
               ["help", "nonsense"], ["run", "missing.goose"], ["check", "missing.goose"], ["check"],
               ["format", "--check", "missing.goose"], ["check", "main.goose", "--bogus"],
               ["run", "main.goose", "--diagnostics", "xml"], ["run", "main.goose", "-O7"], ["run", "main.goose", "-o", "out.c"]]
CLI_VISIBLE = [["version"], ["help"], ["help", "run"], ["help", "format"], ["completion", "bash"], ["biuld", "main.goose"],
               ["run", "missing.goose"], ["check", "main.goose", "--bogus"]]
# Names a rename never touches, besides every name in the standard library and the compiler's builtins.
RESERVED = {"main", "it", "_", "inline", "checkfree", "root", "from", "has_default", "same", "upto"}
WORDS = ["amber", "basil", "cedar", "delta", "ember", "fennel", "garnet", "hazel", "indigo", "juniper", "kestrel",
         "lichen", "marlin", "nutmeg", "ochre", "pepper", "quartz", "russet", "saffron", "tamarind", "umber", "violet",
         "walnut", "yarrow", "zircon"]
PHRASES = ["keep this simple", "see the notes above", "checked by hand", "kept for later", "a small helper",
           "the main loop", "order matters here", "edge case", "fast path", "slow path", "setup", "bookkeeping",
           "tidy up later", "same as before", "worth a second look", "left as it was", "one more step",
           "kept short on purpose", "the usual case", "nothing special here"]


# ---------------------------------------------------------------- lexer (src/lexer.h)

KEYWORDS = frozenset("""import namespace struct enum type fn thread_fn export simd recursive let var extern const pad
reusable if else while for in loop block guard match defer return break continue as true false null self bool varint
i8 i16 i32 i64 u8 u16 u32 u64 f32 f64""".split())
PUNCT = sorted("""( ) [ ] { } , ; : ? :: . .. .= .== .!= + - * / % += -= *= /= %= &= |= ^= ++ -- = == != < > <= >= << >>
<<= >>= ! ~ & | ^ && || -> =>""".split(), key=len, reverse=True)
DIGITS, HEX = "0123456789", "0123456789abcdefABCDEF"


class LexError(ValueError):
    """The text is no sequence of Goose tokens."""


class Tok(NamedTuple):
    kind: str      # ident, keyword, int, float, string, char, punct or comment
    text: str
    start: int
    end: int


def _number(text: str, i: int) -> tuple[int, str]:
    def scan(j: int, digits: str) -> int:
        while j < len(text) and (text[j] in digits or text[j] == "_"):
            j += 1
        return j

    if text.startswith(("0x", "0X"), i):
        j, kind = scan(i + 2, HEX), "int"
        if text[j:j + 1] == "." and text[j + 1:j + 2] and text[j + 1] in HEX:
            j, kind = scan(j + 1, HEX), "float"
        if text[j:j + 1] in ("p", "P"):
            j = j + 2 if text[j + 1:j + 2] in ("+", "-") else j + 1
            j, kind = scan(j, DIGITS), "float"
        return j, kind
    j, kind = scan(i + 1, DIGITS), "int"
    if text[j:j + 1] == "." and text[j + 1:j + 2] and text[j + 1] in DIGITS:
        j, kind = scan(j + 1, DIGITS), "float"
    if text[j:j + 1] in ("e", "E") and (text[j + 1:j + 2] and text[j + 1] in DIGITS or
                                       text[j + 1:j + 2] in ("+", "-") and text[j + 2:j + 3] and text[j + 2] in DIGITS):
        j, kind = scan(j + 2 if text[j + 1] in "+-" else j + 1, DIGITS), "float"
    return j, kind


def _char_end(text: str, i: int) -> int:
    """The index after one character of a quoted literal that starts at i."""
    if i >= len(text) or text[i] == "\n":
        raise LexError("unterminated literal")
    if text[i] != "\\":
        return i + 1
    escape = text[i + 1:i + 2]
    if escape and escape in "ntr0\\\"'":
        return i + 2
    if escape == "x" and re.fullmatch(r"[0-9a-fA-F]{2}", text[i + 2:i + 4]):
        return i + 4
    raise LexError("unknown escape")


def lex(text: str) -> list[Tok]:
    """The tokens of a Goose file, comments included, as src/lexer.h scans them."""
    toks: list[Tok] = []
    i, n = 0, len(text)
    while True:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            return toks
        c, start = text[i], i
        if text.startswith("//", i):
            i = text.find("\n", i)
            i = n if i < 0 else i
        elif text.startswith("/*", i):
            i, depth = i + 2, 1
            while depth:
                if i >= n:
                    raise LexError("unterminated /* comment")
                if text.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                elif text.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                else:
                    i += 1
        elif c == "'":
            i = _char_end(text, i + 1)
            if text[i:i + 1] != "'":
                raise LexError("bad character literal")
            toks.append(Tok("char", text[start:i + 1], start, i + 1))
            i += 1
            continue
        elif text.startswith('"""', i):
            q = i + 3
            while q < n and text[q] in " \t\r":
                q += 1
            close = text.find('"""', q + 1 if text[q:q + 1] == "\n" else i + 3)
            if close < 0 or (text[q:q + 1] != "\n" and "\n" in text[i + 3:close]):
                raise LexError("bad raw string")
            if text[q:q + 1] == "\n" and text[text.rfind("\n", 0, close) + 1:close].strip(" \t"):
                raise LexError("text before the closing quotes of a raw string")
            i = close + 3
            toks.append(Tok("string", text[start:i], start, i))
            continue
        elif c == '"':
            i += 1
            while text[i:i + 1] != '"':
                i = _char_end(text, i)
            i += 1
            toks.append(Tok("string", text[start:i], start, i))
            continue
        elif c in DIGITS:
            i, kind = _number(text, i)
            toks.append(Tok(kind, text[start:i], start, i))
            continue
        elif c.isascii() and (c.isalpha() or c == "_"):
            while i < n and text[i].isascii() and (text[i].isalnum() or text[i] == "_"):
                i += 1
            toks.append(Tok("keyword" if text[start:i] in KEYWORDS else "ident", text[start:i], start, i))
            continue
        else:
            punct = next((p for p in PUNCT if text.startswith(p, i)), None)
            if punct is None:
                raise LexError(f"illegal character {c!r}")
            i += len(punct)
            toks.append(Tok("punct", punct, start, i))
            continue
        toks.append(Tok("comment", text[start:i], start, i))


def lexes(text: str) -> bool:
    try:
        lex(text)
    except LexError:
        return False
    return True


def code(toks: list[Tok]) -> list[tuple[str, str]]:
    return [(t.kind, t.text) for t in toks if t.kind != "comment"]


# ---------------------------------------------------------------- comments and comparison

def _code_part(line: str) -> str:
    """The line up to a `//` comment that is not inside a string or character literal."""
    quote = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif line.startswith("//", index):
            return line[:index].rstrip()
        index += 1
    return line


def strip_comments(text: str) -> str:
    """The text without comments: a line that held only comments goes, and so does a run of
    blank lines beyond one. Text that does not lex (Markdown, a broken test) loses its `//`
    comments line by line and its `/* */` comments by pattern."""
    try:
        spans = [(t.start, t.end) for t in lex(text) if t.kind == "comment"]
    except LexError:
        lines = [_code_part(line) for line in text.split("\n") if not line.strip().startswith("//")]
        text = re.sub(r"/\*.*?\*/", "", "\n".join(lines), flags=re.S)
        return re.sub(r"\n{3,}", "\n\n", text).strip("\n") + "\n"
    inside = bytearray(len(text))
    for start, end in spans:
        inside[start:end] = b"\x01" * (end - start)
    lines, pos = [], 0
    for line in text.split("\n"):
        kept = "".join(char for k, char in enumerate(line) if not inside[pos + k])
        if any(inside[pos:pos + len(line)]):
            kept = kept.rstrip()
            if not kept.strip():
                pos += len(line) + 1
                continue
        lines.append(kept)
        pos += len(line) + 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n") + "\n"


def normalise(text: str) -> str:
    """A text as compared with what ships: without comments and without any whitespace."""
    return re.sub(r"\s+", "", strip_comments(text))


# ---------------------------------------------------------------- programs

class Program(NamedTuple):
    key: str                  # Where it comes from in the checkout: test/..., bench/..., samples/..., docs#N.
    role: str                 # run, error or shown
    files: dict[str, str]     # Case-relative path to source text, comments included; main.goose first.
    warnings: bool            # The source declares warnings its check prints (`// warning:`).
    expected: str | None      # The sha256 of upstream's expected standard output, where it has one.

    def stripped(self) -> dict[str, str]:
        return {name: strip_comments(text) for name, text in self.files.items()}


def imports(text: str) -> list[str]:
    return re.findall(r"^\s*import\s+(\.?[\w.]+)\s*;", strip_comments(text), re.M)


def usable(text: str, local: bool = False, module: bool = False) -> bool:
    """A program the JIT runs and the cases may use: no excluded module, no package, no extern,
    no threads; with `local`, imports of files beside it are allowed too, and a `module` (a file
    one imports) may carry a first-line marker. A file that does not lex (a test of the lexer's
    errors) is judged by its words."""
    if not module and MARKER.match(text.split("\n", 1)[0]) or len(text) > 40_000:
        return False
    try:
        names = {t.text for t in lex(text) if t.kind in ("ident", "keyword")}
    except LexError:
        names = set(re.findall(r"\b\w+\b", strip_comments(text)))
    if "extern" in names or names & THREADS or re.search(r"^\s*import\s+[\w.]+\s+from\b", strip_comments(text), re.M):
        return False
    return local or all(name in MODULES for name in imports(text))


def line_starts(text: str) -> list[int]:
    return [0] + [m.end() for m in re.finditer("\n", text)]


def module_files(main: Path, root: Path) -> dict[str, str] | None:
    """main.goose and every local module it imports, transitively, by their paths relative to
    main's directory; None where an import is neither a module of the standard library nor a
    file beside main, or a file is unusable."""
    files: dict[str, str] = {}
    todo = [(main, "main.goose")]
    while todo:
        path, name = todo.pop()
        if name in files:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not usable(text, local=True, module=name != "main.goose"):
            return None
        files[name] = text
        for imported in imports(text):
            if imported in MODULES:
                continue
            relative = imported.startswith(".")
            target = (path.parent if relative else main.parent) / (imported.lstrip(".").replace(".", "/") + ".goose")
            if not target.is_file():
                return None
            todo.append((target, target.relative_to(main.parent).as_posix()))
    for match in re.finditer(r'embed_file\("([\w.-]+)"\)', strip_comments(files["main.goose"])):
        data = main.parent / match.group(1)
        if data.is_file() and data.stat().st_size <= 4096:
            files[match.group(1)] = data.read_text(encoding="utf-8", errors="replace")
    return files


def scale_bench(text: str, rng: random.Random) -> str:
    """A benchmark at a size the original runs in a fraction of a second: depths shrink by a
    few levels, widths by a factor, counts by a hundred or more."""
    def smaller(match: re.Match) -> str:
        name, value = match.group(2), int(match.group(3))
        if "DEPTH" in name:
            value = max(4, value - rng.randint(6, 9))
        elif name in ("W", "H"):
            value = max(16, value // rng.choice([16, 32]))
        else:
            value = max(1000, value // rng.choice([100, 200, 400]))
        return f"{match.group(1)}{value}{match.group(4)}"
    return BENCH_N.sub(smaller, text, count=1)


def doc_programs(checkout: Path) -> list[str]:
    """Complete programs (with a main) from the documentation, skipping fragments and check-only blocks."""
    programs = []
    for path in sorted((checkout / "docs").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"(<!--[^>]*-->\s*)?```goose\n(.*?)```", text, re.S):
            marker, body = match.group(1) or "", match.group(2)
            if "fragment" in marker or "check-only" in marker:
                continue
            if usable(body) and "fn main" in body:
                programs.append(body)
    return programs


def pools(checkout: Path) -> list[Program]:
    """Every program the cases may use, in a fixed order."""
    tests = checkout / "test"
    found: list[Program] = []
    expected = lambda stem: (tests / "expected" / f"{stem}.out")  # noqa: E731

    def digest(stem: str) -> str | None:
        path = expected(stem)
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

    for role, directories in (("run", RUN_DIRS), ("error", ERROR_DIRS)):
        for directory in directories:
            for path in sorted((tests / directory).glob("*.goose")):
                text = path.read_text(encoding="utf-8", errors="replace")
                wanted = "// error:" in text if role == "error" else expected(path.stem).is_file() and "// error:" not in text
                if not wanted or "fn main" not in text:
                    continue
                files = module_files(path, path.parent)
                if files is None:
                    continue
                found.append(Program(f"test/{directory}/{path.name}", role, files, "// warning:" in text,
                                     digest(path.stem) if role == "run" else None))
    for path in sorted((checkout / "bench" / "goose").glob("*.goose")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if BENCH_N.search(text) and "fn main" in text:
            files = module_files(path, path.parent)
            if files is not None:
                found.append(Program(f"bench/goose/{path.name}", "run", files, False, None))
    for path in sorted((checkout / "samples").glob("*.goose")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if usable(text) and "fn main" in text:
            found.append(Program(f"samples/{path.name}", "shown", {"main.goose": text}, False, None))
    for index, text in enumerate(doc_programs(checkout)):
        found.append(Program(f"docs#{index}", "shown", {"main.goose": text}, False, None))
    return found


def visible_program(key: str) -> bool:
    if not key.startswith(("test/", "bench/")):
        return True
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < VISIBLE_SHARE


def protected_names(checkout: Path) -> set[str]:
    """Names a rename must leave alone: every identifier of the standard library, the compiler's
    builtins and the names its checker treats specially, the modules and the reserved ones."""
    names = set(RESERVED) | MODULES
    for path in sorted((checkout / "stdlib").glob("*.goose")):
        try:
            names |= {t.text for t in lex(path.read_text(encoding="utf-8", errors="replace")) if t.kind == "ident"}
        except LexError:
            names |= set(re.findall(r"\b[A-Za-z_]\w*\b", path.read_text(encoding="utf-8", errors="replace")))
    for path in sorted((checkout / "src").glob("*.h")):
        if path.name.startswith(("builtin", "typecheck", "resolve", "parser", "expansion")):
            names |= set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', path.read_text(encoding="utf-8", errors="replace")))
    return names


# ---------------------------------------------------------------- what an agent can know

def shipped_texts(checkout: Path) -> str:
    """Every file the agent image ships from the checkout (documentation, samples, standard
    library), normalised and joined by NUL, which no normalised program contains."""
    texts = []
    for path in sorted(checkout.rglob("*")):
        name = path.relative_to(checkout).as_posix()
        if path.is_file() and ".git" not in path.relative_to(checkout).parts and agent_visible(name):
            texts.append(normalise(path.read_text(encoding="utf-8", errors="replace")))
    return "\0".join(texts)


def inputs(case: dict) -> list[str]:
    return list(case["files"].values()) + ([case["stdin"]] if case["stdin"] else [])


def leaks(private: list[dict], visible: list[dict], shipped: str) -> list[str]:
    """The private cases with an input that, comments and whitespace aside, is in a shipped file
    or is an input of a visible case. A local module a benchmark shares with the others is no
    input of its own (`shared`, the modules' normalised texts)."""
    seen = {normalise(text) for case in visible for text in inputs(case)}
    shared = {normalise(text) for case in private + visible for name, text in case["files"].items() if name == "rng.goose"}
    found = []
    for case in private:
        if any(key and key not in shared and (key in seen or key in shipped) for key in map(normalise, inputs(case))):
            found.append(case["id"])
    return found


# ---------------------------------------------------------------- edits that keep every token

def _glues(a: Tok, b: Tok) -> bool:
    """Whether a and b written together still lex as a and b."""
    try:
        return [(t.kind, t.text) for t in lex(a.text + b.text)] == [(a.kind, a.text), (b.kind, b.text)]
    except LexError:
        return False


def _same_tokens(old: str, new: str) -> bool:
    try:
        return [(t.kind, t.text.rstrip() if t.kind == "comment" else t.text) for t in lex(new)] == \
               [(t.kind, t.text.rstrip() if t.kind == "comment" else t.text) for t in lex(old)]
    except LexError:
        return False


def relayout(rng: random.Random, text: str) -> str:
    """The same tokens and comments with other whitespace between them: indentation, spaces
    and tabs between tokens, blank lines and trailing spaces. Two tokens touch only where they
    still lex apart, so no operator is ever split or made."""
    toks = lex(text)
    if len(toks) < 2:
        return text
    starts = line_starts(text)
    for _ in range(8):
        out = [text[:toks[0].start], toks[0].text]
        busy = {line for line in range(len(starts)) if rng.random() < 0.35}
        for prev, cur in zip(toks, toks[1:]):
            gap = text[prev.end:cur.start]
            if "\n" in gap:
                breaks = gap.count("\n") + (rng.randint(1, 2) if rng.random() < 0.06 else 0)
                indent = gap.rsplit("\n", 1)[1]
                roll = rng.random()
                if roll < 0.15:
                    indent = ""
                elif roll < 0.30:
                    indent = " " * rng.randint(1, 9)
                elif roll < 0.38:
                    indent = indent.replace("    ", "\t")
                elif roll < 0.46:
                    indent += " " * rng.randint(1, 3)
                trailing = rng.choice([" ", "  ", "\t"]) if prev.kind != "comment" and rng.random() < 0.05 else ""
                out.append(trailing + "\n" * breaks + indent)
            elif bisect.bisect_right(starts, prev.end) - 1 in busy:
                roll = rng.random()
                if roll < 0.3 and gap and _glues(prev, cur):
                    out.append("")
                elif roll < 0.55:
                    out.append(" " * rng.randint(2, 4))
                elif roll < 0.65:
                    out.append("\t")
                elif roll < 0.8 and not gap and cur.kind != "comment":
                    out.append(" ")
                else:
                    out.append(gap)
            else:
                out.append(gap)
            out.append(cur.text)
        out.append(text[toks[-1].end:])
        new = "".join(out)
        if new != text and _same_tokens(text, new):
            return new
    lines = text.split("\n")
    at = next(i for i, line in enumerate(lines) if line.strip())
    lines[at] = "   " + lines[at]
    return "\n".join(lines)


def add_comments(rng: random.Random, text: str, count: int) -> str:
    """Neutral comments where comments go: on lines of their own (documentation where a
    declaration follows), after code (sometimes a run of them sharing a column), and as block
    comments between tokens, nested now and then."""
    toks = lex(text)
    if not toks:
        return text
    starts = [i for i in range(len(toks)) if i == 0 or "\n" in text[toks[i - 1].end:toks[i].start]]
    ends = [i for i in range(len(toks)) if toks[i].kind != "comment" and
            (i + 1 == len(toks) or "\n" in text[toks[i].end:toks[i + 1].start])]
    inner = [i for i in range(len(toks) - 1) if "\n" not in text[toks[i].end:toks[i + 1].start]
             and toks[i].kind != "comment"]
    edits: dict[int, str] = {}
    phrase = lambda: rng.choice(PHRASES)  # noqa: E731
    for _ in range(count):
        roll = rng.random()
        if roll < 0.4 and starts:
            tok = toks[rng.choice(starts)]
            indent = text[text.rfind("\n", 0, tok.start) + 1:tok.start]
            edits.setdefault(tok.start, f"// {phrase()}\n{indent}")
        elif roll < 0.8 and ends:
            first = rng.randrange(len(ends))
            run = ends[first:first + (rng.randint(2, 4) if rng.random() < 0.4 else 1)]
            width = max(toks[i].end - (text.rfind("\n", 0, toks[i].end) + 1) for i in run)
            for i in run:
                column = toks[i].end - (text.rfind("\n", 0, toks[i].end) + 1)
                edits.setdefault(toks[i].end, " " * (width - column + 2) + f"// {phrase()}")
        elif inner:
            tok = toks[rng.choice(inner)]
            body = f"/* {phrase()} /* {phrase()} */ */" if rng.random() < 0.3 else f"/* {phrase()} */"
            edits.setdefault(tok.end, f" {body} ")
    new = text
    for at in sorted(edits, reverse=True):
        new = new[:at] + edits[at] + new[at:]
    try:
        return new if code(lex(new)) == code(toks) else text
    except LexError:
        return text


def shift(rng: random.Random, text: str) -> str:
    """Positions moved without touching a token: blank lines inserted before a line that starts
    outside a token, and extra indentation on a run of such lines."""
    toks = lex(text)
    offsets = line_starts(text)
    first_tok: dict[int, Tok] = {}
    for tok in toks:
        first_tok.setdefault(bisect.bisect_right(offsets, tok.start) - 1, tok)
    lines = text.split("\n")
    starts = [line for line, tok in sorted(first_tok.items()) if text[offsets[line]:tok.start].strip() == ""]
    if not starts:
        return text
    indent = rng.random() < 0.6
    if rng.random() < 0.8 or not indent:
        at = starts[0] if rng.random() < 0.7 else rng.choice([line for line in starts if not lines[line][:1].isspace()] or starts)
        added = rng.randint(1, 3)
        lines[at:at] = [""] * added
        starts = [line + added if line >= at else line for line in starts]
    if indent:
        first = rng.randrange(len(starts))
        pad = " " * rng.randint(1, 4)
        for line in starts[first:first + rng.randint(1, 6)]:
            lines[line] = pad + lines[line]
    new = "\n".join(lines)
    return new if _same_tokens(text, new) else text


def rename(rng: random.Random, files: dict[str, str], protected: set[str], count: int) -> tuple[dict[str, str], dict[str, str]]:
    """The files with up to `count` of the program's own names replaced everywhere by fresh ones
    that clash with nothing, keeping a leading underscore and the name's case."""
    try:
        toks = {name: lex(text) for name, text in files.items()}
    except LexError:
        return files, {}
    modules = {part for name in files for part in re.split(r"[/.]", name)}
    candidates = sorted({t.text for ts in toks.values() for t in ts if t.kind == "ident"} - protected - modules)
    if not candidates:
        return files, {}
    taken = {t.text for ts in toks.values() for t in ts if t.kind in ("ident", "keyword")} | protected | modules
    mapping: dict[str, str] = {}
    for word in rng.sample(candidates, min(count, len(candidates))):
        while True:
            new = f"{rng.choice(WORDS)}{rng.randint(2, 99)}"
            new = new.upper() if word.isupper() else new.capitalize() if word.lstrip("_")[:1].isupper() else new
            new = "_" + new if word.startswith("_") else new
            if new not in taken:
                break
        taken.add(new)
        mapping[word] = new
    out = {}
    for name, text in files.items():
        parts, pos = [], 0
        for tok in toks[name]:
            if tok.kind == "ident" and tok.text in mapping:
                parts += [text[pos:tok.start], mapping[tok.text]]
                pos = tok.end
        out[name] = "".join(parts) + text[pos:]
    return out, mapping


# ---------------------------------------------------------------- edits that change a program

def code_lines(text: str) -> list[int]:
    return [i for i, line in enumerate(text.split("\n")) if line.strip() and line.strip() not in ("{", "}", "};")]


def mutate_literal(rng: random.Random, text: str) -> str:
    spots = [m for m in re.finditer(r"(?<![\w.\"'])(\d{1,4})(?![\w.])", text)]
    if not spots:
        return text
    spot = rng.choice(spots)
    value = int(spot.group(1))
    new = rng.choice([value + 1, max(0, value - 1), value + rng.randint(2, 9), value * 2])
    return text[:spot.start()] + str(new) + text[spot.end():]


def mutate_string(rng: random.Random, text: str) -> str:
    """One letter of a string literal changed, outside its escapes."""
    try:
        strings = [t for t in lex(text) if t.kind == "string" and not t.text.startswith('"""')]
    except LexError:
        return text
    spots = [(t.start + k) for t in strings for k in range(1, len(t.text) - 1)
             if t.text[k].isascii() and t.text[k].isalpha() and t.text[k - 1] != "\\"]
    if not spots:
        return text
    at = rng.choice(spots)
    letters = "abcdefghijklmnopqrstuvwxyz"
    new = rng.choice([c for c in letters if c != text[at].lower()])
    return text[:at] + (new.upper() if text[at].isupper() else new) + text[at + 1:]


def mutate_operator(rng: random.Random, text: str) -> str:
    swaps = [(" < ", " <= "), (" > ", " >= "), (" + ", " - "), (" * ", " + "), (" == ", " != "), (" && ", " || ")]
    present = [(a, b) for a, b in swaps if a in text]
    if not present:
        return text
    a, b = rng.choice(present)
    spots = [m.start() for m in re.finditer(re.escape(a), text)]
    at = rng.choice(spots)
    return text[:at] + b + text[at + len(a):]


def mutate_name(rng: random.Random, text: str) -> str:
    words = re.findall(r"\b[a-z_][a-z0-9_]{2,}\b", text)
    keywords = {"fn", "let", "var", "for", "while", "if", "else", "return", "struct", "enum", "import", "match", "true",
                "false", "and", "not", "break", "continue", "class", "print", "main", "const", "static", "type", "case"}
    common = sorted({w for w in words if words.count(w) >= 2 and w not in keywords})
    if not common:
        return text
    word = rng.choice(common)
    spots = [m.start() for m in re.finditer(rf"\b{word}\b", text)]
    at = rng.choice(spots[1:] or spots)
    replacement = rng.choice([word + "_", word[:-1], word[0] + word])
    return text[:at] + replacement + text[at + len(word):]


def mutate_line(rng: random.Random, text: str) -> str:
    lines = text.split("\n")
    spots = code_lines(text)
    if len(spots) < 3:
        return text
    at = rng.choice(spots)
    if rng.random() < 0.6:
        del lines[at]
    else:
        lines.insert(at, lines[at])
    return "\n".join(lines)


def mutate(rng: random.Random, text: str, breaking: bool, strings: bool = False) -> str:
    """One to three edits that change the text, retried with other edits where one changes
    nothing; the text unchanged only where no edit applies at all. `breaking` prefers edits that
    make the program fail to compile; `strings` adds edits of string literals."""
    if breaking:
        edits = [mutate_name, mutate_line, mutate_operator]
    else:
        edits = [mutate_literal, mutate_literal, mutate_operator] + ([mutate_string, mutate_string] if strings else [])
    for _ in range(rng.randint(1, 3 if breaking else 2)):
        for _ in range(6):
            edited = rng.choice(edits)(rng, text)
            if edited != text:
                text = edited
                break
    return text


# ---------------------------------------------------------------- cases

class Built(NamedTuple):
    case: dict
    kind: str
    keys: list[str]           # The programs it is built on.
    changed: bool             # Its answer differs from what upstream publishes for the program (best known).


class Side:
    """The programs of one side and the names a rename leaves alone."""

    def __init__(self, programs: list[Program], protected: set[str]):
        self.protected = protected
        self.run = [p for p in programs if p.role == "run" and set(p.files) == {"main.goose"}]
        # A side short of library or multi-file programs uses plain run programs instead.
        self.library = [p for p in self.run if LIBRARY & set(imports(p.files["main.goose"]))] or self.run
        self.modules = [p for p in programs if p.role == "run" and set(p.files) != {"main.goose"}] or self.run
        self.errors = [p for p in programs if p.role == "error"]
        self.warned = [p for p in self.run if p.warnings]
        self.shown = [p for p in programs if p.role == "shown"]
        # test/errors/ holds programs that do not parse, which format would only reject.
        self.formattable = [p for p in self.run + self.errors + self.shown
                            if not p.key.startswith("test/errors/") and lexes(p.files["main.goose"])]

    def ready(self) -> bool:
        return all((self.run, self.errors, self.formattable))


def transformed(rng: random.Random, side: Side, program: Program, *, literals: float, strings: float = 0.0,
                operators: float = 0.0, positions: float = 0.0, rename_share: float = 1.0) -> tuple[dict[str, str], bool]:
    """A program's files, comments removed, with consistent renames and, by the given shares,
    changed literals, strings and operators and moved positions; where none of that changed
    anything, a literal or a string is changed after all. Also whether anything changed."""
    files = program.stripped()
    mapping: dict[str, str] = {}
    if rng.random() < rename_share:
        files, mapping = rename(rng, files, side.protected, rng.randint(1, 3))
    main = files["main.goose"]
    edited = main
    if rng.random() < literals:
        edited = mutate_literal(rng, edited)
        edited = edited if edited != main else mutate_string(rng, edited)
    if rng.random() < strings:
        edited = mutate_string(rng, edited)
    if rng.random() < operators:
        edited = mutate_operator(rng, edited)
    if rng.random() < positions and lexes(edited):
        edited = shift(rng, edited)
    if not mapping and edited == main:
        edited = mutate_literal(rng, edited) if positions == 0.0 else shift(rng, edited) if lexes(edited) else edited
        edited = edited if edited != main else mutate_string(rng, edited)
    files = dict(files, **{"main.goose": edited})
    return files, bool(mapping) or edited != main


def run_argv(rng: random.Random, program: Program) -> list[str]:
    argv = ["run", "main.goose"] if rng.random() < 0.9 else ["main.goose"]
    if rng.random() < 0.12:
        argv.append(rng.choice(["-O0", "-O1"]))
    if rng.random() < 0.1:
        argv.append("--debug")
    if program.warnings and rng.random() < 0.5:
        argv += ["--diagnostics", "json"]
    if rng.random() < 0.05:
        argv += ["--", *rng.sample(["input.txt", "--verbose", "-n", "3", "all"], rng.randint(1, 3))]
    return argv


def make_run(rng: random.Random, side: Side, pool: list[Program], kind: str) -> Built:
    program = rng.choice(pool)
    files, changed = transformed(rng, side, program, literals=0.95, strings=0.5 if kind == "library" else 0.2,
                                 operators=0.15)
    return Built({"files": files, "argv": run_argv(rng, program), "stdin": None}, kind, [program.key], changed)


def make_rejected(rng: random.Random, side: Side) -> Built:
    program = rng.choice(side.errors)
    files, changed = transformed(rng, side, program, literals=0.0, positions=1.0)
    argv = ["run", "main.goose", "--diagnostics", "json"] if rng.random() < 0.7 else ["run", "main.goose"]
    return Built({"files": files, "argv": argv, "stdin": None}, "rejected", [program.key], changed)


def make_check(rng: random.Random, side: Side) -> Built:
    roll = rng.random()
    argv = ["check", "main.goose", "--diagnostics", "json"]
    if rng.random() < 0.1:
        argv[1:1] = ["--color", "never"]
    if roll < 0.62:
        program = rng.choice(side.errors)
        files, changed = transformed(rng, side, program, literals=0.0, positions=1.0)
    elif roll < 0.92:
        program = rng.choice(side.run + side.shown)
        files, _ = transformed(rng, side, program, literals=0.0, rename_share=0.5, positions=0.5)
        files = dict(files, **{"main.goose": mutate(rng, files["main.goose"], breaking=True)})
        changed = True
    else:
        program = rng.choice(side.warned or side.errors)
        files, changed = transformed(rng, side, program, literals=0.0, positions=1.0)
    return Built({"files": files, "argv": argv, "stdin": None}, "check", [program.key], changed)


class FormatPlan(NamedTuple):
    """A format case before its comments are chosen: which programs go where."""
    stdin: bool
    argv: list[str]
    places: list[tuple[str, Program, bool]]   # (file name or "-" for standard input, program, disturbed)


def plan_format(rng: random.Random, side: Side) -> FormatPlan:
    if rng.random() < 0.6:
        return FormatPlan(True, ["format"] if rng.random() < 0.8 else ["format", "-"], [("-", rng.choice(side.formattable), True)])
    names = rng.sample(["main.goose", "lib.goose", "src/shapes.goose", "src/util/text.goose", "tools/gen.goose"], rng.randint(1, 3))
    places = [(name, rng.choice(side.formattable), rng.random() < 0.6) for name in names]
    target = rng.choice([".", "src", names[0]]) if any(name.startswith("src/") for name in names) else rng.choice([".", names[0]])
    return FormatPlan(False, ["format", "--check", target], places)


def build_format(rng: random.Random, side: Side, plan: FormatPlan, busy: set[str]) -> Built:
    """Comments from the program itself where no other case is built on it (`busy`), neutral
    ones otherwise; then renames, and a new layout for a disturbed file."""
    texts, changed = {}, not plan.stdin
    for name, program, disturbed in plan.places:
        text = program.files["main.goose"]
        renamed, mapping = rename(rng, {"main.goose": text}, side.protected, rng.randint(1, 3))
        own = program.key not in busy and bool(mapping) and any(t.kind == "comment" for t in lex(text))
        if own:
            text = renamed["main.goose"]
        else:  # neutral comments, renamed alike: unrenamed, the program's own would print as upstream wrote it
            stripped = strip_comments(text)
            text = add_comments(rng, rename(rng, {"main.goose": stripped}, side.protected, rng.randint(1, 3))[0]["main.goose"],
                                rng.randint(2, 6))
            own = False
        changed = changed or not own or bool(mapping)
        texts[name] = relayout(rng, text) if disturbed else text
    keys = [program.key for _, program, _ in plan.places]
    if plan.stdin:
        return Built({"files": {}, "argv": plan.argv, "stdin": texts["-"]}, "format", keys, changed)
    return Built({"files": texts, "argv": plan.argv, "stdin": None}, "format", keys, changed)


def make_cli(rng: random.Random, side: Side, argv: list[str]) -> Built:
    program = rng.choice(side.run + side.errors)
    files, _ = transformed(rng, side, program, literals=0.0)
    return Built({"files": {"main.goose": files["main.goose"]}, "argv": list(argv), "stdin": None}, "cli", [program.key], True)


def generate(rng_for, side: Side, count: int, cli: list[list[str]], first: int, prefix: str) -> list[Built]:
    """`count` cases of one side: the command-line list spread evenly, the other kinds drawn by
    KINDS, format cases finished last so that their comments can depend on the other cases."""
    spots = {first + round(j * count / len(cli)): argv for j, argv in enumerate(cli)}
    built: dict[int, Built | FormatPlan] = {}
    for index in range(first, first + count):
        rng = rng_for(index)
        if index in spots:
            built[index] = make_cli(rng, side, spots[index])
            continue
        pick, kind = rng.random(), None
        for name, share in KINDS:
            pick -= share
            if pick < 0:
                kind = name
                break
        kind = kind or KINDS[-1][0]
        if kind in ("run", "library", "modules"):
            built[index] = make_run(rng, side, {"run": side.run, "library": side.library, "modules": side.modules}[kind], kind)
        elif kind == "rejected":
            built[index] = make_rejected(rng, side)
        elif kind == "check":
            built[index] = make_check(rng, side)
        else:
            built[index] = plan_format(rng, side)
    busy = {key for item in built.values() if isinstance(item, Built) and item.kind != "format" for key in item.keys}
    out = []
    for index in range(first, first + count):
        item = built[index]
        if isinstance(item, FormatPlan):
            item = build_format(rng_for(index + 7_000_000), side, item, busy)
        item.case["id"] = f"{prefix}{index + 1:05d}"
        out.append(item)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--count", type=int, default=1800)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--visible", type=int, default=300)
    parser.add_argument("--out-private", type=Path, required=True)
    parser.add_argument("--out-visible", type=Path, required=True)
    args = parser.parse_args()
    programs = pools(args.checkout)
    shipped = shipped_texts(args.checkout)
    protected = protected_names(args.checkout)
    scaled = []
    for program in programs:
        if program.key.startswith("bench/"):
            rng = random.Random(f"{args.seed}:{program.key}")
            program = program._replace(files=dict(program.files, **{"main.goose": scale_bench(program.files["main.goose"], rng)}))
        scaled.append(program)
    programs = scaled
    visible = [p for p in programs if visible_program(p.key)]
    # A private program must be unknown to the agent: no shown program and no variant of one,
    # nothing a shipped file holds, nothing equal to a visible program.
    seen = {normalise(text) for p in visible for name, text in p.files.items() if name != "rng.goose"}
    excluded = sorted(p.key for p in programs if not visible_program(p.key) and
                      any(key and (key in seen or key in shipped)
                          for key in (normalise(text) for name, text in p.files.items() if name != "rng.goose")))
    private = [p for p in programs if not visible_program(p.key) and p.key not in excluded and p.role != "shown"]
    sides = {"visible": Side(visible, protected), "private": Side(private, protected)}
    for name, side in sides.items():
        if not side.ready() or not side.shown and name == "visible":
            raise SystemExit(f"the {name} side lacks programs of some kind")
    rng_for = lambda index: random.Random(args.seed * 1_000_003 + index)  # noqa: E731
    shown = generate(rng_for, sides["visible"], args.visible, CLI_VISIBLE, 0, "E")
    hidden = generate(rng_for, sides["private"], args.count - args.visible, CLI_PRIVATE, args.visible, "P")
    # For the verifier's record of what it grades (verifier/recording.py): each private case's kind,
    # and for a run case built on an upstream test, the sha256 of the test's expected output.
    expected = {p.key: p.expected for p in programs}
    for item in hidden:
        item.case["kind"] = item.kind
        if item.kind in ("run", "library", "modules") and expected.get(item.keys[0]):
            item.case["upstream"] = expected[item.keys[0]]
    found = leaks([b.case for b in hidden], [b.case for b in shown], shipped)
    if found:
        raise SystemExit(f"{len(found)} private cases have an input the agent can know: {', '.join(found[:20])}")
    for path, chosen in ((args.out_visible, shown), (args.out_private, hidden)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cases": [b.case for b in chosen]}, sort_keys=True, ensure_ascii=False))
    unchanged = Counter(b.kind for b in hidden if b.kind != "cli" and not b.changed)
    print(json.dumps({
        "programs": {name: {"run": len(s.run), "library": len(s.library), "modules": len(s.modules), "error": len(s.errors),
                            "warned": len(s.warned), "shown": len(s.shown)} for name, s in sides.items()},
        "excluded": excluded,
        "kinds": {name: dict(sorted(Counter(b.kind for b in chosen).items())) for name, chosen in (("visible", shown), ("private", hidden))},
        # Cases left exactly as upstream publishes their program: no rename, no edit, no moved position.
        "private_unchanged_from_upstream": dict(sorted(unchanged.items())),
        "cases": args.count, "visible": args.visible, "private": args.count - args.visible,
    }, indent=1))


if __name__ == "__main__":
    main()
