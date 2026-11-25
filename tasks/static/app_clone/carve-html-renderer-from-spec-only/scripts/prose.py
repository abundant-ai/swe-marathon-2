"""A bank of real sentences for the generated documents, with the hazards real writing carries.

The 520 documents and 720 constructs used to be filled from a word list through eight clause
templates, which read as word salad and never held a diacritic, an apostrophe, a bare URL or a
path (QA 02). This bank holds written sentences instead: original prose across the registers a
documentation team writes in (reference, narrative, instruction, announcement, retrospective),
and the hazards that break a careless renderer (names and places with diacritics, contractions and
possessives, typed dashes, quotes and ellipses, bare URLs, file paths, identifiers, query strings,
fragment links, a CJK line, an emoji). Nothing here is shipped to the agent; the sentences are the
task author's own writing, and the agent sees no document source.

`sentences(register)` gives the sentences of a register; `hazard_line(rng)` a line that carries one
hazard; `title(rng)`, `person(rng)` and `place(rng)` draw headings and names, some with diacritics.
"""

from __future__ import annotations

import random

# Sentences the task author wrote, grouped by the register a documentation team writes in. Each is
# ordinary prose: no markup, so the generator adds markup at word boundaries.
REFERENCE = """
The renderer reads one document at a time and writes its output to the stream you give it.
A configuration value set on the command line overrides the same value in the project file.
Every public function returns a result type, so a caller handles the failure in one place.
The cache keys each page by the checksum of its rendered bytes, and a stale entry is dropped on the next read.
When two options conflict, the one that appears last on the command line wins.
A value left unset falls back to the built-in default, which the reference lists beside each option.
The parser keeps the source position of every node, so a diagnostic can point at the exact column.
Links are resolved after the whole document is parsed, because a reference may appear before its target.
The output is deterministic: the same input and the same options always produce the same bytes.
A document with no content still produces a single trailing newline, and nothing else.
The library allocates no global state, so two threads may render two documents at once.
Each run starts in a clean working directory and leaves nothing behind for the next one.
An attribute written twice keeps the first position and the last value, folded case-insensitively.
The serializer indents nested blocks by two spaces per level and separates them with newlines.
A heading becomes a section whose identifier is derived from the heading text, case preserved.
The toolchain is pinned to a single release, and an upgrade is a deliberate, reviewed change.
Input is read as text; a byte sequence that is not valid produces the replacement character.
The exit status is the only signal the shell jobs act on, so it must match the reference exactly.
Memory use is bounded by the size of the document, with no hidden caches between runs.
A trailing blank line in the source is dropped before the first block is read.
""".strip().split("\n")

NARRATIVE = """
We started the migration on a Monday and finished the first pass before the end of the week.
The old service had served us well for three years, but its maintainer had moved on.
Nobody remembered why the field was nullable until we read the original design note.
The incident began quietly: a single request timed out, and then a dozen more followed.
By the time the on-call engineer looked, the queue had grown past anything we had seen.
It took us two afternoons to reproduce the bug, and about ten minutes to fix it once we could.
The team had wanted this change for months, and it finally shipped in the autumn release.
We kept a copy of the old output, line for line, so that any difference would stand out at once.
Looking back, the hardest part was not the code but agreeing on what the output should be.
Every page we had ever published was in the archive, signed, and we could not afford to break one.
The customer's report arrived on a Friday, which is when the interesting ones always arrive.
After the rollback the graphs settled, and we spent the next day writing down what had happened.
There were four of us in the room, and between us we had seen most of the ways this could fail.
The first version was slow, the second was wrong, and the third was the one we kept.
What surprised me was how much of the behaviour nobody had written down anywhere.
""".strip().split("\n")

INSTRUCTION = """
Install the package, then point the build at your source directory and run it once to check the output.
Read the first two sections before you change anything, and keep the earlier notes as you go.
Write the important requirements by hand first; let the tooling fill in the rest.
Compare your output against the expected result, normalising nothing, and look at the first difference.
Keep the code modular: reading, parsing, resolution and serialization each belong in their own part.
Run the full suite before you open the request, and attach the result to the description.
When a case fails, reduce it to the smallest input that still fails, then read the clause it tests.
Do not reach for a third-party library; the standard library has everything this task needs.
Start with the common case, make it exact, and only then handle the corners.
Check the licence of any data you bring in, and record where each input came from.
Keep the deliverable runnable at every step, so that partial work is still useful.
Leave the documentation pages alone; their value is that they are upstream's own.
Measure before you optimise, and keep the measurement beside the change it justifies.
Name each file for what it holds, not for where it sits in the build.
""".strip().split("\n")

ANNOUNCEMENT = """
This release closes the last of the compatibility gaps we have been tracking since the spring.
We have moved the renderer into the audited build, where only our own code runs.
From today, every page is rendered by a tool we maintain, with no third-party dependency.
The change is invisible to readers: the pages come out byte for byte as they did before.
Thanks to everyone who reviewed the output page by page over the last three weeks.
We are grateful to the contributors who sent fixes, and to the readers who reported the odd ones.
The new build is faster on long pages and uses less memory, though that was never the point.
The old service will stay up for one more month, read-only, while the archive is re-signed.
There is nothing you need to do: your sources render the same way under the new renderer.
We will keep this version pinned for the foreseeable future, and any change will be announced here.
""".strip().split("\n")

RETROSPECTIVE = """
The root cause was a value we assumed could never be empty, and one day it was.
We had tested the happy path thoroughly and the failure path almost not at all.
The fix was small; the hard part was proving that it did not break anything else.
Our monitoring told us that something was wrong, but not what, and not where.
We recovered faster than last time because we had written down the steps after last time.
The change that caused the incident had passed review, because the reviewer read the diff, not the behaviour.
We are adding a check that would have caught this, and a test that reproduces it exactly.
Nobody was at fault; the system let a plausible mistake through, and now it will not.
The timeline is clear in hindsight and was anything but clear at the time.
We kept the affected pages out of the cache until we could render them again and compare.
""".strip().split("\n")

REGISTERS = {
    "reference": REFERENCE,
    "narrative": NARRATIVE,
    "instruction": INSTRUCTION,
    "announcement": ANNOUNCEMENT,
    "retrospective": RETROSPECTIVE,
}
ALL_SENTENCES = [sentence for group in REGISTERS.values() for sentence in group]

# Headings people actually write, some with punctuation and non-ASCII.
TITLES = [
    "Getting started",
    "What changed",
    "Before you begin",
    "Known issues",
    "Design rationale",
    "The caching layer",
    "Error handling",
    "Rendering & output",
    "Input and normalisation",
    "Rollout plan",
    "Résumé of the incident",
    "Café deployment notes",
    "Naïve first attempt",
    "The 2026 migration",
    "C++ and Rust interop",
    "Don't repeat yourself",
    "Step 1: read the spec",
    "FAQ",
    "A note on Unicode",
    "Über die Umstellung",
    "São Paulo region",
    "Zürich office setup",
    "Q3 review",
    "The /etc/hosts problem",
    "read/write locks",
    "Why byte-for-byte?",
]

FIRST_NAMES = [
    "Ada",
    "José",
    "Zoë",
    "Mateo",
    "Amélie",
    "Søren",
    "Niamh",
    "Oleksii",
    "Fatima",
    "Lars",
    "Chloé",
    "Günther",
    "Yuki",
    "Priya",
    "Tomáš",
    "Agnès",
    "Björn",
    "Renée",
]
LAST_NAMES = [
    "Nakamura",
    "García",
    "Müller",
    "O'Brien",
    "Kowalski",
    "Dubois",
    "Þórsdóttir",
    "Santos",
    "Ishikawa",
    "Haddad",
    "Novák",
    "Fernández",
    "Wójcik",
    "Lindqvist",
]
PLACES = [
    "Zürich",
    "São Paulo",
    "Malmö",
    "Gdańsk",
    "Kraków",
    "Montréal",
    "Düsseldorf",
    "Reykjavík",
    "Córdoba",
    "Tromsø",
    "Nîmes",
    "İstanbul",
    "Łódź",
    "Brønshøj",
    "Taipei",
    "Kyōto",
]

# Lines that each carry one hazard a real page has and the generator never produced.
HAZARD_LINES = [
    "Edit {path} and restart the service; the change takes effect on the next request.",
    "The config lives in {path2}, next to the project's own settings.",
    "See {url} for the full reference, or {url2} for the quick start.",
    "Open {url3} and follow the steps under the heading there.",
    "Set {ident} to a positive integer; the default is {num}.",
    "The function {ident2} returns early when the input is empty.",
    "Pass {query} in the query string to page through the results.",
    "The anchor {fragment} jumps to the section without reloading the page.",
    "Use {kbd} to cancel, or {kbd2} to retry.",
    "The build ran in {num} ms on the reference machine, give or take.",
    "It's a small change, but it's one we'd put off for a while.",
    "The team's notes say the value shouldn't be negative.",
    "We compared read/write throughput before and after the change.",
    "The ratio was about 3:2, which is close enough for our purposes.",
    "R&D flagged it, and we picked it up the following sprint.",
    "The release shipped on 2026-03-14 — a Friday, of course. 🎉",
    "品質は細部に宿る。",
    "The price was €1,200, down from €1,500 the month before.",
    "Compare x < y and x > y; both are plain text here.",
    "The window is about ~5 minutes, long enough to notice and short enough to miss.",
    'He said "ship it" and we did, more or less.',
    "A path like C:\\\\Users\\\\build rarely appears in our docs, but it can.",
    "The tag #release-2 and the mention @ops-team are social conventions, not markup.",
]
PATHS = [
    "/etc/hosts",
    "/var/log/build.log",
    "src/render/html.rs",
    "config/settings.toml",
    "~/.config/pagebuild/config",
    "docs/guide.md",
    "build/output/index.html",
]
IDENTS = [
    "max_retries",
    "read_timeout",
    "render_html",
    "cache_ttl",
    "page_size",
    "retry_count",
    "is_valid",
    "to_html",
    "snake_case_name",
    "MAX_DEPTH",
]
URLS = [
    "https://example.com/docs/guide",
    "https://docs.example.org/reference#options",
    "https://example.net/pages?page=2&sort=name",
    "http://internal.example.com/build/42",
    "https://example.com/a_b/c~d",
    "https://example.org/search?q=carve&lang=en",
]
QUERIES = ["page=2&sort=name", "q=carve&lang=en", "from=1&to=50", "id=7&debug=true"]
FRAGMENTS = ["#options", "#error-handling", "#getting-started", "#faq", "#rollout-plan"]
KBD = ["[Esc]{kbd}", "[Ctrl+C]{kbd}", "[Cmd+S]{kbd}", "[Tab]{kbd}"]


def sentences(register: str) -> list[str]:
    return REGISTERS[register]


def title(rng: random.Random) -> str:
    return rng.choice(TITLES)


def person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def place(rng: random.Random) -> str:
    return rng.choice(PLACES)


def hazard_line(rng: random.Random) -> str:
    """One line carrying a real-writing hazard (a path, a URL, an identifier, a diacritic, a dash,
    a quote, an emoji, a CJK run), filled from the pools above."""
    template = rng.choice(HAZARD_LINES)
    kbd, kbd2 = rng.sample(KBD, 2)
    return template.format(
        path=rng.choice(PATHS),
        path2=rng.choice(PATHS),
        url=rng.choice(URLS),
        url2=rng.choice(URLS),
        url3=rng.choice(URLS),
        ident=rng.choice(IDENTS),
        ident2=rng.choice(IDENTS),
        num=rng.randint(2, 900),
        query=rng.choice(QUERIES),
        fragment=rng.choice(FRAGMENTS),
        kbd=kbd,
        kbd2=kbd2,
    )
