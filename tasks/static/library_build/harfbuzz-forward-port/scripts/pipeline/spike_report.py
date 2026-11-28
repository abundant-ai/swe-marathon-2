"""Turn the spike's raw outputs into its numbers (S2, S10, S11). Host side; reads only our own outputs.

Usage: python -I scripts/pipeline/spike_report.py SELECTION_JSONL
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

CACHE = Path.home() / "Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port"
WORK = CACHE / "work"
RUNS = WORK / "runs"
W_BROAD = 0.10


def read_out(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return dict(
        line.split("\t", 1) for line in path.read_text().splitlines() if "\t" in line
    )


def builds() -> dict[str, dict]:
    out = {}
    for line in (CACHE / "events.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e.get("event") == "build":
            out[e["id"]] = e
    return out


def differs(a: dict[str, str], b: dict[str, str]) -> dict[str, int]:
    keys = set(a) & set(b)
    return {
        "compared": len(keys),
        "differ": sum(a[k] != b[k] for k in keys),
        "missing": len(set(a) ^ set(b)),
    }


def score(
    selection: list[dict], outputs: dict[str, str], release: str = "15.2.0"
) -> dict:
    """The verifier's formula (tests/verify.py) on outputs keyed by the selection's original candidate ids."""
    units: dict[str, list[bool]] = defaultdict(list)
    duals: dict[str, list[bool]] = defaultdict(list)
    broad: list[bool] = []
    for c in selection:
        ok = outputs.get(c["cid"]) == c["gold"][release]
        if c["kind"] == "changed":
            units[c["unit"]].append(ok)
        elif c["kind"] == "dual":
            duals[c["unit"]].append(ok)
        else:
            broad.append(ok)
    per_unit = {u: sum(v) / len(v) for u, v in units.items()}
    per_dual = {u: sum(v) / len(v) for u, v in duals.items()}
    d = sum(per_unit.values()) / len(per_unit) if per_unit else 0.0
    h_d = sum(per_dual.values()) / len(per_dual) if per_dual else 1.0
    h_b = sum(broad) / len(broad) if broad else 1.0
    gate = h_d * (1 - W_BROAD * (1 - h_b))
    return {
        "reward": round(d * gate, 4),
        "D": round(d, 4),
        "h_dual": round(h_d, 4),
        "h_broad": round(h_b, 4),
        "units": {u: round(p, 3) for u, p in sorted(per_unit.items())},
        "neighbours": {u: round(p, 3) for u, p in sorted(per_dual.items())},
    }


def mutant_w(selection: list[dict], w_out: dict[str, str]) -> dict:
    """S11: does W pass each unit's changed cases and fail its duals? Duals broken down by neighbour."""
    report = {}
    for unit in ("4", "21", "23"):
        changed = [c for c in selection if c["kind"] == "changed" and c["unit"] == unit]
        duals = [c for c in selection if c["kind"] == "dual" and c["unit"] == unit]
        by_nb: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for c in duals:
            row = by_nb[c.get("nb", "")]
            row[0] += 1
            row[1] += w_out.get(c["cid"]) != c["gold"]["15.2.0"]
        report[unit] = {
            "changed": len(changed),
            "W_passes_changed": sum(
                w_out.get(c["cid"]) == c["gold"]["15.2.0"] for c in changed
            ),
            "duals": len(duals),
            "W_fails_duals": sum(v[1] for v in by_nb.values()),
            "by_neighbour": {
                k: {"duals": v[0], "W_fails": v[1]} for k, v in sorted(by_nb.items())
            },
        }
    return report


def main() -> None:
    report: dict = {}
    b = builds()
    report["S2_builds"] = {
        k: {
            f: v.get(f)
            for f in (
                "code",
                "status",
                "cpus",
                "jobs",
                "setup_s",
                "build_s",
                "wall_s",
                "mem_peak_bytes",
                "ragel",
                "ragel_steps",
            )
        }
        for k, v in sorted(b.items())
    }
    report["S2_ragel_off_vs_on"] = differs(
        read_out(RUNS / "rel-15.2.0.out"), read_out(RUNS / "rel-15.2.0-noragel.out")
    )
    report["S10_fma_off_vs_default"] = differs(
        read_out(RUNS / "rel-15.2.0.out"), read_out(RUNS / "rel-15.2.0-nofma.out")
    )
    det = {}
    for build in ("rel-15.2.0", "rel-14.3.0"):
        runs = [
            read_out(RUNS / "det" / f"{build}-{i}.out")
            for i in ("1", "2", "3", "perturbed")
        ]
        det[build] = {
            f"run1_vs_{n}": differs(runs[0], r)
            for n, r in zip(("2", "3", "perturbed"), runs[1:], strict=True)
        }
    report["S10_determinism"] = det
    if len(sys.argv) > 1:
        selection = [
            json.loads(line)
            for line in Path(sys.argv[1]).read_text().splitlines()
            if line
        ]
        report["S11_selection"] = dict(Counter(c["kind"] for c in selection))
        for name in ("rel-15.2.0", "rel-14.3.0", "rel-15.1.0", "mut-W"):
            report[f"score_{name}"] = score(selection, read_out(RUNS / f"{name}.out"))
        report["S11_mutant_W"] = mutant_w(selection, read_out(RUNS / "mut-W.out"))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
