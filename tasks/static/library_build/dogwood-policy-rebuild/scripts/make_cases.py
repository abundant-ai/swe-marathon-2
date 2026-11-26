"""Generate the candidate case set: bundles, the command lines run on them, and their families.

Runs inside the toolchain container (python3 -I), never on the host. Three sources:
- upstream's Apache-2.0 bundle generator (`dogwood-lean/conformance/gen/gen.py` of the 1.2.0
  source), run with private seeds, one family at a time, near misses and schema cases included;
- the paired cases of `pairs.py` (B-dedup, B-scope and the K shapes), and the bundles of
  `restrictions.py`, each breaking one stated restriction the generator never breaks;
- command-line cases (`--help`, `--version`, usage and I/O errors) on a small bundle of their own,
  and, on a quarter of the bundles, commands that read their input from standard input (`-`).

Each bundle is made fit for the command line: provider scripts are inlined (the CLI never resolves
`scriptFile`), and a bundle with a trace whose timestamps repeat or go back is dropped, since the
brief puts such traces out of contract. Every bundle also gets two derived policy files: a copy
with its layout disturbed (whitespace only), for `format`, and a copy with one token broken, for
`check-parse`'s syntax errors.

This writes candidates. `select_cases.py` keeps the cases a trivial program cannot pass, once the
release build's answers are recorded (`run_cases.py`), and `retag.py` then checks the B and K
families against the mutants. Families are assigned by what a case is meant to exercise:
- replay: a pair's declared family; otherwise P for providers bundles, M for macros bundles, R;
- validate: V (human) and V-msg (JSON); explain: X; lower: L;
- format, check-parse, schema and the command line: F.

Usage: make_cases.py --gen DIR --out DIR --seed S [counts...]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pairs
import restrictions

TRACE_NAME = re.compile(r"trace(_\d+)?\.log")
STAMP = re.compile(r"^@(-?\d+)\s")
EVENT_SCHEMAS = ("events.dwschema", "event.dwschema")

CLI_POLICY = """@id("open_reads")
permit (
    principal,
    action == Ledger::Action::"Login",
    resource
);
"""


def trace_ok(path: Path) -> bool:
    """Strictly increasing timestamps, as the brief promises for every trace."""
    last = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        m = STAMP.match(line)
        if not m:
            return True  # an unparsable line is the build's to report, not ours to drop
        ts = int(m.group(1))
        if last is not None and ts <= last:
            return False
        last = ts
    return True


def inline_scripts(bundle: Path) -> None:
    path = bundle / "providers.json"
    if not path.exists():
        return
    decls = json.loads(path.read_text())

    def walk(node):
        if isinstance(node, dict):
            impl = node.get("implementation")
            if isinstance(impl, dict) and "scriptFile" in impl:
                script = bundle / impl.pop("scriptFile")
                impl["script"] = script.read_text() if script.exists() else ""
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(decls)
    path.write_text(json.dumps(decls, indent=1) + "\n")
    for leftover in bundle.glob("*.rhai"):
        leftover.unlink()


def flags(bundle: Path) -> list[str]:
    out: list[str] = []
    if (bundle / "macros.dw").exists():
        out += ["--macros", "macros.dw"]
    if (bundle / "providers.json").exists():
        out += ["--providers", "providers.json"]
    for name in EVENT_SCHEMAS:
        if (bundle / name).exists():
            out += ["--event-schema", name]
            break
    return out


def disturb(text: str, r: random.Random) -> str:
    """The same policy with its layout disturbed: indentation, blank lines and trailing spaces
    change, tokens and comments do not."""
    lines = text.splitlines()
    how = r.choice(["flush", "deep", "blank", "trailing", "mixed"])
    out = []
    for line in lines:
        body = line.lstrip(" ")
        if how in ("flush", "mixed") and r.random() < 0.8:
            line = body
        elif how == "deep" and body:
            line = "        " + line
        if how in ("trailing", "mixed") and line and r.random() < 0.5:
            line += "   "
        out.append(line)
        if how in ("blank", "mixed") and r.random() < 0.3:
            out.append("")
    result = "\n".join(out) + "\n"
    if result == text:
        result = "\n" + result.replace("\n", "\n\n", 1)
    return result


BREAKS = (
    ("drop the last semicolon", lambda t: t[: t.rfind(";")] + t[t.rfind(";") + 1 :]),
    ("misspell permit", lambda t: t.replace("permit", "permt", 1)),
    ("misspell forbid", lambda t: t.replace("forbid", "forbd", 1)),
    ("misspell within", lambda t: t.replace("within", "wthin", 1)),
    ("drop a closing brace", lambda t: t[: t.rfind("}")] + t[t.rfind("}") + 1 :]),
    ("drop a closing parenthesis", lambda t: t[: t.find(")")] + t[t.find(")") + 1 :]),
    ("double an operator", lambda t: t.replace("&&", "&& &&", 1)),
    ("stray token", lambda t: t.replace("when", "when @", 1)),
)


def broken(text: str, r: random.Random) -> str | None:
    """The policy with one token broken, or None when no break changes it."""
    options = list(BREAKS)
    r.shuffle(options)
    for _, f in options:
        try:
            out = f(text)
        except ValueError:
            continue
        if out != text:
            return out
    return None


def case(name, cid, family, args, fmt, pair=None, stdin=None):
    c = {
        "id": f"{name}/{cid}",
        "bundle": name,
        "family": family,
        "pair": pair,
        "args": args,
        "fmt": fmt,
    }
    if stdin:
        c["stdin"] = stdin
    return c


def replay_family(meta: dict) -> str:
    if meta.get("b_family"):
        return meta["b_family"]
    return {"providers": "P", "macros": "M"}.get(meta.get("family", ""), "R")


def cases_for(name: str, bundle: Path, meta: dict, r: random.Random) -> list[dict]:
    base = ["policy.dw", "--policy-schema", "schema.cedarschema"]
    fl = flags(bundle)
    family = meta.get("family", "")
    pair = f"{meta['b_family']}:{meta['pair']}" if meta.get("b_family") else None
    if family == "restrictions":
        return restriction_cases(name, bundle, meta, base, fl)
    out = []
    for trace in sorted(
        p.name for p in bundle.iterdir() if TRACE_NAME.fullmatch(p.name)
    ):
        for fmt in ("human", "json"):
            out.append(
                case(
                    name,
                    f"{trace}/replay/{fmt}",
                    replay_family(meta),
                    ["replay", *base, "--trace", trace, *fl, "--format", fmt],
                    fmt,
                    pair,
                )
            )
    if pair:
        return (
            out  # a pair grades replay; its other routes repeat the generated bundles'
        )
    for fmt, fam in (("human", "V"), ("json", "V-msg")):
        out.append(
            case(
                name,
                f"validate/{fmt}",
                fam,
                ["validate", *base, *fl, "--format", fmt],
                fmt,
            )
        )
    for fmt in ("human", "json"):
        out.append(
            case(
                name,
                f"check-parse/{fmt}",
                "F",
                ["check-parse", "policy.dw", *fl, "--format", fmt],
                fmt,
            )
        )
    if family == "nearmiss":
        out.append(
            case(
                name,
                "lower/human",
                "L",
                ["lower", *base, *fl, "--format", "human"],
                "human",
            )
        )
        return out
    for fmt in ("human", "json"):
        out.append(
            case(
                name,
                f"explain/{fmt}",
                "X",
                ["explain", *base, *fl, "--format", fmt],
                fmt,
            )
        )
        out.append(
            case(
                name,
                f"lower/{fmt}",
                "L",
                ["lower", *base, *fl, "--emit", "both", "--format", fmt],
                fmt,
            )
        )
    emit = r.choice(["cedar-json", "cedar-policies", "cedar-schema"])
    out.append(
        case(
            name,
            f"lower-{emit}/human",
            "L",
            ["lower", *base, *fl, "--emit", emit, "--format", "human"],
            "human",
        )
    )
    if r.random() < 0.3:
        out.append(
            case(
                name,
                "explain-bare/human",
                "X",
                ["explain", "policy.dw", *fl, "--format", "human"],
                "human",
            )
        )
    fmt = r.choice(["human", "json"])
    out.append(
        case(
            name,
            f"schema-action/{fmt}",
            "F",
            ["schema", "action", "schema.cedarschema", "--format", fmt],
            fmt,
        )
    )
    for ev in EVENT_SCHEMAS:
        if (bundle / ev).exists():
            out.append(
                case(
                    name,
                    f"schema-event/{fmt}",
                    "F",
                    ["schema", "event", ev, "--format", fmt],
                    fmt,
                )
            )
    if (bundle / "providers.json").exists():
        out.append(
            case(
                name,
                f"schema-providers/{fmt}",
                "F",
                ["schema", "providers", "providers.json", "--format", fmt],
                fmt,
            )
        )
    policy = (bundle / "policy.dw").read_text(encoding="utf-8")
    (bundle / "layout.dw").write_text(disturb(policy, r), encoding="utf-8")
    out.append(case(name, "format/human", "F", ["format", "layout.dw"], "human"))
    if r.random() < 0.25:  # the same commands reading `-`, standard input
        out.append(
            case(
                name,
                "format-stdin/human",
                "F",
                ["format", "-"],
                "human",
                stdin="layout.dw",
            )
        )
        out.append(
            case(
                name,
                "check-parse-stdin/human",
                "F",
                ["check-parse", "-", *fl],
                "human",
                stdin="policy.dw",
            )
        )
        out.append(
            case(
                name,
                "validate-stdin/human",
                "F",
                ["validate", "-", "--policy-schema", "schema.cedarschema", *fl],
                "human",
                stdin="policy.dw",
            )
        )
        out.append(
            case(
                name,
                "schema-action-stdin/human",
                "F",
                ["schema", "action", "-"],
                "human",
                stdin="schema.cedarschema",
            )
        )
    bad = broken(policy, r)
    if bad is not None:
        (bundle / "typo.dw").write_text(bad, encoding="utf-8")
        fmt = r.choice(["human", "json"])
        out.append(
            case(
                name,
                f"check-parse-typo/{fmt}",
                "F",
                ["check-parse", "typo.dw", *fl, "--format", fmt],
                fmt,
            )
        )
    return out


def restriction_cases(name, bundle, meta, base, fl) -> list[dict]:
    """The commands whose answers show the one restriction a `restrictions.py` bundle breaks."""
    targets = {
        "action": "schema.cedarschema",
        "event": "event.dwschema",
        "providers": "providers.json",
    }
    out = []
    for cmd in meta["cmds"]:
        if cmd == "check-parse":
            args = ["check-parse", "policy.dw", *fl]
            out.append(case(name, "check-parse/human", "F", args, "human"))
        elif cmd == "validate":
            for fmt, fam in (("human", "V"), ("json", "V-msg")):
                args = ["validate", *base, *fl, "--format", fmt]
                out.append(case(name, f"validate/{fmt}", fam, args, fmt))
        elif cmd == "lower":
            args = ["lower", *base, *fl, "--format", "human"]
            out.append(case(name, "lower/human", "L", args, "human"))
        elif cmd == "replay":
            for fmt in ("human", "json"):
                args = ["replay", *base, "--trace", "trace.log", *fl, "--format", fmt]
                out.append(case(name, f"trace.log/replay/{fmt}", "R", args, fmt))
        elif cmd.startswith("schema-"):
            what = cmd.split("-", 1)[1]
            args = ["schema", what, targets[what]]
            out.append(case(name, f"{cmd}/human", "F", args, "human"))
    return out


def cli_cases(bundles: Path) -> list[dict]:
    """The command line itself, on a bundle of its own: help and version text, usage errors and
    I/O errors."""
    name = "cli"
    d = bundles / name
    d.mkdir()
    (d / "policy.dw").write_text(CLI_POLICY)
    (d / "schema.cedarschema").write_text(pairs.SCHEMA)
    (d / "folder").mkdir()
    (d / "folder" / "keep.txt").write_text("\n")
    runs = [
        ("version", ["--version"]),
        ("help", ["--help"]),
        ("help-cmd", ["help"]),
        ("no-args", []),
        ("unknown-cmd", ["audit", "policy.dw"]),
        ("schema-mcp", ["schema", "mcp", "--manifest", "tools.json"]),
        ("validate-no-schema", ["validate", "policy.dw"]),
        (
            "bad-format",
            [
                "validate",
                "policy.dw",
                "--policy-schema",
                "schema.cedarschema",
                "--format",
                "yaml",
            ],
        ),
        (
            "bad-emit",
            [
                "lower",
                "policy.dw",
                "--policy-schema",
                "schema.cedarschema",
                "--emit",
                "rust",
            ],
        ),
        ("missing-file", ["check-parse", "absent.dw"]),
        ("directory", ["format", "folder"]),
        (
            "missing-schema",
            ["validate", "policy.dw", "--policy-schema", "absent.cedarschema"],
        ),
        (
            "missing-trace",
            [
                "replay",
                "policy.dw",
                "--policy-schema",
                "schema.cedarschema",
                "--trace",
                "absent.log",
            ],
        ),
        (
            "replay-no-trace",
            ["replay", "policy.dw", "--policy-schema", "schema.cedarschema"],
        ),
        ("format-with-format", ["format", "policy.dw", "--format", "json"]),
    ]
    for cmd in (
        "format",
        "check-parse",
        "validate",
        "lower",
        "replay",
        "explain",
        "schema",
    ):
        runs.append((f"help-{cmd}", [cmd, "--help"]))
    for sub in ("action", "event", "providers"):
        runs.append((f"help-schema-{sub}", ["schema", sub, "--help"]))
    return [case(name, f"{cid}/human", "F", args, "human") for cid, args in runs]


def generate(gen: Path, raw: Path, seed: int, counts: dict[str, int]) -> None:
    for i, (fam, count) in enumerate(sorted(counts.items())):
        if count:
            subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(gen / "gen.py"),
                    "--seed",
                    str(seed + i),
                    "--count",
                    str(count),
                    "--family",
                    fam,
                    "--out",
                    str(raw),
                ],
                check=True,
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--gen", required=True, type=Path, help="upstream conformance/gen directory"
    )
    ap.add_argument(
        "--out", required=True, type=Path, help="an empty directory for the candidates"
    )
    ap.add_argument("--seed", required=True, type=int)
    ap.add_argument("--temporal", type=int, default=120)
    ap.add_argument(
        "--per-family", type=int, default=40, help="traces, events, providers, macros"
    )
    ap.add_argument("--nearmiss", type=int, default=300)
    ap.add_argument("--schema", type=int, default=60)
    ap.add_argument(
        "--pairs", type=int, default=40, help="B-dedup and B-scope pairs each"
    )
    ap.add_argument("--key-previous", type=int, default=24)
    ap.add_argument("--key-other", type=int, default=12, help="each other K shape")
    a = ap.parse_args()
    bundles = a.out / "bundles"
    if bundles.exists():
        raise SystemExit(f"{bundles} exists; stage into an empty directory")
    raw = Path("/tmp/make-cases-raw")
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    counts = {
        "temporal": a.temporal,
        "traces": a.per_family,
        "events": a.per_family,
        "providers": a.per_family,
        "macros": a.per_family,
        "nearmiss": a.nearmiss,
        "schema": a.schema,
    }
    generate(a.gen, raw, a.seed, counts)
    key = {shape: a.key_other for shape in pairs.KEY_SHAPES}
    key["previous"] = a.key_previous
    pairs.write_pairs(a.seed + 100, a.pairs, raw, key)
    restrictions.write_restrictions(a.seed + 300, raw)

    r = random.Random(a.seed + 200)
    bundles.mkdir(parents=True)
    cases: list[dict] = []
    tags: dict[str, dict] = {}
    dropped = {"timestamps": 0}
    for src in sorted(raw.iterdir()):
        meta_path = src / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        traces = [p for p in src.iterdir() if TRACE_NAME.fullmatch(p.name)]
        if not all(trace_ok(t) for t in traces):
            dropped["timestamps"] += 1
            continue
        dst = bundles / src.name
        shutil.copytree(src, dst)
        (dst / "meta.json").unlink(missing_ok=True)
        inline_scripts(dst)
        tags[src.name] = {
            "family": meta.get("family"),
            "tags": sorted(meta.get("tags", [])),
            "kind": meta.get("kind"),
        }
        cases.extend(cases_for(src.name, dst, meta, r))
    cases.extend(cli_cases(bundles))
    with (a.out / "cases.jsonl").open("w") as f:
        for c in cases:
            f.write(json.dumps(c, sort_keys=True) + "\n")
    (a.out / "bundle_tags.json").write_text(
        json.dumps(tags, indent=0, sort_keys=True) + "\n"
    )
    fams: dict[str, int] = {}
    for c in cases:
        fams[c["family"]] = fams.get(c["family"], 0) + 1
    manifest = {
        "seed": a.seed,
        "generator_counts": counts,
        "pairs": a.pairs,
        "key_pairs": key,
        "bundles": sum(1 for _ in bundles.iterdir()),
        "dropped": dropped,
        "cases": len(cases),
        "families": fams,
    }
    (a.out / "manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
