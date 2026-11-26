"""Generate the private case set: bundles, the command lines run on them, and their families.

Runs inside the toolchain container (python3 -I), never on the host. Two sources:
- upstream's Apache-2.0 bundle generator (`dogwood-lean/conformance/gen/gen.py` of the 1.2.0
  source), run with private seeds, one family at a time;
- the paired cases of `pairs.py` (B-dedup, B-scope and K).

Each bundle is made fit for the command line and for this task: provider scripts are inlined
(the CLI never resolves `scriptFile`), and a bundle with a trace whose timestamps repeat or go back
is dropped. Expected results are not recorded here; the grader's image records them from the
release build.

Families are assigned by what a case is meant to exercise, never by how any build answers:
- replay cases go to B-dedup when an aggregate's `for` list leaves out the timepoint, to B-scope
  for the generator's aggregates whose body has no past operator, and otherwise by the generator
  family (events to K, providers to P, macros to M, the rest to R);
- validate cases to V (human) and V-msg (JSON), lower to L, explain to X, check-parse to F.

Usage: make_cases.py --gen DIR --out DIR --seed S [--per-family N] [--pairs N]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pairs

GEN_FAMILIES = ("temporal", "traces", "events", "providers", "macros")
AGG = re.compile(r"\b(?:count|sum\s+\w+)\s+for\s+\(([^.]*?)\)\.\s*where", re.DOTALL)
TRACE_NAME = re.compile(r"trace(_\d+)?\.log")
STAMP = re.compile(r"^@(-?\d+)\s")


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
    for name in ("events.dwschema", "event.dwschema"):
        if (bundle / name).exists():
            out += ["--event-schema", name]
            break
    return out


def replay_family(policy: str, meta: dict) -> str:
    if meta.get("b_family"):
        return meta["b_family"]
    if any("Timepoint" not in m.group(1) for m in AGG.finditer(policy)):
        return "B-dedup"
    if "temporal:agg_no_temporal" in meta.get("tags", []):
        return "B-scope"
    return {"events": "K", "providers": "P", "macros": "M"}.get(
        meta.get("family", ""), "R"
    )


def cases_for(name: str, bundle: Path, meta: dict) -> list[dict]:
    base = ["policy.dw", "--policy-schema", "schema.cedarschema"]
    fl = flags(bundle)
    policy = (bundle / "policy.dw").read_text(encoding="utf-8", errors="replace")
    pair = f"{meta['b_family']}:{meta['pair']}" if meta.get("b_family") else None
    out = []
    for trace in sorted(
        p.name for p in bundle.iterdir() if TRACE_NAME.fullmatch(p.name)
    ):
        for fmt in ("human", "json"):
            out.append(
                {
                    "id": f"{name}/{trace}/replay/{fmt}",
                    "bundle": name,
                    "family": replay_family(policy, meta),
                    "pair": pair,
                    "args": ["replay", *base, "--trace", trace, *fl, "--format", fmt],
                    "fmt": fmt,
                }
            )
    for cmd, fam_h, fam_j, extra in (
        ("validate", "V", "V-msg", []),
        ("explain", "X", "X", []),
        ("lower", "L", "L", ["--emit", "both"]),
    ):
        for fmt, fam in (("human", fam_h), ("json", fam_j)):
            out.append(
                {
                    "id": f"{name}/{cmd}/{fmt}",
                    "bundle": name,
                    "family": fam,
                    "pair": None,
                    "args": [cmd, *base, *fl, *extra, "--format", fmt],
                    "fmt": fmt,
                }
            )
    out.append(
        {
            "id": f"{name}/check-parse/human",
            "bundle": name,
            "family": "F",
            "pair": None,
            "args": ["check-parse", "policy.dw", *fl],
            "fmt": "human",
        }
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--gen", required=True, type=Path, help="upstream conformance/gen directory"
    )
    ap.add_argument(
        "--out", required=True, type=Path, help="the step's tests/private directory"
    )
    ap.add_argument("--seed", required=True, type=int)
    ap.add_argument("--per-family", type=int, default=40)
    ap.add_argument("--temporal", type=int, default=120)
    ap.add_argument("--pairs", type=int, default=40)
    a = ap.parse_args()
    bundles = a.out / "bundles"
    if bundles.exists():
        raise SystemExit(f"{bundles} exists; stage into an empty directory")
    raw = Path("/tmp/make-cases-raw")
    raw.mkdir(parents=True, exist_ok=True)
    for i, fam in enumerate(GEN_FAMILIES):
        count = a.temporal if fam == "temporal" else a.per_family
        subprocess.run(
            [
                sys.executable,
                "-I",
                str(a.gen / "gen.py"),
                "--seed",
                str(a.seed + i),
                "--count",
                str(count),
                "--family",
                fam,
                "--out",
                str(raw),
            ],
            check=True,
        )
    pairs.write_pairs(a.seed + 100, a.pairs, raw)

    bundles.mkdir(parents=True)
    cases: list[dict] = []
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
        cases.extend(cases_for(src.name, dst, meta))
    with (a.out / "cases.jsonl").open("w") as f:
        for c in cases:
            f.write(json.dumps(c, sort_keys=True) + "\n")
    fams: dict[str, int] = {}
    for c in cases:
        fams[c["family"]] = fams.get(c["family"], 0) + 1
    manifest = {
        "seed": a.seed,
        "generator_counts": {
            f: (a.temporal if f == "temporal" else a.per_family) for f in GEN_FAMILIES
        },
        "pairs": a.pairs,
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
