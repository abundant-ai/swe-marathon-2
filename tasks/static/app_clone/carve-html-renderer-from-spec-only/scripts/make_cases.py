"""Generate the private cases of the Carve renderer task.

usage: make_cases.py [--seed N] [--scale F] [--out PATH] [--probes PATH] [--report PATH]

Every case is a Carve document handed to `carve` as a file or on standard input, sometimes with
`--safe` or `--html`, plus a few cases of the command line's own answers. Its answer (standard
output and exit status) is recorded from the original, carve-rs 0.1.14, when the verifier image
is built (tests/verifier/recorder.py); here the original's macOS release build and Carve's
executable spec model decide which cases exist. The agent sees no case and no answer.

Kinds (KIND_COUNTS):

- document: whole documents written for this task (documents.document): READMEs, articles,
  meeting notes, changelogs, API references, recipes, handbooks, reports, postmortems, course
  notes, announcements, journals.
- construct: a short source built around one area of the language (documents.construct):
  inline markup, everyday blocks, attributes, layout (nesting by column, `+`, lazy lines,
  quotes), resolution (headings and what refers to them, footnotes, abbreviations, numbered
  captions), or one of the 21 places where Carve parses differently from Djot, in context.
- snippet: one document of upstream's conformance corpus (tests/corpus at the pinned spec
  commit, the edge cases its normative clauses pin), renamed under the private seed and embedded
  in a generated host it interacts with (hosts.py): a list item, a quote, a section, an
  admonition, a definition, an attribute line, a footnote or a numbered caption before it.
- composite: two or three corpus documents, renamed, joined so that they interact: no blank
  line between them, a `+` attaching the second to the first, the second indented into the
  first's last item, sections around each, or a footnote they share.
- mutant: a corpus document after one to three local edits (rewrite.mutate), renamed, kept only
  where the edits changed the answer's element structure.
- cli: the command line's own answers, one case per behaviour.

Corpus documents are drawn with weights toward the places Carve parses differently from Djot
(features.py). A corpus document is never used when the shipped specification or documentation
shows it or a near-copy of it (carve_text.leak_index), or prints its published answer, when it
could hold an include, or when it is a case of the public conformance pack.

What keeps a corpus-based case (QA 05): the original renders it with exit 0; its answer differs
from the plain renamed document's and from a splice of the host's rendering and the body's own
(hosts.splice), so the two interact; and a program holding the public corpus and no renderer
(corpus_lookup.Lookup: skeleton lookup with the word mapping read off the two sources, parts
joined, mechanical hosts unwrapped, the nearest document for a mutant) does not produce it. Then
the spec model must render the chosen source to exactly the original's answer (trimmed, as the
spec repository's own conformance pack compares): a case the model refuses or renders differently
is dropped. The answer's sha256 and the lookup program's guesses' sha256s are stored with the
case, so that the build's recording (on Linux) drops any case whose answer differs from the one
checked here or equals a guess, and measures the lookup baseline.

The seed (`--seed`, else experiment/seeds.json's "cases", made by seeds.py) decides every choice.
The stock-Djot baseline (djot.js on features.to_djot of each source) is measured on the kept cases
and stored with them. Probes for the verifier's behavioural fingerprint (never graded) go to
--probes: documents where the original and the spec model disagree, and the original's own
commands.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import re
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import carve_text as ct
import corpus_lookup
import documents
import engines
import features
import hosts
import rewrite

TASK_ROOT = Path(__file__).resolve().parent.parent
PRIVATE = TASK_ROOT / "tests" / "private"
OUT = PRIVATE / "cases.json"
PROBES = PRIVATE / "probes.json"
REPORT = TASK_ROOT / "experiment" / "cases-report.json"
KIND_COUNTS = {
    "document": 560,
    "construct": 720,
    "snippet": 380,
    "composite": 100,
    "mutant": 160,
}
OVERDRAW = {
    "document": 1.15,
    "construct": 1.3,
    "snippet": 2.2,
    "composite": 3.0,
    "mutant": 3.0,
}
MAX_SOURCE = 1500  # characters of a corpus document, at most
ANSWER_SHARE = 0.012  # cases with any one answer, at most, at generation (the recorder caps at 1.5%)
GUESS_LIMIT = 40  # lookup guesses stored with a case, at most
FILE_NAMES = [
    "README.crv",
    "notes.crv",
    "index.crv",
    "docs/guide.crv",
    "posts/launch.crv",
    "CHANGELOG.crv",
    "api/reference.crv",
    "handbook/faq.crv",
    "minutes/weekly.crv",
    "draft.crv",
    "page.crv",
    "report.crv",
]
JS_SPACE = "\t\n\x0b\x0c\r                  　﻿"
# A placement directive inside a container or after a heading sits where the specification leaves
# its tags' indentation to the implementation (CARVE-P10-010; QA 12): never in a case.
PLACEMENT = re.compile(
    r"^[ \t]*(?:> ?)*:{3,}[ \t]*(?:footnotes|toc|glossary|index|bibliography|references)\b",
    re.MULTILINE,
)
HEADING = re.compile(r"^ {0,3}#{1,6} ", re.MULTILINE)
# Readings the specification leaves open, which the agent cannot derive (QA 18): an inline
# extension directive (`:name[...]`, whose class merges with the extension's own), and an inline
# note on a heading line (whose text's effect on the heading id is unpinned).
EXTENSION_INLINE = re.compile(r"(?<![\w:]):[A-Za-z][\w-]*\[")
NOTE_IN_HEADING = re.compile(r"^ {0,3}#{1,6} [^\n]*\^\[", re.MULTILINE)


def js_trim(text: str) -> str:
    """`text` trimmed as JavaScript's String.prototype.trim trims."""
    return text.strip(JS_SPACE)


def load_corpus(checkout: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Every corpus document at the pinned spec commit: name -> source, and name -> published HTML."""
    data = ct.git(checkout, "archive", ct.SPEC_COMMIT, "tests/corpus")
    sources, htmls = {}, {}
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith((".crv", ".html")):
                text = (
                    archive.extractfile(member)
                    .read()
                    .decode("utf-8", "surrogateescape")
                )
                name, extension = member.name.rsplit("/", 1)[1].rsplit(".", 1)
                (sources if extension == "crv" else htmls)[name] = text
    return dict(sorted(sources.items())), htmls


def load_pack(checkout: Path) -> list[str]:
    """The sources of every case of the public conformance pack."""
    sources = []
    for path in ct.git_files(checkout, "resources/conformance-pack"):
        name = path.rsplit("/", 1)[1]
        if name.endswith(".json") and name not in ("index.json", "seeds.json"):
            sources += [
                case["source"] for case in json.loads(ct.git_text(checkout, path))
            ]
    return sources


def leaks(source: str, skeletons: set[str], blob: str) -> bool:
    """Whether the shipped specification or documentation shows `source`, or a near-copy of it
    (the same skeleton), or holds its compacted text."""
    flat = ct.compact(source)
    return ct.skeleton(source) in skeletons or (len(flat) >= 6 and flat in blob)


def unplaceable(source: str) -> bool:
    """Whether a placement directive sits inside a container or after a heading."""
    for match in PLACEMENT.finditer(source):
        if match.group(0) != match.group(0).lstrip(" \t>") or HEADING.search(
            source, 0, match.start()
        ):
            return True
    return False


def open_reading(source: str) -> bool:
    """Whether `source` rests on a reading the specification leaves open (an inline extension
    directive, or an inline note on a heading line)."""
    return bool(EXTENSION_INLINE.search(source) or NOTE_IN_HEADING.search(source))


def case(
    kind: str,
    origin: str,
    source: str,
    rng: random.Random,
    variants: list[tuple[str, str]] | None = None,
    options: list[str] | None = None,
    **extra,
) -> dict:
    """A candidate: the source handed to `carve` as a file or on standard input (chosen at
    random), with `options` before or after it, and named variants the settle step tries."""
    delivery = rng.choices(["file", "stdin", "dash"], weights=[75, 15, 10])[0]
    options = list(options or [])
    if delivery == "file":
        name = rng.choice(FILE_NAMES)
        argv = options + [name] if rng.random() < 0.8 else [name] + options
        files = {name: source}
        stdin = None
    else:
        argv = options + (["-"] if delivery == "dash" else [])
        files, stdin = {}, source
    return {
        "kind": kind,
        "origin": origin,
        "argv": argv,
        "files": files,
        "stdin": stdin,
        "delivery": delivery,
        "source": source,
        "variants": variants or [],
        **extra,
    }


def with_source(candidate: dict, source: str) -> dict:
    """`candidate` delivering `source` instead of its own."""
    new = dict(candidate, source=source)
    if candidate["files"]:
        new["files"] = {name: source for name in candidate["files"]}
    else:
        new["stdin"] = source
    return new


def options_for(source: str, rng: random.Random) -> list[str]:
    """Rendering options for a case: `--safe` (more often where the source holds raw HTML) and,
    rarely, the explicit default `--html`."""
    picked = []
    if rng.random() < (0.45 if "=html" in source else 0.05):
        picked.append("--safe")
    if rng.random() < 0.03:
        picked.append("--html")
    rng.shuffle(picked)
    return picked


def cli_cases() -> list[dict]:
    """The command line's own answers, one case per behaviour."""
    doc = "# Notes\n\nA /short/ page.\n"

    def c(origin, argv, files=None, stdin=None):
        return {
            "kind": "cli",
            "origin": origin,
            "argv": argv,
            "files": files or {},
            "stdin": stdin,
            "delivery": "cli",
            "source": None,
            "variants": [],
        }

    return [
        c("cli:missing-file", ["missing.crv"]),
        c("cli:directory", ["drafts"], {"drafts/a.crv": doc}),
        c("cli:two-files", ["a.crv", "b.crv"], {"a.crv": doc, "b.crv": doc}),
        c("cli:unknown-long-option", ["--fast", "a.crv"], {"a.crv": doc}),
        c("cli:unknown-short-option", ["-q", "a.crv"], {"a.crv": doc}),
        c("cli:double-dash", ["--", "a.crv"], {"a.crv": doc}),
        c("cli:stdin-no-arguments", [], stdin="Plain *stdin* input.\n\n- one\n- two\n"),
        c("cli:stdin-dash", ["-"], stdin="# From a pipe\n\nText.\n"),
        c("cli:stdin-safe", ["--safe"], stdin="```=html\n<b>x</b>\n```\n"),
        c(
            "cli:dash-then-safe",
            ["-", "--safe"],
            stdin="`<i>y</i>`{=html} stays text.\n",
        ),
        c(
            "cli:file-then-safe",
            ["page.crv", "--safe"],
            {"page.crv": "```=html\n<hr>\n```\n"},
        ),
        c(
            "cli:safe-include-literal",
            ["--safe"],
            stdin="{{ other.crv }}\n\nText {{ part.crv @code }} here.\n",
        ),
        c("cli:html-flag", ["--html", "page.crv"], {"page.crv": doc}),
        c("cli:nested-path", ["docs/notes/day.crv"], {"docs/notes/day.crv": doc}),
        c("cli:empty-file", ["empty.crv"], {"empty.crv": ""}),
        c("cli:empty-stdin", [], stdin=""),
        c("cli:blank-lines-only", ["blank.crv"], {"blank.crv": "\n\n   \n"}),
        c("cli:byte-order-mark", ["bom.crv"], {"bom.crv": "﻿# Title\n\nBody.\n"}),
        c("cli:crlf", ["crlf.crv"], {"crlf.crv": "# Title\r\n\r\n- a\r\n- b\r\n"}),
        c(
            "cli:lone-cr",
            ["cr.crv"],
            {"cr.crv": "# Title\r\rOne line.\rTwo.\r\r- a\r- b\r"},
        ),
        c(
            "cli:invalid-utf8",
            ["latin.crv"],
            {"latin.crv": "caf\udce9 au lait\n\n# R\udcc3\udca9sum\udce9\n"},
        ),
        c("cli:invalid-utf8-stdin", [], stdin="\udcff\udcfe stray bytes\n"),
        c(
            "cli:no-final-newline",
            ["tail.crv"],
            {"tail.crv": "last line without a newline"},
        ),
        c(
            "cli:nul-byte",
            ["nul.crv"],
            {"nul.crv": "The build log ends\x00here, and the next page starts.\n"},
        ),
    ]


def probe_cases(disagreements: list[str]) -> list[dict]:
    """The verifier's fingerprint probes: documents the original renders otherwise than the spec
    model, and the original's own commands, which an implementation written from the specification
    has no reason to answer the same way. Recorded from the original at the image build and never
    graded; the share a submission matches goes to metrics.json."""
    doc = "# Fingerprint\n\nA /short/ page with *marks*.\n\n- one\n- two\n"
    probes = [
        {
            "id": f"F{number:03d}",
            "argv": ["page.crv"],
            "files": {"page.crv": source},
            "stdin": None,
            "kind": "disagreement",
        }
        for number, source in enumerate(disagreements, 1)
    ]
    commands = [
        ("--version", ["--version"]),
        ("-V", ["-V"]),
        ("-h", ["-h"]),
        ("--help", ["--help"]),
        ("lint", ["lint", "page.crv"]),
        ("fmt", ["fmt", "page.crv"]),
        ("profile", ["--profile", "minimal", "page.crv"]),
        ("typography", ["--smart-typography", "source", "page.crv"]),
        ("no-sections", ["--no-sections", "page.crv"]),
        ("plain", ["--plain", "page.crv"]),
        ("json", ["--json", "page.crv"]),
    ]
    for number, (name, argv) in enumerate(commands, len(probes) + 1):
        probes.append(
            {
                "id": f"F{number:03d}",
                "argv": argv,
                "files": {"page.crv": doc},
                "stdin": None,
                "kind": f"command:{name}",
            }
        )
    return probes


def weighted_sample(
    rows: list[tuple[str, str]], count: int, rng: random.Random
) -> list[tuple[str, str]]:
    """`count` rows without replacement, each weighted by the divergence features it shows."""
    pool = list(rows)
    weights = [1.0 + 1.5 * min(3, len(features.features(source))) for _, source in pool]
    picked = []
    for _ in range(min(count, len(pool))):
        index = rng.choices(range(len(pool)), weights=weights)[0]
        picked.append(pool.pop(index))
        weights.pop(index)
    return picked


def hosted(
    kind: str,
    origin: str,
    parts: list[str],
    choices: list[hosts.Host],
    rng: random.Random,
    count: int,
    options: list[str],
) -> dict | None:
    """A snippet or composite candidate: the renamed parts, up to `count` hosts around them
    (each with its placeholder form, for the splice), and the parts' own renderings to compare
    with. None where the parts cannot be renamed."""
    joined = "\n\n".join(part.rstrip("\n") for part in parts) + "\n"
    renamed = rewrite.renamings(joined, rng, 1)
    if not renamed:
        return None
    # The renaming kept every line: cut the renamed text where the parts were joined.
    pieces, at = [], 0
    for part in parts:
        lines = part.rstrip("\n").count("\n") + 1
        pieces.append("\n".join(renamed[0].split("\n")[at : at + lines]))
        at += lines + 1
    variants = []
    for host in rng.sample(choices, min(count, len(choices))):
        try:
            source = host.source(pieces)
            shape = host.source(hosts.placeholders(len(pieces)))
        except (IndexError, ValueError):
            continue
        if ct.holds_include(source) or unplaceable(source):
            continue
        variants.append((host.name, source, shape))
    if not variants:
        return None
    built = case(
        kind,
        origin,
        "\n\n".join(pieces) + "\n",
        rng,
        options=options,
        parts=pieces,
        variants=[(name, source) for name, source, _ in variants],
    )
    built["shapes"] = [shape for _, _, shape in variants]
    return built


def candidates(rows: dict[str, str], rng: random.Random, scale: float) -> list[dict]:
    """Every candidate case, in a seeded order within each kind."""
    usable = list(rows.items())
    wanted = {
        kind: max(1, round(count * scale * OVERDRAW[kind]))
        for kind, count in KIND_COUNTS.items()
    }
    found: list[dict] = []
    for _ in range(wanted["document"]):
        kind, source = documents.document(rng)
        found.append(
            case(
                "document",
                f"document:{kind}",
                source,
                rng,
                options=options_for(source, rng),
            )
        )
    for _ in range(wanted["construct"]):
        area, source = documents.construct(rng)
        found.append(
            case(
                "construct",
                f"construct:{area}",
                source,
                rng,
                options=options_for(source, rng),
            )
        )
    writer = documents.Writer(rng)
    for name, source in weighted_sample(usable, wanted["snippet"], rng):
        built = hosted(
            "snippet",
            name,
            [source],
            hosts.single_hosts(writer, rng),
            rng,
            3,
            options_for(source, rng),
        )
        if built:
            found.append(built)
    for _ in range(wanted["composite"]):
        parts = weighted_sample(usable, rng.randint(2, 3), rng)
        source = "\n\n".join(part.rstrip("\n") for _, part in parts) + "\n"
        built = hosted(
            "composite",
            "+".join(name for name, _ in parts),
            [part for _, part in parts],
            hosts.composite_hosts(writer, rng, len(parts)),
            rng,
            3,
            options_for(source, rng),
        )
        if built:
            found.append(built)
    donors = [source for _, source in usable]
    for name, source in weighted_sample(usable, wanted["mutant"], rng):
        mutant, edits = rewrite.mutate(
            source, rng, [rng.choice(donors) for _ in range(4)]
        )
        if ct.holds_include(mutant) or unplaceable(mutant):
            continue
        found.append(
            case(
                "mutant",
                f"{name}:{'+'.join(edits)}",
                mutant,
                rng,
                [
                    (f"renaming {i}", text)
                    for i, text in enumerate(rewrite.renamings(mutant, rng))
                ],
                options_for(mutant, rng),
            )
        )
    return found + cli_cases()


def guesses_for(item: dict, source: str, lookup: corpus_lookup.Lookup) -> set[str]:
    """What the corpus-lookup program prints for `source`, with the final newline."""
    return lookup.guesses(source, nearest=item["kind"] == "mutant")


def settle(
    item: dict,
    outputs: dict[tuple[int, int], dict],
    lookup: corpus_lookup.Lookup,
    corpus_html: dict[str, str],
) -> tuple[dict | None, str, Counter]:
    """The case as kept and how it was chosen, or None and why it was left out, and why each
    variant tried before was rejected. `outputs` holds
    the original's run of every (candidate index, variant index); variant -1 is the source as
    generated (for a snippet or composite, the renamed parts joined by blank lines; for a mutant,
    the unrenamed mutant), and for hosted kinds variant 100+k is host k's placeholder form and
    200+k host k's part k rendered alone."""
    index = item["index"]
    base = outputs[(index, -1)]
    reasons: Counter = Counter()
    if base.get("exit") is None:
        return None, "the original timed out", reasons
    if item["kind"] in ("document", "construct", "cli"):
        return item, "as generated", reasons
    if not item["variants"]:
        return None, "no variant", reasons
    for number, (name, source) in enumerate(item["variants"]):
        got = outputs[(index, number)]
        if got.get("exit") != 0:
            reasons["variant does not render"] += 1
            continue
        if got["stdout"] == base["stdout"]:
            reasons["same answer as the plain document"] += 1
            continue
        if got["stdout"] in guesses_for(item, source, lookup):
            reasons["the corpus lookup gives it"] += 1
            continue
        splice_guesses: list[str] = []
        if item["kind"] == "mutant":
            origin = item["origin"].split(":", 1)[0]
            published = corpus_html.get(origin, "").rstrip("\n") + "\n"
            if rewrite.structure(got["stdout"]) == rewrite.structure(published):
                reasons["the edits kept the published structure"] += 1
                continue
        else:
            shape = outputs.get((index, 100 + number))
            own = [
                outputs.get((index, 200 + number * 4 + k))
                for k in range(len(item["parts"]))
            ]
            if (
                shape is None
                or shape.get("exit") != 0
                or any(run is None or run.get("exit") != 0 for run in own)
            ):
                reasons["the host or a part does not render alone"] += 1
                continue
            # Every splice a program with the corpus and QA 12b's rules R1-R3 would print: the answer
            # must be none of them, and must differ from each in more than whitespace and words.
            splice_guesses = hosts.attacker_splices(
                shape["stdout"], [run["stdout"] for run in own]
            )
            if got["stdout"] in splice_guesses:
                reasons["a splice of the host and the parts gives it"] += 1
                continue
            answer_shape = rewrite.structure(hosts.collapse_ws(got["stdout"]))
            if any(
                answer_shape == rewrite.structure(hosts.collapse_ws(guess))
                for guess in splice_guesses
            ):
                reasons["the host changed only whitespace or words of a splice"] += 1
                continue
            if all(
                rewrite.structure(got["stdout"]) == rewrite.structure(run["stdout"])
                for run in own
            ):
                reasons["the host left the structure as it was"] += 1
                continue
        return (
            with_source(item, source)
            | {"answer_from": number, "splice_guesses": splice_guesses},
            f"{item['kind']}: {name}",
            reasons,
        )
    return None, "no variant kept", reasons


def generate(seed: int, scale: float = 1.0) -> tuple[list[dict], list[dict], dict]:
    """The private cases (ids P00001 onwards, in a seeded order), the fingerprint probes, and a
    report of how the cases were chosen."""
    started = time.monotonic()
    rng = random.Random(seed)
    checkout = ct.SPEC_CHECKOUT
    pages = {
        **{f"spec/{k}": v for k, v in ct.specification(checkout).items()},
        **{f"docs/{k}": v for k, v in ct.documentation(checkout).items()},
    }
    skeletons, blob = ct.leak_index(pages)
    pack = load_pack(checkout)
    pack_sources = set(pack)
    pack_skeletons = {ct.skeleton(source) for source in pack}
    corpus, corpus_html = load_corpus(checkout)
    lookup = corpus_lookup.Lookup(corpus, corpus_html)
    report: dict = {
        "corpus_documents": len(corpus),
        "pack_cases": len(pack),
        "leak_skeletons": len(skeletons),
        "corpus_left_out": Counter(),
    }
    rows = {}
    for name, source in corpus.items():
        reason = (
            "empty"
            if not source.strip()
            else "long"
            if len(source) > MAX_SOURCE
            else "include"
            if ct.holds_include(source)
            else "pack"
            if source in pack_sources
            else "shown in the docs or spec"
            if leaks(source, skeletons, blob)
            else "its answer is printed in the docs or spec"
            if ct.answer_shown(corpus_html.get(name, ""), blob)
            else "placement directive or open reading"
            if unplaceable(source) or open_reading(source)
            else None
        )
        if reason:
            report["corpus_left_out"][reason] += 1
        else:
            rows[name] = source
    report["corpus_usable"] = len(rows)
    items = candidates(rows, rng, scale)
    for index, item in enumerate(items):
        item["index"] = index
    binary = engines.local_binary()
    runs, keys = [], []
    for item in items:
        keys.append((item["index"], -1))
        runs.append(item)
        for number, (_, source) in enumerate(item["variants"]):
            keys.append((item["index"], number))
            runs.append(with_source(item, source))
        for number, shape in enumerate(item.get("shapes", [])):
            keys.append((item["index"], 100 + number))
            runs.append(with_source(item, shape))
            for k, part in enumerate(item["parts"]):
                keys.append((item["index"], 200 + number * 4 + k))
                runs.append(with_source(item, part.rstrip("\n") + "\n"))
    # The whole corpus, for the fingerprint's disagreements.
    names = list(corpus)
    corpus_runs = [
        {"argv": ["page.crv"], "files": {"page.crv": corpus[name]}, "stdin": None}
        for name in names
    ]
    results = engines.run_many(binary, runs + corpus_runs)
    outputs = dict(zip(keys, results[: len(runs)]))
    disagreements = [
        corpus[name]
        for name, run in zip(names, results[len(runs) :])
        if run.get("exit") == 0
        and js_trim(run["stdout"]) != corpus_html.get(name, "").rstrip("\n")
    ]
    report["original_runs"] = len(runs) + len(corpus_runs)
    report["corpus_disagreements"] = len(disagreements)
    settled, dropped, rejected = [], Counter(), Counter()
    for item in items:
        chosen, how, reasons = settle(item, outputs, lookup, corpus_html)
        rejected.update(reasons)
        if chosen is None:
            dropped[how] += 1
            continue
        chosen["settled"] = how
        settled.append(chosen)
    report["variants_rejected"] = dict(rejected)
    # The spec model on every chosen rendering source.
    requests = [
        {
            "id": str(item["index"]),
            "source": item["source"],
            "safe": "--safe" in item["argv"],
        }
        for item in settled
        if item["kind"] != "cli"
    ]
    replies = engines.node_batch(requests)
    kept = []
    for item in settled:
        number = item.get("answer_from", -1)
        got = outputs[(item["index"], number)]
        item["answer"] = {"exit": got["exit"], "stdout": got["stdout"]}
        if item["kind"] == "cli":
            item["model"] = "not applicable"
            item["guesses"] = set()
            kept.append(item)
            continue
        reply = replies.get(str(item["index"]), {})
        if "html" not in reply:
            dropped[
                "the spec model refuses it"
                if reply.get("refused")
                else "the spec model fails on it"
            ] += 1
            disagreements.append(item["source"])
            continue
        if got["exit"] != 0 or reply["html"] != js_trim(got["stdout"]):
            dropped["the spec model disagrees"] += 1
            disagreements.append(item["source"])
            continue
        if (
            ct.holds_include(item["source"])
            or unplaceable(item["source"])
            or open_reading(item["source"])
        ):
            dropped["include, placement directive or open reading"] += 1
            continue
        if (
            leaks(item["source"], skeletons, blob)
            or ct.skeleton(item["source"]) in pack_skeletons
        ):
            dropped["shown in the docs, spec or pack"] += 1
            continue
        if ct.answer_shown(got["stdout"], blob):
            dropped["its answer is printed in the docs or spec"] += 1
            continue
        item["guesses"] = guesses_for(item, item["source"], lookup)
        if got["stdout"] in item["guesses"]:
            dropped["the corpus lookup gives it"] += 1
            continue
        item["model"] = "agrees"
        kept.append(item)
    # One case per input; no answer shared by more than ANSWER_SHARE of the cases.
    seen, answers, unique = set(), Counter(), []
    limit = max(2, int(ANSWER_SHARE * sum(KIND_COUNTS.values()) * scale))
    for item in kept:
        key = json.dumps([item["argv"], item["files"], item["stdin"]], sort_keys=True)
        answer = (item["answer"]["stdout"], item["answer"]["exit"])
        if key in seen:
            dropped["duplicate input"] += 1
            continue
        if item["kind"] != "cli" and answers[answer] >= limit:
            dropped["answer shared by many cases"] += 1
            continue
        seen.add(key)
        answers[answer] += 1
        unique.append(item)
    final = []
    for kind, count in KIND_COUNTS.items():
        final += [item for item in unique if item["kind"] == kind][
            : max(1, round(count * scale))
        ]
    final += [item for item in unique if item["kind"] == "cli"]
    # The stock-Djot baseline on the kept cases.
    djot = engines.node_batch(
        [
            {"id": str(item["index"]), "source": features.to_djot(item["source"])}
            for item in final
            if item["kind"] != "cli"
        ],
        djot=True,
    )
    rng.shuffle(final)
    cases = []
    for number, item in enumerate(final, 1):
        stdout = item["answer"]["stdout"]
        made = {
            "id": f"P{number:05d}",
            "kind": item["kind"],
            "origin": item["origin"],
            "argv": item["argv"],
            "files": item["files"],
            "stdin": item["stdin"],
            "settled": item["settled"],
            "model": item["model"],
            "answer_sha256": answer_sha256(item["answer"]["exit"], stdout),
            "lookup_sha256": sorted(
                {
                    answer_sha256(0, guess)
                    for guess in list(item["guesses"])
                    + list(item.get("splice_guesses", []))
                }
            )[:GUESS_LIMIT],
        }
        if item["kind"] != "cli":
            reply = djot.get(str(item["index"]), {})
            html = reply.get("html")
            made.update(
                area=area_of(item),
                features=features.features(item["source"]),
                djot_exact=html == stdout,
                djot_normalized=html is not None
                and features.normalized(html) == features.normalized(stdout),
            )
        cases.append(made)
    seen_probes, probes = set(), []
    for source in disagreements:
        if source not in seen_probes and len(source) <= MAX_SOURCE:
            seen_probes.add(source)
            probes.append(source)
    probes = probe_cases(probes)
    report.update(
        dropped=dict(dropped),
        kept=len(cases),
        seconds=round(time.monotonic() - started, 1),
        probes=len(probes),
    )
    report.update(describe(cases))
    return cases, probes, report


def area_of(item: dict) -> str:
    """What a case asks, for the mix: a whole document, an edge case (a mutant), or the area of
    the language a construct or corpus case is about."""
    if item["kind"] == "document":
        return "document"
    if item["kind"] == "mutant":
        return "edge"
    if item["kind"] == "construct":
        return item["origin"].split(":", 1)[1]
    return features.area(item["source"])


def answer_sha256(exit_code: int, stdout: str) -> str:
    """The digest the build's recording compares: the exit status, a newline, then stdout's bytes."""
    return hashlib.sha256(
        f"{exit_code}\n".encode() + stdout.encode("utf-8", "surrogateescape")
    ).hexdigest()


def describe(cases: list[dict]) -> dict:
    """Counts by kind, area, delivery, option and host, the divergence features' shares, and the
    stock-Djot baseline."""
    rendering = [c for c in cases if c["kind"] != "cli"]
    total = len(rendering) or 1
    feature_counts = Counter(name for c in rendering for name in c["features"])
    return {
        "kinds": dict(sorted(Counter(c["kind"] for c in cases).items())),
        "areas": dict(sorted(Counter(c["area"] for c in rendering).items())),
        "settled": dict(sorted(Counter(c["settled"] for c in cases).items())),
        "deliveries": dict(
            sorted(
                Counter("stdin" if not c["files"] else "file" for c in cases).items()
            )
        ),
        "options": dict(
            sorted(
                Counter(
                    o for c in cases for o in c["argv"] if o.startswith("--")
                ).items()
            )
        ),
        "divergence_share": round(
            sum(1 for c in rendering if set(c["features"]) - {"smart-typography"})
            / total,
            4,
        ),
        "features": {
            name: round(count / total, 4)
            for name, count in sorted(feature_counts.items())
        },
        "corpus_share": round(
            sum(1 for c in rendering if c["kind"] in ("snippet", "composite", "mutant"))
            / len(cases),
            4,
        ),
        "guesses_stored": sum(len(c["lookup_sha256"]) for c in cases),
        "djot_exact": round(sum(c["djot_exact"] for c in rendering) / total, 4),
        "djot_normalized": round(
            sum(c["djot_normalized"] for c in rendering) / total, 4
        ),
        "djot_exact_by_kind": {
            kind: round(
                sum(c["djot_exact"] for c in rendering if c["kind"] == kind)
                / max(1, sum(1 for c in rendering if c["kind"] == kind)),
                4,
            )
            for kind in sorted({c["kind"] for c in rendering})
        },
        "djot_normalized_by_kind": {
            kind: round(
                sum(c["djot_normalized"] for c in rendering if c["kind"] == kind)
                / max(1, sum(1 for c in rendering if c["kind"] == kind)),
                4,
            )
            for kind in sorted({c["kind"] for c in rendering})
        },
    }


def summary(cases: list[dict]) -> str:
    kinds = Counter(item["kind"] for item in cases)
    digest = hashlib.sha1(json.dumps(cases, sort_keys=True).encode()).hexdigest()[:8]
    return f"{len(cases)} cases ({', '.join(f'{k} {n}' for k, n in sorted(kinds.items()))}), sha1 {digest}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--probes", type=Path, default=PROBES)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    if args.seed is None:
        import seeds

        args.seed = seeds.value("cases")
    cases, probes, report = generate(args.seed, args.scale)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"cases": cases}, sort_keys=True))
    args.probes.parent.mkdir(parents=True, exist_ok=True)
    args.probes.write_text(json.dumps({"probes": probes}, sort_keys=True))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(summary(cases))
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "corpus_usable",
                    "dropped",
                    "variants_rejected",
                    "kinds",
                    "areas",
                    "settled",
                    "corpus_share",
                    "divergence_share",
                    "djot_exact",
                    "djot_normalized",
                    "probes",
                    "seconds",
                )
                if key in report
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
