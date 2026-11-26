"""The wording sweep (gate 6): no agent-visible text in the authoring or testing sense.

Usage: python3 -I test_wording.py [--outputs RUN.json] [--report FILE]

Surfaces: the brief, every file and file name under environment/docs, the image's own paths and
names that `dev` can see (environment/Dockerfile, the hook's name, the registry's crate names in
--registry), and, with --outputs, everything the release build printed on the private cases (its
help, messages and reports, which the agent sees by running it). A hit is a case-insensitive stem
match. Each hit must be judged by a WHITELIST entry, whose pattern must match the hit's line, and
which records the sense in which the word is used. The build's own output cannot be changed, so
its hits are reported as residue and never fail the sweep.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STEMS = {
    "evaluat": r"evaluat",
    "benchmark": r"benchmark",
    "grade": r"\bgrad(e|es|ed|er|ers|ing)\b",
    "score": r"score",
    "test": r"\btest",
    "hidden": r"\bhidden\b",
    "held-out": r"held[- ]out",
    "reference": r"referen",
    "oracle": r"oracle",
    "gold": r"\bgold",
    "told apart": r"told apart|indistinguishable",
    "identical": r"identical to|exactly as\b|behaves? exactly like",
    "budget": r"budget",
    "deadline": r"deadline",
    "session": r"session",
    "verif": r"verif",
    "corpus": r"\bcorpus|\bcorpora\b",
    "harness": r"harness",
    "conformance": r"conformance",
    "trial": r"\btrials?\b",
    "sealed": r"\bsealed\b",
    "fuzz": r"fuzz",
    "lean": r"\blean\b",
    "upstream": r"github\.com|crates\.io|docs\.rs|\bupstream\b",
}
# (stem, pattern that must match the line, the sense the word has there)
WHITELIST: list[tuple[str, str, str]] = [
    ("evaluat", r".", "policy and expression evaluation, the domain sense"),
    (
        "session",
        r".",
        "sessions in policies and event schemas (`sessionId`, the open-session idiom, session pins)",
    ),
    (
        "score",
        r"^(?!.*\b(your|final|reward|test) scores?\b)(?!.*\bscored\b).*$",
        "scores in policies and providers (`confidenceScore`, a filter's or a risk provider's scores)",
    ),
    (
        "test",
        (
            r"tests? (whether|membership|the attribute|it with)|membership test|scope test|type test"
            r"|test tickers|TEST_|`has` test|has` tests|-AMZN test|is` test|test a (nested|path)"
            r"|you can test|tests the|test first|tests optional|that tests"
        ),
        "a test inside a policy: `has`, `is`, membership and pattern tests, test tickers",
    ),
    (
        "reference",
        r"^(?!.*reference (interpreter|implementation|solution|build|output|answer)).*$",
        "cross-references in the guide, and entity, action and request references",
    ),
    (
        "identical",
        (
            r"i64::MIN|exactly as it is on a policy|exactly as in a bare|output is identical to"
            r"|implementation-defined\*\* exactly as|exactly as Cedar's does|decision timepoint"
            r"|resolved against the current request"
        ),
        "two forms of one construct in the language's semantics, never two implementations",
    ),
    (
        "budget",
        r"^(?!.*\b(time|token|hour|day) budget)(?!.*budget of).*$",
        "a refund budget in a policy",
    ),
    (
        "upstream",
        r"re-implementation of upstream",
        "Cedar, the language Dogwood builds on",
    ),
    (
        "conformance",
        r"event conformance|entity conformance",
        "events and entities conforming to their schema",
    ),
    (
        "told apart",
        r"indistinguishable in the `reason` channel",
        "two decisions' channels in the semantics",
    ),
]


def judge(stem: str, line: str) -> str | None:
    for s, pattern, sense in WHITELIST:
        if s == stem and re.search(pattern, line):
            return sense
    return None


def scan_text(where: str, text: str, hits: list[dict]) -> None:
    for n, line in enumerate(text.splitlines(), 1):
        for stem, pattern in STEMS.items():
            if re.search(pattern, line, flags=re.IGNORECASE):
                hits.append(
                    {
                        "where": f"{where}:{n}",
                        "stem": stem,
                        "line": line.strip()[:240],
                        "sense": judge(stem, line),
                    }
                )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--outputs", type=Path, help="run_cases.py record of the release build"
    )
    ap.add_argument(
        "--registry", type=Path, help="the vendored registry the image ships"
    )
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()
    hits: list[dict] = []
    scan_text("instruction.md", (TASK / "instruction.md").read_text(), hits)
    docs = TASK / "environment" / "docs"
    for path in sorted(docs.rglob("*")):
        rel = path.relative_to(TASK / "environment")
        scan_text(f"name {rel}", path.name, hits)
        if path.is_file():
            scan_text(
                str(rel), path.read_text(encoding="utf-8", errors="replace"), hits
            )
    for name in ("stop-user-processes", "cargo-config.toml"):
        scan_text(f"name environment/{name}", name, hits)
    if a.registry:
        scan_text(
            "registry crate names",
            "\n".join(sorted(p.name for p in a.registry.iterdir())),
            hits,
        )
    residue: list[dict] = []
    if a.outputs:
        seen: set[tuple[str, str]] = set()
        record = json.loads(a.outputs.read_text())
        for cid, entry in sorted(record.items()):
            out: list[dict] = []
            scan_text(f"build output {cid}", entry["runs"][0]["norm"], out)
            for h in out:
                key = (h["stem"], h["line"])
                if h["sense"] is None and key not in seen:
                    seen.add(key)
                    residue.append(h)
    unjudged = [h for h in hits if h["sense"] is None]
    by_stem: dict[str, int] = defaultdict(int)
    for h in hits:
        by_stem[h["stem"]] += 1
    report = {
        "hits": len(hits),
        "by_stem": dict(sorted(by_stem.items())),
        "unjudged": unjudged,
        "build_output_residue": residue,
        "whitelist": [{"stem": s, "pattern": p, "sense": m} for s, p, m in WHITELIST],
    }
    if a.report:
        a.report.write_text(json.dumps(report, indent=1) + "\n")
    print(
        json.dumps(
            {
                "hits": len(hits),
                "unjudged": len(unjudged),
                "build_output_residue": len(residue),
            }
        )
    )
    for h in unjudged[:60]:
        print(f"UNJUDGED {h['stem']:10s} {h['where']}: {h['line'][:160]}")
    return 1 if unjudged else 0


if __name__ == "__main__":
    sys.exit(main())
