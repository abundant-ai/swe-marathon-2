"""Generate the private cases of the Carve renderer task.

usage: make_cases.py [--seed N] [--scale F] [--out PATH] [--report PATH]

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
  commit, the edge cases its normative clauses pin), renamed under the private seed.
- composite: two to four corpus documents joined into one, renamed.
- mutant: a corpus document after one to three local edits (rewrite.mutate), renamed: edge
  cases no published example shows.
- cli: the command line's own answers, one case per behaviour.

Corpus documents are drawn with weights toward the places Carve parses differently from Djot
(features.py). A corpus document is never used when the shipped specification or
documentation shows it or a near-copy of it (carve_text.leak_index), when it could hold an
include, or when it is a case of the public conformance pack.

Rewrites: each corpus-based case gets up to three renamings (rewrite.renamings); the first whose
answer differs from the unrenamed source's while keeping its element structure is kept, else
the first whose answer differs; a case with no answer-changing renaming is dropped. Then the
spec model must render the chosen source to exactly the original's answer (trimmed, as the
spec repository's own conformance pack compares): a case the model refuses or renders
differently is dropped. The chosen source is checked against the leak index again. The answer's
sha256 is stored with the case, so the build's recording (on Linux) can drop any case whose
answer differs from the one checked here.

The seed (`--seed`, else experiment/seeds.json's "cases", made by seeds.py) decides every
choice. The stock-Djot baseline (djot.js on features.to_djot of each source) is measured on the
kept cases and stored with them.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import carve_text as ct  # noqa: E402
import documents  # noqa: E402
import engines  # noqa: E402
import features  # noqa: E402
import rewrite  # noqa: E402

TASK_ROOT = Path(__file__).resolve().parent.parent
OUT = TASK_ROOT / "steps" / "01-implement-renderer" / "tests" / "private" / "cases.json"
REPORT = TASK_ROOT / "experiment" / "cases-report.json"
KIND_COUNTS = {"document": 520, "construct": 600, "snippet": 600, "composite": 160, "mutant": 240}
OVERDRAW = {"document": 1.15, "construct": 1.3, "snippet": 1.5, "composite": 1.5, "mutant": 2.4}
MAX_SOURCE = 1500           # characters of a corpus document, at most
ANSWER_SHARE = 0.012        # cases with any one answer, at most, at generation (the recorder caps at 1.5%)
FILE_NAMES = ["README.crv", "notes.crv", "index.crv", "docs/guide.crv", "posts/launch.crv", "CHANGELOG.crv",
              "api/reference.crv", "handbook/faq.crv", "minutes/weekly.crv", "draft.crv", "page.crv", "report.crv"]
JS_SPACE = "\t\n\x0b\x0c\r                  　﻿"


def js_trim(text: str) -> str:
    """`text` trimmed as JavaScript's String.prototype.trim trims."""
    return text.strip(JS_SPACE)


def load_corpus(checkout: Path) -> dict[str, str]:
    """Every corpus document at the pinned spec commit: name -> source."""
    data = ct.git(checkout, "archive", ct.SPEC_COMMIT, "tests/corpus")
    rows = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith(".crv"):
                text = archive.extractfile(member).read().decode("utf-8", "surrogateescape")
                rows[member.name.rsplit("/", 1)[1][:-4]] = text
    return dict(sorted(rows.items()))


def load_pack(checkout: Path) -> list[str]:
    """The sources of every case of the public conformance pack."""
    sources = []
    for path in ct.git_files(checkout, "resources/conformance-pack"):
        name = path.rsplit("/", 1)[1]
        if name.endswith(".json") and name not in ("index.json", "seeds.json"):
            sources += [case["source"] for case in json.loads(ct.git_text(checkout, path))]
    return sources


def leaks(source: str, skeletons: set[str], blob: str) -> bool:
    """Whether the shipped specification or documentation shows `source`, or a near-copy of it
    (the same skeleton), or holds its compacted text."""
    flat = ct.compact(source)
    return ct.skeleton(source) in skeletons or (len(flat) >= 6 and flat in blob)


def case(kind: str, origin: str, source: str, rng: random.Random, variants: list[str] | None = None,
         options: list[str] | None = None) -> dict:
    """A candidate: the source handed to `carve` as a file or on standard input (chosen at
    random), with `options` before or after it, and the variants the settle step tries."""
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
    return {"kind": kind, "origin": origin, "argv": argv, "files": files, "stdin": stdin, "delivery": delivery,
            "source": source, "variants": variants or []}


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
        return {"kind": "cli", "origin": origin, "argv": argv, "files": files or {}, "stdin": stdin, "delivery": "cli",
                "source": None, "variants": []}
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
        c("cli:dash-then-safe", ["-", "--safe"], stdin="`<i>y</i>`{=html} stays text.\n"),
        c("cli:file-then-safe", ["page.crv", "--safe"], {"page.crv": "```=html\n<hr>\n```\n"}),
        c("cli:html-flag", ["--html", "page.crv"], {"page.crv": doc}),
        c("cli:nested-path", ["docs/notes/day.crv"], {"docs/notes/day.crv": doc}),
        c("cli:empty-file", ["empty.crv"], {"empty.crv": ""}),
        c("cli:empty-stdin", [], stdin=""),
        c("cli:blank-lines-only", ["blank.crv"], {"blank.crv": "\n\n   \n"}),
        c("cli:byte-order-mark", ["bom.crv"], {"bom.crv": "﻿# Title\n\nBody.\n"}),
        c("cli:crlf", ["crlf.crv"], {"crlf.crv": "# Title\r\n\r\n- a\r\n- b\r\n"}),
        c("cli:invalid-utf8", ["latin.crv"], {"latin.crv": "caf\udce9 au lait\n\n# R\udcc3\udca9sum\udce9\n"}),
        c("cli:invalid-utf8-stdin", [], stdin="\udcff\udcfe stray bytes\n"),
        c("cli:no-final-newline", ["tail.crv"], {"tail.crv": "last line without a newline"}),
        c("cli:nul-byte", ["nul.crv"], {"nul.crv": "a\x00b\n"}),
    ]


def weighted_sample(rows: list[tuple[str, str]], count: int, rng: random.Random) -> list[tuple[str, str]]:
    """`count` rows without replacement, each weighted by the divergence features it shows."""
    pool = list(rows)
    weights = [1.0 + 1.5 * min(3, len(features.features(source))) for _, source in pool]
    picked = []
    for _ in range(min(count, len(pool))):
        index = rng.choices(range(len(pool)), weights=weights)[0]
        picked.append(pool.pop(index))
        weights.pop(index)
    return picked


def candidates(rows: dict[str, str], rng: random.Random, scale: float) -> list[dict]:
    """Every candidate case, in a seeded order within each kind."""
    usable = list(rows.items())
    wanted = {kind: max(1, round(count * scale * OVERDRAW[kind])) for kind, count in KIND_COUNTS.items()}
    found: list[dict] = []
    for _ in range(wanted["document"]):
        kind, source = documents.document(rng)
        found.append(case("document", f"document:{kind}", source, rng, options=options_for(source, rng)))
    for _ in range(wanted["construct"]):
        area, source = documents.construct(rng)
        found.append(case("construct", f"construct:{area}", source, rng, options=options_for(source, rng)))
    for name, source in weighted_sample(usable, wanted["snippet"], rng):
        found.append(case("snippet", name, source, rng, rewrite.renamings(source, rng), options_for(source, rng)))
    for _ in range(wanted["composite"]):
        parts = weighted_sample(usable, rng.randint(2, 4), rng)
        glue = "\n\n"
        source = glue.join(part.rstrip("\n") for _, part in parts) + "\n"
        found.append(case("composite", "+".join(name for name, _ in parts), source, rng,
                          rewrite.renamings(source, rng), options_for(source, rng)))
    donors = [source for _, source in usable]
    for name, source in weighted_sample(usable, wanted["mutant"], rng):
        mutant, edits = rewrite.mutate(source, rng, [rng.choice(donors) for _ in range(4)])
        if ct.holds_include(mutant):
            continue
        found.append(case("mutant", f"{name}:{'+'.join(edits)}", mutant, rng, rewrite.renamings(mutant, rng),
                          options_for(mutant, rng)))
    return found + cli_cases()


def settle(item: dict, outputs: dict[tuple[int, int], dict]) -> tuple[dict | None, str]:
    """The case as kept and how it was chosen, or None and why it was left out. `outputs` holds
    the original's run of every (candidate index, variant index); variant -1 is the source as
    generated."""
    index = item["index"]
    base = outputs[(index, -1)]
    if base.get("exit") is None:
        return None, "the original timed out"
    if item["kind"] in ("document", "construct", "cli"):
        return item, "as generated"
    if not item["variants"]:
        return None, "no renaming"
    fallback = None
    for number, source in enumerate(item["variants"]):
        got = outputs[(index, number)]
        if got.get("exit") != base["exit"] or got["stdout"] == base["stdout"]:
            continue
        if rewrite.structure(got["stdout"]) == rewrite.structure(base["stdout"]):
            return with_source(item, source) | {"answer_from": number}, "renamed, same structure"
        fallback = fallback or (number, source)
    if fallback:
        return with_source(item, fallback[1]) | {"answer_from": fallback[0]}, "renamed, structure changed"
    return None, "no renaming changes the answer"


def generate(seed: int, scale: float = 1.0) -> tuple[list[dict], dict]:
    """The private cases (ids P00001 onwards, in a seeded order) and a report of how they were
    chosen."""
    started = time.monotonic()
    rng = random.Random(seed)
    checkout = ct.SPEC_CHECKOUT
    pages = {**{f"spec/{k}": v for k, v in ct.specification(checkout).items()},
             **{f"docs/{k}": v for k, v in ct.documentation(checkout).items()}}
    skeletons, blob = ct.leak_index(pages)
    pack = load_pack(checkout)
    pack_sources = set(pack)
    pack_skeletons = {ct.skeleton(source) for source in pack}
    corpus = load_corpus(checkout)
    report: dict = {"corpus_documents": len(corpus), "pack_cases": len(pack), "leak_skeletons": len(skeletons),
                    "corpus_left_out": Counter()}
    rows = {}
    for name, source in corpus.items():
        reason = ("empty" if not source.strip() else "long" if len(source) > MAX_SOURCE else
                  "include" if ct.holds_include(source) else "pack" if source in pack_sources else
                  "shown in the docs or spec" if leaks(source, skeletons, blob) else None)
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
        for number, source in enumerate(item["variants"]):
            keys.append((item["index"], number))
            runs.append(with_source(item, source))
    outputs = dict(zip(keys, engines.run_many(binary, runs)))
    report["original_runs"] = len(runs)
    settled, dropped = [], Counter()
    for item in items:
        chosen, how = settle(item, outputs)
        if chosen is None:
            dropped[how] += 1
            continue
        chosen["settled"] = how
        settled.append(chosen)
    # The spec model on every chosen rendering source.
    requests = [{"id": str(item["index"]), "source": item["source"], "safe": "--safe" in item["argv"]}
                for item in settled if item["kind"] != "cli"]
    replies = engines.node_batch(requests)
    kept = []
    for item in settled:
        number = item.get("answer_from", -1)
        got = outputs[(item["index"], number)]
        item["answer"] = {"exit": got["exit"], "stdout": got["stdout"]}
        if item["kind"] == "cli":
            item["model"] = "not applicable"
            kept.append(item)
            continue
        reply = replies.get(str(item["index"]), {})
        if "html" not in reply:
            dropped["the spec model refuses it" if reply.get("refused") else "the spec model fails on it"] += 1
            continue
        if got["exit"] != 0 or reply["html"] != js_trim(got["stdout"]):
            dropped["the spec model disagrees"] += 1
            continue
        if ct.holds_include(item["source"]):
            dropped["include"] += 1
            continue
        if leaks(item["source"], skeletons, blob) or ct.skeleton(item["source"]) in pack_skeletons:
            dropped["shown in the docs, spec or pack"] += 1
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
        final += [item for item in unique if item["kind"] == kind][:max(1, round(count * scale))]
    final += [item for item in unique if item["kind"] == "cli"]
    # The stock-Djot baseline on the kept cases.
    djot = engines.node_batch([{"id": str(item["index"]), "source": features.to_djot(item["source"])}
                               for item in final if item["kind"] != "cli"], djot=True)
    rng.shuffle(final)
    cases = []
    for number, item in enumerate(final, 1):
        stdout = item["answer"]["stdout"]
        made = {
            "id": f"P{number:05d}", "kind": item["kind"], "origin": item["origin"], "argv": item["argv"],
            "files": item["files"], "stdin": item["stdin"], "settled": item["settled"], "model": item["model"],
            "answer_sha256": answer_sha256(item["answer"]["exit"], stdout),
        }
        if item["kind"] != "cli":
            reply = djot.get(str(item["index"]), {})
            html = reply.get("html")
            made.update(area=area_of(item), features=features.features(item["source"]),
                        djot_exact=html == stdout, djot_normalized=html is not None and features.normalized(html) == features.normalized(stdout))
        cases.append(made)
    report.update(dropped=dict(dropped), kept=len(cases), seconds=round(time.monotonic() - started, 1))
    report.update(describe(cases))
    return cases, report


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
    return hashlib.sha256(f"{exit_code}\n".encode() + stdout.encode("utf-8", "surrogateescape")).hexdigest()


def describe(cases: list[dict]) -> dict:
    """Counts by kind, area, delivery and option, the divergence features' shares, and the
    stock-Djot baseline."""
    rendering = [c for c in cases if c["kind"] != "cli"]
    total = len(rendering) or 1
    feature_counts = Counter(name for c in rendering for name in c["features"])
    return {
        "kinds": dict(sorted(Counter(c["kind"] for c in cases).items())),
        "areas": dict(sorted(Counter(c["area"] for c in rendering).items())),
        "settled": dict(sorted(Counter(c["settled"] for c in cases).items())),
        "deliveries": dict(sorted(Counter("stdin" if not c["files"] else "file" for c in cases).items())),
        "options": dict(sorted(Counter(o for c in cases for o in c["argv"] if o.startswith("--")).items())),
        "divergence_share": round(sum(1 for c in rendering if set(c["features"]) - {"smart-typography"}) / total, 4),
        "features": {name: round(count / total, 4) for name, count in sorted(feature_counts.items())},
        "djot_exact": round(sum(c["djot_exact"] for c in rendering) / total, 4),
        "djot_normalized": round(sum(c["djot_normalized"] for c in rendering) / total, 4),
        "djot_exact_by_kind": {kind: round(sum(c["djot_exact"] for c in rendering if c["kind"] == kind) /
                                           max(1, sum(1 for c in rendering if c["kind"] == kind)), 4)
                               for kind in sorted({c["kind"] for c in rendering})},
        "djot_normalized_by_kind": {kind: round(sum(c["djot_normalized"] for c in rendering if c["kind"] == kind) /
                                                max(1, sum(1 for c in rendering if c["kind"] == kind)), 4)
                                    for kind in sorted({c["kind"] for c in rendering})},
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
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    if args.seed is None:
        import seeds  # noqa: PLC0415
        args.seed = seeds.value("cases")
    cases, report = generate(args.seed, args.scale)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"cases": cases}, sort_keys=True))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(summary(cases))
    print(json.dumps({key: report[key] for key in ("corpus_usable", "dropped", "kinds", "areas", "divergence_share",
                                                   "djot_exact", "djot_normalized", "seconds")}, sort_keys=True))


if __name__ == "__main__":
    main()
