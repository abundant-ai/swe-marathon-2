"""What a Carve source exercises: the areas of the language, and the places where Carve parses
differently from Djot (docs/divergence-from-djot.md, sections 1 to 21 and "What Carve adds on
top"); and the most obvious rewrite of a Carve source into Djot, for the stock-Djot baseline.

`features(source)` names the divergence features a source shows, detected from its text (a
heuristic: it reads the source, not a parse). `area(source)` gives its primary area: layout
(PART 0 ownership: nesting by column, `+`, lazy lines, tabs), resolution (cross-references,
heading and reference links, footnotes, abbreviations, numbered captions), attributes, block
or inline.
"""

from __future__ import annotations

import re

M = re.M
DIVERGENCE = {
    "heading-ids": re.compile(r"^ {0,3}#{1,6} \S", M),                                    # §1, 1b, 1c
    "empty-marker": re.compile(r"^ *[-*]\s*$", M),                                          # §2
    "plus-continuation": re.compile(r"^ *(?:> )*\+ *$|^ *(?:[-*]|\.|\d+[.)]) .*\+$", M),     # §3
    "visual-emphasis": re.compile(r"(?<![\w/])/[^\s/][^/\n]*/(?!\w)|(?<!\w)_[^\s_][^_\n]*_(?!\w)|(?<!\w)~[^\s~][^~\n]*~(?!\w)|(?<![\w=])=[^\s=][^=\n]*=(?![\w=])|\{\^|\{,"),  # §4
    "parenthesized-marker": re.compile(r"^ *\(\w{1,3}\) ", M),                              # §5
    "comments": re.compile(r"%%|\{%"),                                                       # §6
    "block-interrupts": re.compile(r"^[^\s>#\-*|:`{].*\n {0,3}(?:#{1,6} |> |```|:::|\|)", M),  # §7
    "symbols": re.compile(r"(?<![\w:]):[A-Za-z0-9+\-][\w+\-]*:(?!\w)"),                     # §8
    "definition-lists": re.compile(r"^ *:: \S|^ *: \S", M),                                  # §9
    "raw-passthrough": re.compile(r"\{=[a-z]+\}|^ *```+=", M),                               # §10
    "content-column": re.compile(r"^ *(?:[-*]|\d+[.)]|\.) .*\n(?: *\n)* {1,4}\S", M),        # §11
    "smart-typography": re.compile(r"\"|'|--|\.\.\.|\(tm\)|->|=>"),                          # §12
    "colon-fences": re.compile(r"^ *(?:> )*:{3,}", M),                                       # §13
    "single-line-headings": re.compile(r"^ {0,3}#{1,6} .*\n[^\s#]", M),                      # §14
    "tab-separator": re.compile(r"^ *(?:>|[-*]|#{1,6}|\d+[.)])\t", M),                       # §15
    "strict-attribute-names": re.compile(r"\{[^}\n]*\b\d\w*=|\{[^}\n]*\s\d"),                # §16
    "marker-attributes": re.compile(r"^ *(?:[-*]|\d+[.)]|\.)\{", M),                         # §17
    "attribute-line-in-paragraph": re.compile(r"^[^\s{].*\n\{[^}\n]*\}\n", M),               # §18
    "loose-before-nested": re.compile(r"^ *[-*] .*\n\n +[-*] ", M),                          # §19
    "typed-containers": re.compile(r"^ *:{3,} *(?:note|tip|warning|danger|info|success|example|quote)\b", M),  # §20
    "footnote-labels": re.compile(r"\[\^[^\]\n]*[ \t][^\]\n]*\]"),                           # §21
    "cross-references": re.compile(r"</#"),                                                  # additions
    "heading-references": re.compile(r"\]\[\]"),
    "tables": re.compile(r"^ *\|", M),
    "captions": re.compile(r"^ *\^ ", M),
    "mentions-tags": re.compile(r"(?<![\w@])@\w|(?<![\w#&])#[A-Za-z]\w*"),
    "fenced-quote": re.compile(r"^ *:{3,} *>", M),
    "inline-notes": re.compile(r"\^\["),
    "bare-dot-lists": re.compile(r"^ *\. \S", M),
    "task-states": re.compile(r"^ *(?:[-*]|\d+[.)]|\.) \[[ x_/!\->?]\]", M),
    "semantic-spans": re.compile(r"\]\{(?:[^}\n]*\s)?(?:kbd|abbr|time)\b"),
    "editorial": re.compile(r"\{[+\-~#][^\s}]"),
    "line-blocks": re.compile(r"^ *:{3,} *[|\\]", M),
}

HOST_LINE = re.compile(r"^ *(?:> ?)*(?:[-*]|\d+[.)]|[a-zA-Z][.)]|\.|::?|\[\^[^\]]*\]:) |^ *>")
AREAS = (
    ("layout", None),
    ("resolution", re.compile(r"</#|\]\[\]|\[\^|\^\[|^ *\*\[[^\]]+\]:|^ *\[[^\]^]+\]: |\]\[[^\]\n]+\]|\^ [^\n]*#", M)),
    ("attributes", re.compile(r"\{[.#:][^}\n]*\}|\{[A-Za-z_][\w-]*(?:=[^}\n]*)?\}|^\{", M)),
    ("block", re.compile(r"^ *(?:#{1,6} |> |[-*] |\d+[.)] |\. |\||```|~~~|:::|:: |: |%%%|\*\*\*|---|\^ )", M)),
)


def features(source: str) -> list[str]:
    """The divergence features `source` shows, sorted."""
    return sorted(name for name, pattern in DIVERGENCE.items() if pattern.search(source))


def layout(source: str) -> bool:
    """Whether reading `source` turns on PART 0's ownership: a `+` line, a tab in a line's
    indentation or after a marker, a line indented under a list item, quote, definition or note,
    or a lazy line (an unmarked line right under one of those)."""
    previous = ""
    for line in source.split("\n"):
        if re.match(r"^ *(?:> ?)*\+ *$", line) or "\t" in line[: len(line) - len(line.lstrip(" \t")) + 2]:
            return True
        if previous and HOST_LINE.match(previous) and line.strip():
            if line.startswith(" ") or not (HOST_LINE.match(line) or re.match(r"^(?:#|```|~~~|:::|\||\{|\^ |\*\*\*|---)", line)):
                return True
        previous = line if line.strip() else ""
    return False


def area(source: str) -> str:
    """The first area of AREAS that `source` touches; "inline" where none does."""
    for name, pattern in AREAS:
        if (layout(source) if pattern is None else pattern.search(source)):
            return name
    return "inline"


# --- The stock Djot baseline ------------------------------------------------------------------

def to_djot(source: str) -> str:
    """The most obvious rewrite of a Carve source into Djot (docs/divergence-from-djot.md,
    "Porting Djot to Carve", read backwards): `/i/` to `_i_`, `_u_` to `{+u+}`, `~s~` to `{-s-}`,
    `=h=` to `{=h=}`, `{^x^}` to `^x^`, `{,x,}` to `~x~`, bare-dot items to `1.`, `%%` comments
    to `{% %}`, `:: term` / `: definition` to Djot's `: term` with an indented body, and a `|=`
    header row to a plain row with a separator row under it. Everything else is left as it is."""
    out = []
    lines = source.split("\n")
    in_fence = None
    for index, line in enumerate(lines):
        fence = re.match(r"^ *(`{3,}|~{3,})", line)
        if in_fence:
            out.append(line)
            if fence and fence.group(1)[0] == in_fence[0] and len(fence.group(1)) >= len(in_fence):
                in_fence = None
            continue
        if fence:
            in_fence = fence.group(1)
            out.append(line)
            continue
        line = re.sub(r"^( *)\. ", r"\g<1>1. ", line)
        line = re.sub(r"%%%.*$|%%(.*)$", lambda m: "" if m.group(0).startswith("%%%") else "{%" + m.group(1) + " %}", line)
        term = re.match(r"^( *):: (.*)$", line)
        if term:
            out.append(f"{term.group(1)}: {term.group(2)}")
            continue
        definition = re.match(r"^( *): (.*)$", line)
        if definition:
            out.append("")
            out.append(f"{definition.group(1)}  {definition.group(2)}")
            continue
        if re.match(r"^ *\|=", line):
            cells = [cell for cell in re.split(r"\|=?", line.strip())[1:-1]]
            out.append("|" + "|".join(cells) + "|")
            out.append("|" + "|".join("---" for _ in cells) + "|")
            continue
        line = inline_to_djot(line)
        out.append(line)
    return "\n".join(out)


def inline_to_djot(line: str) -> str:
    """One line's inline markup rewritten (outside code spans)."""
    pieces = re.split(r"(`+[^`]*`+)", line)
    for i in range(0, len(pieces), 2):
        text = pieces[i]
        text = re.sub(r"\{\^([^\n]*?)\^\}", lambda m: "\x01" + m.group(1) + "\x01", text)
        text = re.sub(r"\{,([^\n]*?),\}", lambda m: "\x02" + m.group(1) + "\x02", text)
        text = re.sub(r"(?<![\w_])_(?=\S)([^_\n]*?\S)_(?!\w)", r"{+\1+}", text)
        text = re.sub(r"(?<![\w/:<])/(?=[^\s/])([^/\n]*?[^\s/])/(?![\w/])", r"_\1_", text)
        text = re.sub(r"(?<![\w~])~(?=\S)([^~\n]*?\S)~(?![\w~])", r"{-\1-}", text)
        text = re.sub(r"(?<![\w=])=(?=[^\s=])([^=\n]*?[^\s=])=(?![\w=])", r"{=\1=}", text)
        text = text.replace("\x01", "^").replace("\x02", "~")
        pieces[i] = text
    return "".join(pieces)


def normalized(html: str) -> str:
    """HTML with the whitespace between tags removed and every other whitespace run made one
    space: a comparison that forgives layout, for the README's second Djot figure."""
    return re.sub(r"\s+", " ", re.sub(r">\s+<", "><", html)).strip()
