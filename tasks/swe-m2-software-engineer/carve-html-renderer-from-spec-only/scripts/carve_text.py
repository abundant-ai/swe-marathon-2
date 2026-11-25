"""Pins, the shipped specification and documentation, and the leak index of the Carve task.

What the agent sees is the normative specification at the pinned spec tag (resources/spec/:
the EBNF modules and their structured contracts, plus resources/normative-clauses.txt) and
the documentation site's own pages (docs/**/*.md), as text. Nothing else of upstream's is
shipped: not the aggregate grammar (the same bytes as the modules), not the derived checkers
(resources/carve-core.ohm, scripts/spec/), not the conformance corpus or pack, and not the four
example pages the site generates from the corpus (resources/examples/).

`leak_index` turns everything shipped into the set of example skeletons and the compact text
that make_cases.leaks() checks every private case against: no case may be an example the
agent can read, or a near-copy of one (the same text with its words, numbers or letters
changed). Examples written with `\n` and `\t` escapes (the ownership ledger's code spans) are
unescaped first, and the indented example blocks of the EBNF modules are read too (QA 06).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

SPEC_TAG = "0.1.14"
SPEC_COMMIT = "51c5631541efb60faad51f81ac7dbf881150b757"   # markup-carve/carve, tag 0.1.14, 2026-11-12
CARVE_RS_TAG = "0.1.14"
CARVE_RS_COMMIT = "0a56283f1e745643bc78cdd6fb11ac7344fb88c7"  # markup-carve/carve-rs, tag 0.1.14; its tests/spec pins SPEC_COMMIT
# The release's Linux build: static-pie, records the answers in the verifier's builder stage and
# is the reference solution.
LINUX_ARCHIVE = "carve-0.1.14-x86_64-unknown-linux-musl.tar.gz"
LINUX_ARCHIVE_SHA256 = "af082997672a9dc12a36a48a2dc4a72d0541b7418eb6a1c57b57f1068c0fc4ac"
LINUX_BINARY_SHA256 = "05d0898dd1c8918adee5a3b2e5a1ae1b5697acd75c7b692bf4a4ea0e4fae2048"
# The release's macOS arm64 build, for selecting and checking cases on the author's machine.
MAC_ARCHIVE = "carve-0.1.14-aarch64-apple-darwin.tar.gz"
MAC_ARCHIVE_SHA256 = "6787862ceef5241f0967326520d33fbff378d5db45110f2c81294e37c605f9ba"
MAC_BINARY_SHA256 = "10257b84a0eff11cf26455914707cbab1ee049022204a61c06914f654422c591"

CACHE = Path(__file__).resolve().parents[5] / ".cache-src"   # beside the repository checkout
SPEC_CHECKOUT = CACHE / "carve"
RS_CHECKOUT = CACHE / "carve-rs"

# resources/spec/ as shipped: the modules and the structured contracts they cite.
SPEC_DIR = "resources/spec"
SPEC_EXTRA = ("resources/normative-clauses.txt",)
DOCS_DIR = "docs"
DOCS_SKIPPED = (".vitepress/", "public/")   # the site's theme, build config and assets


def git(checkout: Path, *args: str) -> bytes:
    """Output of a git command in `checkout`.

    Raises:
        subprocess.CalledProcessError: git failed (a missing commit, say).
    """
    return subprocess.run(["git", "-C", str(checkout), *args], check=True, capture_output=True).stdout


def git_files(checkout: Path, prefix: str, commit: str = SPEC_COMMIT) -> list[str]:
    """Every file path under `prefix` at `commit`, sorted."""
    return sorted(git(checkout, "ls-tree", "-r", "--name-only", commit, "--", prefix).decode().splitlines())


def git_bytes(checkout: Path, path: str, commit: str = SPEC_COMMIT) -> bytes:
    """A file's bytes at `commit`."""
    return git(checkout, "show", f"{commit}:{path}")


def git_text(checkout: Path, path: str, commit: str = SPEC_COMMIT) -> str:
    """A file's text at `commit`."""
    return git_bytes(checkout, path, commit).decode("utf-8")


def specification(checkout: Path = SPEC_CHECKOUT) -> dict[str, str]:
    """The specification as shipped in /app/spec: name -> text."""
    pages = {path[len(SPEC_DIR) + 1:]: git_text(checkout, path) for path in git_files(checkout, SPEC_DIR)}
    for path in SPEC_EXTRA:
        pages[path.rsplit("/", 1)[1]] = git_text(checkout, path)
    pages["LICENSE"] = git_text(checkout, "LICENSE")
    return dict(sorted(pages.items()))


def documentation(checkout: Path = SPEC_CHECKOUT) -> dict[str, str]:
    """The documentation site's pages as shipped in /app/docs: relative path -> text."""
    pages = {}
    for path in git_files(checkout, DOCS_DIR):
        relative = path[len(DOCS_DIR) + 1:]
        if path.endswith(".md") and not relative.startswith(DOCS_SKIPPED):
            pages[relative] = git_text(checkout, path)
    pages["LICENSE"] = git_text(checkout, "LICENSE")
    return dict(sorted(pages.items()))


FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})([^\n]*)\n(.*?)^\1\2[ \t]*$", re.M | re.S)
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
INDENTED = re.compile(r"^((?: {5,}|\t+)[^\n]*\n)+", re.M)
ESCAPES = {"\\n": "\n", "\\t": "\t", "\\r": "\r", "⇥": "\t", "<TAB>": "\t", "<SP>": " ", "<BOM>": "\ufeff", "<U+FEFF>": "\ufeff",
           "<U+200B>": "\u200b", "<U+00A0>": "\u00a0"}
LETTERS = re.compile(r"[^\W\d_]+")
DIGITS = re.compile(r"\d+")


SOURCE_FIELDS = re.compile(r'"(?:source|canonical|aligned|input|carve)"\s*:\s*"((?:[^"\\]|\\.)*)"')
ARROW = re.compile(r"\s*(?:->|→|=>|\bgives\b|\brenders\b|Djot:|Carve:)")


def unescaped(text: str) -> str:
    """`text` with the written escapes of an example (`\\n`, `\\t`, `⇥`, `<TAB>`, `<BOM>`) as the
    characters they stand for."""
    for written, char in ESCAPES.items():
        text = text.replace(written, char)
    return text


def with_parts(piece: str) -> list[str]:
    """`piece`, its unescaped form, and each blank-line-separated part of either."""
    forms = [piece]
    other = unescaped(piece)
    if other != piece:
        forms.append(other)
    found = list(forms)
    for form in forms:
        found += [part for part in re.split(r"\n[ \t]*\n", form) if part.strip() and part.strip() != form.strip()]
    return found


def indented_blocks(text: str) -> list[str]:
    """The indented example blocks of a specification module (runs of lines indented by five
    spaces or more inside its prose), dedented, with any `->` or `→` result column cut off."""
    found = []
    for match in INDENTED.finditer(text):
        lines = match.group(0).rstrip("\n").split("\n")
        width = min(len(line) - len(line.lstrip(" \t")) for line in lines if line.strip())
        body = "\n".join(line[width:] for line in lines)
        found.append(body)
        cut = [re.split(r"\s+(?:->|→)\s", line, maxsplit=1)[0] for line in body.split("\n")]
        if cut != body.split("\n"):
            found.append("\n".join(cut))
    return found


def example_sides(line: str) -> list[str]:
    """The source side of a `SOURCE -> RESULT` example written on one line, cut a few ways
    (the whole left side, after its last `: ` or `, `, its last word), as candidates."""
    if not ARROW.search(line):
        return []
    left = ARROW.split(line, maxsplit=1)[0].rstrip()
    parts = {left.strip(), left.split(": ")[-1].strip(), left.split(", ")[-1].strip(),
             left.split("  ")[-1].strip(), (left.split() or [""])[-1]}
    return [part for part in parts if part]


def snippets(text: str, name: str = "page.md") -> list[str]:
    """The example sources a page shows. In Markdown: the bodies of its fenced code blocks (other
    than code in other languages and HTML output) and, inside them, each block separated by
    blank lines; its inline code spans of three characters or more; and the source side of every
    one-line `SOURCE -> RESULT` example. In the specification's modules, which give examples in
    prose: backtick spans and the source sides of examples. In its JSON contracts: every
    source-like string field. A `.crv` file is a source as a whole."""
    found = []
    if name.endswith(".crv"):
        found.append(text)
    if name.endswith(".json"):
        for match in SOURCE_FIELDS.finditer(text):
            try:
                found += with_parts(json.loads(f'"{match.group(1)}"'))
            except ValueError:
                continue
        return found
    if name.endswith((".ebnf", ".txt")):
        for block in indented_blocks(text):
            found += with_parts(block)
    for match in FENCE.finditer(text):
        info = match.group(3).strip().lower()
        if info.startswith(("html", "json", "js", "ts", "php", "rust", "rs", "bash", "sh", "toml", "yaml", "ebnf", "css")):
            continue
        body = match.group(4)
        found += with_parts(body)
        for line in body.splitlines():
            found += example_sides(line)
    for match in INLINE_CODE.finditer(text):
        if len(match.group(2).strip()) >= 3:
            found += with_parts(match.group(2).strip())
    for line in text.splitlines():
        found += example_sides(line)
    return found


def skeleton(text: str) -> str:
    """`text` with every run of letters (any script) written `a` and every run of digits `0`, line
    ends normalized and trailing blanks dropped: two sources with the same skeleton differ only in
    their words and numbers."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    shape = "\n".join(DIGITS.sub("0", LETTERS.sub("a", line)).rstrip() for line in lines)
    return shape.strip("\n")


def compact(text: str) -> str:
    """`text` without any whitespace."""
    return re.sub(r"\s+", "", text)


def leak_index(pages: dict[str, str]) -> tuple[set[str], str]:
    """The skeletons of every example the pages show, and all their text compacted, both with the
    written escapes unescaped."""
    skeletons = set()
    for name, text in pages.items():
        for piece in snippets(text, name):
            shape = skeleton(piece)
            if len(compact(shape)) >= 3:
                skeletons.add(shape)
    return skeletons, "\n".join(compact(text) + "\n" + compact(unescaped(text)) for text in pages.values())


ANSWER_LEN = 20  # characters of a compacted answer, at least, for it to count as shown


def answer_shown(html: str, blob: str) -> bool:
    """Whether the shipped text holds a rendered answer (compacted, at least ANSWER_LEN characters
    or three tags): the docs print the HTML of some examples, and a case whose answer they print
    is a leak whatever its source looks like."""
    flat = compact(html)
    if len(flat) < ANSWER_LEN and flat.count("<") < 3:
        return False
    return flat in blob


INCLUDE = re.compile(r"\{\{")


def holds_include(source: str) -> bool:
    """Whether a source could hold an include directive (`{{ path }}`), which is out of scope:
    the original resolves it against the file system."""
    return bool(INCLUDE.search(source))
