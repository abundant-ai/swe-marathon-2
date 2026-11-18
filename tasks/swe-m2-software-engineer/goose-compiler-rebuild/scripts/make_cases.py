"""Generate the cases for the Goose compiler rebuild: one or a few Goose files, a command line and
optional standard input.

Programs come from a checkout of aardappel/goose: its test suite (never shipped to the
candidate), its samples and the complete programs in its documentation (both shipped).
Visible cases use the samples, the documentation's programs and a fixed 15% of the test
programs; private cases use the other test programs and mutated variants of anything, so no
private input is a file the candidate has seen. Every comment is removed from a program before
it is used: the error tests name the error they expect in comments. Expected outputs are NOT
produced here: they are recorded from the original compiler on Linux when the images are built.

usage: make_cases.py <goose checkout> --count 1800 --seed N --visible 300 --out-private P --out-visible V
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

RUN_DIRS = ("codegen", "lifetimes", "typing", "optimizer", "stdlib", "runtime", "storage", "syntax")
ERROR_DIRS = ("errors_tc", "errors")
# Modules a program may import: the standard library, less what touches the machine (os, ffi).
MODULES = {"std", "vec", "slot_pool", "slice_pool", "slice_pool_internal", "math", "exception", "dictionary", "json",
           "mat", "quat", "base64", "binary", "csv", "regex"}
MARKER = re.compile(r"//\s*(no-jit|parse-only)\b")  # first-line markers: refused by the JIT, or not a program
COMMANDS = ["run", "build", "check", "fetch", "format", "toolchain", "version", "lsp", "completion", "help"]
VISIBLE_SHARE = 0.15


def code_part(line: str) -> str:
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
    """Drop every `//` comment: the tests name their expected errors and outputs in comments."""
    out = []
    for line in text.split("\n"):
        if line.strip().startswith("//"):
            continue
        out.append(code_part(line))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip("\n") + "\n"


def usable(text: str) -> bool:
    first = text.split("\n", 1)[0]
    if MARKER.match(first):
        return False
    imports = re.findall(r"^\s*import\s+([\w.]+)", text, re.M)
    if any(name not in MODULES for name in imports):
        return False
    return "extern " not in text and "/*" not in text and "fn main" in text and len(text) <= 40_000


def doc_programs(checkout: Path) -> list[str]:
    """Complete programs (with a main) from the documentation, skipping fragments and check-only blocks."""
    programs = []
    for path in sorted((checkout / "docs").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"(<!--[^>]*-->\s*)?```goose\n(.*?)```", text, re.S):
            marker, body = match.group(1) or "", match.group(2)
            if "fragment" in marker or "check-only" in marker:
                continue
            if usable(body):
                programs.append(strip_comments(body))
    return programs


def pools(checkout: Path) -> dict[str, list[tuple[str, str]]]:
    """Programs by role, each as (stable key, text without comments)."""
    tests = checkout / "test"
    expected = {path.stem for path in (tests / "expected").glob("*.out")}
    result: dict[str, list[tuple[str, str]]] = {"run": [], "error": [], "shown": []}
    for directory in RUN_DIRS:
        for path in sorted((tests / directory).glob("*.goose")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if path.stem in expected and "// error:" not in text and usable(text):
                result["run"].append((f"test/{directory}/{path.name}", strip_comments(text)))
    for directory in ERROR_DIRS:
        for path in sorted((tests / directory).glob("*.goose")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if "// error:" in text and usable(text):
                result["error"].append((f"test/{directory}/{path.name}", strip_comments(text)))
    for path in sorted((checkout / "samples").glob("*.goose")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if usable(text):
            result["shown"].append((f"samples/{path.name}", strip_comments(text)))
    for index, text in enumerate(doc_programs(checkout)):
        result["shown"].append((f"docs#{index}", text))
    return result


def visible_program(key: str) -> bool:
    if not key.startswith("test/"):
        return True
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < VISIBLE_SHARE


# ---------------------------------------------------------------- mutations

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


def mutate(rng: random.Random, text: str, breaking: bool) -> str:
    """One to three edits that always change the text. `breaking` prefers edits that make the
    program fail to compile."""
    original = text
    edits = [mutate_name, mutate_line, mutate_operator] if breaking else [mutate_literal, mutate_literal, mutate_operator]
    for _ in range(rng.randint(1, 3 if breaking else 2)):
        text = rng.choice(edits)(rng, text)
    if text == original:  # nothing to edit: add a statement at the top of main
        statement = f"    let unknown_{rng.randint(1, 99)} = missing_{rng.randint(1, 99)};" if breaking else f"    print({rng.randint(1, 999)});"
        lines = text.split("\n")
        at = next((i + 1 for i, line in enumerate(lines) if "fn main" in line and line.rstrip().endswith("{")), len(lines))
        lines.insert(at, statement)
        text = "\n".join(lines)
    return text


def unformat(rng: random.Random, text: str) -> str:
    """Disturb the layout the formatter owns: indentation, spaces between tokens, trailing commas."""
    out = []
    for line in text.split("\n"):
        roll = rng.random()
        if roll < 0.2:
            line = line.lstrip()
        elif roll < 0.3:
            line = " " * rng.randint(1, 7) + line.lstrip()
        if rng.random() < 0.25:
            line = re.sub(r"\s*([=+\-*/<>,:])\s*", lambda m: rng.choice([m.group(1), " " + m.group(1) + " ", m.group(1) + "  "]), line)
        if rng.random() < 0.05:
            line += "   "
        out.append(line)
    disturbed = "\n".join(out)
    if disturbed == text:  # make sure the formatter has something to do
        lines = text.split("\n")
        at = next((i for i, line in enumerate(lines) if line.strip()), 0)
        lines[at] = "   " + lines[at]
        disturbed = "\n".join(lines)
    return disturbed


# ---------------------------------------------------------------- cases

def run_case(rng: random.Random, program: str, mutated: bool) -> dict:
    source = mutate(rng, program, breaking=False) if mutated else program
    argv = ["run", "main.goose"] if rng.random() < 0.9 else ["main.goose"]
    if rng.random() < 0.12:
        argv.append(rng.choice(["-O0", "-O1"]))
    if rng.random() < 0.1:
        argv.append("--debug")
    if rng.random() < 0.15:
        argv += ["--diagnostics", "json"]
    return {"files": {"main.goose": source}, "argv": argv, "stdin": None}


def check_case(rng: random.Random, program: str, breaking: bool) -> dict:
    source = mutate(rng, program, breaking=True) if breaking else program
    argv = ["check", "main.goose", "--diagnostics", "json"]
    if rng.random() < 0.1:
        argv.insert(1, "--color")
        argv.insert(2, "never")
    return {"files": {"main.goose": source}, "argv": argv, "stdin": None}


def format_case(rng: random.Random, programs: list[str], always_disturb: bool = False) -> dict:
    if rng.random() < 0.6:
        return {"files": {}, "argv": ["format"] if rng.random() < 0.8 else ["format", "-"], "stdin": unformat(rng, rng.choice(programs))}
    names = rng.sample(["main.goose", "lib.goose", "src/shapes.goose", "src/util/text.goose", "tools/gen.goose"], rng.randint(1, 3))
    files = {name: (unformat(rng, rng.choice(programs)) if always_disturb or rng.random() < 0.6 else rng.choice(programs)) for name in names}
    target = rng.choice([".", "src", names[0]]) if any(name.startswith("src/") for name in names) else rng.choice([".", names[0]])
    return {"files": files, "argv": ["format", "--check", target], "stdin": None}


def cli_case(rng: random.Random, program: str) -> dict:
    files = {"main.goose": program}
    argv = rng.choice([
        ["version"], ["--version"], ["help"], ["help", rng.choice(COMMANDS)], ["run", "--help"], ["check", "-h"],
        ["completion", rng.choice(["bash", "zsh", "fish"])], ["biuld", "main.goose"], ["chekc", "main.goose"],
        ["run", "missing.goose"], ["check", "missing.goose"], ["check", "main.goose", "--bogus"],
        ["run", "main.goose", "--diagnostics", "xml"], ["check"], ["format", "--check", "missing.goose"],
        ["run", "main.goose", "-O7"], ["help", "nonsense"],
    ])
    return {"files": files, "argv": argv, "stdin": None}


def make_case(rng: random.Random, side: dict[str, list[str]], everything: list[str], private: bool, cli_pool: list[str]) -> dict:
    """A private case built on a shown program (side has no run or error programs) always changes it first."""
    shown_only = private and not side["run"] and not side["error"]
    pick = rng.random()
    if pick < 0.42:
        mutated = rng.random() < (0.45 if private else 0.25) or not side["run"]
        base = rng.choice(side["run"] if side["run"] and rng.random() < 0.8 else side["run"] + side["shown"] or everything)
        if private and not side["run"]:
            mutated = True
        return run_case(rng, base, mutated)
    if pick < 0.78:
        if rng.random() < 0.7 and side["error"]:
            return check_case(rng, rng.choice(side["error"]), breaking=False)
        return check_case(rng, rng.choice(side["run"] + side["shown"] or everything), breaking=True)
    if pick < 0.92:
        return format_case(rng, side["run"] + side["shown"] + side["error"] or everything, always_disturb=shown_only)
    return cli_case(rng, rng.choice(cli_pool or everything))


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
    visible_side = {role: [text for key, text in items if visible_program(key)] for role, items in programs.items()}
    private_side = {role: [text for key, text in items if not visible_program(key)] for role, items in programs.items()}
    private_side["shown"] = []  # shown programs reach private cases only as mutated variants (run and check)
    everything = [text for items in programs.values() for _, text in items]
    cases = []
    for index in range(args.count):
        private = index >= args.visible
        rng = random.Random(args.seed * 1_000_003 + index)
        side = dict(private_side) if private else visible_side
        if private and rng.random() < 0.15:
            side = {"run": [], "error": [], "shown": visible_side["shown"]}  # a mutated variant of a shown program
        cli_pool = private_side["run"] + private_side["error"] if private else visible_side["run"] + visible_side["error"] + visible_side["shown"]
        case = make_case(rng, side, everything, private, cli_pool)
        case["id"] = f"{'E' if not private else 'P'}{index + 1:05d}"
        cases.append(case)
    for path, chosen in ((args.out_visible, cases[:args.visible]), (args.out_private, cases[args.visible:])):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cases": chosen}, sort_keys=True, ensure_ascii=False))
    print(json.dumps({role: {"visible": len(visible_side[role]), "private": len(private_side[role])} for role in programs}
                     | {"cases": len(cases), "visible": args.visible, "private": len(cases) - args.visible}))


if __name__ == "__main__":
    main()
