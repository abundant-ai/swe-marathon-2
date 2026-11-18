"""Generate the cases for the Goose compiler rebuild: one or a few Goose files, a command line and
optional standard input.

Programs come from a checkout of aardappel/goose: its test suite and benchmark programs, with
LangArena's benchmarks (bench/kostya) each run by a program of its own (none of them shipped to
the agent), its samples and the complete programs in its documentation (both shipped). Visible
cases use the samples, the documentation's programs and a fixed 15% of the other programs'
families (variants of one another go to one side together), adjusted so that both sides have
programs whose check prints warnings and programs of every library module. Private cases use
only the others, and leave out any that a shipped file already holds (comments and whitespace
aside) or that equals a visible program; the generator refuses to write a private case whose
input an agent could know.

Comments are removed from a program before it runs or is checked: the error tests name the error
they expect in comments, and many run tests write their output after each `print`. Each case is
then edited the way people edit a program, so that most answers differ from what upstream
publishes: names renamed to ordinary words (first those its expected messages mention), blank
lines and indentation added so that positions move, and for run cases literals and printed
words changed, never in an assert, a size or an index. A run case carries up to three such
edits, and a check case on a program broken on purpose three breaking edits, for the recorder to
choose from (runcases.settle); recording.json counts the answers that are still upstream's. A
format input keeps every token of its program but a trailing comma and gets comments back: the
program's own where no other case is built on its family (less those upstream's test runner
reads and those quoting an answer upstream publishes), comments of the kind people write
otherwise; and the layout a person leaves before formatting, except a file a --check workspace
has formatted first. Expected outputs are NOT produced here: they are recorded from the original
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
KINDS = (("run", 0.33), ("library", 0.05), ("modules", 0.08), ("rejected", 0.08), ("check", 0.395), ("format", 0.065))
# One case for each command-line behaviour of the commands in scope, on the private side, none of
# them an argument list the visible side shows or an alias of one; the visible side shows a few.
CLI_PRIVATE = [["help", "check"], ["help", "completion"], ["help", "version"], ["help", "c"], ["help", "internals"],
               ["check", "-h"], ["completion", "zsh"], ["completion", "fish"], ["completion", "powershell"], ["completion"],
               ["completion", "tcsh"], ["chekc", "main.goose"], ["frobnicate"], ["help", "nonsense"],
               ["check", "missing.goose"], ["check"], ["format", "--check", "missing.goose"],
               ["run", "main.goose", "--diagnostics", "xml"], ["run", "main.goose", "-O7"]]
CLI_VISIBLE = [["version"], ["help"], ["help", "run"], ["help", "format"], ["completion", "bash"], ["biuld", "main.goose"],
               ["run", "missing.goose"], ["check", "main.goose", "--bogus"]]
# LangArena's benchmarks (bench/kostya), each run by a program of its own: the suite's dispatch
# for it, with the suite's harness (bench.goose) replaced by KOSTYA_BENCH, a fixed configuration
# and no clock, and its helper's C library externs by the standard library's formatter. Left out:
# the harness and its runner, brainfuck (its programs come from the configuration file) and matmul
# (threads).
KOSTYA = "bench/kostya/goose/src"
KOSTYA_LEFT_OUT = {"bench", "helper", "main", "brainfuck_array", "brainfuck_recursion", "matmul"}
KOSTYA_CONFIG = {"iterations": 2, "warmup_iterations": 1, "depth": 6, "n": 7, "size": 160, "rows": 40, "h": 24, "w": 32,
                 "operations": 40, "count": 24, "values": 64, "lines_count": 60, "limit": 3000, "word_len": 5, "words": 80,
                 "coords": 24, "vertices": 120, "jumps": 3, "jump_len": 5}
KOSTYA_BENCH = """// The suite's run loop with a fixed configuration in place of its JSON file, and no clock: a
// benchmark is prepared, warmed up and run, and its checksum returned.

import std;
import helper;

struct Bench { name: const u8[:], iterations: i64, warmup: i64, time: f64 }

fn config_i64(bench: u8[:], key: u8[:]) -> i64 {
@CONFIG@
    return 8;
}

fn make_bench(name: const u8[:]) -> Bench {
    return Bench { name: name, iterations: config_i64(name, "iterations"), warmup: config_i64(name, "warmup_iterations"),
                   time: 0.0 };
}

// The Benchmark class's prepare, warmup, run and checksum, with the helper's random numbers
// reset as the other runners reset them. P, R and C are the benchmark's prepare, run and
// checksum; its warmup runs R.
fn execute<P, R, C, B>(b: Bench&, s: B&) -> u32 {
    fn warmup(t: B&, iterations: i64) { for i in iterations { R(t, i); } }
    return execute_with_warmup(b, s, P, warmup, R, C);
}

// The same for a benchmark with a warmup of its own, W(s, iterations).
fn execute_with_warmup<P, W, R, C, B>(b: Bench&, s: B&) -> u32 {
    reset();
    P(s);
    W(s, b.warmup);
    reset();
    for i in b.iterations { R(s, i); }
    return C(s);
}
"""
KOSTYA_FORMAT_FIXED = """// --- fixed-point float text --------------------------------------------------

// `v` with `decimals` digits after the point, as the standard library writes it.
fn format_fixed(out: u8[>..]&, v: f64, decimals: i64) {
    format_flt(out, v, decimals);
}
"""
# Names a rename never touches, besides every name in the standard library and the compiler's builtins.
RESERVED = {"main", "it", "_", "inline", "checkfree", "root", "from", "has_default", "same", "upto"}
# The words a renamed identifier is made of: ordinary names, alone or two together, in the
# original's case (snake_case, CamelCase or UPPER_CASE).
NOUNS = ["count", "cursor", "holder", "scratch", "entry", "limit", "offset", "pending", "row", "column", "cell", "item",
         "node", "slot", "page", "chunk", "token", "frame", "batch", "span", "block", "record", "field", "pair", "edge",
         "step", "level", "depth", "width", "height", "total", "score", "weight", "mark", "label", "result", "buffer",
         "queue", "table", "grid", "tree", "shape", "point", "color", "pixel", "word", "line", "digit", "amount", "price",
         "order", "unit", "piece", "card", "player", "round", "tile", "room", "route", "stop", "client", "request",
         "reply", "message", "event", "task", "job", "worker", "timer", "tick", "rate", "ratio", "gap", "margin", "bucket",
         "window", "cache", "state", "target", "source", "origin", "anchor", "parent", "child", "owner", "group", "range"]
ADJECTIVES = ["next", "prev", "last", "first", "base", "head", "tail", "left", "right", "top", "inner", "outer", "raw",
              "old", "new", "temp", "local", "max", "min", "mid", "low", "high", "full", "spare", "extra", "start", "end",
              "best", "main", "total", "open", "free", "used", "seen"]
# Comments a developer writes, for a format input whose program's own comments cannot be used:
# alone, or about one or two of the program's names ({a}, {b}), or before a function ({f}).
PHRASES = ["may be empty", "sorted by key", "one entry per line", "see above", "cheap enough here", "keep this small",
           "order matters", "not used yet", "assumes the input is not empty", "fast path", "slow path, rarely taken",
           "first pass", "second pass", "bounds checked below", "runs once", "no allocation here", "reused below",
           "the caller owns this", "TODO: tidy this up", "TODO: handle the empty case", "FIXME: quadratic for large inputs",
           "hot loop", "simplest thing that works", "keeps the old behaviour", "wraps around", "inclusive range",
           "exclusive end", "updated in place", "a copy, not a view", "keeps the order stable", "counted from zero",
           "never negative here", "see the spec", "for debugging", "stops at the first match", "in bytes", "one per item"]
NAME_PHRASES = ["{a} may be empty", "{a} is sorted here", "reset {a} each round", "{a} holds the running total",
                "see {a} below", "{a} only grows here", "{a} starts at zero", "{a} comes from above",
                "{a} is owned by the caller", "updates {a} in place", "{a} and {b} change together",
                "{a} is never null here", "check {a} first", "{a} is reused below", "{a} before {b}"]
DOC_PHRASES = ["{f} walks the input once.", "{f} is called once per item.", "Helper used by main.",
               "{f}: the simple version.", "Kept apart so main stays short.", "{f} returns early on bad input.",
               "{f} does the real work.", "See main for how {f} is used."]
# Comments upstream's test runner reads, never kept in a program's own comments: expected errors
# and warnings, defines, specs, bounds-check annotations, and first-line run markers.
MARKERS = re.compile(r"//\s*(error:|warning:|runtime-define:|spec\b|bce:)")
FIRST_LINE_MARKERS = re.compile(r"//\s*(runtime-debug|dump-runtime|all-levels|no-jit|parse-only|lsp)\b")


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


def strip_comments(text: str, drop=lambda comment, first: True) -> str:
    """The text without the comments `drop` picks (all by default; it is given each comment's
    text and whether it starts the file): a line that held only such comments goes, and so does
    a run of blank lines beyond one. Text that does not lex (Markdown, a broken test) loses its
    `//` comments line by line and its `/* */` comments by pattern."""
    try:
        spans = [(t.start, t.end) for t in lex(text) if t.kind == "comment" and drop(t.text, "\n" not in text[:t.start])]
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


def strip_markers(text: str) -> str:
    """The text without the comments upstream's test runner reads (MARKERS, FIRST_LINE_MARKERS),
    its prose comments kept."""
    return strip_comments(text, lambda comment, first: bool(MARKERS.match(comment) or
                                                             first and FIRST_LINE_MARKERS.match(comment)))


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
    messages: tuple[str, ...] = ()   # The errors and warnings its comments name (`// error:`, `// warning:`).
    complete: bool = False    # Upstream expects it to run to the end: exit 0.
    silent: bool = False      # Upstream expects it to abort before printing anything.
    edit: tuple[str, ...] = ("main.goose",)   # The files an edit of its literals may touch.

    def stripped(self) -> dict[str, str]:
        return {name: strip_comments(text) for name, text in self.files.items()}

    def lines(self) -> int:
        return sum(1 for text in self.files.values() for line in text.split("\n") if line.strip())


def family(key: str) -> str:
    """The programs written as variants of one another, which go to one side together: a test with
    the same name but its last word, a benchmark with the same first word, or one LangArena program."""
    if key.startswith("test/"):
        directory, _, name = key[len("test/"):].rpartition("/")
        stem = name[:-len(".goose")]
        # The standard library's tests are named stdlib_<module>: each module's test is its own.
        return f"test/{directory}/{stem if directory == 'stdlib' else stem.rsplit('_', 1)[0]}"
    if key.startswith("bench/goose/"):
        return "bench/" + key[len("bench/goose/"):].split("_", 1)[0].split(".", 1)[0]
    if key.startswith(f"{KOSTYA}#"):  # the programs that share a module of their own are one family
        return "kostya/" + key.split("#", 1)[1].split("_", 1)[0].split("+", 1)[0]
    return key


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


def kostya_programs(checkout: Path) -> list[Program]:
    """LangArena's benchmarks as programs: for each group of the runner's dispatch blocks that use
    the same benchmark modules, a main.goose with those blocks and a main that runs every
    benchmark they name once and prints its checksum; KOSTYA_BENCH as bench.goose; the helper
    without its C library externs; and the modules, with the local modules they import."""
    src = checkout / KOSTYA
    if not (src / "main.goose").is_file():
        return []
    runner = (src / "main.goose").read_text(encoding="utf-8")
    head = "fn dispatch(b: Bench&) -> u32, bool {\n    let n = b.name;\n"
    body = runner[runner.index(head) + len(head):runner.index("    return 0, false;\n}", runner.index(head))]
    modules = {path.stem for path in src.glob("*.goose")}
    blocks, current, depth = [], [], 0
    for line in body.split("\n"):
        if not current and not line.startswith("    if "):
            continue
        current.append(line)
        toks = code(lex(strip_comments(line))) if line.strip() else []
        depth += sum(1 for kind, text in toks if text == "{") - sum(1 for kind, text in toks if text == "}")
        if depth == 0:
            blocks.append("\n".join(current))
            current = []
    grouped: dict[frozenset, list[str]] = {}
    for block in blocks:
        used = frozenset(name for name in re.findall(r"\b(\w+)::", block) if name in modules)
        if used and not used & KOSTYA_LEFT_OUT:
            grouped.setdefault(used, []).append(block)
    config = "\n".join(f'    if key == "{key}" {{ return {value}; }}' for key, value in KOSTYA_CONFIG.items())
    harness = KOSTYA_BENCH.replace("@CONFIG@", config)
    helper = (src / "helper.goose").read_text(encoding="utf-8")
    helper = helper[:helper.index("// --- exact fixed-point float text")] + KOSTYA_FORMAT_FIXED
    found = []
    for used, chosen in sorted(grouped.items(), key=lambda item: sorted(item[0])):
        names = list(dict.fromkeys(name for block in chosen for name in re.findall(r'n == "([^"]+)"', block)))
        files = {"bench.goose": harness, "helper.goose": helper}
        todo = sorted(used)
        while todo:
            name = todo.pop()
            if f"{name}.goose" in files:
                continue
            text = (src / f"{name}.goose").read_text(encoding="utf-8")
            if not usable(text, local=True, module=True):
                break
            files[f"{name}.goose"] = text
            todo += [i for i in imports(text) if i in modules and i not in ("bench", "helper")]
        else:
            calls = "\n".join(f'    var b{i} = make_bench("{name}");\n    let sum{i}, found{i} = dispatch(b{i});\n'
                              f'    assert(found{i});\n    print("{name}: ", sum{i});' for i, name in enumerate(names))
            main = (f"// LangArena's {', '.join(names)}, run with the fixed configuration of bench.goose:\n"
                    "// each prints its checksum.\n\nimport std;\nimport slice_pool;\nimport bench;\nimport helper;\n"
                    + "".join(f"import {name};\n" for name in sorted(used)) + "\n"
                    "// The checksum of one benchmark, or false for a name with no implementation.\n"
                    + head + "\n".join(chosen) + "\n    return 0, false;\n}\n\nfn main() {\n" + calls + "\n}\n")
            if usable(main, local=True):
                key = f"{KOSTYA}#{'+'.join(sorted(used))}"
                found.append(Program(key, "run", {"main.goose": main, **dict(sorted(files.items()))}, False, None,
                                     complete=True, edit=tuple(f"{name}.goose" for name in sorted(used))))
    return found


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
                aborts = (tests / "expected" / f"{path.stem}.aborts").is_file()
                silent = aborts and expected(path.stem).is_file() and not expected(path.stem).read_text().strip()
                messages = tuple(re.findall(r"//\s*(?:error|warning):\s*(.*?)\s*$", text, re.M))
                found.append(Program(f"test/{directory}/{path.name}", role, files, "// warning:" in text,
                                     digest(path.stem) if role == "run" else None, messages,
                                     role == "run" and not aborts, bool(silent)))
    for path in sorted((checkout / "bench" / "goose").glob("*.goose")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if BENCH_N.search(text) and "fn main" in text:
            files = module_files(path, path.parent)
            if files is not None:
                found.append(Program(f"bench/goose/{path.name}", "run", files, False, None, complete=True))
    found += kostya_programs(checkout)
    for path in sorted((checkout / "samples").glob("*.goose")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if usable(text) and "fn main" in text:
            found.append(Program(f"samples/{path.name}", "shown", {"main.goose": text}, False, None))
    for index, text in enumerate(doc_programs(checkout)):
        found.append(Program(f"docs#{index}", "shown", {"main.goose": text}, False, None))
    return found


def share(name: str) -> float:
    return int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def visible_families(programs: list[Program]) -> set[str]:
    """The families (`family`) on the visible side: the samples and the documentation's programs,
    and a fixed VISIBLE_SHARE of the others by the hash of their family's name, adjusted so that
    each side keeps some of every kind the cases test on purpose. Programs whose check prints
    warnings get at least three visible families of their own, and every library module keeps a
    private family, and a visible one where it has two or more."""
    families = {family(p.key) for p in programs if p.key.startswith(("test/", "bench/"))}
    visible = {name for name in families if share(name) < VISIBLE_SHARE}
    warned = sorted({family(p.key) for p in programs if p.warnings}, key=share)
    visible |= set(warned[:max(3, round(VISIBLE_SHARE * len(warned)))])
    for module in sorted(LIBRARY):
        using = sorted({family(p.key) for p in programs if p.key.startswith(("test/", "bench/")) and
                        any(module in imports(text) for text in p.files.values())}, key=share)
        if using and all(name in visible for name in using):
            visible.discard(using[-1])
        if len(using) >= 2 and not any(name in visible for name in using):
            visible.add(using[0])
    return visible | {family(p.key) for p in programs if not p.key.startswith(("test/", "bench/"))}


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


def shared_modules(checkout: Path) -> set[str]:
    """The normalised texts of the modules many programs share as they are, which are no input of
    a program's own: the benchmarks' random number module, and LangArena's harness and helper."""
    texts = {normalise((checkout / "bench" / "goose" / "rng.goose").read_text(encoding="utf-8"))}
    for program in kostya_programs(checkout)[:1]:
        texts |= {normalise(program.files[name]) for name in ("bench.goose", "helper.goose")}
    return texts


def leaks(private: list[dict], visible: list[dict], shipped: str, shared: set[str]) -> list[str]:
    """The private cases with an input that, comments and whitespace aside, is in a shipped file
    or is an input of a visible case. A module many programs share unchanged is no input of its
    own (`shared`, by content: shared_modules)."""
    seen = {normalise(text) for case in visible for text in inputs(case)}
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


def _layout(text: str) -> tuple[list[Tok], list[str], list[int], dict[int, Tok]]:
    """The text's tokens, its lines, where each line starts, and for each line that starts with a
    token (not inside a raw string or a comment) that token."""
    toks = lex(text)
    starts = line_starts(text)
    first: dict[int, Tok] = {}
    for tok in toks:
        line = bisect.bisect_right(starts, tok.start) - 1
        if line not in first and text[starts[line]:tok.start].strip() == "":
            first[line] = tok
    return toks, text.split("\n"), starts, first


def _ends_outside(text: str, toks: list[Tok], starts: list[int], line: int) -> bool:
    """Whether the line ends outside any token (a raw string or a block comment)."""
    end = starts[line + 1] - 1 if line + 1 < len(starts) else len(text)
    return not any(t.start < end < t.end for t in toks)


CLOSERS = {")", "]", "}"}
OPERATORS = {"=", "==", "!=", "<=", ">=", "+", "-", "*", "/", "%", "+=", "-=", "*=", "/=", "&&", "||", "->", "=>"}


def reindent(text: str, unit: str) -> str:
    """Every indentation level of four spaces written as `unit` instead, where a line starts with a token."""
    _, lines, _, first = _layout(text)
    for line in first:
        lead = len(lines[line]) - len(lines[line].lstrip(" "))
        lines[line] = unit * (lead // 4) + " " * (lead % 4) + lines[line][lead:]
    return "\n".join(lines)


def slip_compact(rng: random.Random, text: str, every: bool = False) -> str:
    """No space around operators and after commas, on a line or two (or every line)."""
    toks, _, starts, _ = _layout(text)
    code_toks = [t for t in toks if t.kind != "comment"]
    lines = {bisect.bisect_right(starts, t.start) - 1 for t in code_toks if t.text in OPERATORS | {","}}
    if not lines:
        return text
    chosen = lines if every else set(rng.sample(sorted(lines), min(len(lines), rng.randint(1, 2))))
    cuts = []
    for prev, cur in zip(code_toks, code_toks[1:]):
        if text[prev.end:cur.start] != " " or bisect.bisect_right(starts, prev.start) - 1 not in chosen:
            continue
        if (cur.text in OPERATORS or prev.text in OPERATORS or prev.text == ",") and _glues(prev, cur):
            cuts.append(prev.end)
    for at in sorted(cuts, reverse=True):
        text = text[:at] + text[at + 1:]
    return text


def slip_brackets(rng: random.Random, text: str) -> str:
    """Spaces inside the brackets of a call or an index, on one line."""
    toks, _, starts, _ = _layout(text)
    code_toks = [t for t in toks if t.kind != "comment"]
    spots = [k for k in range(len(code_toks) - 1) if code_toks[k].text in ("(", "[") and
             code_toks[k + 1].text not in CLOSERS and code_toks[k].end == code_toks[k + 1].start]
    if not spots:
        return text
    k = rng.choice(spots)
    depth, j = 0, k
    while j < len(code_toks):
        depth += code_toks[j].text in ("(", "[", "{")
        depth -= code_toks[j].text in CLOSERS
        if depth == 0:
            break
        j += 1
    if j >= len(code_toks) or "\n" in text[code_toks[k].start:code_toks[j].end]:
        return text
    close, open_ = code_toks[j], code_toks[k]
    text = text[:close.start] + " " + text[close.start:]
    return text[:open_.end] + " " + text[open_.end:]


def slip_indent(rng: random.Random, text: str) -> str:
    """A line indented a space or two off, or a run of lines left one level out or in."""
    _, lines, _, first = _layout(text)
    indented = sorted(line for line, tok in first.items() if lines[line].startswith("    ") and tok.text not in CLOSERS)
    if not indented:
        return text
    if rng.random() < 0.5:
        line = rng.choice(indented)
        lines[line] = (" " * rng.choice([1, 2]) + lines[line]) if rng.random() < 0.6 else lines[line][rng.choice([1, 2]):]
        return "\n".join(lines)
    at = rng.randrange(len(indented))
    run = [line for line in indented[at:at + rng.randint(2, 4)] if line - indented[at] < 6]
    out = rng.random() < 0.5
    for line in run:
        lines[line] = lines[line][4:] if out else "    " + lines[line]
    return "\n".join(lines)


def slip_trailing(rng: random.Random, text: str) -> str:
    """Trailing spaces at the end of a line or two."""
    toks, lines, starts, _ = _layout(text)
    spots = [k for k, line in enumerate(lines) if line.strip() and _ends_outside(text, toks, starts, k)]
    for line in rng.sample(spots, min(len(spots), rng.randint(1, 2))):
        lines[line] += rng.choice([" ", "  ", "   "])
    return "\n".join(lines)


def slip_blank(rng: random.Random, text: str) -> str:
    """One blank line more where there is one already."""
    toks, lines, starts, _ = _layout(text)
    spots = [k for k, line in enumerate(lines) if not line.strip() and 0 < k < len(lines) - 1
             and _ends_outside(text, toks, starts, k) and _ends_outside(text, toks, starts, k - 1)]
    if not spots:
        return text
    at = rng.choice(spots)
    lines.insert(at, "")
    return "\n".join(lines)


def slip_comma(rng: random.Random, text: str) -> str:
    """The trailing comma left off a list whose closing bracket starts a line (the formatter adds it)."""
    toks = [t for t in lex(text) if t.kind != "comment"]
    spots = [prev for prev, cur in zip(toks, toks[1:]) if prev.text == "," and cur.text in CLOSERS
             and "\n" in text[prev.end:cur.start]]
    if not spots:
        return text
    comma = rng.choice(spots)
    return text[:comma.start] + text[comma.end:]


def slip_column(rng: random.Random, text: str) -> str:
    """A column of a lined-up table or comment run off by a space or more."""
    toks, _, starts, _ = _layout(text)
    gaps = [(prev.end, cur.start) for prev, cur in zip(toks, toks[1:])
            if cur.start - prev.end >= 2 and "\n" not in text[prev.end:cur.start]]
    if not gaps:
        return text
    start, end = rng.choice(gaps)
    width = max(1, end - start + rng.choice([-2, -1, 1, 2]))
    return text[:start] + " " * width + text[end:]


def slip_wrap(rng: random.Random, text: str) -> str:
    """A long line broken after a comma inside brackets, the rest a level or two further in."""
    toks, lines, starts, _ = _layout(text)
    code_toks = [t for t in toks if t.kind != "comment"]
    spots = []
    for prev, cur in zip(code_toks, code_toks[1:]):
        line = bisect.bisect_right(starts, prev.start) - 1
        if prev.text == "," and text[prev.end:cur.start] == " " and len(lines[line]) >= 60:
            spots.append((prev, line))
    if not spots:
        return text
    comma, line = rng.choice(spots)
    lead = len(lines[line]) - len(lines[line].lstrip(" "))
    return text[:comma.end] + "\n" + " " * (lead + rng.choice([4, 8])) + text[comma.end + 1:]


def slip_brace(rng: random.Random, text: str) -> str:
    """A one-line block written tight against its braces: {x} for { x }."""
    toks = [t for t in lex(text) if t.kind != "comment"]
    spots = [(prev, cur) for prev, cur in zip(toks, toks[1:]) if text[prev.end:cur.start] == " " and
             ((prev.text == "{" and cur.text != "}") or (cur.text == "}" and prev.text != "{")) and _glues(prev, cur)]
    if not spots:
        return text
    prev, cur = rng.choice(spots)
    return text[:prev.end] + text[cur.start:]


SLIPS = (slip_compact, slip_brackets, slip_indent, slip_trailing, slip_blank, slip_comma, slip_column, slip_wrap, slip_brace)


def disturb(rng: random.Random, text: str) -> str:
    """The file as a person leaves it before running the formatter: in a style of its own throughout
    (two-space indentation, now and then tabs, operators written tight), or with a few slips
    (SLIPS: a line or block indented off, spacing around an operator or inside brackets, a
    trailing comma left off, a column out of line, a long line wrapped, trailing spaces, an extra
    blank line). Every token stays but a trailing comma; the text is unchanged where nothing applies."""
    for _ in range(10):
        roll, new = rng.random(), text
        if roll < 0.18:
            new = reindent(text, "  ")
            new = rng.choice(SLIPS)(rng, new) if rng.random() < 0.5 else new
        elif roll < 0.22:
            new = reindent(text, "\t")
        elif roll < 0.28:
            new = slip_compact(rng, text, every=True)
        else:
            for slip in rng.sample(SLIPS, rng.randint(1, 3)):
                new = slip(rng, new)
        if new != text and lexes(new) and [t for t in code(lex(new)) if t != ("punct", ",")] == \
                [t for t in code(lex(text)) if t != ("punct", ",")]:
            return new
    return text


def add_comments(rng: random.Random, text: str, count: int) -> str:
    """Comments where people write them: a line of documentation before a function or a struct,
    a note on a line of its own before a statement (indented as it, never before a closing
    bracket), a note after a statement; and in one file in ten an argument's name in a block
    comment before a literal argument."""
    toks, lines, starts, first = _layout(text)
    names = sorted({t.text for t in toks if t.kind == "ident" and len(t.text) > 2})
    if not names:
        return text
    phrase = lambda: (rng.choice(NAME_PHRASES).format(a=rng.choice(names), b=rng.choice(names))  # noqa: E731
                      if rng.random() < 0.4 else rng.choice(PHRASES))
    code_toks = [t for t in toks if t.kind != "comment"]
    after = {bisect.bisect_right(starts, t.start) - 1 for t in toks if t.kind == "comment"}
    edits: dict[int, str] = {}
    for _ in range(count):
        roll = rng.random()
        if roll < 0.3:
            spots = [(line, tok) for line, tok in first.items() if tok.text in ("fn", "struct", "enum") and
                     not lines[line][:1].isspace() and line - 1 not in after]
            if spots:
                line, tok = rng.choice(spots)
                index = code_toks.index(tok) if tok in code_toks else -1
                name = code_toks[index + 1].text if 0 <= index < len(code_toks) - 1 else "it"
                edits.setdefault(starts[line], "// " + rng.choice(DOC_PHRASES).format(f=name) + "\n")
        elif roll < 0.65:
            spots = [(line, tok) for line, tok in first.items() if lines[line][:1].isspace() and tok.text not in CLOSERS
                     and tok.kind != "comment" and line - 1 not in after]
            if spots:
                line, tok = rng.choice(spots)
                indent = lines[line][:len(lines[line]) - len(lines[line].lstrip())]
                edits.setdefault(starts[line], f"{indent}// {phrase()}\n")
        else:
            spots = [k for k, line in enumerate(lines) if line.rstrip().endswith((";", "{")) and k not in after
                     and len(line) < 72 and _ends_outside(text, toks, starts, k)]
            if spots:
                line = rng.choice(spots)
                edits.setdefault(starts[line] + len(lines[line].rstrip()), rng.choice([" ", "  "]) + f"// {phrase()}")
    if rng.random() < 0.1:
        spots = [cur for prev, cur in zip(code_toks, code_toks[1:]) if prev.text in ("(", ",") and cur.kind == "int"]
        if spots:
            tok = rng.choice(spots)
            edits.setdefault(tok.start, f"/*{rng.choice(NOUNS)}=*/")
    new = text
    for at in sorted(edits, reverse=True):
        new = new[:at] + edits[at] + new[at:]
    try:
        return new if code(lex(new)) == code(toks) else text
    except LexError:
        return text


def shift(rng: random.Random, text: str) -> str:
    """Positions moved without touching a token: a blank line or two before a line that starts
    with a token (never the first), and a run of such lines indented a level further."""
    _, lines, _, first = _layout(text)
    starts = sorted(line for line in first if line > 0)
    if not starts:
        return text
    indent = rng.random() < 0.5
    if rng.random() < 0.85 or not indent:
        at = rng.choice(starts)
        added = rng.choice([1, 1, 2])
        lines[at:at] = [""] * added
        starts = [line + added if line >= at else line for line in starts]
    if indent:
        first_line = rng.randrange(len(starts))
        for line in starts[first_line:first_line + rng.randint(1, 4)]:
            lines[line] = "    " + lines[line]
    new = "\n".join(lines)
    return new if new != text and _same_tokens(text, new) else text


def natural_name(rng: random.Random, word: str, taken: set[str]) -> str:
    """An ordinary name for `word`, one or two words in its case (UPPER_CASE, CamelCase or
    snake_case) and with its leading underscore, that clashes with nothing in `taken`; a number
    is added only where every draw clashes."""
    core = word.lstrip("_")
    style = "upper" if core.isupper() else "camel" if core[:1].isupper() else "snake"
    for attempt in range(40):
        parts = [rng.choice(NOUNS)] if rng.random() < 0.45 else [rng.choice(ADJECTIVES + NOUNS), rng.choice(NOUNS)]
        if len(parts) == 2 and parts[0] == parts[1]:
            continue
        name = ("_".join(parts).upper() if style == "upper" else "".join(part.capitalize() for part in parts)
                if style == "camel" else "_".join(parts))
        name = word[:len(word) - len(core)] + name + (str(attempt - 28) if attempt > 30 else "")
        if name not in taken and name != word:
            return name
    raise SystemExit(f"no clash-free name for {word}")


def rename(rng: random.Random, files: dict[str, str], protected: set[str], count: int,
           prefer: tuple[str, ...] = ()) -> tuple[dict[str, str], dict[str, str]]:
    """The files with `count` of the program's own names (first those in `prefer`, all of them,
    where the program has them) replaced everywhere by ordinary ones that clash with nothing,
    keeping a leading underscore and the name's case; in comments too, as whole words."""
    try:
        toks = {name: lex(text) for name, text in files.items()}
    except LexError:
        return files, {}
    modules = {part for name in files for part in re.split(r"[/.]", name)}
    candidates = sorted({t.text for ts in toks.values() for t in ts if t.kind == "ident"} - protected - modules)
    if not candidates:
        return files, {}
    taken = {t.text for ts in toks.values() for t in ts if t.kind == "ident"} | protected | modules | KEYWORDS
    first = [word for word in candidates if word in set(prefer)][:4]
    rest = [word for word in candidates if word not in first]
    mapping: dict[str, str] = {}
    for word in first + rng.sample(rest, max(0, min(count, len(candidates)) - len(first))):
        new = natural_name(rng, word, taken)
        taken.add(new)
        mapping[word] = new
    if not mapping:
        return files, {}
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted(mapping, key=len, reverse=True))) + r")\b")
    out = {}
    for name, text in files.items():
        parts, pos = [], 0
        for tok in toks[name]:
            if tok.kind == "ident" and tok.text in mapping:
                parts += [text[pos:tok.start], mapping[tok.text]]
                pos = tok.end
            elif tok.kind == "comment":
                parts += [text[pos:tok.start], pattern.sub(lambda m: mapping[m.group(1)], tok.text)]
                pos = tok.end
        out[name] = "".join(parts) + text[pos:]
    return out, mapping


# ---------------------------------------------------------------- edits that change a program

def code_lines(text: str) -> list[int]:
    return [i for i, line in enumerate(text.split("\n")) if line.strip() and line.strip() not in ("{", "}", "};")]


def literal_spots(text: str) -> list[Tok]:
    """The integer literals an edit may change, where they are values that flow into what the
    program computes: not inside an assert, a match, an array type's size, a repeat count, an
    index or a slice, or a shift amount."""
    try:
        toks = [t for t in lex(text) if t.kind != "comment"]
    except LexError:
        return []
    lines, starts = text.split("\n"), line_starts(text)
    spots = []
    for k, tok in enumerate(toks):
        if tok.kind != "int" or not tok.text.isdigit() or len(tok.text) > 4:
            continue
        before = toks[k - 1].text if k else ""
        after = toks[k + 1].text if k + 1 < len(toks) else ""
        line = lines[bisect.bisect_right(starts, tok.start) - 1]
        loop = line.lstrip().startswith("for ") and "[" not in line
        if before in ("[", ";", "<<", ">>", "<<=", ">>=") or after in ("]", "=>", ":") or \
                (".." in (before, after) and not loop) or "assert" in line or "match" in line:
            continue
        spots.append(tok)
    return spots


def mutate_literal(rng: random.Random, text: str) -> str:
    spots = literal_spots(text)
    if not spots:
        return text
    tok = rng.choice(spots)
    value = int(tok.text)
    new = rng.choice([value + 1, value - 1, value + rng.randint(2, 9), value * 2])
    new = new if new >= 0 and new != value else value + 1
    return text[:tok.start] + str(new) + text[tok.end:]


def mutate_string(rng: random.Random, text: str) -> str:
    """One word of a string that a print prints changed for another, outside its escapes."""
    try:
        toks = [t for t in lex(text) if t.kind == "string" and not t.text.startswith('"""')]
    except LexError:
        return text
    lines, starts = text.split("\n"), line_starts(text)
    spots = []
    for tok in toks:
        line = lines[bisect.bisect_right(starts, tok.start) - 1]
        if "print" in line and "assert" not in line:
            spots += [(tok.start + m.start(), tok.start + m.end()) for m in re.finditer(r"[A-Za-z]{3,}", tok.text)
                      if tok.text[m.start() - 1] != "\\"]
    if not spots:
        return text
    start, end = rng.choice(spots)
    word = rng.choice([w for w in NOUNS if w != text[start:end].lower()])
    word = word.capitalize() if text[start].isupper() else word
    return text[:start] + word + text[end:]


def mutate_operator(rng: random.Random, text: str) -> str:
    swaps = [(" < ", " <= "), (" > ", " >= "), (" + ", " - "), (" * ", " + "), (" == ", " != "), (" && ", " || ")]
    lines = text.split("\n")
    spots = [(k, m.start(), a, b) for k, line in enumerate(lines) if "assert" not in line
             for a, b in swaps for m in re.finditer(re.escape(a), line)]
    if not spots:
        return text
    k, at, a, b = rng.choice(spots)
    lines[k] = lines[k][:at] + b + lines[k][at + len(a):]
    return "\n".join(lines)


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


def mutate(rng: random.Random, text: str) -> str:
    """One to three edits that break the program as people break one while editing: a name
    misspelt, a line deleted or doubled, an operator changed; retried where an edit changes
    nothing. A file never starts with a blank line."""
    edits = [mutate_name, mutate_line, mutate_operator]
    for _ in range(rng.randint(1, 3)):
        for _ in range(6):
            edited = rng.choice(edits)(rng, text)
            if edited != text:
                text = edited
                break
    return text.lstrip("\n")


# ---------------------------------------------------------------- cases

class Built(NamedTuple):
    case: dict
    kind: str
    keys: list[str]           # The programs it is built on.
    changed: bool             # Its answer differs from what upstream publishes for the program (best known).


class Side:
    """The programs of one side, the names a rename leaves alone, and the answer texts upstream
    publishes, which no comment of an input may hold."""

    def __init__(self, programs: list[Program], protected: set[str], answers: set[str]):
        self.protected = protected
        self.answers = answers
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


LINES: dict[str, int] = {}


def pick(rng: random.Random, pool: list[Program]) -> Program:
    """A program of the pool, larger ones more often (weight the square root of its lines), and
    tests that abort before printing anything seldom."""
    weights = [min(LINES.setdefault(p.key, p.lines()), 400) ** 0.5 * (0.1 if p.silent else 1.0) for p in pool]
    return rng.choices(pool, weights)[0]


def renamed(rng: random.Random, side: Side, program: Program, positions: bool = False) -> tuple[dict[str, str], bool]:
    """The program's files without comments, one to three names renamed (first the names its
    expected errors and warnings mention), and with `positions` lines moved; and whether
    anything changed."""
    files, mapping = rename(rng, program.stripped(), side.protected, rng.randint(1, 3),
                            prefer=tuple(re.findall(r"[A-Za-z_]\w*", " ".join(program.messages))))
    if positions and lexes(files["main.goose"]):
        files = dict(files, **{"main.goose": shift(rng, files["main.goose"])})
    return files, bool(mapping) or files != program.stripped()


def edited(rng: random.Random, files: dict[str, str], program: Program, strings: float, operators: float) -> dict | None:
    """The files with a literal of one of the program's own files changed (program.edit), and by
    the given shares a printed string and an operator too; None where nothing applies."""
    names = [name for name in program.edit if name in files]
    for _ in range(8):
        name = rng.choice(names)
        text = files[name]
        new = mutate_literal(rng, text)
        if rng.random() < strings:
            new = mutate_string(rng, new)
        if rng.random() < operators:
            new = mutate_operator(rng, new)
        new = new if new != text else mutate_string(rng, text)
        if new != text:
            return dict(files, **{name: new})
    return None


def run_argv(rng: random.Random, program: Program) -> list[str]:
    argv = ["run", "main.goose"] if rng.random() < 0.9 else ["main.goose"]
    if rng.random() < 0.12:
        argv.append(rng.choice(["-O0", "-O1"]))
    if rng.random() < 0.1:
        argv.append("--debug")
    if program.warnings and rng.random() < 0.5:
        argv += ["--diagnostics", "json"]
    return argv


def make_run(rng: random.Random, side: Side, pool: list[Program], kind: str) -> Built:
    """A program, renamed, with up to three edits of its literals for the recorder to choose from
    (runcases.settle): the first that ends as the unedited program does and prints otherwise."""
    program = pick(rng, pool)
    base, changed = renamed(rng, side, program)
    options = []
    for _ in range(3):
        option = edited(rng, base, program, strings=0.5 if kind == "library" else 0.2, operators=0.15)
        if option and option not in options:
            options.append(option)
    case = {"files": options[0] if options else base, "argv": run_argv(rng, program), "stdin": None}
    if options:
        case["record"] = {"variants": options[1:] + [base], "want": "same", "complete": program.complete}
    return Built(case, kind, [program.key], changed or bool(options))


def make_rejected(rng: random.Random, side: Side) -> Built:
    program = rng.choice(side.errors)
    files, changed = renamed(rng, side, program, positions=True)
    argv = ["run", "main.goose", "--diagnostics", "json"] if rng.random() < 0.97 else ["run", "main.goose"]
    return Built({"files": files, "argv": argv, "stdin": None}, "rejected", [program.key], changed)


def make_check(rng: random.Random, side: Side) -> Built:
    roll = rng.random()
    argv = ["check", "main.goose", "--diagnostics", "json"]
    if rng.random() < 0.1:
        argv[1:1] = ["--color", "never"]
    record = None
    if roll < 0.62:
        program = rng.choice(side.errors)
        files, changed = renamed(rng, side, program, positions=True)
    elif roll < 0.92:  # a program broken while editing it, three ways for the recorder to choose from
        program = pick(rng, side.run + side.shown)
        files, _ = renamed(rng, side, program, positions=rng.random() < 0.5)
        options = []
        for _ in range(3):
            option = dict(files, **{"main.goose": mutate(rng, files["main.goose"])})
            if option not in options and option != files:
                options.append(option)
        files = options[0] if options else files
        record = {"variants": options[1:], "want": "diagnostics"} if len(options) > 1 else None
        changed = True
    else:
        program = rng.choice(side.warned or side.errors)
        files, changed = renamed(rng, side, program, positions=True)
    case = {"files": files, "argv": argv, "stdin": None}
    if record:
        case["record"] = record
    return Built(case, "check", [program.key], changed)


class FormatPlan(NamedTuple):
    """A format case before its comments are chosen: which programs go where."""
    stdin: bool
    argv: list[str]
    places: list[tuple[str, Program, bool]]   # (file name or "-" for standard input, program, formatted first)


FORMAT_NAMES = ["main.goose", "lib.goose", "util.goose", "src/app.goose", "src/model.goose", "src/text/parse.goose",
                "tools/gen.goose"]


def plan_format(rng: random.Random, side: Side) -> FormatPlan:
    """Standard input four times in five; else a workspace for --check of one to three files, all
    formatted already, some of them, or none."""
    if rng.random() < 0.8:
        return FormatPlan(True, ["format"] if rng.random() < 0.8 else ["format", "-"], [("-", pick(rng, side.formattable), False)])
    names = rng.sample(FORMAT_NAMES, rng.randint(1, 3))
    roll = rng.random()
    tidy = [True] * len(names) if roll < 0.3 else [False] * len(names) if roll >= 0.8 else \
        [rng.random() < 0.5 for _ in names]
    if 0.3 <= roll < 0.8 and len(names) > 1 and len(set(tidy)) == 1:
        tidy[rng.randrange(len(names))] = not tidy[0]
    places = [(name, pick(rng, side.formattable), formatted) for name, formatted in zip(names, tidy)]
    target = rng.choice([".", "src", names[0]]) if any(name.startswith("src/") for name in names) else rng.choice([".", names[0]])
    return FormatPlan(False, ["format", "--check", target], places)


def quotes_an_answer(comment: str, answers: set[str]) -> bool:
    return any(answer in comment for answer in answers)


def own_comments(program: Program, side: Side) -> str:
    """The program's text with its own comments but those upstream's test runner reads (MARKERS,
    FIRST_LINE_MARKERS) and those that quote an answer upstream publishes for any program."""
    return strip_comments(program.files["main.goose"], lambda comment, first: bool(
        MARKERS.match(comment) or first and FIRST_LINE_MARKERS.match(comment) or quotes_an_answer(comment, side.answers)))


def build_format(rng: random.Random, side: Side, plan: FormatPlan, busy: set[str]) -> Built:
    """Comments from the program itself where no other case is built on its family (`busy`), else
    comments of the kind people write; then renames, and the layout a person leaves (`disturb`)
    in a file not formatted first. A file formatted first is left for the recorder to format."""
    texts, changed, formatted = {}, not plan.stdin, []
    for name, program, tidy in plan.places:
        own = family(program.key) not in busy and any(t.kind == "comment" for t in lex(own_comments(program, side)))
        if own:
            text, mapping = rename(rng, {"main.goose": own_comments(program, side)}, side.protected, rng.randint(1, 3))
        else:
            text, mapping = rename(rng, {"main.goose": strip_comments(program.files["main.goose"])}, side.protected,
                                   rng.randint(1, 3))
            text = {"main.goose": add_comments(rng, text["main.goose"], max(1, min(6, program.lines() // 15)))}
        changed = changed or not own or bool(mapping)
        if tidy:
            formatted.append(name)
            texts[name] = text["main.goose"]
        else:
            texts[name] = disturb(rng, text["main.goose"])
    keys = [program.key for _, program, _ in plan.places]
    if plan.stdin:
        return Built({"files": {}, "argv": plan.argv, "stdin": texts["-"]}, "format", keys, changed)
    case = {"files": texts, "argv": plan.argv, "stdin": None}
    if formatted:
        case["record"] = {"formatted": formatted}
    return Built(case, "format", keys, changed)


def make_cli(rng: random.Random, side: Side, argv: list[str]) -> Built:
    program = rng.choice(side.run + side.errors)
    files, _ = renamed(rng, side, program)
    case = {"files": {"main.goose": files["main.goose"]}, "argv": list(argv), "stdin": None, "record": {"cli": True}}
    return Built(case, "cli", [program.key], True)


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
        pick_, kind = rng.random(), None
        for name, share_ in KINDS:
            pick_ -= share_
            if pick_ < 0:
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
    busy = {family(key) for item in built.values() if isinstance(item, Built) and item.kind != "format" for key in item.keys}
    out = []
    for index in range(first, first + count):
        item = built[index]
        if isinstance(item, FormatPlan):
            item = build_format(rng_for(index + 7_000_000), side, item, busy)
        item.case["id"] = f"{prefix}{index + 1:05d}"
        out.append(item)
    return out


def fingerprints(cases: list[dict]) -> dict:
    """Marks a generator could leave, counted over the inputs: names with a number on the end that
    the source does not have, lines starting with a tab, block comments, inputs that start with a
    blank line, and comments upstream's test runner reads."""
    texts = [text for case in cases for text in inputs(case)]
    lines = [line for text in texts for line in text.split("\n")]
    numbered = sum(1 for text in texts for word in set(re.findall(r"\b[A-Za-z_]+\d{1,2}\b", text))
                   if word.rstrip("0123456789").lower() in set(NOUNS) | {"_" + n for n in NOUNS})
    return {"inputs": len(texts), "lines": len(lines), "lines_starting_with_a_tab": sum(line.startswith("\t") for line in lines),
            "block_comments": sum(text.count("/*") for text in texts), "starting_with_a_blank_line": sum(
                text.startswith("\n") for text in texts), "runner_markers": sum(
                1 for text in texts for line in text.split("\n") if MARKERS.search(line)), "numbered_names": numbered}


def lines_summary(built: list[Built], by_key: dict) -> dict:
    sizes = sorted(by_key[b.keys[0]].lines() for b in built)
    return {"median": sizes[len(sizes) // 2], "p90": sizes[int(0.9 * (len(sizes) - 1))], "max": sizes[-1],
            "at_least_80": sum(size >= 80 for size in sizes)} if sizes else {}


def library_use(cases: list[dict]) -> dict:
    return dict(sorted(Counter(module for case in cases if case.get("kind", "") != "cli"
                               for module in {m for text in case["files"].values() for m in imports(text)} & LIBRARY).items()))


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
    shared = shared_modules(args.checkout)
    families = visible_families(programs)
    visible = [p for p in programs if family(p.key) in families]
    # A private program must be unknown to the agent: no shown program and no variant of one,
    # nothing a shipped file holds, nothing equal to a visible program.
    seen = {normalise(text) for p in visible for text in p.files.values()} - shared
    excluded = sorted(p.key for p in programs if family(p.key) not in families and
                      any(key and key not in shared and (key in seen or key in shipped)
                          for key in (normalise(text) for text in p.files.values())))
    private = [p for p in programs if family(p.key) not in families and p.key not in excluded and p.role != "shown"]
    # What upstream publishes as any program's answer, which no comment of an input may quote: the
    # errors and warnings its tests name, and every line of 12 characters or more of their outputs.
    answers = {message for p in programs for message in p.messages if len(message) >= 8}
    for path in sorted((args.checkout / "test" / "expected").glob("*.out")):
        answers |= {line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                    if len(line.strip()) >= 12}
    sides = {"visible": Side(visible, protected, answers), "private": Side(private, protected, answers)}
    for name, side in sides.items():
        if not side.ready() or not side.shown and name == "visible":
            raise SystemExit(f"the {name} side lacks programs of some kind")
    rng_for = lambda index: random.Random(args.seed * 1_000_003 + index)  # noqa: E731
    shown = generate(rng_for, sides["visible"], args.visible, CLI_VISIBLE, 0, "E")
    hidden = generate(rng_for, sides["private"], args.count - args.visible, CLI_PRIVATE, args.visible, "P")
    # For the verifier's record of what it grades (verifier/recording.py): each private case's kind,
    # and for a run case built on an upstream test, the sha256 of the test's expected output.
    by_key = {p.key: p for p in programs}
    for item in hidden:
        item.case["kind"] = item.kind
        program = by_key[item.keys[0]]
        if item.kind in ("run", "library", "modules") and program.expected:
            item.case["upstream"] = program.expected
        if item.kind in ("check", "rejected") and program.messages and "record" not in item.case:
            item.case["upstream_messages"] = sorted({hashlib.sha256(m.encode()).hexdigest() for m in program.messages})
    found = leaks([b.case for b in hidden], [b.case for b in shown], shipped, shared)
    if found:
        raise SystemExit(f"{len(found)} private cases have an input the agent can know: {', '.join(found[:20])}")
    for path, chosen in ((args.out_visible, shown), (args.out_private, hidden)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cases": [b.case for b in chosen]}, sort_keys=True, ensure_ascii=False))
    unchanged = Counter(b.kind for b in hidden if b.kind != "cli" and not b.changed)
    print(json.dumps({
        "fingerprints": {name: fingerprints([b.case for b in chosen]) for name, chosen in (("visible", shown), ("private", hidden))},
        "programs_lines": {name: lines_summary([b for b in chosen if b.kind != "cli"], by_key)
                           for name, chosen in (("visible", shown), ("private", hidden))},
        "library_modules": {name: library_use([b.case for b in chosen]) for name, chosen in (("visible", shown), ("private", hidden))},
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
