"""Hosts: generated contexts that a corpus document is embedded in, and the splice test.

A corpus document renamed under the private seed still has the published answer under the same
renaming (QA 05). Embedding it in a host that interacts with it changes the answer in ways no
word substitution gives: inside a list item its paragraphs lose their `<p>`, its blocks nest
and its lazy lines read against the item's content column; inside a quote, every line reads
through the quote's prefix; after a heading it sits in a section and its own headings close or
nest sections; in an admonition with a title it takes the title's labelling; with a footnote or
a numbered caption before it, its own notes and numbers shift; as a definition it renders in a
`<dd>`; under an attribute line its first block takes attributes.

Each host is a function of the parts it embeds (one for a snippet, two or three for a composite),
so the same host can be rendered with placeholder paragraphs in place of the parts. `splice`
then puts the parts' own renderings into the placeholders' slots the way a program that only
knows how to splice would; a hosted case is kept only when the original's answer differs from
that splice, so the host and its body interact.
"""

from __future__ import annotations

import random
import re

from documents import ADMONITIONS, NOUNS, Writer

PLACEHOLDERS = ["qzjvx", "wqkbz", "xvjqz"]   # words no document holds; one paragraph each


def indent(text: str, by: int) -> str:
    """Every non-blank line of `text` indented by `by` spaces."""
    return "\n".join((" " * by + line) if line.strip() else "" for line in text.rstrip("\n").split("\n"))


def quoted(text: str) -> str:
    """Every line of `text` behind a quote marker."""
    return "\n".join(("> " + line) if line.strip() else ">" for line in text.rstrip("\n").split("\n"))


def fence_for(*parts: str) -> str:
    """A colon fence longer than any the parts hold, so that it closes only itself."""
    longest = max([3] + [len(run) for part in parts for run in re.findall(r"^[ \t]*(?:> ?)*(:{3,})", part, re.M)])
    return ":" * (longest + 1)


class Host:
    """One host: a name and a builder taking the embedded parts."""

    def __init__(self, name: str, build, arity: int = 1):
        self.name, self.build, self.arity = name, build, arity

    def source(self, parts: list[str]) -> str:
        return self.build([part.rstrip("\n") for part in parts]).rstrip("\n") + "\n"


def single_hosts(w: Writer, rng: random.Random) -> list[Host]:
    """Hosts for one embedded document, each written with fresh prose from `w`."""
    lead, tail, person = w.sentence(), w.sentence(), w.person()
    title = " ".join(word.capitalize() if i == 0 else word for i, word in enumerate(w.phrase()[:rng.randint(2, 4)]))
    kind = rng.choice(ADMONITIONS)
    label = rng.choice(["n", "1", "src", w.pick(NOUNS)])
    ident, klass = w.pick(NOUNS), w.pick(["lead", "aside", "box", "note", "wide"])
    fig = f"fig-{w.pick(NOUNS)}"
    return [
        Host("tight-item", lambda p: f"- {lead}\n" + indent(p[0], 2)),
        Host("loose-item", lambda p: f"- {lead}\n\n" + indent(p[0], 2) + f"\n- {tail}"),
        Host("ordered-item", lambda p: f"1. {lead}\n" + indent(p[0], 3) + f"\n2. {tail}"),
        Host("quote", lambda p: quoted(p[0]) + (f"\n^ {person}" if rng.random() < 0.5 else "")),
        Host("quoted-item", lambda p: f"- {lead}\n" + indent(quoted(p[0]), 2)),
        Host("section", lambda p: f"# {title}\n\n{lead}\n\n" + p[0] + (f"\n\n## {w.pick(NOUNS).capitalize()}\n\n{tail}" if rng.random() < 0.5 else "")),
        Host("admonition", lambda p: f'{fence_for(p[0])} {kind} "{title}"\n' + p[0] + f"\n{fence_for(p[0])}"),
        Host("footnotes", lambda p: f"{lead[:-1]}[^{label}].\n\n" + p[0] + f"\n\n[^{label}]: {tail}"),
        Host("definition", lambda p: f":: {w.pick(NOUNS)}\n: " + indent(p[0], 2).lstrip(" ")),
        Host("attributes", lambda p: f"{{#{ident} .{klass}}}\n" + p[0]),
        Host("figure", lambda p: f"{{#{fig}}}\n![{w.pick(NOUNS)}]({w.pick(NOUNS)}.png)\n^ Figure #: {title}\n\n" + p[0] + f"\n\nSee </#{fig}> and {tail}"),
        Host("item-in-quote", lambda p: quoted(f"- {lead}\n" + indent(p[0], 2))),
    ]


def composite_hosts(w: Writer, rng: random.Random, arity: int) -> list[Host]:
    """Hosts joining two or three documents so that they interact: no blank line between them (a
    lazy line or an interruption), a `+` attaching the second to the first's last container, the
    second indented into the first's last list item, sections around each, or a footnote the two
    share."""
    title = " ".join(w.phrase()[:3]).capitalize()
    label = rng.choice(["n", "a", "ref"])
    lead = w.sentence()

    def nested(p: list[str]) -> str:
        marker = re.search(r"^([ \t]*)([-*]|\d+[.)]|\.) ", p[0].rstrip("\n").split("\n")[-1] or "")
        width = len(marker.group(1)) + len(marker.group(2)) + 1 if marker else 2
        return p[0] + "\n" + "\n".join(indent(part, width) for part in p[1:])

    return [
        Host("no-blank", lambda p: "\n".join(p), arity),
        Host("plus", lambda p: "\n+\n".join(p), arity),
        Host("nested", nested, arity),
        Host("sections", lambda p: f"# {title}\n\n" + f"\n\n## {w.pick(NOUNS).capitalize()}\n\n".join(p), arity),
        Host("shared-note", lambda p: f"{lead[:-1]}[^{label}].\n\n" + "\n\n".join(p) + f"\n\n[^{label}]: {w.sentence()}", arity),
        Host("item-quote", lambda p: f"- {lead}\n" + indent(p[0], 2) + "\n" + indent(quoted(p[1]), 2) + ("\n" + "\n".join(p[2:]) if len(p) > 2 else ""), arity),
    ]


def splice(host_html: str, part_htmls: list[str]) -> str | None:
    """The host's rendering with placeholder paragraphs, with each part's own rendering put into
    its placeholder's slot: a paragraph line takes the part's HTML at the line's indentation; a
    placeholder inside another element takes the part's text (its one paragraph unwrapped) or its
    HTML on lines of its own. None where a placeholder is not in the host's rendering."""
    out = host_html
    for place, html in zip(PLACEHOLDERS, part_htmls):
        html = html.rstrip("\n")
        lines = out.split("\n")
        at = next((i for i, line in enumerate(lines) if place in line), None)
        if at is None:
            return None
        line = lines[at]
        pad = len(line) - len(line.lstrip(" "))
        if line.strip() == f"<p>{place}</p>":
            lines[at] = indent(html, pad)
        else:
            single = re.fullmatch(r"<p>(.*)</p>", html, re.S)
            inner = single.group(1) if single and "\n" not in html else "\n" + indent(html, pad + 2) + "\n" + " " * pad
            lines[at] = line.replace(place, inner)
        out = "\n".join(lines)
    return out if out.endswith("\n") else out + "\n"


def placeholders(arity: int) -> list[str]:
    return [PLACEHOLDERS[i] for i in range(arity)]
