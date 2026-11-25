"""BPL source as tokens, upstream's reference records, and the documentation the agent is given.

Shared by scripts/make_cases.py (case generation and its leak checks) and scripts/package_step.py
(the documentation staged into the agent image, and the leak check repeated on the real files).
Nothing here runs BPL; it reads text only.
"""

from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

UPSTREAM_COMMIT = "af3609a9348471494d2bed952cbbf2a5ecdbd53e"  # AnswerDotAI/basedpl v0.1.95, Apache-2.0

# Characters that end a name (upstream's syntax.rs `name_char`): syntax, the function and operator
# glyphs, the implicit names, sub- and superscripts and the number marks. Any other character
# that is not blank or an ASCII digit belongs to a name, `∆`, `⍙`, `⍴` and emoji included.
RESERVED = set("()[]{}'\";:?$•←⎕⍝◇⁝⍬¯∞⍛.") | set("⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉⁻₋ᵀˢₓᵣₑⱼₕₛₚᵇᵘ") | set("αω⍶⍹∇⍢") \
    | set("+-×÷⌊⌈|*⊛○π√!⍭⨸⌻¿∨∧⊼⊽~=≠<≤>≥≡≢ρ,⍪⌽⍉↑↓↕⊂⊆⊃⌷ι↦⍸∊∪∩⍷⍋⍒#⊤⊥⌹⊣⊢⍎⍕/⌿\\⍀¨⍨⊗⌸⇄∂↣↢⍤∘⍠⍥⍣⊘⍚@⌺")
DIGITS = set("0123456789")
NUMBER_SUFFIXES = ("ₓ₁", "ₓ₂", "ₓ₄", "ₓ₈", "ₓ", "ᵣ", "ₕ", "ₛ", "ₚ")
_NUMBER = re.compile(
    r"¯?[0-9]+(?:\.[0-9]+)?(?:[eEₑ]¯?[0-9]+)?"                # mantissa and exponent
    r"(?:[jJⱼ]¯?[0-9]+(?:\.[0-9]+)?(?:[eEₑ]¯?[0-9]+)?)?"      # complex part
    r"(?:[rᵣ]¯?[0-9]+)?"                                        # rational denominator
)


@dataclass(frozen=True)
class Token:
    """One lexical piece of BPL source: `kind` is space, newline, comment, string, char, number,
    name, system, constant, or glyph (any other single character, sub- and superscripts included);
    `text` is exactly the source it covers, so joining every token's text gives the source back."""

    kind: str
    text: str


def is_name_char(char: str) -> bool:
    """Whether `char` can be part of a BPL name: not blank, not a control character, not an ASCII
    digit, not RESERVED and not a modifier letter (the sub- and superscript letters)."""
    if char.isspace() or char in DIGITS or char in RESERVED:
        return False
    category = unicodedata.category(char)
    return not category.startswith("C") and category != "Lm"


def tokenize(code: str) -> list[Token]:
    """Split BPL source into tokens without interpreting it.

    Used by the rewrites in make_cases.py (renames, literal edits) and by the leak checks, which
    compare token skeletons. Strings may span lines and double their quotes; `'''` is the quote
    character and `''` the empty vector; `⍝` comments run to the end of the line; a digit ends a
    name except straight after `_`; after `.`, digits stay in a key (`T.q1`).

    Args:
        code: BPL source text, any number of lines.

    Returns:
        Tokens whose texts, joined in order, equal `code` exactly.
    """
    tokens: list[Token] = []
    at, size = 0, len(code)
    while at < size:
        char = code[at]
        if char == "\n":
            tokens.append(Token("newline", "\n"))
            at += 1
        elif char in " \t\r":
            end = at
            while end < size and code[end] in " \t\r":
                end += 1
            tokens.append(Token("space", code[at:end]))
            at = end
        elif char == "⍝":
            end = code.find("\n", at)
            end = size if end < 0 else end
            tokens.append(Token("comment", code[at:end]))
            at = end
        elif char == '"':
            end = at + 1
            while end < size:
                if code[end] == '"':
                    if code.startswith('""', end):
                        end += 2
                        continue
                    break
                end += 1
            tokens.append(Token("string", code[at:end + 1]))
            at = min(end + 1, size)
        elif char == "'":
            width = 3 if code.startswith("'''", at) else 2 if code.startswith("''", at) else 3
            tokens.append(Token("char", code[at:at + width]))
            at += width
        elif char == "•" and at + 1 < size and is_name_char(code[at + 1]):
            end = at + 1
            while end < size and (is_name_char(code[end]) or code[end] in DIGITS):
                end += 1
            tokens.append(Token("system", code[at:end]))
            at = end
        elif char == "$" and at + 1 < size and code[at + 1].isalpha():
            tokens.append(Token("constant", code[at:at + 2]))
            at += 2
        elif char in DIGITS or (char == "¯" and at + 1 < size and code[at + 1] in DIGITS):
            match = _NUMBER.match(code, at)
            end = match.end()
            for suffix in NUMBER_SUFFIXES:
                if code.startswith(suffix, end):
                    end += len(suffix)
                    break
            tokens.append(Token("number", code[at:end]))
            at = end
        elif is_name_char(char):
            key = bool(tokens) and tokens[-1].text == "."
            end = at
            while end < size:
                if code[end] == "_" and end + 1 < size and code[end + 1] in DIGITS:  # a subscript: x_1
                    end += 2
                    while end < size and code[end] in DIGITS:
                        end += 1
                    continue
                if is_name_char(code[end]) or (key and code[end] in DIGITS):
                    end += 1
                    continue
                break
            tokens.append(Token("name", code[at:end]))
            at = end
        else:
            tokens.append(Token("glyph", char))
            at += 1
    return tokens


def untokenize(tokens: list[Token]) -> str:
    """The source text of `tokens` (their texts joined)."""
    return "".join(token.text for token in tokens)


def skeleton(code: str) -> str:
    """The shape of a program with its particulars taken out, for finding near-copies.

    Comments and blank space are dropped (a newline counts as a statement break, like `◇`), every
    number becomes `N`, every string and character `S`, and every name `X`; glyphs, system names and
    constants stay. Two programs with the same skeleton differ only in names, literals and layout.

    Args:
        code: BPL source.

    Returns:
        The skeleton as one line of text.
    """
    parts: list[str] = []
    for token in tokenize(code):
        if token.kind in ("space", "comment"):
            continue
        if token.kind == "newline":
            if parts and parts[-1] != "◇":
                parts.append("◇")
            continue
        parts.append({"number": "N", "string": "S", "char": "S", "name": "X"}.get(token.kind, token.text))
    while parts and parts[-1] == "◇":
        parts.pop()
    return "".join(parts)


def statements(code: str) -> list[str]:
    """The top-level statements of a program: split at newlines and `◇` outside any bracket,
    parenthesis, brace, string or comment. Comments and empty statements are dropped."""
    found, current, depth = [], [], 0
    for token in tokenize(code):
        if token.kind == "comment":
            continue
        if token.kind == "glyph" and token.text in "([{":
            depth += 1
        elif token.kind == "glyph" and token.text in ")]}":
            depth = max(0, depth - 1)
        if depth == 0 and (token.kind == "newline" or token.text == "◇"):
            found.append(untokenize(current).strip())
            current = []
            continue
        current.append(token)
    found.append(untokenize(current).strip())
    return [text for text in found if text]


# --- Upstream's reference records (a port of testkit/src/reference.rs `file`) ---------------------


def _header(line: str) -> tuple[str, str] | None:
    """The id and comment of a record header `⍝ id — comment`, or None for any other line."""
    if not line.startswith("⍝ "):
        return None
    line = line[2:]
    if line.startswith("—"):
        ident, comment = "", line[1:]
    elif " —" in line:
        ident, comment = line.split(" —", 1)
    else:
        return None
    if any(char.isspace() for char in ident) or (comment and not comment.startswith(" ")):
        return None
    return ident, comment[1:]


def _inline(text: str) -> tuple[str, str] | None:
    """`code ⍝ expectation` split at the first `⍝` outside a string or character literal on the
    last line, or None."""
    at, size, string = 0, len(text), False
    while at < size:
        char = text[at]
        if char == '"':
            string = not string
        elif char == "'" and not string:
            at += 1 if text.startswith("''", at) and not text.startswith("'''", at) else 2
        elif char == "⍝" and not string:
            if "\n" in text[at:]:
                at = text.index("\n", at)
            else:
                return text[:at].rstrip(), text[at + 1:].lstrip()
        at += 1
    return None


def reference_records(name: str, text: str) -> tuple[str, list[dict]]:
    """The shared setup and the records of one upstream reference file (tests/reference/*.bpl).

    Follows upstream's reader: a first line that calls `•prefs` sets every record's settings, as
    does a section heading's `•prefs` suffix and the `_mathish` file name; `⍝⍝ setup` holds
    definitions every record of the file starts from; a record is a header, its code, and an
    inline, `⍝ =>`-separated or next-line expectation (`⍝ error: KIND` for an error); a last
    `⍝ input:` line gives what `⎕` reads. Timed records (a `⍝⍝:` footer) are marked `timed`.

    Args:
        name: The file's name, such as `core.bpl`.
        text: The file's contents.

    Returns:
        The setup text (empty when there is none), and one dict per record with keys `file`,
        `line`, `id`, `section`, `comment`, `prefs`, `code`, and where present `expected`,
        `expected_error`, `input`, `output`, `timed`.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    header_prefs = lines[0] if lines and lines[0].startswith("•prefs") else ""
    mathish = '•prefs ["mathish":$t]' if name.endswith("_mathish.bpl") else ""
    at, title, local, setup, records = (1 if header_prefs else 0), "", "", "", []
    while at < len(lines):
        if lines[at] == "":
            at += 1
            continue
        if lines[at].startswith("⍝⍝ "):
            heading, start = lines[at][3:], at
            at += 1
            if heading == "setup":
                while at < len(lines) and not lines[at].startswith("⍝⍝ "):
                    at += 1
                setup = "\n".join(lines[start + 1:at]).rstrip()
            else:
                title, _, rest = heading.partition(" •prefs")
                local = ("•prefs" + rest) if rest else ""
            continue
        start, head = at, _header(lines[at])
        at += 1
        while at < len(lines) and _header(lines[at]) is None and not lines[at].startswith("⍝⍝ ") \
                and not lines[at - 1].startswith("⍝⍝:"):
            at += 1
        end = at
        while end > start and lines[end - 1] == "":
            end -= 1
        body = lines[start + (1 if head else 0):end]
        record = {"file": name, "line": start + 1, "id": head[0] if head else "", "section": title,
                  "comment": head[1] if head else "",
                  "prefs": "\n".join(part for part in (mathish, header_prefs, local) if part)}
        if body and body[-1].startswith("⍝⍝:"):
            record["timed"] = True
            body = body[:-1]
        elif head is None:
            continue
        body = [line for line in body if not line.startswith("⍝⍝⍝ ")]
        for marker, key in (("⍝ ⎕:", "output"), ("⍝ input:", "input")):
            if body and body[-1].startswith(marker):
                value = body[-1][len(marker):]
                value = value[1:] if value.startswith(" ") else value
                record[key] = value.replace("\\n", "\n").replace("\\\\", "\\")
                body = body[:-1]
        splits = [index for index, line in enumerate(body) if line == "⍝ =>"]
        pair = _inline("\n".join(body))
        if pair and len(body) > 1 and pair[0].count("\n") + 1 != len(body):
            pair = None
        if not splits and pair:
            code, expect = pair
        elif not splits and record.get("timed"):
            code, expect = "\n".join(body), None
        elif not splits and len(body) == 2:
            code, expect = body[0], body[1]
        elif len(splits) == 1:
            code, expect = "\n".join(body[:splits[0]]), "\n".join(body[splits[0] + 1:])
        else:
            continue
        record["code"] = code
        if expect is not None:
            if expect.startswith("⍝ error: "):
                record["expected_error"] = expect[len("⍝ error: "):]
            else:
                record["expected"] = expect
        records.append(record)
    return setup, records


# --- The upstream checkout, read at the pinned commit -----------------------------------------------


def git_files(checkout: Path, prefix: str = "") -> list[str]:
    """Paths of the files at the pinned commit under `prefix` (all files for ""). `checkout` is a
    git checkout that holds the commit (any branch may be checked out), or a plain directory that
    holds the commit's files (an export, or a test's stand-in), read as it is."""
    if not (checkout / ".git").exists():
        top = checkout / prefix if prefix else checkout
        return sorted(path.relative_to(checkout).as_posix() for path in top.rglob("*") if path.is_file())
    listed = subprocess.run(["git", "-C", str(checkout), "ls-tree", "-r", "--name-only", UPSTREAM_COMMIT, "--", prefix or "."],
                            capture_output=True, text=True, check=True).stdout
    return [line for line in listed.split("\n") if line]


def git_bytes(checkout: Path, path: str) -> bytes:
    """A file's bytes at the pinned commit (see `git_files` for `checkout`)."""
    if not (checkout / ".git").exists():
        return (checkout / path).read_bytes()
    return subprocess.run(["git", "-C", str(checkout), "show", f"{UPSTREAM_COMMIT}:{path}"], capture_output=True,
                          check=True).stdout


def git_text(checkout: Path, path: str) -> str:
    """A file's text at the pinned commit."""
    return git_bytes(checkout, path).decode("utf-8")


# --- The documentation the agent is given -----------------------------------------------------------


def page_text(path: str, text: str) -> str:
    """A documentation page as `]help` shows it (upstream's build.rs `page_text`): a Quarto page
    as written; a notebook as its Markdown cells and its code cells in ```bpl fences, with no
    stored outputs."""
    if not path.endswith(".ipynb"):
        return text
    notebook = json.loads(text)
    language = notebook.get("metadata", {}).get("kernelspec", {}).get("language", "bpl")
    parts = []
    for cell in notebook["cells"]:
        source = cell["source"] if isinstance(cell["source"], str) else "".join(cell["source"])
        if cell["cell_type"] == "markdown":
            parts.append(source)
        elif cell["cell_type"] == "code":
            parts.append(f"```{language}\n{source}\n```")
    return "\n\n".join(parts) + "\n\n"


def documentation(checkout: Path) -> dict[str, str]:
    """The documentation the agent image holds in /app/docs, by path there.

    Every page of upstream's documentation site (nbs/: the guides, the glyph pages, the system
    function pages and the study notebooks) in the form the interpreter's own `]help` shows it,
    notebooks as Markdown without their stored outputs (`page_text`), plus `llms.txt`, the
    licence and the README of upstream's documentation. No test, reference case, expected output
    or development note: the agent finds out what the interpreter prints by running it.

    Args:
        checkout: An upstream checkout that holds the pinned commit.

    Returns:
        Path under /app/docs to Markdown text, sorted by path.
    """
    pages: dict[str, str] = {}
    for path in git_files(checkout, "nbs"):
        relative = path[len("nbs/"):]
        if not re.fullmatch(r"((glyphs|system|study)/)?[^/]+\.(qmd|ipynb)", relative):
            continue
        name = re.sub(r"\.(qmd|ipynb)$", ".md", relative)
        pages[name] = page_text(path, git_text(checkout, path))
    pages["llms.txt"] = git_text(checkout, "nbs/llms.txt")
    pages["LICENSE"] = git_text(checkout, "LICENSE")
    return dict(sorted(pages.items()))


def function_table(pages: dict[str, str]) -> list[str]:
    """The documented table of the language's primitive functions: the glyph of every glyph page
    (glyphs/*.md) that the documentation calls a function (its third line begins "Function."), in
    the order of the pages' paths.

    Used to write the verifier's tests/verifier/functions.json (scripts/function_table.py), which
    packaging checks against the pages it ships, so that the verifier's list of what one primitive
    can do to a literal is the documentation's and no one's choice.

    Args:
        pages: The documentation, as documentation() returns it (path under /app/docs to text).

    Returns:
        The functions' glyphs, each a short string such as "⌽" or "≢".
    """
    found = []
    for path, text in sorted(pages.items()):
        lines = text.splitlines()
        if path.startswith("glyphs/") and len(lines) > 2 and lines[2].startswith("Function."):
            title = re.match(r"# `([^`]+)`", lines[0])
            if title:
                found.append(title[1])
    return found


def doc_programs(pages: dict[str, str]) -> list[str]:
    """Every piece of BPL the documentation shows: each fenced code block (bpl, text, bash or
    unlabelled), each line of one, and each inline code span of more than three characters, with
    the shell's `bpl -e '...'` unwrapped. These are what no private case may hold or nearly copy."""
    found: list[str] = []
    for text in pages.values():
        for block in re.findall(r"```[a-z]*\n(.*?)```", text, flags=re.S):
            found.append(block)
            for line in block.split("\n"):
                line = re.sub(r"^\s*bpl -e '(.*)'.*$", r"\1", line)
                code = _inline(line)
                found.append(code[0] if code else line)
        for span in re.findall(r"`([^`\n]{4,})`", text):
            found.append(span)
    return [piece for piece in found if piece.strip()]


def leak_index(pages: dict[str, str]) -> tuple[set[str], set[str]]:
    """What the documentation shows, for the leak checks: the skeleton (`skeleton`) of every
    program and statement it holds, and the same with comments and blank space removed, as exact
    texts.

    Returns:
        (skeletons, texts): two sets of one-line strings.
    """
    skeletons, texts = set(), set()
    for piece in doc_programs(pages):
        parts = statements(piece)
        # The block whole, each statement, and each run of 2 to 6 consecutive statements: a record
        # that is the start or the middle of a longer documented block is still the docs' program.
        runs = ["\n".join(parts[start:start + length]) for length in range(2, 7) for start in range(len(parts) - length + 1)]
        for part in [piece] + parts + runs:
            shape = skeleton(part)
            if len(shape) >= 3:
                skeletons.add(shape)
            texts.add(compact(part))
    return skeletons, texts


def compact(code: str) -> str:
    """A program without comments or blank space, as one line."""
    return "".join(token.text for token in tokenize(code) if token.kind not in ("space", "comment", "newline"))
