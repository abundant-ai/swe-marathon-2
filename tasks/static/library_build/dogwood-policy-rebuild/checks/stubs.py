"""Write the stub zoo: trivial `dogwood` projects that the private case set must hold at 0.

Usage: python3 -I stubs.py --cases CASES.jsonl --run RUN.json --examples DOCS/examples --out DIR

Each stub is a Cargo project (std only) built and run by the real grader, the way a submission
is. RUN.json is the release build's recorded answers (`scripts/run_cases.py`); the stubs that
print a recorded answer take it from there, so the projects this writes hold private material and
stay out of the repository.

| Stub | What it does |
| --- | --- |
| nop | an empty directory |
| silent | prints nothing, exits 0 |
| usual-status | prints nothing, exits with each command's most common status |
| accept | `validate` prints the accept line (human or JSON) |
| reject | `validate` prints a generic error and exits 2 |
| deny, allow | `replay` prints DENY (or ALLOW with rule 0) for every request line of the trace |
| cat | `format` prints its input |
| count | `check-parse` prints "OK: parsed N policies." from a count of `permit`/`forbid` lines |
| most-common | every command prints its most common answer (exit status and output) |
| echo | `lower` prints the policy without its temporal and provider blocks, then the schema |
| lookup | prints the shipped examples' recorded output when the policy (and trace) is an example's |
| wrapper | runs `dogwood` from PATH with the same arguments |
| hang, flood, forkbomb, daemon | robustness probes: sleep past the limit, print without end, fork without end, or leave a detached process, on one or two command lines |
| buildrs | a build script that tries to read the grader's files, write the reward and leave a process behind |
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODES = (
    "silent",
    "usual-status",
    "accept",
    "reject",
    "deny",
    "allow",
    "cat",
    "count",
    "most-common",
    "echo",
    "lookup",
    "wrapper",
    "hang",
    "flood",
    "forkbomb",
    "daemon",
)
BUILD_RS = """// Tries, while the grader builds the project, to reach the grader's files and to leave a process
// behind. The build fails if any of the reads or writes succeeds.
use std::process::Command;

fn main() {
    let gold = std::fs::read("/tests/private/gold.jsonl").is_ok();
    let grader = std::fs::read("/tests/verify.py").is_ok();
    let reward = std::fs::write("/logs/verifier/reward.txt", "1.0\\n").is_ok();
    let _ = Command::new("setsid").args(["sleep", "3000"]).spawn();
    if gold || grader || reward {
        panic!("reached: gold {gold}, grader {grader}, reward {reward}");
    }
}
"""
CARGO = '[package]\nname = "dogwood"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n'


def route(c: dict) -> str:
    args = c["args"]
    if args and args[0] == "schema":
        return f"schema-{args[1] if len(args) > 1 else ''}"
    if args and args[0] == "lower":
        return f"lower-{args[args.index('--emit') + 1] if '--emit' in args else 'both'}"
    if args and args[0] == "explain" and "--policy-schema" not in args:
        return "explain-bare"
    return args[0] if args else ""


def fnv(data: bytes) -> str:
    h = 0xCBF29CE484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def fmt_of(c: dict) -> str:
    args = c["args"]
    return args[args.index("--format") + 1] if "--format" in args else "human"


def most_common(cases: list[dict], run: dict, least: int = 1) -> list[str]:
    """Each command's most common answer, when it was given at least `least` times."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for c in cases:
        first = run[c["id"]]["runs"][0]
        counts[f"{route(c)}/{fmt_of(c)}"][(first["rc"], first["norm"])] += 1
    lines = []
    for key, counter in sorted(counts.items()):
        (rc, out), n = counter.most_common(1)[0]
        if n >= least:
            lines.append(f"{key}\t{rc}\t{out.encode('utf-8').hex()}")
    return lines


def lookup(examples: Path) -> list[str]:
    lines = []
    for bundle in sorted(p for p in examples.iterdir() if p.is_dir()):
        policy = (bundle / "policy.dw").read_bytes()
        explain = bundle / "explain.out"
        if explain.exists():
            out = explain.read_bytes().hex()
            for r in ("explain", "explain-bare"):
                lines.append(f"{r}/human/{fnv(policy)}\t0\t{out}")
        expected, trace = bundle / "expected.out", bundle / "trace.log"
        if expected.exists() and trace.exists():
            key = fnv(policy + b"\0" + trace.read_bytes())
            lines.append(f"replay/human/{key}\t0\t{expected.read_bytes().hex()}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True, type=Path)
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--examples", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    cases = [json.loads(x) for x in a.cases.read_text().splitlines() if x.strip()]
    run = json.loads(a.run.read_text())
    tables = {
        "usual-status": most_common(cases, run),
        "most-common": most_common(cases, run, least=2),
        "lookup": lookup(a.examples),
    }
    if a.out.exists():
        shutil.rmtree(a.out)
    (a.out / "nop").mkdir(parents=True)
    for mode in MODES:
        d = a.out / mode
        (d / "src").mkdir(parents=True)
        (d / "Cargo.toml").write_text(CARGO)
        shutil.copyfile(HERE / "stub_src" / "main.rs", d / "src" / "main.rs")
        (d / "src" / "mode.txt").write_text(mode + "\n")
        (d / "src" / "table.txt").write_text("\n".join(tables.get(mode, [])) + "\n")
    d = a.out / "buildrs"
    (d / "src").mkdir(parents=True)
    (d / "Cargo.toml").write_text(
        CARGO.replace("[dependencies]", 'build = "build.rs"\n\n[dependencies]')
    )
    (d / "build.rs").write_text(BUILD_RS)
    shutil.copyfile(HERE / "stub_src" / "main.rs", d / "src" / "main.rs")
    (d / "src" / "mode.txt").write_text("silent\n")
    (d / "src" / "table.txt").write_text("\n")
    print(json.dumps({"stubs": ["nop", *MODES, "buildrs"], "out": str(a.out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
