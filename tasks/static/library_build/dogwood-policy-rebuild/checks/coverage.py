"""Coverage inventory and kill matrix (gates 1 and 2).

Usage: python3 -I coverage.py --private DIR --gold RUN.json [--mutants DIR] [--report FILE]

`checks/features.json` lists every documented feature and stated restriction of the shipped
guide. Each id needs cases that fail when an implementation lacks it: at least 3 for a feature,
at least 1 for a restriction. The evidence, strongest first:
- mutant: a patch in `checks/mutants/` that names the id in its `MUTANT (<id>)` line; the cases whose recorded answer that mutant's build changes (its run in
  --mutants, `<patch name>.json`);
- error: for a restriction, the cases whose recorded answer carries the restriction's message,
  which a build without the check does not print;
- use: for a feature, the cases whose inputs use it (its `detect` patterns) and whose recorded
  answer is a success (exit status 0): a build without the feature cannot print that answer.
Out-of-scope ids must have no case; unchecked restrictions are not counted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

CHECKS = Path(__file__).resolve().parent
FILE_FLAGS = {
    "--policy-schema": "schema",
    "--event-schema": "schema",
    "--providers": "schema",
    "--macros": "policy",
    "--trace": "trace",
}


def route(args: list[str]) -> str:
    if not args:
        return "cli"
    if args[0] in (
        "format",
        "check-parse",
        "validate",
        "lower",
        "replay",
        "explain",
        "schema",
    ):
        return args[0]
    return "cli"


def inputs(private: Path, case: dict) -> dict[str, str]:
    """The text of the policy, schemas and trace a case reads, by kind."""
    args = case["args"]
    bundle = private / "bundles" / case["bundle"]
    text: dict[str, list[str]] = defaultdict(list)

    def add(kind: str, name: str) -> None:
        p = bundle / name
        if p.is_file():
            text[kind].append(p.read_text(encoding="utf-8", errors="replace"))

    if (
        route(args)
        in (
            "format",
            "check-parse",
            "validate",
            "lower",
            "replay",
            "explain",
        )
        and len(args) > 1
    ):
        add("policy", args[1])
    if route(args) == "schema" and len(args) > 2:
        add("schema", args[2])
    for i, a in enumerate(args):
        if a in FILE_FLAGS and i + 1 < len(args):
            add(FILE_FLAGS[a], args[i + 1])
    out = {k: "\n".join(v) for k, v in text.items()}
    out["args"] = " ".join(args)
    return out


def matches(detect: dict, inp: dict, tags: list[str]) -> bool:
    for key, field in (
        ("policy_regex", "policy"),
        ("trace_regex", "trace"),
        ("schema_regex", "schema"),
        ("args_regex", "args"),
    ):
        pattern = detect.get(key)
        if pattern and re.search(pattern, inp.get(field, ""), flags=re.MULTILINE):
            return True
    tag = detect.get("gen_tag")
    return bool(tag) and any(t == tag or t.startswith(tag + ":") for t in tags)


def mutant_ids() -> dict[str, list[str]]:
    """Patch name -> the ids its MUTANT lines name."""
    out: dict[str, list[str]] = {}
    for patch in sorted((CHECKS / "mutants").glob("*.patch")):
        ids = re.findall(r"MUTANT \(([^)]+)\)", patch.read_text())
        out[patch.stem] = sorted({i.strip() for x in ids for i in x.split(",")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", required=True, type=Path)
    ap.add_argument("--gold", required=True, type=Path)
    ap.add_argument(
        "--mutants", type=Path, help="directory of run_cases.py records, one per mutant"
    )
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()
    features = json.loads((CHECKS / "features.json").read_text())
    cases = [
        json.loads(x)
        for x in (a.private / "cases.jsonl").read_text().splitlines()
        if x.strip()
    ]
    gold = json.loads(a.gold.read_text())
    tags = json.loads((a.private / "bundle_tags.json").read_text())

    def answer(run: dict, cid: str):
        r = run.get(cid)
        return None if r is None else (r["runs"][0]["rc"], r["runs"][0]["norm"])

    killed: dict[str, set[str]] = defaultdict(set)  # id -> case ids
    mutant_runs = {}
    names = mutant_ids()
    if a.mutants:
        for name, ids in names.items():
            path = a.mutants / f"{name}.json"
            if path.is_file():
                run = json.loads(path.read_text())
                mutant_runs[name] = run
                changed = {
                    c["id"]
                    for c in cases
                    if answer(run, c["id"]) != answer(gold, c["id"])
                }
                for i in ids:
                    killed[i] |= changed
    by_id: dict[str, dict] = {}
    inp_cache = {c["id"]: inputs(a.private, c) for c in cases}
    for f in features:
        fid, kind = f["id"], f["kind"]
        routes = set(f.get("routes") or [])
        detect = f.get("detect") or {}
        err = detect.get("error")
        use, errors = set(), set()
        for c in cases:
            if routes and route(c["args"]) not in routes:
                continue
            g = answer(gold, c["id"])
            if g is None:
                continue
            inp = inp_cache[c["id"]]
            if (
                err
                and err.get("message_substring")
                and err["message_substring"] in g[1]
            ):
                errors.add(c["id"])
            elif (
                matches(detect, inp, tags.get(c["bundle"], {}).get("tags", []))
                and g[0] == 0
            ):
                use.add(c["id"])
        mutated = killed.get(fid, set())
        if kind == "restriction":
            n = len(errors | mutated)
            need = 1
        elif kind == "feature":
            n = len(mutated) if mutated else len(use)
            need = 3
        else:
            n = len(use | errors)
            need = 0
        by_id[fid] = {
            "kind": kind,
            "family": f.get("family"),
            "unchecked": bool(f.get("unchecked")),
            "mutant_kills": len(mutated),
            "error_cases": len(errors),
            "use_cases": len(use),
            "count": n,
            "need": need,
        }
    gaps = sorted(
        fid
        for fid, r in by_id.items()
        if not r["unchecked"]
        and (
            (r["kind"] in ("feature", "restriction") and r["count"] < r["need"])
            or (r["kind"] == "out_of_scope" and r["count"] > 0)
        )
    )
    report = {
        "ids": len(by_id),
        "by_kind": {
            k: sum(1 for r in by_id.values() if r["kind"] == k)
            for k in ("feature", "restriction", "out_of_scope")
        },
        "unchecked": sum(1 for r in by_id.values() if r["unchecked"]),
        "gaps": gaps,
        "mutants": {
            name: sum(1 for c in cases if answer(run, c["id"]) != answer(gold, c["id"]))
            for name, run in mutant_runs.items()
        },
        "detail": by_id,
    }
    if a.report:
        a.report.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps(
            {k: report[k] for k in ("ids", "by_kind", "unchecked")}
            | {"gaps": len(gaps)}
        )
    )
    for g in gaps[:80]:
        r = by_id[g]
        print(
            f"GAP {g}: {r['count']} of {r['need']} (mutant {r['mutant_kills']}, error {r['error_cases']}, use {r['use_cases']})"
        )
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
