"""Coverage inventory and kill matrix (gates 1 and 2).

Usage: python3 -I coverage.py --private DIR --gold RUN.json [--mutants DIR] [--report FILE]

`checks/features.json` lists every documented feature and stated restriction of the shipped
guide. Each id needs cases that fail when an implementation lacks it: at least 3 for a feature,
at least 1 for a restriction. The evidence, strongest first:
- mutant: a patch in `checks/mutants/` that names the id in its `MUTANT (<id>)` line; the cases whose recorded answer that mutant's build changes (its run in
  --mutants, `<patch name>.json`);
- error: for a restriction, the cases whose inputs have the breaking shape (its detectors, or a
  template bundle built to break it) and whose recorded answer refuses it (the restriction's
  message, or a failing exit status; a template for a restriction with a known message must show
  the message), or, for a restriction known only by its message, the cases whose answer carries
  it: a build without the check does not print that;
- use: for a feature, the cases whose inputs use it (its `detect` patterns, or a template bundle
  built to use it) and whose recorded answer is a success (exit status 0), or whose answer
  carries one of its messages: a build without the feature cannot print that answer.
Out-of-scope ids must have no case, whatever its exit status; unchecked restrictions are not
counted. An id is stated only when its quote stands in the shipped guide or in the brief: an id
sourced from anything else (upstream's code, say) is reported as not stated.

The other direction: every graded case must be claimed by a stated id (by its detectors without
the catch-all ones, its generator tag, the template it was built from, or a message of the id in
its answer), so a graded behaviour no agent-visible text states is a bug; every error, warning
and fail-closed message in a graded answer must hold the message of a stated id (the rule that
gives it); and every key of every graded JSON answer must be named in the guide.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
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
        add(
            "policy", case["stdin"] if args[1] == "-" and case.get("stdin") else args[1]
        )
    if route(args) == "schema" and len(args) > 2:
        add(
            "schema", case["stdin"] if args[2] == "-" and case.get("stdin") else args[2]
        )
    for i, a in enumerate(args):
        if a in FILE_FLAGS and i + 1 < len(args):
            add(FILE_FLAGS[a], args[i + 1])
    out = {k: "\n".join(v) for k, v in text.items()}
    out["args"] = " ".join(args)
    return out


def alternatives(f: dict) -> list[dict]:
    d = f.get("detect") or []
    return d if isinstance(d, list) else [d]


KEYS = (
    ("policy_regex", "policy"),
    ("trace_regex", "trace"),
    ("schema_regex", "schema"),
    ("args_regex", "args"),
)


def matches(detect: list[dict], inp: dict, tags: list[str]) -> bool:
    """Whether any alternative of an id's `detect` matches the case's inputs. Alternatives are
    OR-ed; inside one alternative every regex and the generator tag must all match (AND)."""
    for alt in detect:
        keys = [(k, field) for k, field in KEYS if alt.get(k)]
        tag = alt.get("gen_tag")
        if not keys and not tag:
            continue
        ok = all(
            re.search(alt[k], inp.get(field, ""), flags=re.MULTILINE)
            for k, field in keys
        )
        if tag:
            ok = ok and any(t == tag or t.startswith(tag + ":") for t in tags)
        if ok:
            return True
    return False


def catch_all(alt: dict) -> bool:
    """An alternative that matches every case (`args_regex: "."`), which claims nothing."""
    keys = [k for k, _ in KEYS if alt.get(k)]
    return keys == ["args_regex"] and alt["args_regex"] in (".", "^", ".*", "")


def json_keys(text: str) -> set[str]:
    try:
        value = json.loads(text)
    except ValueError:
        return set()
    out: set[str] = set()
    stack = [value]
    while stack:
        v = stack.pop()
        if isinstance(v, dict):
            out.update(v)
            stack.extend(v.values())
        elif isinstance(v, list):
            stack.extend(v)
    return out


def messages(text: str, fmt: str) -> list[str]:
    """The error, warning and fail-closed messages of one recorded answer."""
    out: list[str] = []
    if fmt == "json":
        try:
            value = json.loads(text)
        except ValueError:
            return out
        stack = [value]
        while stack:
            v = stack.pop()
            if isinstance(v, dict):
                for k, x in v.items():
                    if k in ("message", "reason") and isinstance(x, str):
                        out.append(x)
                    elif k in ("errors", "warnings") and isinstance(x, list):
                        out.extend(y for y in x if isinstance(y, str))
                        stack.extend(y for y in x if not isinstance(y, str))
                    else:
                        stack.append(x)
            elif isinstance(v, list):
                stack.extend(v)
        return out
    for line in text.splitlines():
        s = line.strip()
        for head in ("error: ", "warning: "):
            if s.startswith(head):
                out.append(s[len(head) :])
    return out


def template(message: str) -> str:
    return re.sub(r"\b\d+\b", "N", re.sub(r"`[^`]*`", "`_`", message))[:160]


def squash(text: str) -> str:
    return " ".join(text.replace("**", "").replace("`", "").split())


def stated(f: dict, guide: dict[str, str]) -> str | None:
    """The shipped guide chapter that still holds the id's quote, or None."""
    quote = squash((f.get("doc") or {}).get("quote", ""))
    if not quote:
        return None
    for name, text in guide.items():
        if quote in text:
            return name
    return None


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
    ap.add_argument("--docs", type=Path, default=CHECKS.parent / "environment" / "docs")
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

    def answers(run: dict, cid: str) -> set:
        return {(x["rc"], x["norm"]) for x in run[cid]["runs"]}

    killed: dict[str, set[str]] = defaultdict(set)  # id -> case ids
    mutant_runs = {}
    names = mutant_ids()
    if a.mutants:
        for name, ids in names.items():
            path = a.mutants / f"{name}.json"
            if path.is_file():
                run = json.loads(path.read_text())
                mutant_runs[name] = run
                # A kill is an answer the release build never gave in any recorded run, so a
                # case whose answer varies between runs cannot pass for one.
                changed = {
                    c["id"]
                    for c in cases
                    if c["id"] in gold
                    and answer(run, c["id"]) not in answers(gold, c["id"])
                }
                for i in ids:
                    killed[i] |= changed
    by_id: dict[str, dict] = {}
    inp_cache = {c["id"]: inputs(a.private, c) for c in cases}
    guide = {
        p.name: squash(p.read_text(encoding="utf-8"))
        for p in sorted((a.docs / "guide").glob("*.md"))
    }
    brief_path = a.docs.parent.parent / "instruction.md"
    brief = (
        {"instruction.md": squash(brief_path.read_text(encoding="utf-8"))}
        if brief_path.is_file()
        else {}
    )
    claimed: dict[str, set[str]] = defaultdict(set)  # case id -> ids that claim it
    for f in features:
        fid, kind = f["id"], f["kind"]
        routes = set(f.get("routes") or [])
        detect = alternatives(f)
        errs = [alt["error"] for alt in detect if alt.get("error")]
        has_shape = any(k != "error" for alt in detect for k in alt)
        use, errors = set(), set()
        for c in cases:
            if routes and route(c["args"]) not in routes:
                continue
            g = answer(gold, c["id"])
            if g is None:
                continue
            msg = any(
                e.get("message_substring") and e["message_substring"] in g[1]
                for e in errs
            )
            # A template bundle (`scripts/restrictions.py`) is built to break or use this id.
            targeted = tags.get(c["bundle"], {}).get("kind") == fid
            hit = targeted or (
                has_shape
                and matches(
                    detect,
                    inp_cache[c["id"]],
                    tags.get(c["bundle"], {}).get("tags", []),
                )
            )
            if (
                targeted
                or msg
                or (
                    has_shape
                    and matches(
                        [alt for alt in detect if not catch_all(alt)],
                        inp_cache[c["id"]],
                        tags.get(c["bundle"], {}).get("tags", []),
                    )
                )
            ):
                claimed[c["id"]].add(fid)
            if kind == "out_of_scope":
                if hit:
                    use.add(c["id"])
                continue
            if kind == "restriction":
                # The breaking shape and a refusal (its message, or a failing exit status),
                # or, for an id known only by its message, the message. A template for an id
                # with a known message must show that message, so it broke this rule.
                if targeted and errs:
                    ok = msg
                else:
                    ok = (hit and (msg or g[0] != 0)) or (not has_shape and msg)
                if ok:
                    errors.add(c["id"])
            elif (hit and g[0] == 0) or msg:
                use.add(c["id"])
        mutated = killed.get(fid, set())
        if kind == "restriction":
            n, need = len(errors | mutated), 1
            evidence = "mutant" if mutated else ("error" if errors else "none")
        elif kind == "feature":
            need = f.get("min_cases", 3)  # fewer only with a recorded reason
            if need < 3 and not f.get("min_cases_why"):
                raise SystemExit(f"{fid}: min_cases without min_cases_why")
            n = len(mutated) if mutated else len(use)
            evidence = "mutant" if mutated else ("use" if use else "none")
        else:
            n, need, evidence = len(use | errors), 0, "out of scope"
        doc = (f.get("doc") or {}).get("file", "")
        by_id[fid] = {
            "kind": kind,
            "family": f.get("family"),
            "unchecked": bool(f.get("unchecked")),
            "mutant_kills": len(mutated),
            "error_cases": len(errors),
            "use_cases": len(use),
            "count": n,
            "need": need,
            "evidence": evidence,
            "stated_in": (
                stated(f, guide)
                if doc.startswith("guide/")
                else stated(f, brief)
                if doc == "instruction.md"
                else None
            ),
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
    stated_ids = {
        fid
        for fid, r in by_id.items()
        if r["kind"] in ("feature", "restriction") and r["stated_in"] is not None
    }
    unclaimed = sorted(c["id"] for c in cases if not (claimed[c["id"]] & stated_ids))
    raw_guide = "\n".join(
        p.read_text(encoding="utf-8") for p in sorted((a.docs / "guide").glob("*.md"))
    )
    keys: set[str] = set()
    for c in cases:
        g = answer(gold, c["id"])
        if g is not None and c["fmt"] == "json":
            keys |= json_keys(g[1])
    undocumented_keys = sorted(
        k for k in keys if f'"{k}"' not in raw_guide and f"`{k}`" not in raw_guide
    )
    substrings = [
        alt["error"]["message_substring"]
        for f in features
        if f["id"] in stated_ids
        for alt in alternatives(f)
        if (alt.get("error") or {}).get("message_substring")
    ]
    unnamed: Counter = Counter()
    for c in cases:
        g = answer(gold, c["id"])
        if g is None:
            continue
        for m in messages(g[1], c["fmt"]):
            if not any(s in m for s in substrings):
                unnamed[template(m)] += 1
    report = {
        "unnamed_messages": dict(unnamed.most_common()),
        "unclaimed_cases": len(unclaimed),
        "unclaimed_examples": unclaimed[:40],
        "undocumented_json_keys": undocumented_keys,
        "ids": len(by_id),
        "by_kind": {
            k: sum(1 for r in by_id.values() if r["kind"] == k)
            for k in ("feature", "restriction", "out_of_scope")
        },
        "unchecked": sum(1 for r in by_id.values() if r["unchecked"]),
        "gaps": gaps,
        "evidence": dict(Counter(r["evidence"] for r in by_id.values())),
        "not_stated": sorted(
            fid
            for fid, r in by_id.items()
            if r["kind"] in ("feature", "restriction")
            and not r["unchecked"]
            and r["stated_in"] is None
        ),
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
            {k: report[k] for k in ("ids", "by_kind", "unchecked", "evidence")}
            | {
                "gaps": len(gaps),
                "not_stated": len(report["not_stated"]),
                "unclaimed_cases": len(unclaimed),
                "undocumented_json_keys": undocumented_keys,
                "unnamed_messages": len(unnamed),
            }
        )
    )
    for fid in report["not_stated"][:40]:
        print(f"NOT STATED {fid}")
    for cid in unclaimed[:40]:
        print(f"UNCLAIMED {cid}")
    for tpl, n in unnamed.most_common(40):
        print(f"UNNAMED MESSAGE ({n}) {tpl}")
    for g in gaps[:80]:
        r = by_id[g]
        print(
            f"GAP {g}: {r['count']} of {r['need']} (mutant {r['mutant_kills']}, error {r['error_cases']}, use {r['use_cases']})"
        )
    failed = gaps or report["not_stated"] or unclaimed or undocumented_keys or unnamed
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
