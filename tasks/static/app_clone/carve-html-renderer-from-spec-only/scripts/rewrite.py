"""Private-seed rewrites of Carve sources, so that a case's answer is not one upstream publishes.

Two kinds:

- `renamed`: every ASCII word in prose position becomes another word of the same length and the
  same letter case, consistently across the document (a word touching a non-ASCII character, a
  letter with a diacritic or a combining mark, is kept, so that nothing is renamed by halves) (so a cross-reference, a heading
  reference, a footnote label or an abbreviation still finds what it found before). Words that
  are syntax or that the renderer treats specially are kept everywhere in the document: a
  container's type word, a code or raw fence's info string, an attribute block other than its
  `.class` and `#id` tokens, entity names, URL schemes and other `word:` forms, a task item's
  state, a letter or roman list marker, `(tm)`-style replacements, backslash words, a
  frontmatter format, and common file extensions. Non-ASCII text is kept.
- `mutated`: one to three local edits of the lines (delete, duplicate, swap, indent, dedent,
  insert a blank line, insert a marker or delimiter fragment, prefix a run of lines, splice a
  line from another document, delete or duplicate a character), in the manner of upstream's
  mutation fuzzer, with this task's own fragments and the private seed.

make_cases.py renames every case built from upstream's corpus and keeps the first rewrite that
prints something else than the unrewritten source while keeping its element structure (see
`structure`).
"""

from __future__ import annotations

import random
import re

from words import WORDS_BY_LENGTH

WORD = re.compile(r"[A-Za-z]+")
CONTAINER_TYPE = re.compile(
    r"^[ \t]*(?:(?:>|[-*+]|\d+[.)]|\.|::?|\[\^[^\]\n]*\]:)[ \t]+)*(?:>[ \t]?)*:{3,}[ \t]*([^\s{\"\[]+)",
    re.MULTILINE,
)
FENCE_INFO = re.compile(
    r"^[ \t]*(?:(?:>|[-*+]|\d+[.)]|\.|:{1,2}|\[\^[^\]]*\]:)[ \t]*)*(?:`{3,}|~{3,})([^\n]*)$",
    re.MULTILINE,
)
ATTRIBUTE_BLOCK = re.compile(r"\{([^{}\n]*)\}")
BRACED_SPAN = re.compile(
    r"^([*/_~=^,+\-#%])\S.*\S?\1$|^[*/_~=^,+\-#%].+[*/_~=^,+\-#%]$"
)
ENTITY = re.compile(r"&#?[A-Za-z0-9]+;")
WORD_COLON = re.compile(r"\b([A-Za-z][A-Za-z0-9+.\-]*):")
TASK = re.compile(
    r"^[ \t]*(?:>[ \t]?)*(?:[-*]|\.|\d+[.)])(?:\{[^}\n]*\})?[ \t]+\[([^\]\n])\]",
    re.MULTILINE,
)
ORDERED_LETTER = re.compile(
    r"^[ \t]*(?:>[ \t]?)*(?:(?:[-*]|\.|\d+[.)])[ \t]+)*([A-Za-z]{1,6})([.)])(?=[ \t])",
    re.MULTILINE,
)
REPLACEMENT = re.compile(r"\((tm|TM|c|C|r|R|p|P|sm|SM)\)")
BACKSLASH_WORD = re.compile(r"\\([A-Za-z]+)")
FRONTMATTER = re.compile(r"\A---([A-Za-z]+)")
EXTENSION_NAME = re.compile(r":([A-Za-z][A-Za-z0-9-]*)\[")
FILE_EXTENSION = re.compile(
    r"\.(png|jpe?g|gif|svg|webp|avif|bmp|ico|mp4|webm|ogg|mp3|wav|pdf|crv|md|html?|txt|csv|tsv|json|ya?ml|toml|js|ts|py|rs|go|css)\b",
    re.IGNORECASE,
)
RAW_FENCE = re.compile(
    r"^([ \t]*)(`{3,}|~{3,})[ \t]*=[^\n]*\n.*?^\1\2[ \t]*$", re.MULTILINE | re.DOTALL
)
RAW_INLINE = re.compile(r"(`+)[^`]*\1\{=[A-Za-z]+\}")
ROMAN = re.compile(r"^[ivxlcdmIVXLCDM]+$")
CONTRACTION = re.compile(r"(?<=[A-Za-z])['’](s|t|d|m|ll|re|ve)\b", re.IGNORECASE)


def protected_words(source: str) -> set[str]:
    """Words the renaming keeps, wherever they occur in `source`."""
    keep: set[str] = set()
    for match in WORD.finditer(
        source
    ):  # a word that touches a non-ASCII character is part of a larger one
        before = source[match.start() - 1] if match.start() else ""
        after = source[match.end()] if match.end() < len(source) else ""
        if (before and ord(before) > 127) or (after and ord(after) > 127):
            keep.add(match.group(0))

    def words_of(text: str) -> None:
        keep.update(WORD.findall(text))

    for match in CONTAINER_TYPE.finditer(source):
        words_of(match.group(1))
    for match in FENCE_INFO.finditer(source):
        words_of(match.group(1))
    for match in ATTRIBUTE_BLOCK.finditer(source):
        inner = match.group(1)
        if BRACED_SPAN.match(inner):  # {*strong*}, {+ins+}, {#comment#}: prose inside
            continue
        for token in re.split(r"[\s]+", inner):
            if token.startswith((".", "#")) and len(token) > 1:
                continue
            words_of(token)
    for pattern in (
        ENTITY,
        REPLACEMENT,
        BACKSLASH_WORD,
        FRONTMATTER,
        EXTENSION_NAME,
        FILE_EXTENSION,
        CONTRACTION,
    ):
        for match in pattern.finditer(source):
            words_of(match.group(0))
    for match in WORD_COLON.finditer(source):
        words_of(match.group(1))
    for match in TASK.finditer(source):
        words_of(match.group(1))
    for match in ORDERED_LETTER.finditer(source):
        marker = match.group(1)
        if len(marker) == 1 or ROMAN.match(marker):
            keep.add(marker)
    for pattern in (RAW_FENCE, RAW_INLINE):
        for match in pattern.finditer(source):
            words_of(match.group(0))
    return keep


def case_like(word: str, model: str) -> str:
    """`word` (lower case) written in the letter case of `model`: lower, Capitalized, UPPER, or
    letter by letter."""
    if model.islower():
        return word
    if model.isupper():
        return word.upper()
    if model[0].isupper() and (len(model) == 1 or model[1:].islower()):
        return word.capitalize()
    return "".join(c.upper() if m.isupper() else c for c, m in zip(word, model))


def renaming(source: str, rng: random.Random) -> dict[str, str]:
    """A rename of each word of `source` that the renaming may change, keyed by its lower-case
    form, to a word of the same length the document does not hold. Different words get
    different replacements, so equal spellings stay equal and different ones stay different."""
    keep = {word.lower() for word in protected_words(source)}
    present = {word.lower() for word in WORD.findall(source)}
    taken = set(present)
    mapping: dict[str, str] = {}
    for word in sorted(present - keep):
        pool = WORDS_BY_LENGTH.get(len(word))
        choice = None
        if pool:
            for _ in range(12):
                candidate = rng.choice(pool)
                if candidate not in taken:
                    choice = candidate
                    break
        if (
            choice is None
        ):  # no listed word of that length is free: letters drawn at random
            for _ in range(50):
                candidate = "".join(
                    rng.choice("bcdfghjklmnprstvwz" if i % 2 == 0 else "aeiou")
                    for i in range(len(word))
                )
                if candidate not in taken:
                    choice = candidate
                    break
        if choice is None:
            continue
        taken.add(choice)
        mapping[word] = choice
    return mapping


def renamed(source: str, mapping: dict[str, str]) -> str:
    """`source` with every word that `mapping` names replaced, in its own letter case."""

    def swap(match: re.Match) -> str:
        word = match.group(0)
        new = mapping.get(word.lower())
        return case_like(new, word) if new else word

    return WORD.sub(swap, source)


def renamings(source: str, rng: random.Random, count: int = 3) -> list[str]:
    """Up to `count` different renamed copies of `source`, each from its own draw."""
    found: list[str] = []
    for _ in range(count * 2):
        candidate = renamed(source, renaming(source, rng))
        if candidate != source and candidate not in found:
            found.append(candidate)
        if len(found) == count:
            break
    return found


# --- Structure -------------------------------------------------------------------------------

TAG_OR_TEXT = re.compile(r"<[^>]*>|[^<]+")
ATTRIBUTE_VALUE = re.compile(r'="([^"]*)"')


def structure(html: str) -> str:
    """The element structure of an answer: tags with their attribute names, every run of letters
    written `a` and every run of digits `0`, in text and in attribute values alike. A rewrite that
    only changes words keeps it."""
    out = []
    for piece in TAG_OR_TEXT.findall(html):
        if piece.startswith("<"):
            piece = ATTRIBUTE_VALUE.sub(
                lambda m: (
                    '="'
                    + re.sub(r"\d+", "0", re.sub(r"[^\W\d_]+", "a", m.group(1)))
                    + '"'
                ),
                piece,
            )
            out.append(piece)
        else:
            out.append(re.sub(r"\d+", "0", re.sub(r"[^\W\d_]+", "a", piece)))
    return "".join(out)


# --- Mutations -------------------------------------------------------------------------------

FRAGMENTS = [
    "::: warning",
    "::: tip",
    ":::",
    "::::",
    "::: >",
    "::: |",
    "{.lead}",
    "{#top}",
    "{",
    "}",
    "> ",
    "> > ",
    "- ",
    "* ",
    "2. ",
    ". ",
    "a)  ",
    ":: term",
    ": meaning",
    "+",
    "|= Key |= Value |",
    "| x | y |",
    "^ Caption",
    "%%",
    "%%%",
    "```",
    "```sh",
    "~~~",
    "$`n^2`",
    "!`raw`",
    "[see](https://example.org)",
    "[ref][doc]",
    "[doc]: https://example.com/doc",
    "*[CLI]: command line",
    "</#top>",
    "^[aside]",
    "[^one]",
    "[^one]: Note text.",
    "@sam",
    "#todo",
    "\t",
    "   ",
    "words here",
    "/slant/",
    "*heavy*",
    "_under_",
    "~gone~",
    "=marked=",
    "{*x*}",
    "{^2^}",
    "{,i,}",
    "***",
    "## Part",
    "`",
    "``",
    "\\",
    "--",
    "...",
    '"q"',
    "'s",
    "(tm)",
    "- [x] ",
    "- [/] ",
    "-{.c} ",
    ":name:",
    "{% hidden %}",
    "{+new+}",
    "{-old-}",
]
PREFIXES = ["> ", "  ", "   ", " ", "- ", ". ", "1. ", ": ", "+ ", "\t", "    "]


def _lines(source: str) -> list[str]:
    return source.rstrip("\n").split("\n")


def mutate(source: str, rng: random.Random, donors: list[str]) -> tuple[str, list[str]]:
    """One to three local edits of `source`; returns the mutant and the edits' names."""
    lines = _lines(source)
    applied = []
    for _ in range(1 + rng.randrange(3)):
        name = rng.choice(MUTATORS)
        lines = globals()["_" + name](lines, rng, donors)
        applied.append(name)
        if not lines:
            lines = [""]
    return "\n".join(lines) + "\n", applied


def _delete_line(lines, rng, donors):
    if len(lines) < 2:
        return lines
    i = rng.randrange(len(lines))
    return lines[:i] + lines[i + 1 :]


def _duplicate_line(lines, rng, donors):
    i = rng.randrange(len(lines))
    return lines[:i] + [lines[i]] + lines[i:]


def _swap_lines(lines, rng, donors):
    if len(lines) < 2:
        return lines
    i = rng.randrange(len(lines) - 1)
    return lines[:i] + [lines[i + 1], lines[i]] + lines[i + 2 :]


def _indent_line(lines, rng, donors):
    i = rng.randrange(len(lines))
    return lines[:i] + [rng.choice([" ", "  ", "   "]) + lines[i]] + lines[i + 1 :]


def _dedent_line(lines, rng, donors):
    i = rng.randrange(len(lines))
    return lines[:i] + [re.sub(r"^[ \t]", "", lines[i])] + lines[i + 1 :]


def _insert_blank(lines, rng, donors):
    i = rng.randrange(len(lines) + 1)
    return lines[:i] + [""] + lines[i:]


def _insert_fragment_line(lines, rng, donors):
    i = rng.randrange(len(lines) + 1)
    return lines[:i] + [rng.choice(FRAGMENTS)] + lines[i:]


def _insert_fragment_inline(lines, rng, donors):
    i = rng.randrange(len(lines))
    at = rng.randrange(len(lines[i]) + 1)
    return (
        lines[:i]
        + [lines[i][:at] + rng.choice(FRAGMENTS) + lines[i][at:]]
        + lines[i + 1 :]
    )


def _prefix_run(lines, rng, donors):
    start = rng.randrange(len(lines))
    end = min(len(lines), start + 1 + rng.randrange(3))
    prefix = rng.choice(PREFIXES)
    rest = (
        " " * len(prefix)
        if re.match(r"^[-+:>.]|^1\.", prefix) and rng.random() < 0.5
        else prefix
    )
    return [
        prefix + line if i == start else rest + line if start < i < end else line
        for i, line in enumerate(lines)
    ]


def _splice_donor(lines, rng, donors):
    if not donors:
        return lines
    donor = _lines(rng.choice(donors))
    start = rng.randrange(len(donor))
    run = donor[start : start + 1 + rng.randrange(2)]
    i = rng.randrange(len(lines) + 1)
    return lines[:i] + run + lines[i:]


def _delete_char(lines, rng, donors):
    i = rng.randrange(len(lines))
    if not lines[i]:
        return lines
    at = rng.randrange(len(lines[i]))
    return lines[:i] + [lines[i][:at] + lines[i][at + 1 :]] + lines[i + 1 :]


def _duplicate_char(lines, rng, donors):
    i = rng.randrange(len(lines))
    if not lines[i]:
        return lines
    at = rng.randrange(len(lines[i]))
    return lines[:i] + [lines[i][: at + 1] + lines[i][at:]] + lines[i + 1 :]


MUTATORS = [
    "delete_line",
    "duplicate_line",
    "swap_lines",
    "indent_line",
    "dedent_line",
    "insert_blank",
    "insert_fragment_line",
    "insert_fragment_inline",
    "prefix_run",
    "splice_donor",
    "delete_char",
    "duplicate_char",
]
