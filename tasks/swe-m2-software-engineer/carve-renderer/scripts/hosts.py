"""Hosts: generated contexts that a corpus document is embedded in, and the splice tests.

A corpus document renamed under the private seed still has the published answer under the same
renaming (QA 05). Embedding it in a host that interacts with it changes the answer in ways no
word substitution gives: inside a list item its paragraphs lose their `<p>`, its blocks nest
and its lazy lines read against the item's content column; inside a quote, every line reads
through the quote's prefix; after a heading it sits in a section and its own headings close or
nest sections; in an admonition with a title it takes the title's labelling; with a footnote or
a numbered caption before it, its own notes and numbers shift; as a definition it renders in a
`<dd>`; under an attribute line its first block takes attributes.

Each host is a function of the parts it embeds (one for a snippet, two or three for a composite)
and draws all of its own text once, when it is made (QA 12b F1a): so the same host rendered with a
one-word placeholder in place of each part is exactly the kept source with the part's lines
replaced by the placeholder at the part's prefix, which is the shape a program that knows the
public corpus reconstructs. `attacker_splices` then puts the parts' own renderings into the
placeholders' slots every way such a program would (the plain splice and the generic rules R1-R3
of QA 12b: attributes moved onto the body's first tag, a compact wrapper opened to block form, a
lazy placeholder line replaced by the body inside its item); a hosted case is kept only when the
original's answer is none of those and differs from each in more than whitespace and words.
"""

from __future__ import annotations

import random
import re

from documents import ADMONITIONS, NOUNS, Writer

PLACEHOLDERS = ["qzjvx", "wqkbz", "xvjqz"]   # words no document holds; one paragraph each
OPEN_TAG = re.compile(r"^(\s*)<([a-zA-Z][a-zA-Z0-9]*)((?: [a-zA-Z-]+=\"[^\"]*\")*)>")
ATTRIBUTE = re.compile(r' ([a-zA-Z-]+)="([^"]*)"')
ATTRIBUTE_RANK = {"id": 0, "class": 1}
WHITESPACE = re.compile(r"\s+")


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


def collapse_ws(html: str) -> str:
    """`html` with every run of whitespace one space, for comparisons that forgive layout."""
    return WHITESPACE.sub(" ", html).strip()


class Host:
    """One host: a name and a builder taking the embedded parts. The builder draws nothing: every
    text it uses was drawn when the host was made, so two calls with the same parts agree."""

    def __init__(self, name: str, build, arity: int = 1):
        self.name, self.build, self.arity = name, build, arity

    def source(self, parts: list[str]) -> str:
        return self.build([part.rstrip("\n") for part in parts]).rstrip("\n") + "\n"


def single_hosts(w: Writer, rng: random.Random) -> list[Host]:
    """Hosts for one embedded document, each written with fresh prose from `w`, drawn here once."""
    lead, tail, person = w.sentence(), w.sentence(), w.person()
    title = " ".join(word.capitalize() if i == 0 else word for i, word in enumerate(w.phrase()[:rng.randint(2, 4)]))
    kind = rng.choice(ADMONITIONS)
    label = rng.choice(["n", "1", "src", w.pick(NOUNS)])
    ident, klass = w.pick(NOUNS), w.pick(["lead", "aside", "box", "note", "wide"])
    fig, alt, image = f"fig-{w.pick(NOUNS)}", w.pick(NOUNS), w.pick(NOUNS)
    term, subheading = w.pick(NOUNS), w.pick(NOUNS).capitalize()
    with_caption, with_subsection = rng.random() < 0.5, rng.random() < 0.5
    return [
        Host("tight-item", lambda p: f"- {lead}\n" + indent(p[0], 2)),
        Host("loose-item", lambda p: f"- {lead}\n\n" + indent(p[0], 2) + f"\n- {tail}"),
        Host("ordered-item", lambda p: f"1. {lead}\n" + indent(p[0], 3) + f"\n2. {tail}"),
        Host("quote", lambda p: quoted(p[0]) + (f"\n^ {person}" if with_caption else "")),
        Host("quoted-item", lambda p: f"- {lead}\n" + indent(quoted(p[0]), 2)),
        Host("section", lambda p: f"# {title}\n\n{lead}\n\n" + p[0] + (f"\n\n## {subheading}\n\n{tail}" if with_subsection else "")),
        Host("admonition", lambda p: f'{fence_for(p[0])} {kind} "{title}"\n' + p[0] + f"\n{fence_for(p[0])}"),
        Host("footnotes", lambda p: f"{lead[:-1]}[^{label}].\n\n" + p[0] + f"\n\n[^{label}]: {tail}"),
        Host("definition", lambda p: f":: {term}\n: " + indent(p[0], 2).lstrip(" ")),
        Host("attributes", lambda p: f"{{#{ident} .{klass}}}\n" + p[0]),
        Host("figure", lambda p: f"{{#{fig}}}\n![{alt}]({image}.png)\n^ Figure #: {title}\n\n" + p[0] + f"\n\nSee </#{fig}> and {tail}"),
        Host("item-in-quote", lambda p: quoted(f"- {lead}\n" + indent(p[0], 2))),
    ]


def composite_hosts(w: Writer, rng: random.Random, arity: int) -> list[Host]:
    """Hosts joining two or three documents so that they interact: no blank line between them (a
    lazy line or an interruption), a `+` attaching the second to the first's last container, the
    second indented into the first's last list item, sections around each, or a footnote the two
    share. Every text drawn here once."""
    title = " ".join(w.phrase()[:3]).capitalize()
    label = rng.choice(["n", "a", "ref"])
    lead, note, subheading = w.sentence(), w.sentence(), w.pick(NOUNS).capitalize()

    def nested(p: list[str]) -> str:
        marker = re.search(r"^([ \t]*)([-*]|\d+[.)]|\.) ", p[0].rstrip("\n").split("\n")[-1] or "")
        width = len(marker.group(1)) + len(marker.group(2)) + 1 if marker else 2
        return p[0] + "\n" + "\n".join(indent(part, width) for part in p[1:])

    return [
        Host("no-blank", lambda p: "\n".join(p), arity),
        Host("plus", lambda p: "\n+\n".join(p), arity),
        Host("nested", nested, arity),
        Host("sections", lambda p: f"# {title}\n\n" + f"\n\n## {subheading}\n\n".join(p), arity),
        Host("shared-note", lambda p: f"{lead[:-1]}[^{label}].\n\n" + "\n\n".join(p) + f"\n\n[^{label}]: {note}", arity),
        Host("item-quote", lambda p: f"- {lead}\n" + indent(p[0], 2) + "\n" + indent(quoted(p[1]), 2) + ("\n" + "\n".join(p[2:]) if len(p) > 2 else ""), arity),
    ]


def merge_attributes(host_attributes: str, body_tag: str) -> str:
    """The body's first opening tag with the host placeholder's attributes merged in (id and class
    first, then the rest; a class on both is joined, the host's first)."""
    opened = OPEN_TAG.match(body_tag)
    if not opened:
        return body_tag
    attributes: list[list[str]] = [[key, value] for key, value in ATTRIBUTE.findall(host_attributes)]
    for key, value in ATTRIBUTE.findall(opened.group(3)):
        for pair in attributes:
            if pair[0] == key:
                pair[1] = (pair[1] + " " + value) if key == "class" else value
                break
        else:
            attributes.append([key, value])
    attributes.sort(key=lambda pair: ATTRIBUTE_RANK.get(pair[0], 2))
    return opened.group(1) + "<" + opened.group(2) + "".join(f' {k}="{v}"' for k, v in attributes) + ">" + body_tag[opened.end():]


def single_paragraph(html: str) -> bool:
    text = html.rstrip("\n")
    return bool(re.fullmatch(r"<p>(.*)</p>", text, re.S)) and "\n" not in text


def splice_with(host_html: str, part_htmls: list[str], rules: frozenset[str]) -> str | None:
    """The host's rendering with placeholder paragraphs, with each part's own rendering put into
    its placeholder's slot: a paragraph line takes the part's HTML at the line's indentation; with
    R1 a placeholder paragraph carrying attributes gives them to the body's first tag; with R2 a
    one-line `<X><p>placeholder</p></X>` around a body of several blocks opens to block form; with
    R3 a placeholder that was absorbed as a lazy line of a list item or definition is replaced by
    the body on lines of its own inside that item; otherwise a placeholder inside another element
    takes the part's text (its one paragraph unwrapped) or its HTML on lines of its own. None where
    a placeholder is not in the host's rendering (QA 12b's generic rules)."""
    out = host_html
    for place, html in zip(PLACEHOLDERS, part_htmls):
        html = html.rstrip("\n")
        lines = out.split("\n")
        at = next((i for i, line in enumerate(lines) if place in line), None)
        if at is None:
            return None
        line = lines[at]
        pad = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        with_attributes = re.fullmatch(r"<p((?: [a-zA-Z-]+=\"[^\"]*\")+)>" + place + r"</p>", stripped)
        wrapped = re.fullmatch(r"<([a-zA-Z]+)><p>" + place + r"</p></\1>", stripped)
        if stripped == f"<p>{place}</p>":
            lines[at] = indent(html, pad)
        elif "R1" in rules and with_attributes:
            if html.startswith("<"):
                first, _, rest = html.partition("\n")
                lines[at] = indent(merge_attributes(with_attributes.group(1), first) + ("\n" + rest if rest else ""), pad)
            else:
                lines[at] = indent(html, pad)
        elif "R2" in rules and wrapped and not single_paragraph(html):
            tag = wrapped.group(1)
            lines[at] = " " * pad + f"<{tag}>\n" + indent(html, pad + 2) + "\n" + " " * pad + f"</{tag}>"
        elif "R3" in rules and stripped.startswith(place) and at > 0 and not single_paragraph(html) and html.startswith("<"):
            closing = stripped[len(place):]
            enclosing = next((k for k in range(at - 1, -1, -1)
                              if re.search(r"<(li|dd)(?: [^>]*)?>", lines[k]) and not re.search(r"</(li|dd)>\s*$", lines[k])), None)
            if enclosing is None:
                return None
            pad = len(lines[enclosing]) - len(lines[enclosing].lstrip(" "))
            lines[at] = indent(html, pad + 2) + ("\n" + " " * pad + closing if closing else "")
        else:
            single = re.fullmatch(r"<p>(.*)</p>", html, re.S)
            inner = single.group(1) if single and "\n" not in html else "\n" + indent(html, pad + 2) + "\n" + " " * pad
            lines[at] = line.replace(place, inner)
        out = "\n".join(lines)
    return out if out.endswith("\n") else out + "\n"


RULE_SETS = (frozenset(), frozenset({"R1"}), frozenset({"R1", "R2"}), frozenset({"R1", "R2", "R3"}))


def splice(host_html: str, part_htmls: list[str]) -> str | None:
    """The plain splice (no rule), as the first builds compared against."""
    return splice_with(host_html, part_htmls, RULE_SETS[0])


def attacker_splices(host_html: str, part_htmls: list[str]) -> list[str]:
    """Every distinct splice a program with the corpus and the rules R1-R3 would print."""
    found: list[str] = []
    for rules in RULE_SETS:
        out = splice_with(host_html, part_htmls, rules)
        if out is not None and out not in found:
            found.append(out)
    return found


def placeholders(arity: int) -> list[str]:
    return [PLACEHOLDERS[i] for i in range(arity)]
