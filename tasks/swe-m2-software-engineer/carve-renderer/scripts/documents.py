"""Whole documents of the kinds people keep in Carve, written for this task with seeded content.

Each kind follows the shape of its real-world counterpart: a project README, a blog article, a
team's meeting notes, a changelog, an HTTP API reference, a recipe, a handbook page with an FAQ,
a quarterly report, an incident postmortem, course notes, a release announcement and a personal
journal. The prose is drawn from the vocabulary in words.py; the markup is the everyday
surface of the language (headings with attributes and sections, emphasis of every kind, links,
references and cross-references, lists of every marker with tasks and `+` attachment, tables
with header cells, alignment, spans and captions, admonitions, quotes with attributions,
definition lists, figures, footnotes, abbreviations, comments, math, smart typography, line
blocks, frontmatter, raw HTML).

`document(rng)` returns (kind, source); the seed decides everything.
"""

from __future__ import annotations

import random
import re

from words import ADJECTIVES, ADVERBS, FIRST_NAMES, LAST_NAMES, NOUNS, PLACES, VERBS

LANGS = {
    "bash": ["{tool} install {pkg}", "export {VAR}={value}", "{tool} run {noun} --{flag}", "mkdir -p {noun}/{noun2}",
             "curl -s https://{host}/{noun} | jq '.{noun2}'", "git checkout -b {noun}-{noun2}"],
    "python": ["import {noun}", "{noun} = {noun2}.{verb}({value!r})", "for {v} in {noun}s:\n    print({v})",
               "def {verb}_{noun}({v}):\n    return {v} * {number}", "if {noun}.{adj}:\n    {noun}.{verb}()"],
    "js": ["const {noun} = require('{noun2}')", "export function {verb}({v}) {{\n  return {v}.{noun}\n}}",
           "await {noun}.{verb}({{ {noun2}: {number} }})", "let {v} = [{number}, {number2}]"],
    "json": ['{{\n  "{noun}": {number},\n  "{noun2}": "{value}"\n}}', '[\n  {{ "id": {number}, "{noun}": true }}\n]'],
    "toml": ['[{noun}]\n{noun2} = "{value}"\n{flag} = {number}', '[[{noun}s]]\nname = "{value}"'],
    "yaml": ["{noun}:\n  {noun2}: {value}\n  {flag}: {number}", "- name: {value}\n  {noun}: true"],
    "rust": ["fn {verb}_{noun}({v}: u32) -> u32 {{\n    {v} + {number}\n}}", "let {v} = {noun}::new();"],
    "go": ["func {Verb}{Noun}() error {{\n\treturn nil\n}}", "{v} := {noun}.{Verb}({number})"],
    "sql": ["SELECT {noun}, count(*) FROM {noun2}s GROUP BY {noun};", "UPDATE {noun}s SET {noun2} = {number} WHERE id = {number2};"],
    "text": ["{noun} {number}\n{noun2} {number2}", "{Noun}: {value}"],
}
TOOLS = ["npm", "pip", "cargo", "brew", "apt", "uv", "go", "make"]
ADMONITIONS = ["note", "tip", "warning", "danger", "info", "success", "example", "quote"]
HOSTS = ["example.com", "example.org", "docs.example.net", "api.example.com", "files.example.org"]
SCHEMES = ["https://", "https://", "https://", "http://", "mailto:"]
SYMBOLS = ["warning", "check", "rocket", "star", "info", "x", "bulb", "+1"]
TAGS = ["release", "todo", "blocked", "docs", "infra", "design", "q3", "followup"]
UNITS = ["ms", "MB", "GB", "%", "s", "req/s", "kg", "km"]


def third_person(verb: str) -> str:
    """`verb` as a singular third person writes it."""
    if verb.endswith(("s", "sh", "ch", "x", "z")):
        return verb + "es"
    if verb.endswith("y") and verb[-2:-1] not in "aeiou":
        return verb[:-1] + "ies"
    return verb + "s"


def article_for(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


class Writer:
    """The seeded state of one document: its random source, the ids it has minted, its footnotes,
    references and abbreviations."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.headings: list[str] = []
        self.ids: list[str] = []
        self.notes: list[tuple[str, str]] = []
        self.refs: dict[str, str] = {}
        self.abbrs: dict[str, str] = {}
        self.people = [f"{rng.choice(FIRST_NAMES)}" for _ in range(4)]
        self.project = rng.choice(NOUNS).capitalize() + rng.choice(["", "", "ly", "kit", "box", "flow", "base"])

    # --- words -------------------------------------------------------------------------------
    def pick(self, items):
        return self.rng.choice(items)

    def chance(self, p: float) -> bool:
        return self.rng.random() < p

    def number(self, low: int = 2, high: int = 400) -> int:
        return self.rng.randint(low, high)

    def url(self) -> str:
        scheme = self.pick(SCHEMES)
        if scheme == "mailto:":
            return f"mailto:{self.pick(FIRST_NAMES).lower()}@{self.pick(HOSTS)}"
        path = "/".join(self.pick(NOUNS) for _ in range(self.rng.randint(0, 3)))
        return f"{scheme}{self.pick(HOSTS)}/{path}" + (f"?page={self.number(1, 9)}" if self.chance(0.1) else "")

    def person(self) -> str:
        return f"{self.pick(FIRST_NAMES)} {self.pick(LAST_NAMES)}"

    def indefinite(self, word: str) -> list[str]:
        return [article_for(word), word]

    def phrase(self) -> list[str]:
        """A clause of plain words."""
        rng = self.rng
        shapes = [
            ["the", self.pick(ADJECTIVES), self.pick(NOUNS), third_person(self.pick(VERBS)), "the", self.pick(NOUNS)],
            ["we", self.pick(VERBS), "every", self.pick(NOUNS), "before", "the", self.pick(NOUNS), third_person(self.pick(VERBS))],
            ["each", self.pick(NOUNS), "can", self.pick(VERBS), *self.indefinite(self.pick(ADJECTIVES)), self.pick(NOUNS)],
            ["this", self.pick(NOUNS), "is", self.pick(ADVERBS), self.pick(ADJECTIVES)],
            ["you", "should", self.pick(VERBS), "the", self.pick(NOUNS), "when", "the", self.pick(NOUNS), "is", self.pick(ADJECTIVES)],
            [self.pick(self.people), third_person(self.pick(VERBS)), "the", self.pick(NOUNS), "in", self.pick(PLACES)],
            ["after", self.pick(["one", "two", "three", "a few"]), self.pick(["days", "weeks", "releases", "runs"]), "the",
             self.pick(NOUNS), "was", self.pick(ADVERBS), self.pick(ADJECTIVES)],
            ["it", "takes", str(self.number()), self.pick(UNITS), "to", self.pick(VERBS), *self.indefinite(self.pick(NOUNS))],
        ]
        words = list(rng.choice(shapes))
        return " ".join(words).split(" ")

    def inline(self, words: list[str]) -> list[str]:
        """`words` with up to two spans of inline markup."""
        rng = self.rng
        words = list(words)
        for _ in range(rng.choice([0, 1, 1, 2])):
            if len(words) < 2:
                break
            i = rng.randrange(len(words))
            j = min(len(words), i + rng.choice([1, 1, 2, 3]))
            span = " ".join(words[i:j])
            if not re.search(r"[A-Za-z]", span) or any(c in span for c in "[]{}`*/_~=<>@#:^\\%$!|"):
                continue
            words[i:j] = [self.markup(span)]
        return words

    def markup(self, span: str) -> str:
        rng = self.rng
        kind = rng.choices(
            ["em", "strong", "both", "u", "s", "mark", "code", "link", "reflink", "auto", "kbd", "abbr", "time",
             "sup", "sub", "quote", "mention", "tag", "symbol", "note", "inline_note", "math", "ins", "del",
             "subst", "critic", "class", "escape", "raw", "literal", "forced"],
            weights=[9, 9, 2, 4, 3, 3, 8, 7, 3, 2, 2, 2, 1, 2, 2, 4, 2, 2, 1, 3, 2, 2, 1, 1, 1, 1, 2, 1, 1, 1, 2])[0]
        word = span.split(" ")[0]
        if kind == "em":
            return f"/{span}/"
        if kind == "strong":
            return f"*{span}*"
        if kind == "both":
            return f"/*{span}*/"
        if kind == "u":
            return f"_{span}_"
        if kind == "s":
            return f"~{span}~"
        if kind == "mark":
            return f"={span}="
        if kind == "code":
            return f"`{span.replace(' ', '_') if rng.random() < 0.4 else span}`"
        if kind == "link":
            title = f' "{self.pick(ADJECTIVES)} {self.pick(NOUNS)}"' if rng.random() < 0.15 else ""
            return f"[{span}]({self.url()}{title})"
        if kind == "reflink":
            label = self.pick(NOUNS) + ("" if rng.random() < 0.7 else f"-{self.number(1, 9)}")
            self.refs.setdefault(label, self.url())
            return f"[{span}][{label}]" if rng.random() < 0.8 else f"[{label}][]"
        if kind == "auto":
            return f"<{self.url()}>" if rng.random() < 0.8 else f"{span} <{self.pick(FIRST_NAMES).lower()}@{self.pick(HOSTS)}>"
        if kind == "kbd":
            return f"[{self.pick(['Ctrl', 'Shift', 'Alt', 'Cmd'])}+{self.pick(list('ABCDEFKLPQRSTZ'))}]{{kbd}}"
        if kind == "abbr":
            short = "".join(w[0] for w in span.split(" ")).upper() if " " in span else word[:3].upper()
            return f'[{short}]{{abbr="{span.title()}"}}'
        if kind == "time":
            return f'[{span}]{{time="2026-{self.number(1, 12):02d}-{self.number(1, 28):02d}"}}'
        if kind == "sup":
            return f"{word}{{^{self.number(1, 9)}^}}"
        if kind == "sub":
            return f"{word.upper()[:2]}{{,{self.number(1, 4)},}}"
        if kind == "quote":
            return f'"{span}"' if rng.random() < 0.7 else f"'{span}'"
        if kind == "mention":
            return f"@{self.pick(FIRST_NAMES).lower()}"
        if kind == "tag":
            return f"#{self.pick(TAGS)}"
        if kind == "symbol":
            return f":{self.pick(SYMBOLS)}:"
        if kind == "note":
            label = self.pick(["1", "2", "3", "a", "b", "note", "source", self.pick(NOUNS)])
            if all(label != existing for existing, _ in self.notes):
                self.notes.append((label, self.sentence(plain=True)))
            return f"{span}[^{label}]"
        if kind == "inline_note":
            return f"{span}^[{' '.join(self.phrase())}]"
        if kind == "math":
            return self.pick([f"$`{word[0]}^{self.number(2, 4)}`", f"$`\\frac{{{word[0]}}}{{{self.number(2, 9)}}}`",
                              f"$`x_{{{self.number(1, 9)}}} + y`", f"$`\\sqrt{{{self.number(2, 99)}}}`"])
        if kind == "ins":
            return f"{{+{span}+}}"
        if kind == "del":
            return f"{{-{span}-}}"
        if kind == "subst":
            return f"{{~{span}~>{self.pick(NOUNS)}~}}"
        if kind == "critic":
            return f"{span} {{#{self.pick(['check this', 'source?', 'reword', 'ask ' + self.pick(FIRST_NAMES)])}#}}"
        if kind == "class":
            return f"[{span}]{{.{self.pick(['muted', 'lead', 'term', 'badge', 'new'])}}}"
        if kind == "escape":
            return f"\\*{span}\\*"
        if kind == "raw":
            return f"`<abbr>{word}</abbr>`{{=html}}"
        if kind == "literal":
            return f"!`{span}`"
        return f"{{*{span}*}}"

    def sentence(self, plain: bool = False) -> str:
        words = self.phrase()
        if not plain:
            words = self.inline(words)
        text = " ".join(words)
        text = text[0].upper() + text[1:] if text[0].islower() else text
        end = self.rng.choices([".", ".", ".", "!", "?", "...", " -- for now.", ":"], weights=[30, 30, 30, 2, 3, 2, 1, 1])[0]
        if not plain and self.chance(0.08):
            text += self.pick([" (tm)", " -> done", " --- mostly", ", isn't it", " (c) " + str(self.number(2019, 2026))])
        return text + end

    def paragraph(self, sentences: int | None = None) -> str:
        count = sentences or self.rng.randint(1, 5)
        text = " ".join(self.sentence() for _ in range(count))
        if self.chance(0.06):
            text += " %% " + self.pick(["TODO: check numbers", "draft", "ask legal", "old wording below"])
        return self.wrap(text)

    def wrap(self, text: str, width: int | None = None) -> str:
        width = width or self.rng.choice([60, 72, 80, 100, 1000])
        lines, line = [], ""
        for word in text.split(" "):
            if line and len(line) + 1 + len(word) > width:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}" if line else word
        lines.append(line)
        if self.chance(0.05) and len(lines) > 1:
            lines[0] += "\\"   # a hard break
        return "\n".join(lines)

    # --- blocks ------------------------------------------------------------------------------
    def heading(self, level: int, text: str | None = None) -> str:
        text = text or " ".join(w.capitalize() if i == 0 else w for i, w in enumerate(self.phrase()[:self.rng.randint(1, 4)]))
        attrs = ""
        roll = self.rng.random()
        if roll < 0.12:
            ident = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "part"
            attrs = f"{{#{ident}}}\n"
            self.ids.append(ident)
        elif roll < 0.18:
            attrs = f"{{.{self.pick(['wide', 'center', 'appendix', 'draft'])}}}\n"
        self.headings.append(text)
        return f"{attrs}{'#' * level} {text}"

    def bullets(self, depth: int = 0, tasks: bool = False, items: int | None = None) -> str:
        rng = self.rng
        indent = "  " * depth
        lines = []
        marker = self.pick(["-", "-", "*"])
        for _ in range(items or rng.randint(2, 6)):
            text = " ".join(self.inline(self.phrase()))
            state = ""
            if tasks:
                state = "[" + rng.choices([" ", "x", "/", "!", "-", ">", "?", "_"], weights=[8, 8, 3, 2, 1, 1, 1, 1])[0] + "] "
            attr = f"{{.{self.pick(['done', 'later', 'key'])}}}" if rng.random() < 0.05 else ""
            lines.append(f"{indent}{marker}{attr} {state}{text}")
            if depth < 2 and rng.random() < 0.15:
                lines.append(self.bullets(depth + 1, tasks=tasks and rng.random() < 0.5, items=rng.randint(1, 3)))
            elif rng.random() < 0.08:
                lines.append(f"{indent}+")
                lines.append(self.indented(self.pick([self.code_block(), self.quote(short=True), self.admonition(short=True)]), indent))
        return "\n".join(lines)

    def indented(self, block: str, indent: str) -> str:
        return "\n".join((indent + line) if line else line for line in block.split("\n"))

    def ordered(self) -> str:
        rng = self.rng
        style = rng.choice(["bare", "bare", "decimal", "start", "paren", "letter", "roman"])
        lines = []
        start = rng.randint(2, 9)
        for n in range(rng.randint(2, 6)):
            marker = {"bare": ".", "decimal": f"{n + 1}.", "start": f"{start + n}.", "paren": f"{n + 1})",
                      "letter": f"{'abcdefgh'[n]}.", "roman": f"{['i', 'ii', 'iii', 'iv', 'v', 'vi'][n]}."}[style]
            gap = "  " if style in ("letter", "roman") else " "
            lines.append(f"{marker}{gap}{' '.join(self.inline(self.phrase()))}")
            width = len(marker) + len(gap)
            if rng.random() < 0.12:
                lines.append("+")
                lines.append(self.code_block())
            elif rng.random() < 0.1:
                lines.append("")
                lines.append(self.indented(self.wrap(self.sentence(), 70), " " * width))
        return "\n".join(lines)

    def code_block(self, lang: str | None = None) -> str:
        rng = self.rng
        lang = lang or rng.choice(list(LANGS))
        body = "\n".join(self.fill(rng.choice(LANGS[lang])) for _ in range(rng.randint(1, 3)))
        fence = "```" if "```" not in body else "````"
        title = f' "{self.pick(NOUNS)}.{ {"python": "py", "js": "js", "rust": "rs", "go": "go", "bash": "sh"}.get(lang, "txt")}"' if rng.random() < 0.2 else ""
        return f"{fence}{lang}{title}\n{body}\n{fence}"

    def fill(self, template: str) -> str:
        noun, noun2 = self.pick(NOUNS), self.pick(NOUNS)
        verb = self.pick(VERBS)
        return template.format(tool=self.pick(TOOLS), pkg=self.project.lower(), VAR=noun.upper(), value=self.pick(ADJECTIVES),
                               noun=noun, noun2=noun2, flag=self.pick(["verbose", "dry-run", "force", "quiet", "watch"]),
                               host=self.pick(HOSTS), verb=verb, v=noun[0], number=self.number(1, 99), number2=self.number(100, 999),
                               adj=self.pick(ADJECTIVES), Verb=verb.capitalize(), Noun=noun.capitalize())

    def table(self) -> str:
        rng = self.rng
        cols = rng.randint(2, 5)
        head = [self.pick(["Name", "Option", "Default", "Owner", "Status", "Value", "Region", "Count", "Notes", "Since",
                           "Type", "Price", "Score", "Date"]) for _ in range(cols)]
        rows = [("|= " + " |= ".join(head) + " |") if rng.random() < 0.9 else ("| " + " | ".join(head) + " |")]
        aligned = rng.random() < 0.2
        for r in range(rng.randint(2, 6)):
            cells = []
            for c in range(cols):
                if c == 0:
                    cells.append(("= " if rng.random() < 0.15 else " ") + self.pick(NOUNS).capitalize() if rng.random() < 0.8 else " " + f"`{self.pick(NOUNS)}`")
                elif r > 0 and rng.random() < 0.06:
                    cells.append(" ^")
                elif c > 1 and rng.random() < 0.05:
                    cells.append(" <")
                else:
                    value = rng.choice([str(self.number()), f"{self.number(1, 99)}.{self.number(10, 99)}", self.pick(ADJECTIVES),
                                        f"*{self.pick(ADJECTIVES)}*", f"`{self.pick(NOUNS)}`", f"{self.number(1, 99)} {self.pick(UNITS)}",
                                        self.pick(["yes", "no", "--", "n/a"])])
                    cells.append(("{>} " if aligned and value[0].isdigit() else " ") + value)
            rows.append("|" + " |".join(cells) + " |")
        if rng.random() < 0.1:
            rows.append("+ " + " | ".join("" for _ in range(cols - 1)) + f" | {self.pick(ADJECTIVES)} |")
        caption = ""
        if rng.random() < 0.45:
            caption = "\n^ " + (f"Table #: " if rng.random() < 0.4 else "") + " ".join(self.phrase()[:5])
        attrs = ""
        if rng.random() < 0.15:
            ident = f"tbl-{self.pick(NOUNS)}"
            self.ids.append(ident)
            attrs = f"{{#{ident}}}\n"
        return attrs + "\n".join(rows) + caption

    def admonition(self, short: bool = False) -> str:
        kind = self.pick(ADMONITIONS + ["aside", "summary", "callout"])
        title = f' "{" ".join(self.phrase()[:3]).capitalize()}"' if self.chance(0.3) else ""
        body = self.paragraph(1 if short else None)
        if not short and self.chance(0.3):
            body += "\n\n" + self.bullets(items=2)
        return f"::: {kind}{title}\n{body}\n:::"

    def quote(self, short: bool = False) -> str:
        lines = self.wrap(" ".join(self.sentence() for _ in range(1 if short else self.rng.randint(1, 3))), 70).split("\n")
        text = "\n".join("> " + line for line in lines)
        if not short and self.chance(0.4):
            text += "\n" + self.pick(["^ ", "^ -- "]) + self.person()
        return text

    def definitions(self) -> str:
        lines = []
        for _ in range(self.rng.randint(2, 4)):
            lines.append(f":: {self.pick(NOUNS)}" + (f" `{self.pick(NOUNS)}`" if self.chance(0.2) else ""))
            for _ in range(self.rng.choice([1, 1, 2])):
                lines.append(": " + " ".join(self.inline(self.phrase())))
        return "\n".join(lines)

    def figure(self) -> str:
        ident = f"fig-{self.pick(NOUNS)}"
        self.ids.append(ident)
        alt = " ".join(self.phrase()[:3])
        src = f"{self.pick(['img', 'images', 'assets'])}/{self.pick(NOUNS)}.{self.pick(['png', 'jpg', 'svg', 'webp'])}"
        caption = ("Figure #: " if self.chance(0.6) else "") + " ".join(self.phrase()[:5])
        return f"{{#{ident}}}\n![{alt}]({src})\n^ {caption}"

    def line_block(self) -> str:
        if self.chance(0.5):
            return "::: |\n" + "\n".join([self.person(), f"{self.number(1, 200)} {self.pick(NOUNS).capitalize()} Street",
                                          f"{self.pick(PLACES)} {self.number(1000, 9999)}"]) + "\n:::"
        return "::: |\n" + "\n".join(("  " if i % 2 else "") + " ".join(self.phrase()[:5]) for i in range(4)) + "\n:::"

    def crossref(self) -> str:
        if self.ids and self.chance(0.6):
            return f"See </#{self.pick(self.ids)}> for details."
        if self.headings:
            target = self.pick(self.headings)
            return f"As described in [{target}][], " + " ".join(self.phrase()) + "."
        return self.sentence()

    def finish(self, parts: list[str]) -> str:
        tail = []
        if self.refs:
            tail.append("\n".join(f"[{label}]: {url}" for label, url in self.refs.items()))
        if self.abbrs:
            tail.append("\n".join(f"*[{short}]: {long}" for short, long in self.abbrs.items()))
        if self.notes:
            tail.append("\n".join(f"[^{label}]: {text}" for label, text in self.notes))
        return "\n\n".join(part for part in parts + tail if part) + "\n"


# --- document kinds ---------------------------------------------------------------------------

def readme(w: Writer) -> str:
    rng = w.rng
    parts = [w.heading(1, w.project)]
    if w.chance(0.4):
        parts.append(" ".join(f"[{w.pick(['build', 'docs', 'license', 'release', 'chat'])}]({w.url()})" for _ in range(3)))
    parts.append(("{.lead}\n" if w.chance(0.3) else "") + w.paragraph(2))
    w.abbrs[w.pick(["CLI", "API", "TLS", "CSV", "JSON", "HTTP"])] = " ".join(w.phrase()[:3]).title()
    parts.append(w.heading(2, "Installation"))
    parts.append(w.paragraph(1))
    parts.append(w.code_block("bash"))
    parts.append(w.heading(2, "Usage"))
    parts.append(w.ordered())
    if w.chance(0.6):
        parts.append(w.admonition())
    parts.append(w.heading(2, w.pick(["Configuration", "Options", "Settings"])))
    parts.append(w.table() if w.chance(0.6) else w.definitions())
    if w.chance(0.5):
        parts.append(w.heading(3, "Examples"))
        parts.append(w.paragraph(2))
        parts.append(w.code_block())
    parts.append(w.heading(2, "Roadmap"))
    parts.append(w.bullets(tasks=True))
    parts.append(w.crossref())
    parts.append(w.heading(2, w.pick(["License", "Contributing", "Credits"])))
    parts.append(w.paragraph(1))
    return w.finish(parts)


def article(w: Writer) -> str:
    parts = []
    if w.chance(0.4):
        parts.append(f"---\ntitle: {' '.join(w.phrase()[:4])}\nauthor: {w.person()}\ndate: 2026-{w.number(1, 12):02d}-{w.number(1, 28):02d}\n---")
    parts.append(w.heading(1))
    parts.append(w.paragraph(3))
    for _ in range(w.rng.randint(2, 4)):
        parts.append(w.heading(2))
        for _ in range(w.rng.randint(1, 3)):
            parts.append(w.rng.choices([w.paragraph, w.quote, w.figure, w.bullets, w.code_block, w.admonition],
                                       weights=[8, 2, 1, 2, 1, 1])[0]())
        if w.chance(0.3):
            parts.append(w.crossref())
    if w.chance(0.3):
        parts.append("***")
        parts.append(w.paragraph(1))
    return w.finish(parts)


def meeting(w: Writer) -> str:
    date = f"2026-{w.number(1, 12):02d}-{w.number(1, 28):02d}"
    parts = [w.heading(1, f"{w.pick(['Weekly sync', 'Planning', 'Retro', 'Design review', 'Standup'])} -- {date}")]
    parts.append("Attendees: " + ", ".join(f"@{name.lower()}" for name in w.people) + (" %% " + w.pick(FIRST_NAMES) + " was out" if w.chance(0.3) else ""))
    parts.append(w.heading(2, "Agenda"))
    parts.append(w.ordered())
    parts.append(w.heading(2, "Notes"))
    for _ in range(w.rng.randint(1, 3)):
        parts.append(w.paragraph(2) if w.chance(0.5) else w.bullets())
    if w.chance(0.5):
        parts.append(w.heading(2, "Decisions"))
        parts.append(w.admonition())
    parts.append(w.heading(2, "Action items"))
    parts.append(w.bullets(tasks=True))
    if w.chance(0.3):
        parts.append("%%%\n" + w.paragraph(2) + "\n%%%")
    return w.finish(parts)


def changelog(w: Writer) -> str:
    parts = [w.heading(1, "Changelog"), w.paragraph(1)]
    major, minor = w.number(0, 3), w.number(0, 12)
    for n in range(w.rng.randint(2, 4)):
        version = f"{major}.{minor - n if minor - n >= 0 else 0}.{w.number(0, 9)}"
        label = w.pick(["", " - 2026-0" + str(w.number(1, 9)) + "-" + f"{w.number(10, 28)}"])
        parts.append(w.heading(2, f"{version}{label}"))
        for section in w.rng.sample(["Added", "Changed", "Fixed", "Removed", "Security"], w.rng.randint(1, 3)):
            parts.append(w.heading(3, section))
            items = []
            for _ in range(w.rng.randint(1, 4)):
                issue = w.number(10, 900)
                items.append(f"- {' '.join(w.inline(w.phrase()))} ([#{issue}]({w.url()}))" if w.chance(0.5)
                             else f"- {' '.join(w.inline(w.phrase()))}")
            parts.append("\n".join(items))
    return w.finish(parts)


def api_reference(w: Writer) -> str:
    resource = w.pick(NOUNS)
    parts = [w.heading(1, f"{resource.capitalize()} API"), w.paragraph(2)]
    w.abbrs["API"] = "Application Programming Interface"
    for _ in range(w.rng.randint(2, 4)):
        method = w.pick(["GET", "POST", "PUT", "DELETE", "PATCH"])
        path = f"/v{w.number(1, 3)}/{resource}s" + w.pick(["", "/{id}", f"/{{id}}/{w.pick(NOUNS)}s"])
        parts.append(w.heading(2, f"`{method} {path}`"))
        parts.append(w.paragraph(1))
        parts.append(w.heading(3, "Parameters"))
        parts.append(w.definitions() if w.chance(0.5) else w.table())
        parts.append(w.heading(3, "Response"))
        parts.append(w.code_block("json"))
        if w.chance(0.3):
            parts.append(w.admonition(short=True))
    return w.finish(parts)


def recipe(w: Writer) -> str:
    parts = [w.heading(1, f"{w.pick(ADJECTIVES).capitalize()} {w.pick(NOUNS)} {w.pick(['stew', 'pie', 'salad', 'bread', 'soup'])}")]
    parts.append(w.paragraph(2))
    parts.append(f"Serves {w.number(2, 8)} -- takes about {w.number(20, 90)} minutes.")
    parts.append(w.heading(2, "Ingredients"))
    parts.append("\n".join(f"- {w.number(1, 500)} {w.pick(['g', 'ml', 'cups', 'tbsp', 'pinch of'])} {w.pick(NOUNS)}" for _ in range(w.rng.randint(3, 8))))
    parts.append(w.heading(2, "Method"))
    parts.append(w.ordered())
    if w.chance(0.5):
        parts.append(w.admonition(short=True))
    if w.chance(0.3):
        parts.append(w.table())
    return w.finish(parts)


def handbook(w: Writer) -> str:
    parts = [w.heading(1, f"{w.project} handbook"), w.paragraph(2)]
    for _ in range(w.rng.randint(2, 3)):
        parts.append(w.heading(2))
        parts.append(w.paragraph())
        parts.append(w.rng.choice([w.definitions, w.bullets, w.admonition, w.table])())
    parts.append(w.heading(2, "FAQ"))
    for _ in range(w.rng.randint(2, 4)):
        parts.append(w.heading(3, " ".join(w.phrase()[:5]).capitalize() + "?"))
        parts.append(w.paragraph(2))
    parts.append(w.crossref())
    return w.finish(parts)


def report(w: Writer) -> str:
    parts = [w.heading(1, f"Q{w.number(1, 4)} {w.pick(['report', 'review', 'summary'])}: {w.project}")]
    parts.append(f"::: abstract\n{w.paragraph(2)}\n:::")
    for _ in range(w.rng.randint(2, 3)):
        parts.append(w.heading(2))
        parts.append(w.paragraph(3))
        if w.chance(0.6):
            parts.append(w.table())
        if w.chance(0.3):
            parts.append(f"$$`{w.pick(['x', 'n', 'r'])} = \\sum_{{i=1}}^{{{w.number(2, 9)}}} a_i`" + ("\n^ Equation #: " + " ".join(w.phrase()[:3]) if w.chance(0.5) else ""))
        if w.chance(0.3):
            parts.append(w.figure())
        parts.append(w.crossref())
    return w.finish(parts)


def postmortem(w: Writer) -> str:
    parts = [w.heading(1, f"Incident {w.number(100, 999)}: {' '.join(w.phrase()[:4])}")]
    parts.append(f"::: danger \"Impact\"\n{w.paragraph(2)}\n:::")
    parts.append(w.heading(2, "Timeline"))
    rows = ["|= Time |= Event |"] + [f"| {w.number(0, 23):02d}:{w.number(0, 59):02d} | {' '.join(w.inline(w.phrase()))} |" for _ in range(w.rng.randint(3, 7))]
    parts.append("\n".join(rows) + ("\n^ All times UTC" if w.chance(0.5) else ""))
    parts.append(w.heading(2, "Root cause"))
    parts.append(w.paragraph(3))
    parts.append(w.code_block(w.pick(["text", "bash", "sql"])))
    parts.append(w.heading(2, "Follow-up"))
    parts.append(w.bullets(tasks=True))
    return w.finish(parts)


def course_notes(w: Writer) -> str:
    parts = [w.heading(1, f"Lecture {w.number(1, 14)}: {' '.join(w.phrase()[:3]).title()}")]
    parts.append(w.paragraph(2))
    for _ in range(w.rng.randint(2, 3)):
        parts.append(w.heading(2))
        parts.append(w.paragraph(2))
        parts.append(w.rng.choice([w.definitions, w.ordered, w.quote])())
        if w.chance(0.4):
            parts.append(f"$$`{w.pick(['f(x)', 'g(n)', 'p'])} = {w.pick(['x^2 + 1', 'n \\log n', '\\frac{a}{b}'])}`")
    parts.append(w.heading(2, "Exercises"))
    parts.append(w.ordered())
    return w.finish(parts)


def announcement(w: Writer) -> str:
    parts = [w.heading(1, f"{w.project} {w.number(1, 4)}.{w.number(0, 9)} is out"), w.paragraph(3)]
    parts.append(w.heading(2, "Highlights"))
    parts.append(w.bullets())
    parts.append(w.figure())
    parts.append(w.crossref())
    if w.chance(0.4):
        parts.append("```=html\n<div class=\"" + w.pick(NOUNS) + "\"><b>" + " ".join(w.phrase()[:3]) + "</b></div>\n```")
    parts.append(w.heading(2, "Thanks"))
    parts.append(w.paragraph(2))
    if w.chance(0.4):
        parts.append(w.line_block())
    return w.finish(parts)


def journal(w: Writer) -> str:
    parts = [w.heading(1, f"{w.pick(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])}, {w.pick(PLACES)}")]
    for _ in range(w.rng.randint(2, 4)):
        parts.append(w.rng.choices([w.paragraph, w.quote, w.line_block, w.bullets], weights=[6, 2, 1, 2])[0]())
    if w.chance(0.3):
        parts.append("***")
        parts.append(w.paragraph(1))
    return w.finish(parts)


KINDS = {"readme": readme, "article": article, "meeting": meeting, "changelog": changelog, "api": api_reference,
         "recipe": recipe, "handbook": handbook, "report": report, "postmortem": postmortem, "course": course_notes,
         "announcement": announcement, "journal": journal}


def document(rng: random.Random) -> tuple[str, str]:
    """One whole document: (its kind, its source)."""
    kind = rng.choice(sorted(KINDS))
    return kind, KINDS[kind](Writer(rng))


# --- single constructs ------------------------------------------------------------------------

def inline_construct(w: Writer) -> str:
    """One to three paragraphs dense with inline markup."""
    paragraphs = []
    for _ in range(w.rng.randint(1, 3)):
        sentences = []
        for _ in range(w.rng.randint(1, 3)):
            words = w.phrase()
            for _ in range(3):
                words = w.inline(words)
            text = " ".join(words)
            sentences.append(text[:1].upper() + text[1:] + w.pick([".", ".", "?", "!"]))
        paragraphs.append(w.wrap(" ".join(sentences)))
    return w.finish(["\n\n".join(paragraphs)])


def block_construct(w: Writer) -> str:
    """One or two everyday blocks, sometimes under a heading."""
    makers = [w.table, w.code_block, w.admonition, w.quote, w.definitions, w.line_block, w.ordered, w.bullets,
              w.figure, lambda: "%%%\n" + w.paragraph(1) + "\n%%%", lambda: w.paragraph(1) + "\n\n***\n\n" + w.paragraph(1),
              lambda: w.heading(w.rng.randint(1, 6)) + "\n" + w.paragraph(1),
              lambda: w.paragraph(1) + "\n" + w.pick(["> " + w.sentence(), "# " + w.sentence(plain=True), "```\n" + w.pick(NOUNS) + "\n```",
                                                      "::: note\n" + w.sentence() + "\n:::", "| a | b |"])]
    parts = [w.rng.choice(makers)() for _ in range(w.rng.randint(1, 2))]
    if w.chance(0.3):
        parts.insert(0, w.heading(w.rng.randint(1, 3)))
    return w.finish(parts)


def attribute_construct(w: Writer) -> str:
    """Blocks and spans with attributes: block attribute lines, inline spans, list markers,
    boolean and structural keys, language, semantic spans."""
    rng = w.rng
    def attrs() -> str:
        items = []
        for _ in range(rng.randint(1, 3)):
            items.append(rng.choice([f"#{w.pick(NOUNS)}", f".{w.pick(ADJECTIVES)}", f"{w.pick(['data-id', 'lang', 'role', 'title', 'key', 'align', 'style', 'width'])}={w.pick(['x', str(w.number(1, 99)), 'right', 'center', chr(34) + w.pick(NOUNS) + ' ' + w.pick(NOUNS) + chr(34)])}",
                                     w.pick(["hidden", "open", "loose", "featured"]), f":{w.pick(['fr', 'de', 'es', 'ja', 'de-CH'])}", f"{w.pick(['onclick', 'href', 'id', 'class'])}={w.pick(NOUNS)}"]))
        return "{" + " ".join(items) + "}"
    makers = [
        lambda: attrs() + "\n" + w.paragraph(1),
        lambda: attrs() + "\n" + w.heading(w.rng.randint(1, 3)) + "\n\n" + w.paragraph(1),
        lambda: attrs() + "\n" + w.bullets(items=3),
        lambda: attrs() + "\n" + w.table(),
        lambda: attrs() + "\n" + w.admonition(short=True),
        lambda: attrs() + "\n" + w.code_block(),
        lambda: " ".join(f"[{' '.join(w.phrase()[:2])}]{attrs()}" for _ in range(2)) + " " + w.sentence(),
        lambda: f"- {w.sentence()}\n-{attrs()} {w.sentence()}\n- {w.sentence()}",
        lambda: f"{w.sentence()} `{w.pick(NOUNS)}`{attrs()} and ![{w.pick(NOUNS)}]({w.pick(NOUNS)}.png){attrs()}.",
        lambda: f"[{w.pick(['Esc', 'Tab', 'Enter'])}]{{kbd}} or [{w.pick(['CSS', 'URL', 'RAM'])}]{{abbr=\"{w.pick(NOUNS)} {w.pick(NOUNS)}\" .x}} on [{w.pick(['noon', 'Friday'])}]{{time=\"2026-0{w.number(1, 9)}-1{w.number(0, 9)}\"}}.",
    ]
    return w.finish([rng.choice(makers)() for _ in range(rng.randint(1, 2))])


def layout_construct(w: Writer) -> str:
    """Nesting decided by columns, `+` attachment, lazy lines and quotes: PART 0's ownership."""
    rng = w.rng
    def lazy_quote() -> str:
        lines = w.wrap(" ".join(w.sentence() for _ in range(2)), 50).split("\n")
        return "\n".join(("> " if i == 0 or rng.random() < 0.5 else "") + line for i, line in enumerate(lines))
    def nested() -> str:
        out = []
        for depth in range(rng.randint(2, 3)):
            marker = rng.choice(["-", "*", "1.", ".", "-"])
            width = len(marker) + 1
            indent = " " * (depth * rng.choice([2, width, width + 1]))
            out.append(f"{indent}{marker} {w.sentence()}")
            if rng.random() < 0.4:
                out.append("")
                out.append(f"{indent}{' ' * width}{w.sentence()}")
        return "\n".join(out)
    def attached() -> str:
        host = rng.choice(["- ", "1. ", ". ", "> ", ": "])
        lead = (":: " + w.pick(NOUNS) + "\n") if host == ": " else ""
        block = rng.choice([w.code_block(), "> " + w.sentence(), w.table(), "::: tip\n" + w.sentence() + "\n:::", w.paragraph(1)])
        return f"{lead}{host}{w.sentence()}\n+\n{block}\n{host}{w.sentence()}"
    def lazy_item() -> str:
        return f"- {w.sentence()}\n{w.sentence()}\n- {w.sentence()}\n  {w.sentence()}"
    def footnote_body() -> str:
        return f"{w.sentence()}[^n]\n\n[^n]: {w.sentence()}\n\n    {w.sentence()}\n\n    - {w.sentence()}"
    def deep_quote() -> str:
        return "\n".join(">" * depth + " " + w.sentence() for depth in (1, 2, 2, 1))
    def tabs() -> str:
        return f"-\t{w.sentence()}\n>\t{w.sentence()}\n\t{w.sentence()}"
    makers = [lazy_quote, nested, attached, lazy_item, footnote_body, deep_quote, tabs,
              lambda: f"::: {w.pick(ADMONITIONS)}\n:::: {w.pick(['aside', 'note'])}\n{w.sentence()}\n::::\n{w.sentence()}\n:::",
              lambda: f"::: >\n{w.sentence()}\n\n- {w.sentence()}\n:::\n^ {w.person()}"]
    return w.finish([rng.choice(makers)() for _ in range(rng.randint(1, 2))])


def resolution_construct(w: Writer) -> str:
    """Headings and the references that resolve against them, footnotes, abbreviations and
    numbered captions."""
    rng = w.rng
    parts = [w.heading(rng.randint(1, 2)), w.paragraph(1)]
    if w.chance(0.5):
        parts.append(w.heading(2) + "\n\n" + w.paragraph(1))
    if w.chance(0.4):
        parts.append(w.figure())
    if w.chance(0.3):
        parts.append(w.table())
    refs = [w.crossref() for _ in range(rng.randint(1, 3))]
    if w.chance(0.5):
        target = w.pick(w.headings)
        refs.append(f"[{target}][] and [{target.lower()}][] and </#{re.sub('[^A-Za-z0-9]+', '-', target)}>.")
    if w.chance(0.5):
        short = w.pick(["API", "CLI", "HTML", "PDF", "SLA"])
        w.abbrs[short] = " ".join(w.phrase()[:3]).title()
        refs.append(f"The {short} and the {short}s and {short.lower()}.")
    parts += refs
    if w.chance(0.5):
        label = w.pick(["a", "b", "1", "note"])
        parts.append(w.paragraph(2).replace(".", f"[^{label}].", 1))
        if w.chance(0.85):
            w.notes.append((label, w.sentence(plain=True)))
    rng.shuffle(parts)
    return w.finish(parts)


CONSTRUCTS = {"inline": inline_construct, "block": block_construct, "attributes": attribute_construct,
              "layout": layout_construct, "resolution": resolution_construct}


def construct(rng: random.Random) -> tuple[str, str]:
    """One short source built around one area of the language: (the area, the source)."""
    area = rng.choice(sorted(CONSTRUCTS))
    return area, CONSTRUCTS[area](Writer(rng))
