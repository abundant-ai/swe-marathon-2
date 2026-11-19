"""Generate the private cases of the BasedPL interpreter rebuild.

usage: make_cases.py [checkout] [--seed N] [--count N] [--out PATH]

Every case is a few files, an argument list and sometimes standard input for `bpl`; its answer
(standard output and exit code) is recorded from the original when the verifier image is built
(tests/verifier/recorder.py). The agent sees no case and no answer.

Sources, by kind (see KIND_COUNTS):

- expr, script: upstream's own reference records (tests/reference: core, static, regex, the
  mathish files), run with `bpl -e` (one line) or as a script file, with names, numbers and words
  rewritten under the private seed (rewrite.py) so that the answers differ from the ones upstream
  publishes; the recorder keeps the first rewrite that ends as the unrewritten code does.
- apl: the reference records ported from APL suites (APLcart, April, ngn, Dyalog, BQN), kept to a
  small share because their idioms are widely known.
- error: records that raise an error, inside a handler that prints what it caught (`$e`, its
  kind, message and position), or run plainly (exit status 1, output up to the error).
- worker: `bpl --worker` sessions of JSON requests (code, bindings, calls, echo), whose replies
  carry exact values and errors with their messages and source spans.
- display: how values print: boxes, precision, elision of large arrays, line width, diagrams,
  function trees and notation, `⍕` with format specs.
- stdin: programs that read standard input (`⎕`, `•nget "-"`), programs given on standard input
  (`bpl -`), and sessions piped into `bpl` with no arguments.
- module: upstream's library modules (lib/) loaded by a main program, from the library records.
- program: new programs (programs.py), written for this task, with seeded data.
- cli: the command line's own answers, one case per behaviour.

Nothing the agent can see is used: no record or program whose text, or whose skeleton (names,
numbers and text abstracted, bpl_text.skeleton), the shipped documentation holds. Records that
use randomness, the clock, files, the network, plots, images, timings or the interpreter's
internals (`•storage`, `•memory`, `•explain`) are left out, as are thread and seed settings.

The seed (`--seed`, else experiment/seeds.json's "cases", made by seeds.py) decides every choice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpl_text  # noqa: E402
import programs  # noqa: E402
import rewrite  # noqa: E402
from bpl_text import compact, documentation, git_files, git_text, leak_index, reference_records, skeleton, tokenize  # noqa: E402

TASK_ROOT = Path(__file__).resolve().parent.parent
OUT = TASK_ROOT / "steps" / "01-rebuild-interpreter" / "tests" / "private" / "cases.json"
KIND_COUNTS = {"expr": 420, "apl": 120, "script": 170, "error": 240, "worker": 190, "display": 230, "stdin": 90,
               "module": 50, "program": 260, "cli": 19}
OWN_SUITES = ("core.bpl", "core_mathish.bpl", "static.bpl", "static-int32.bpl", "regex.bpl")
APL_SUITES = ("aplcart.bpl", "aplcart_mathish.bpl", "april.bpl", "april_mathish.bpl", "ngn.bpl", "ngn_mathish.bpl",
              "dyalog.bpl", "dyalog_mathish.bpl", "bqn.bpl")
# Anything these mark is random, reads the clock, touches files or the network, draws, times, or
# reports on the interpreter's internals: never in a case.
EXCLUDED = ("¿", "•rand", "•distribution", "•time", "•date", "•delay", "•uuid", "•index", "•memory", "•explain",
            "•storage", "•plot", "•svg", "•image", "•canvas", "•fetch", "•readdir", "•metadata", "•copy", "•rename",
            "•remove", "•mkdir", "•nput", "•nget", "•load", "testpath", "⇄", "•host", "•mime", "•deflate", "•js",
            "]help", '"threads"', '"seed"', '"fusion"', "•hash", "]clear")
MAX_CODE = 1500  # characters of a record's code, at most
DERIVATIVE_KEEP = 0.55  # of the reference records that use ∂, the share drawn from: about 5-6% of the cases


def load_records(checkout: Path) -> dict[str, tuple[str, list[dict]]]:
    """Every reference file at the pinned commit: its setup and its records (their code without
    comments), by file name."""
    found = {}
    for path in git_files(checkout, "tests/reference"):
        if path.endswith(".bpl"):
            name = path.rsplit("/", 1)[1]
            setup, records = reference_records(name, git_text(checkout, path))
            for record in records:
                if record.get("code"):
                    record["code"] = uncommented(record["code"]).strip("\n")
            found[name] = (uncommented(setup).strip("\n"), records)
    return found


def excluded(text: str, allowed: tuple[str, ...] = ()) -> bool:
    """Whether BPL `text` uses anything EXCLUDED (other than `allowed`): a system function by its
    exact name (`•json` is not `•js`; names ignore case), anything else as written."""
    systems = {token.text.lower() for token in bpl_text.tokenize(text) if token.kind == "system"}
    return any((marker.lower() in systems) if marker.startswith("•") else (marker in text)
               for marker in EXCLUDED if marker not in allowed)


def usable(record: dict, setup: str) -> bool:
    """Whether a reference record can become a case: untimed, short, with nothing EXCLUDED in it or
    in its file's setup, and with an expectation (a value, an error or output)."""
    text = record.get("code", "") + "\n" + setup + "\n" + record.get("prefs", "")
    if record.get("timed") or not record.get("code") or len(record["code"]) > MAX_CODE:
        return False
    if excluded(text):
        return False
    return any(key in record for key in ("expected", "expected_error", "output"))


def checks_a_result(record: dict) -> bool:
    """Whether a record's value is a check (true, false, 0 or 1): its literals stay as written."""
    return record.get("expected", "").strip() in ("$t", "$f", "1", "0", "1ₓ", "0ₓ")


def uncommented(code: str) -> str:
    """`code` without its comments (upstream's may state a result) or the blank space they leave
    at the ends of lines."""
    tokens = [token for token in bpl_text.tokenize(code) if token.kind != "comment"]
    return "\n".join(line.rstrip() for line in bpl_text.untokenize(tokens).split("\n"))


def program_text(record: dict, setup: str) -> str:
    """A record as one program: its settings, its file's setup, then its code."""
    return "\n".join(part for part in (record.get("prefs", ""), uncommented(setup), record["code"]) if part)


def rewritten(code: str, rng: random.Random, edit: bool) -> tuple[str, list[str]]:
    """`code` renamed under the seed (the base), and up to three literal rewrites of the base
    (none when `edit` is false)."""
    base = rewrite.renamed(code, rewrite.renaming(code, rng))
    return base, (rewrite.variants(base, rng) if edit else [])


def case(kind: str, source: str, argv: list[str], files: dict[str, str] | None = None, stdin: str | None = None,
         variants: list[dict] | None = None, **extra) -> dict:
    """One case as the recorder and the verifier read it.

    Args:
        kind: The case's kind (KIND_COUNTS).
        source: Where it came from (upstream file and line, or the program's name); private.
        argv: The arguments after `bpl`.
        files: Files written into the run's working directory, by relative path.
        stdin: Standard input, or None for none.
        variants: Other inputs to try first (each a dict of any of argv, files, stdin), for the
            recorder's settle step; the case's own inputs are the base.
        extra: Further fields kept with the case (e.g. "family").

    Returns:
        The case dict, without an id yet.
    """
    built = {"kind": kind, "source": source, "argv": argv, "files": files or {}, "stdin": stdin, **extra}
    if variants:
        built["record"] = {"variants": variants, "want": "same"}
    return built


def expression_case(kind: str, record: dict, setup: str, rng: random.Random) -> dict:
    """A reference record as `bpl -e CODE` where it is one line with no settings, setup or input,
    else as `bpl main.bpl` with its settings and setup above its code. The code is rewritten under
    the seed; settings and setup stay as written."""
    code, edits = rewritten(record["code"], rng, not checks_a_result(record))
    lead = "\n".join(part for part in (record.get("prefs", ""), setup) if part)
    source = f"{record['file']}:{record['line']}"
    if not lead and "\n" not in code and "input" not in record:
        return case(kind, source, ["-e", code], variants=[{"argv": ["-e", edit]} for edit in edits])
    whole = lambda body: (lead + "\n" if lead else "") + body + "\n"  # noqa: E731
    return case(kind, source, ["main.bpl"], {"main.bpl": whole(code)}, record.get("input"),
                variants=[{"files": {"main.bpl": whole(edit)}} for edit in edits])


# Each handler prints the error's message, so that no guess of its kind alone passes.
HANDLERS = ("$e", "$e.message", '$e.kind,": ",$e.message', '(⍕$e.line),":",(⍕$e.column),": ",$e.message')
# What a run prints before its error: a value it has to compute (a literal could be echoed).
LEADS = (
    lambda rng: f"⎕←+/ι{rng.randint(5, 60)}",
    lambda rng: f"⎕←{rng.randint(2, 9)}×ι{rng.randint(3, 7)}",
    lambda rng: f"⎕←⌽ι{rng.randint(3, 9)}",
    lambda rng: f'⎕←⌽"{rng.choice(rewrite.WORDS)}"',
    lambda rng: f'⎕←≢"{rng.choice(rewrite.WORDS)} {rng.choice(rewrite.WORDS)}"',
    lambda rng: "⎕←⌈/" + " ".join(str(rng.randint(1, 99)) for _ in range(rng.randint(3, 6))),
    lambda rng: "⎕←+/" + " ".join(str(rng.randint(1, 99)) for _ in range(rng.randint(3, 6))),
    lambda rng: f"⎕←{rng.randint(2, 30)}+{rng.randint(2, 9)}×{rng.randint(2, 9)}",
)


def guarded_case(record: dict, setup: str, rng: random.Random) -> dict:
    """A record that raises an error, run inside a dfn whose guard prints what it caught: the
    whole error record, its message, its kind and message, or its position and message. A
    multi-line record becomes the dfn's body line by line."""
    handler = rng.choice(HANDLERS)
    code = record["code"]
    body = code.replace("\n", "\n    ") if "\n" in code else code
    opener = "{∞::" + handler + ("\n    " if "\n" in code else " ◇ ")
    program = "\n".join(part for part in (record.get("prefs", ""), setup) if part)
    program = (program + "\n" if program else "") + opener + body + ("\n}0" if "\n" in code else "}0")
    base, edits = rewritten(program, rng, True)
    return case("error", f"{record['file']}:{record['line']}", ["main.bpl"], {"main.bpl": base + "\n"},
                variants=[{"files": {"main.bpl": edit + "\n"}} for edit in edits], form="guarded")


def plain_error_case(record: dict, setup: str, rng: random.Random, reply: bool = False) -> dict:
    """A record that raises an error with nothing to catch it, after a computed value (LEADS). As a
    worker request (form "reply", most of them), the reply carries the error's kind, message, span
    and display; run as a program (form "plain"), standard output holds the value printed before
    the error and the run ends with exit status 1 (the message goes to standard error)."""
    lead = rng.choice(LEADS)(rng)
    source = f"{record['file']}:{record['line']}"
    if reply or rng.random() < 0.6:
        setup_lines = "\n".join(part for part in (record.get("prefs", ""), setup) if part)
        code, edits = rewritten(record["code"], rng, True)
        ident = rng.randint(1, 60)
        requests = lambda body: [{"id": ident, "code": lead[2:]}] + (  # noqa: E731
            [{"id": ident + 1, "code": setup_lines, "echo": False}] if setup_lines else []) + [{"id": ident + 2, "code": body}]
        text = lambda body: "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in requests(body))  # noqa: E731
        built = case("error", source, ["--worker"], stdin=text(code), variants=[{"stdin": text(edit)} for edit in edits],
                     form="reply")
        built.setdefault("record", {"variants": [], "want": "same"})["scaffold_lines"] = [0]
        return built
    program = "\n".join(part for part in (record.get("prefs", ""), setup, lead, record["code"]) if part)
    base, edits = rewritten(program, rng, True)
    return case("error", source, ["main.bpl"], {"main.bpl": base + "\n"},
                variants=[{"files": {"main.bpl": edit + "\n"}} for edit in edits], form="plain")


STATE_NAMES = ("sales", "totals", "rates", "stock", "scores", "costs", "counts", "levels", "margins", "volumes")


def notebook_state(lines: list[dict], rng: random.Random) -> list[dict]:
    """A worker session's requests with a notebook's state between them, at seeded places: a value
    defined in one request and used in later ones, a function defined and then called, a display
    setting followed by values it shows, and a bound name used again after its own request. Every
    request after the first state request depends on what earlier requests left."""
    ident = max((line["id"] for line in lines if isinstance(line.get("id"), int)), default=0) + 1
    name = rng.choice(STATE_NAMES)
    values = " ".join(f"¯{-value}" if value < 0 else str(value) for value in (rng.randint(-20, 90) for _ in range(rng.randint(3, 7))))
    steps: list[list[dict]] = [
        [{"code": f"{name}←{values}", "echo": False}, {"code": f"+/{name}"},
         {"code": f"{name}←{name},{rng.randint(1, 50)}", "echo": False}, {"code": rng.choice([f"≢{name}", f"⌈/{name}", f"⌽{name}"])}],
        [{"code": f"scale←{{ω×{rng.randint(2, 9)}}}", "echo": False}, {"code": f"scale {values}"},
         {"code": f"scale scale {rng.randint(1, 20)}"}],
        [{"code": f'•prefs ["prec":{rng.choice([3, 4, 5, 6])}]', "echo": False}, {"code": f"÷{rng.randint(3, 13)}"},
         {"code": f"{rng.randint(1, 9)}÷7"}],
    ]
    bound = [line for line in lines if "bindings" in line]
    if bound:
        used = next(iter(bound[0]["bindings"]))
        steps.append([{"code": rng.choice([f"{used}+1", f"⌽{used}", f"+/{used}×2"])}])
    chosen = [step for step in steps if rng.random() < 0.55] or [rng.choice(steps)]
    out = list(lines)
    for step in chosen:
        at = rng.randint(0, len(out))
        numbered = []
        for request in step:
            numbered.append({"id": ident, **request})
            ident += 1
        if "bindings" not in str(step) and step is steps[-1] and bound:
            at = len(out)  # a use of the bound name comes after the binding
        out[at:at] = numbered
    return out


def worker_case(records: list[tuple[dict, str]], rng: random.Random) -> dict:
    """A `bpl --worker` session: a request per record (its code, with the record's setup as an
    earlier request), ids rising from a random start, some without ids, some with echo off, some
    as bindings of a small array and a call of a function on encoded arguments."""
    lines: list[dict] = []
    ident = rng.randint(1, 60)
    for record, setup in records:
        if setup:
            lines.append({"id": ident, "code": setup, "echo": False})
            ident += 1
        request: dict = {"code": record["code"]}
        if rng.random() < 0.85:
            request = {"id": ident, **request}
            ident += 1
        if rng.random() < 0.15:
            request["echo"] = False
        lines.append(request)
    if rng.random() < 0.6:
        size = rng.randint(2, 6)
        data = [rng.randint(-9, 30) for _ in range(size)]
        name = rng.choice(["prices", "counts", "scores", "weights", "sizes", "totals"])
        lines.append({"id": ident, "bindings": {name: {"shape": [size], "data": data, "prototype": 0}},
                      "code": rng.choice([f"+/{name}", f"{name}×2", f"⌽{name}", f"(+/÷≢){name}", f"{name}⌈3"])})
        ident += 1
    if rng.random() < 0.5:
        size = rng.randint(1, 5)
        args = [{"shape": [size], "data": [rng.randint(0, 20) for _ in range(size)], "prototype": 0}]
        if rng.random() < 0.5:
            args.insert(0, rng.randint(1, 9))
        lines.append({"id": ident, "call": rng.choice(["+", "×", "⌈", "{α+ω}", "+/", "⌽", "ρ"]), "args": args})
        ident += 1
    own = [id(line) for line in lines if "code" in line and "bindings" not in line]  # the records' requests and setups
    lines = notebook_state(lines, rng)
    scaffold = [number for number, line in enumerate(lines) if id(line) not in own]
    text = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines)
    edits = []
    for share in (1.0, 0.5):
        changed = []
        for line in lines:
            if "code" in line and "bindings" not in line:
                edited = rewrite.edit(line["code"], rng, share)
                changed.append(dict(line, code=edited))
            else:
                changed.append(line)
        variant = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in changed)
        if variant != text:
            edits.append({"stdin": variant})
    built = case("worker", ",".join(f"{record['file']}:{record['line']}" for record, _ in records), ["--worker"], stdin=text,
                 variants=edits)
    built.setdefault("record", {"variants": [], "want": "same"})["scaffold_lines"] = scaffold
    return built


def display_case(record: dict, setup: str, rng: random.Random) -> dict:
    """A record shown under display settings: boxes, precision, a width, elision, `]display`'s
    diagram, `]dissect`, function trees or another notation. The record's own code is rewritten
    under the seed; the settings line stays as written."""
    code, edits = rewritten(record["code"], rng, not checks_a_result(record))
    form = rng.choice(display_forms(code))
    head = {"box": '•prefs ["box":$t]', "prec": f'•prefs ["prec":{rng.choice([3, 4, 6, 8, 12, 15])}]',
            "width": f'•prefs ["width":{rng.choice([20, 32, 40, 60])}]',
            "limit": f'•prefs ["limit":{rng.choice([4, 6, 10, 20])} "edges":{rng.choice([1, 2, 3])}]',
            "trees": '•prefs ["trees":$t]', "notation": f'•prefs ["notation":"{rng.choice(["traditional", "simplified"])}"]',
            "diagram": "", "dissect": ""}[form]
    lead = [part for part in (record.get("prefs", ""), setup) if part]

    def shown_as(body: str) -> str:
        if form in ("diagram", "dissect") and "\n" not in body:
            return "\n".join(lead + [("]display " if form == "diagram" else "]dissect ") + body]) + "\n"
        return "\n".join(lead + ([head] if head else []) + [body]) + "\n"
    built = case("display", f"{record['file']}:{record['line']}", ["main.bpl"], {"main.bpl": shown_as(code)},
                 variants=[{"files": {"main.bpl": shown_as(edit)}} for edit in edits], form=form)
    unset = ["main.bpl", head + "\n", ""] if head else (["main.bpl", "]display " if form == "diagram" else "]dissect ", ""]
                                                         if "\n" not in code else None)
    if unset:  # the recorder keeps the case only if the setting changes what it prints
        built.setdefault("record", {"variants": [], "want": "same"})["unset"] = unset
    return built


def display_forms(code: str) -> list[str]:
    """The display settings worth trying on a value from its code: precision where it computes
    fractions, the item limit and the width where it makes long or wide arrays, and boxes, diagrams
    and dissection anywhere."""
    forms = ["box", "diagram", "diagram", "dissect", "dissect"]
    numbers = [int(value) for value in re.findall(r"(?<![\d.])\d+(?![\d.])", code) if len(value) < 7]
    if re.search(r"\d\.\d|[÷○*√⍟]", code):
        forms += ["prec"] * 2
    if re.search(r"[ι⍳ρ↕]", code) and any(value >= 10 for value in numbers) or len(numbers) >= 12:
        forms += ["limit", "width"] * 2
    return forms  # notation and trees show functions, which the built displays hold


def stdin_case(record: dict, setup: str, rng: random.Random, breaker: str | None = None) -> dict:
    """A multi-line record given on standard input: as a program (`bpl -`), or as lines piped into
    `bpl` with no arguments, where every line runs, an error does not stop the rest and later lines
    use what earlier ones defined. A piped record gets a line that fails (`breaker`, a one-line
    record that raises an error) after its first statement."""
    text = program_text(record, setup)
    base, edits = rewritten(text, rng, not checks_a_result(record))
    if rng.random() < 0.5:
        return case("stdin", f"{record['file']}:{record['line']}", ["-"], stdin=base + "\n",
                    variants=[{"stdin": edit + "\n"} for edit in edits], form="dash")

    def piped(program: str) -> str:
        lines = program.split("\n")
        depth, boundaries = 0, []
        for number, line in enumerate(lines[:-1], 1):  # after a line that closes every bracket it opened
            for token in tokenize(line):
                if token.kind == "glyph" and token.text in "([{":
                    depth += 1
                elif token.kind == "glyph" and token.text in ")]}":
                    depth = max(0, depth - 1)
            if depth == 0:
                boundaries.append(number)
        if breaker is not None and boundaries:
            lines.insert(boundaries[0], breaker)
        return "\n".join(lines) + "\n"
    return case("stdin", f"{record['file']}:{record['line']}", [], stdin=piped(base),
                variants=[{"stdin": piped(edit)} for edit in edits], form="pipe")


LIBRARY_LOADS = {"array.bpl": [], "string.bpl": [], "power.bpl": [], "tree.bpl": [], "regex.bpl": [],
                 "graph.bpl": ["array.bpl"], "numeric.bpl": ["graph.bpl", "array.bpl"], "dyalog.bpl": ["array.bpl"]}


def module_case(record: dict, library: dict[str, str], rng: random.Random) -> dict:
    """A library record: main.bpl loads modules from lib/, which the working directory holds (each
    module with the modules it loads), and its literals are rewritten under the seed."""
    code = record["code"]
    needed = set()
    for name in re.findall(r'•load "lib/([a-z]+\.bpl)"', code):
        needed |= {name, *LIBRARY_LOADS.get(name, [])}
    files = {f"lib/{name}": library[name] for name in sorted(needed)}
    edits = rewrite.variants(code, rng) if not checks_a_result(record) else []
    return case("module", f"{record['file']}:{record['line']}", ["main.bpl"], dict(files, **{"main.bpl": code + "\n"}),
                variants=[{"files": dict(files, **{"main.bpl": edit + "\n"})} for edit in edits])


def cli_cases() -> list[dict]:
    """The command line's own answers, one case per behaviour: help, version, unknown options and
    the modes this build does not have, a missing program file, a program file outside the
    working directory's reach, arguments handed to a program, and the worker's request errors."""
    worker_errors = '{"id":1,"code":"1+1"\n{"id":"two","code":"2"}\n{"id":3}\n{"id":4,"code":"1","call":"+"}\n' \
                    '{"id":5,"args":[1]}\n{"id":6,"call":"+","args":{"x":1}}\n{"id":7,"code":"⍳"}\n'
    return [
        case("cli", "cli:help", ["--help"]),
        case("cli", "cli:h", ["-h"]),
        case("cli", "cli:version", ["--version"]),
        case("cli", "cli:unknown-option", ["--verbose"]),
        case("cli", "cli:costs", ["--costs", "speed.bpl"], {"speed.bpl": "+/ι10\n"}),
        case("cli", "cli:kernel", ["--kernel", "-f", "connection.json"], {"connection.json": "{}\n"}),
        case("cli", "cli:e-alone", ["-e"]),
        case("cli", "cli:worker-extra", ["--worker", "now"]),
        case("cli", "cli:missing-file", ["report.bpl"]),
        case("cli", "cli:directory", ["lib"], {"lib/a.bpl": "1\n"}),
        case("cli", "cli:args-e", ["-e", '•host "args"', "north", "south", "--fast"]),
        case("cli", "cli:args-file", ["tally.bpl", "3", "seven"], {"tally.bpl": 'a←•host "args"\n≢a\n⌽a\n'}),
        case("cli", "cli:args-dash", ["-", "alpha"], stdin='⎕←•host "args"\n'),
        case("cli", "cli:version-fact", ["-e", '•host "version"']),
        case("cli", "cli:shebang", ["run.bpl"], {"run.bpl": "#!/usr/bin/env bpl\n⎕←2+3\n"}),
        case("cli", "cli:worker-errors", ["--worker"], stdin=worker_errors),
        case("cli", "cli:pipe-errors", [], stdin="x←4\nx×\n÷0\nx+1\n"),
        case("cli", "cli:dash-reads-input", ["-"], stdin='⎕←"before"\n⎕\n⎕←"after"\n'),
        case("cli", "cli:outside", ["/etc/passwd"]),
    ]


def leaks(cases: list[dict], skeletons: set[str], texts: set[str]) -> list[str]:
    """Indexes (as strings) of the cases whose program the documentation holds, exactly or as a
    near-copy, in their own inputs or in any rewrite the recorder may settle on: a file, the `-e`
    code or a worker request whose skeleton is a documented program's (a whole block, a statement
    or a run of 2-6 of its statements), or whose compact text a documented program holds."""
    found = []
    blob = "\n".join(texts)
    for index, item in enumerate(cases):
        if item["kind"] == "cli":
            continue
        pieces = []
        # The case's own inputs and every rewrite of them the recorder may settle on.
        for option in [item] + item.get("record", {}).get("variants", []):
            shown = dict(item, **{key: option[key] for key in ("argv", "files", "stdin") if key in option})
            pieces += [text for name, text in shown["files"].items() if not name.startswith("lib/")]
            if shown["argv"][:1] == ["-e"]:
                pieces.append(shown["argv"][1])
            if shown["stdin"] and shown["argv"][:1] == ["--worker"]:  # the records' requests, not the generator's own
                scaffold = set(item.get("record", {}).get("scaffold_lines", []))
                pieces += [request.get("code", "") for number, request in enumerate(map(json.loads, shown["stdin"].splitlines()))
                           if "bindings" not in request and number not in scaffold]
            elif shown["stdin"]:
                pieces.append(shown["stdin"])
        for piece in pieces:
            if not piece.strip():
                continue
            if skeleton(piece) in skeletons or (len(compact(piece)) >= 6 and compact(piece) in blob):
                found.append(str(index))
                break
    return found


def generate(checkout: Path, seed: int, scale: float = 1.0) -> list[dict]:
    """The private cases, ids P00001 onwards in a seeded order.

    Args:
        checkout: An upstream checkout that holds the pinned commit.
        seed: The private case seed.
        scale: A factor on every kind's count (tests use small ones).

    Returns:
        Cases with ids, kinds and, where rewrites exist, "record" plans for the recorder.
    """
    rng = random.Random(seed)
    counts = {kind: max(1, round(count * scale)) for kind, count in KIND_COUNTS.items()}
    files = load_records(checkout)
    skeletons, texts = leak_index(documentation(checkout))
    shown = lambda record: skeleton(record["code"]) in skeletons or compact(record["code"]) in texts  # noqa: E731
    pairs = lambda suites: [(record, files[name][0]) for name in suites if name in files for record in files[name][1]  # noqa: E731
                            if usable(record, files[name][0]) and not shown(record)]
    own, apl = pairs(OWN_SUITES), pairs(APL_SUITES)
    # Differentiation fills a large part of upstream's reference suite; keep DERIVATIVE_KEEP of
    # those records, so that it weighs about as much as the other parts of the manual.
    thin = lambda pool: [pair for pair in pool if "∂" not in pair[0]["code"] + pair[1] or rng.random() < DERIVATIVE_KEEP]  # noqa: E731
    own, apl = thin(own), thin(apl)
    # A value case needs a literal the seed can change, so that its answer is not upstream's own.
    editable = lambda pair: not checks_a_result(pair[0]) and bool(  # noqa: E731
        rewrite.number_sites(pair[0]["code"]) or rewrite.text_sites(pair[0]["code"]))
    is_value = lambda pair: "expected_error" not in pair[0] and "input" not in pair[0]  # noqa: E731
    single = [pair for pair in own if is_value(pair) and editable(pair) and "\n" not in pair[0]["code"] and not pair[1]]
    multi = [pair for pair in own if is_value(pair) and editable(pair) and pair not in single]
    plain = [pair for pair in own if is_value(pair) and not editable(pair)]
    own_errors = [pair for pair in own if "expected_error" in pair[0]]
    apl_values = [pair for pair in apl if is_value(pair) and editable(pair)]
    apl_errors = [pair for pair in apl if "expected_error" in pair[0]]
    readers = [pair for pair in own + apl if "input" in pair[0]]
    for pool in (single, multi, plain, own_errors, apl_values, apl_errors, readers):
        rng.shuffle(pool)
    take = lambda pool, n: [pool.pop() for _ in range(min(max(n, 0), len(pool)))]  # noqa: E731
    suite = lambda pair: "apl" if pair[0]["file"] in APL_SUITES else "own"  # noqa: E731
    cases: list[dict] = []
    piped = take(multi, counts["stdin"] - min(len(readers), counts["stdin"] // 3))  # multi-line, before scripts take them
    for pair in take(single, counts["expr"]):
        cases.append(dict(expression_case("expr", *pair, rng), suite=suite(pair)))
    for pair in take(multi, counts["script"]):
        cases.append(dict(expression_case("script", *pair, rng), suite=suite(pair)))
    for pair in take(apl_values, counts["apl"]):
        cases.append(dict(expression_case("apl", *pair, rng), suite=suite(pair)))
    errors = take(own_errors, counts["error"] - counts["error"] // 5) + take(apl_errors, counts["error"] // 5)
    for pair in errors:
        # A syntax error stops the whole program before any guard or lead runs, so only a worker
        # reply shows it (plain_error_case's "reply" form).
        syntax = "SYNTAX" in str(pair[0].get("expected_error", ""))
        built = plain_error_case(*pair, rng, syntax) if syntax or rng.random() >= 0.8 else guarded_case(*pair, rng)
        cases.append(dict(built, suite=suite(pair)))
    # What the value kinds leave goes to the worker sessions (with records that cannot change their
    # answers among them: a session's other requests still do), the displays and stdin.
    reserve = take(single + multi, counts["display"])
    session_pool = single + multi + plain
    rng.shuffle(session_pool)
    for _ in range(counts["worker"]):
        picked = take(session_pool, rng.randint(2, 4)) + take(own_errors, 1 if rng.random() < 0.6 else 0)
        if picked:
            cases.append(dict(worker_case(picked, rng), suite="apl" if any(suite(pair) == "apl" for pair in picked) else "own"))
    built_displays = programs.display_cases(rng, counts["display"] // 2)
    for pair in take(reserve, counts["display"] - len(built_displays)):
        cases.append(dict(display_case(*pair, rng), suite=suite(pair)))
    cases += built_displays
    for pair in readers[:counts["stdin"] // 3]:
        cases.append(dict(expression_case("stdin", *pair, rng), suite=suite(pair)))
    breakers = [pair for pair in own_errors if "\n" not in pair[0]["code"] and not pair[1]]
    for pair in piped:
        cases.append(dict(stdin_case(*pair, rng, rng.choice(breakers)[0]["code"] if breakers else None), suite=suite(pair)))
    library = {path.rsplit("/", 1)[1]: git_text(checkout, path) for path in git_files(checkout, "lib") if path.endswith(".bpl")}
    lib_records = [record for record in files.get("lib.bpl", ("", []))[1] + files.get("lib_mathish.bpl", ("", []))[1]
                   if record.get("code") and not record.get("timed") and not excluded(record["code"], ("•load",))]
    rng.shuffle(lib_records)
    for record in lib_records[:counts["module"]]:
        cases.append(dict(module_case(record, library, rng), suite="own"))
    cases += programs.program_cases(rng, counts["program"])
    cases += cli_cases()
    leaked = set(leaks(cases, skeletons, texts))
    cases = [item for index, item in enumerate(cases) if str(index) not in leaked]
    rng.shuffle(cases)
    for index, item in enumerate(cases, 1):
        item["id"] = f"P{index:05d}"
    return cases


def summary(cases: list[dict]) -> str:
    """Counts by kind and the sha1 of the cases, for the development log."""
    kinds = Counter(item["kind"] for item in cases)
    digest = hashlib.sha1(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]
    return f"{len(cases)} cases ({', '.join(f'{kind} {count}' for kind, count in sorted(kinds.items()))}), sha1 {digest}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", nargs="?", type=Path,
                        default=Path(os.environ.get("BASEDPL_CHECKOUT", TASK_ROOT.parents[3] / ".cache-src" / "basedpl")))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if args.seed is None:
        import seeds  # noqa: PLC0415
        args.seed = int(seeds.value("cases"))
    cases = generate(args.checkout, args.seed, args.scale)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"cases": cases}, ensure_ascii=False, sort_keys=True))
    print(summary(cases))


if __name__ == "__main__":
    main()
