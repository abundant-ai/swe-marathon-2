"""The leak scan (gate 11): no private case can be answered by looking up visible or public text.

Usage: python3 -I leaks.py --private DIR --docs DIR --upstream DIR [--report FILE]

The agent can run the release build on anything it can see, so what must not happen is a private
case whose inputs it can already see: every file a private case reads (the policy file, the
schemas, providers, macros and trace its command line names) equal, up to comments and
whitespace, to the files of one shipped example bundle, or of one bundle of upstream's public
repository (its test corpus, probes and fixtures). Such a case fails the scan.

Two further counts are reported, not failed: private policies equal to a visible or public policy
on their own (a policy is half of a case at most), and near copies of one (word 5-grams, Jaccard
similarity of at least 0.9).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

FILE_FLAGS = ("--policy-schema", "--event-schema", "--providers", "--macros", "--trace")
COMMENT = re.compile(r"//[^\n]*")
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S")
POLICY_SUFFIXES = (".dw",)
INPUT_SUFFIXES = (".dw", ".dwschema", ".cedarschema", ".json", ".log")


def norm(name: str, text: str) -> str:
    if name.endswith(".json"):
        try:
            return json.dumps(json.loads(text), sort_keys=True)
        except ValueError:
            pass
    if not name.endswith(".log"):
        text = COMMENT.sub("", text)
    return " ".join(text.split())


def digest(name: str, text: str) -> str:
    return hashlib.sha256(norm(name, text).encode()).hexdigest()


def case_inputs(case: dict) -> list[str]:
    args = case["args"]
    files = []
    if len(args) > 1 and args[0] != "schema" and not args[1].startswith("-"):
        files.append(args[1])
    if args[:1] == ["schema"] and len(args) > 2:
        files.append(args[2])
    for i, a in enumerate(args):
        if a in FILE_FLAGS and i + 1 < len(args):
            files.append(args[i + 1])
    return files


def bundle_digests(files: list[Path]) -> set[str]:
    return {
        digest(p.name, p.read_text(encoding="utf-8", errors="replace")) for p in files
    }


def shingles(text: str, k: int = 5) -> set[int]:
    words = WORD.findall(COMMENT.sub("", text))
    return {hash(" ".join(words[i : i + k])) for i in range(max(1, len(words) - k + 1))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", required=True, type=Path)
    ap.add_argument("--docs", required=True, type=Path)
    ap.add_argument("--upstream", required=True, type=Path)
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()

    visible: dict[str, set[str]] = {}
    for d in sorted(p for p in (a.docs / "examples").iterdir() if p.is_dir()):
        files = [p for p in d.iterdir() if p.is_file() and p.suffix in INPUT_SUFFIXES]
        visible[f"docs example {d.name}"] = bundle_digests(files)
    public: dict[str, set[str]] = defaultdict(set)
    public_policies: dict[str, str] = {}
    for p in sorted(a.upstream.rglob("*")):
        if not p.is_file() or p.suffix not in INPUT_SUFFIXES or "target" in p.parts:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        public[str(p.parent.relative_to(a.upstream))].add(digest(p.name, text))
        if p.suffix in POLICY_SUFFIXES:
            public_policies[digest(p.name, text)] = str(p.relative_to(a.upstream))
    sources = {**visible, **{f"upstream {k}": v for k, v in public.items()}}
    for d in sorted(p for p in (a.docs / "examples").iterdir() if p.is_dir()):
        for p in d.glob("*.dw"):
            public_policies.setdefault(
                digest(p.name, p.read_text(encoding="utf-8")), f"docs example {d.name}"
            )
    by_digest: dict[str, set[str]] = defaultdict(set)
    for name, ds in sources.items():
        for x in ds:
            by_digest[x].add(name)

    cases = [
        json.loads(x)
        for x in (a.private / "cases.jsonl").read_text().splitlines()
        if x.strip()
    ]
    leaks = []
    for c in cases:
        names = case_inputs(c)
        ds = []
        for n in names:
            path = a.private / "bundles" / c["bundle"] / n
            if path.is_file():
                ds.append(digest(n, path.read_text(encoding="utf-8", errors="replace")))
        if not ds:
            continue
        common = set.intersection(*(by_digest.get(x, set()) for x in ds))
        if common:
            leaks.append({"case": c["id"], "sources": sorted(common)[:5]})

    policy_equal = []
    near = []
    public_shingles = {}
    for dg, where in public_policies.items():
        path = a.upstream / where if not where.startswith("docs example") else None
        if path is not None and path.is_file():
            public_shingles[where] = shingles(
                path.read_text(encoding="utf-8", errors="replace")
            )
    for bundle in sorted((a.private / "bundles").iterdir()):
        p = bundle / "policy.dw"
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        dg = digest(p.name, text)
        if dg in public_policies:
            policy_equal.append({"bundle": bundle.name, "equals": public_policies[dg]})
            continue
        mine = shingles(text)
        if len(mine) < 8:
            continue
        for where, theirs in public_shingles.items():
            if not theirs:
                continue
            j = len(mine & theirs) / len(mine | theirs)
            if j >= 0.9:
                near.append(
                    {"bundle": bundle.name, "near": where, "jaccard": round(j, 3)}
                )
                break
    report = {
        "cases": len(cases),
        "case_leaks": leaks,
        "policies_equal_to_public": policy_equal,
        "policies_near_public": near,
        "visible_bundles": len(visible),
        "public_dirs": len(public),
        "public_policies": len(public_policies),
    }
    if a.report:
        a.report.write_text(json.dumps(report, indent=1) + "\n")
    print(
        json.dumps(
            {
                "cases": len(cases),
                "case_leaks": len(leaks),
                "policies_equal_to_public": len(policy_equal),
                "policies_near_public": len(near),
            }
        )
    )
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
