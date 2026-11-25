"""The corpus-lookup baseline: what a program with the public conformance corpus and no renderer
would answer for a case (QA 05).

Upstream publishes 4,631 source/HTML pairs. A case built from one of them by renaming its words
has the same skeleton (letters and digits abstracted), so such a program can find the pair by
skeleton, read the word mapping off the two sources and push the published HTML through it.
For a case made of several documents it concatenates the parts' answers; for a case wrapped in
a host it strips the host's prefix, looks the body up and adds the host's tags back.

`guesses(source)` returns every answer such a program would produce for `source`, as the bytes
it would print (the HTML and a final newline). make_cases.py drops any case whose recorded
answer is among them and stores the guesses' digests with the case, so that the build's recording
measures the baseline on the Linux answers (recorder.py) and fails the build above its cap.
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict

import carve_text as ct

WORD = re.compile(r"[A-Za-z]+")
ENTITY = re.compile(r"&#?[A-Za-z0-9]+;")
TAG_OR_TEXT = re.compile(r"<[^>]*>|[^<]+")
ATTR_VALUE = re.compile(r'="([^"]*)"')
ADMONITIONS = {
    "note",
    "tip",
    "warning",
    "danger",
    "info",
    "success",
    "example",
    "quote",
}


def case_like(word: str, model: str) -> str:
    if model.islower():
        return word
    if model.isupper():
        return word.upper()
    if model[0].isupper() and (len(model) == 1 or model[1:].islower()):
        return word.capitalize()
    return "".join(c.upper() if m.isupper() else c for c, m in zip(word, model))


def mapping_between(original: str, renamed: str) -> dict[str, str] | None:
    """original word (lower) -> renamed word (lower), read off aligned word tokens; None when the
    two texts do not align word for word or the mapping is inconsistent."""
    a, b = WORD.findall(original), WORD.findall(renamed)
    if len(a) != len(b):
        return None
    mapping: dict[str, str] = {}
    for x, y in zip(a, b):
        if len(x) != len(y):
            return None
        if mapping.setdefault(x.lower(), y.lower()) != y.lower():
            return None
    return {k: v for k, v in mapping.items() if k != v}


def mapping_fuzzy(original: str, renamed: str) -> dict[str, str]:
    """A mapping read off the lines of `original` and `renamed` that align by skeleton: what a
    program would read off a mutated case's nearest corpus document."""
    la, lb = original.split("\n"), renamed.split("\n")
    matcher = difflib.SequenceMatcher(
        a=[ct.skeleton(x) for x in la], b=[ct.skeleton(x) for x in lb], autojunk=False
    )
    mapping: dict[str, str] = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for i, j in zip(range(i1, i2), range(j1, j2)):
            wa, wb = WORD.findall(la[i]), WORD.findall(lb[j])
            if len(wa) == len(wb):
                for x, y in zip(wa, wb):
                    if len(x) == len(y):
                        mapping.setdefault(x.lower(), y.lower())
    return {k: v for k, v in mapping.items() if k != v}


def rename_text(text: str, mapping: dict[str, str]) -> str:
    def swap(match: re.Match) -> str:
        word = match.group(0)
        new = mapping.get(word.lower())
        return case_like(new, word) if new else word

    out, pos = [], 0
    for match in ENTITY.finditer(text):
        out.append(WORD.sub(swap, text[pos : match.start()]))
        out.append(match.group(0))
        pos = match.end()
    out.append(WORD.sub(swap, text[pos:]))
    return "".join(out)


def map_html(html: str, mapping: dict[str, str]) -> str:
    """The mapping applied to text and attribute values, never to tag or attribute names."""
    out = []
    for piece in TAG_OR_TEXT.findall(html):
        if piece.startswith("<"):
            out.append(
                ATTR_VALUE.sub(
                    lambda m: '="' + rename_text(m.group(1), mapping) + '"', piece
                )
            )
        else:
            out.append(rename_text(piece, mapping))
    return "".join(out)


def indent(html: str, by: int = 2) -> str:
    return "\n".join((" " * by + line) if line else line for line in html.split("\n"))


class Lookup:
    """The published corpus indexed by skeleton, and the answers a renderer-free program gives."""

    def __init__(self, sources: dict[str, str], htmls: dict[str, str]):
        self.sources = sources
        self.htmls = {
            name: htmls[name].rstrip("\n") for name in sources if name in htmls
        }
        self.by_skeleton: dict[str, list[str]] = defaultdict(list)
        for name, source in sources.items():
            if name in self.htmls:
                self.by_skeleton[ct.skeleton(source)].append(name)
        self.names = sorted(self.htmls)

    def direct(self, source: str) -> set[str]:
        """The published HTML, mapped, of every corpus document with the source's skeleton."""
        found = set()
        for name in self.by_skeleton.get(ct.skeleton(source), []):
            mapping = mapping_between(self.sources[name], source)
            if mapping is not None:
                found.add(map_html(self.htmls[name], mapping))
        return found

    def blocks(self, source: str, most: int = 64) -> set[str]:
        """The parts' answers joined with newlines, for every way of cutting the source's lines into
        consecutive runs that are each a corpus document (blank lines between runs skipped): a
        composite of parts that do not interact, however they are joined."""
        lines = source.rstrip("\n").split("\n")
        count = len(lines)
        answers: list[set[str] | None] = [None] * (count + 1)
        answers[count] = {""}

        def after(start: int) -> set[str]:
            if answers[start] is None:
                found: set[str] = set()
                if not lines[start].strip():
                    found |= after(start + 1)
                else:
                    for end in range(start + 1, count + 1):
                        part = "\n".join(lines[start:end]) + "\n"
                        for name in self.by_skeleton.get(ct.skeleton(part), []):
                            mapping = mapping_between(self.sources[name], part)
                            if mapping is None:
                                continue
                            head = map_html(self.htmls[name], mapping)
                            for rest in after(end):
                                found.add(head + ("\n" + rest if rest else ""))
                                if len(found) >= most:
                                    break
                        if len(found) >= most:
                            break
                answers[start] = found
            return answers[start]

        whole = after(0) - self.direct(source)
        return {html for html in whole if html}

    def unwrapped(self, source: str) -> set[str]:
        """A body inside one mechanical host, looked up and wrapped again: every line quoted with
        `> `, a colon container, a list item whose body is indented to its content column, or a
        heading above the body (a section wrapper)."""
        found = set()
        lines = source.rstrip("\n").split("\n")
        if lines and all(
            line.startswith("> ") or line == ">" or not line for line in lines
        ):
            body = (
                "\n".join(line[2:] if line.startswith("> ") else "" for line in lines)
                + "\n"
            )
            for inner in self.direct(body) | self.blocks(body):
                if (
                    inner.startswith("<p>")
                    and inner.endswith("</p>")
                    and inner.count("<p>") == 1
                ):
                    found.add(f"<blockquote>{inner}</blockquote>")
                found.add("<blockquote>\n" + indent(inner) + "\n</blockquote>")
        match = re.match(
            r"^(:{3,}) ?([A-Za-z][\w-]*)?[^\n]*\n(.*)\n\1[ \t]*$",
            source.rstrip("\n"),
            re.DOTALL,
        )
        if match:
            word = match.group(2) or ""
            for inner in self.direct(match.group(3) + "\n") | self.blocks(
                match.group(3) + "\n"
            ):
                if word in ADMONITIONS:
                    found.add(
                        f'<aside class="admonition {word}" aria-label="{word.capitalize()}">\n'
                        + indent(inner)
                        + "\n</aside>"
                    )
                elif word:
                    found.add(f'<div class="{word}">\n' + indent(inner) + "\n</div>")
                else:
                    found.add("<div>\n" + indent(inner) + "\n</div>")
        match = re.match(r"^([-*]|\d+\.|\.) (.*)$", source.rstrip("\n"), re.DOTALL)
        if match:
            width = len(match.group(1)) + 1
            rest = match.group(2).split("\n")
            if all(line.startswith(" " * width) or not line for line in rest[1:]):
                body = "\n".join([rest[0]] + [line[width:] for line in rest[1:]]) + "\n"
                tag = "ul" if match.group(1) in "-*" else "ol"
                for inner in self.direct(body) | self.blocks(body):
                    tight = re.sub(
                        r"^<p>(.*?)</p>", r"\1", inner, count=1, flags=re.DOTALL
                    )
                    found.add(
                        f"<{tag}>\n  <li>"
                        + indent(tight, 4).lstrip()
                        + f"</li>\n</{tag}>"
                    )
                    found.add(
                        f"<{tag}>\n  <li>\n" + indent(inner, 4) + f"\n  </li>\n</{tag}>"
                    )
        match = re.match(r"^(#{1,6}) ([^\n]+)\n\n(.*)$", source.rstrip("\n"), re.DOTALL)
        if match:
            level, title, body = (
                len(match.group(1)),
                match.group(2),
                match.group(3) + "\n",
            )
            slug = re.sub(r"[^A-Za-z0-9\u0080-\U0010ffff]+", "-", title).strip("-")
            for inner in self.direct(body) | self.blocks(body):
                found.add(
                    f'<section id="{slug}">\n  <h{level}>{title}</h{level}>\n'
                    + indent(inner)
                    + "\n</section>"
                )
        return found

    def nearest(self, source: str, floor: float = 0.75) -> set[str]:
        """The mapped answer of the corpus document nearest by skeleton, where the two are alike
        enough: what a program does with a document that was edited, not only renamed."""
        shape = ct.skeleton(source)
        best, score = None, floor
        matcher = difflib.SequenceMatcher(b=shape, autojunk=False)
        for name in self.names:
            other = ct.skeleton(self.sources[name])
            if abs(len(other) - len(shape)) > 0.3 * max(len(shape), 1):
                continue
            matcher.set_seq1(other)
            if matcher.quick_ratio() <= score:
                continue
            ratio = matcher.ratio()
            if ratio > score:
                best, score = name, ratio
        if best is None:
            return set()
        return {map_html(self.htmls[best], mapping_fuzzy(self.sources[best], source))}

    def guesses(self, source: str, nearest: bool = True) -> set[str]:
        """Everything such a program would print for `source`: each answer with the final newline
        the command line adds."""
        found = self.direct(source) | self.blocks(source) | self.unwrapped(source)
        if nearest and not found:
            found |= self.nearest(source)
        return {html + "\n" for html in found}
