"""The pre-upload gate's measurable items, from the pipeline's outputs and the verifier runs (development tooling).

usage: gate_checks.py SELECTION [--json OUT]

Reads the private selection, the pipeline's driver outputs (CACHE/work/runs), the verifier runs (CACHE/work/verify),
units.tsv and notes_map.tsv, and prints one line per item: inventory, kill matrix, stub zoo, oracle and nop,
determinism, cue words, leak scan, band check (the verification-gap mutant V, with W, W_literal and R_unbuilt as
secondary bounds). Items it cannot see (the protection probe, robustness, isolation, no
early stops) are reported from their own runs.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
CACHE = Path.home() / "Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port"
RUNS = CACHE / "work" / "runs-c3"
VERIFY = CACHE / "work" / "verify"
CUES = re.compile(
    r"evaluation|benchmark|graded|grader|hidden test|golden|behave exactly like|every request exactly as|"
    r"cannot be told apart|reference implementation|time budget|\bhours?\b",
    re.IGNORECASE,
)
RELEASE_OF = {"A": "15.0.0", "B": "15.1.0", "C": "15.2.0"}


def read_build(build: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in [RUNS / f"{build}.out", *sorted(RUNS.glob(f"{build}.*.out"))]:
        if f.exists():
            for line in f.read_text(errors="replace").splitlines():
                cid, _, result = line.partition("\t")
                out[cid] = result
    return out


def tier_c() -> set[str]:
    rows = (TASK / "scripts/pipeline/tiers.tsv").read_text().splitlines()[1:]
    return {r.split("\t")[0] for r in rows if r and r.split("\t")[1] == "C"}


def units_table() -> dict[str, dict[str, str]]:
    rows = (TASK / "scripts/pipeline/units.tsv").read_text().splitlines()
    head = rows[0].split("\t")
    return {
        r["unit"]: r
        for r in (dict(zip(head, x.split("\t"), strict=True)) for x in rows[1:] if x)
    }


def verify_result(name: str) -> dict:
    d = VERIFY / name
    reward = (
        (d / "reward.txt").read_text().strip() if (d / "reward.txt").exists() else None
    )
    metrics = (
        json.loads((d / "metrics.json").read_text())
        if (d / "metrics.json").exists()
        else {}
    )
    return {"reward": reward, **{k: metrics.get(k) for k in ("D", "h_dual", "h_broad")}}


def inventory(selection: list[dict], cut: dict[str, str]) -> dict:
    graded = Counter(c["unit"] for c in selection if c["kind"] == "changed")
    notes = (TASK / "scripts/pipeline/notes_map.tsv").read_text().splitlines()[1:]
    missing = []
    for row in notes:
        note, _, units, _ = row.split("\t")
        if not any(graded.get(u, 0) >= 3 for u in units.split()) and not all(
            u in cut for u in units.split()
        ):
            missing.append(note)
    return {
        "notes": len(notes),
        "graded_units": len(graded),
        "cut_units": cut,
        "notes_without_graded_unit_or_recorded_cut": missing,
        "pass": not missing,
    }


def kill_matrix(selection: list[dict], units: dict[str, dict[str, str]]) -> dict:
    changed = defaultdict(list)
    for c in selection:
        if c["kind"] == "changed":
            changed[c["unit"]].append(c)
    rel = {w: read_build(f"rel-{v}") for w, v in RELEASE_OF.items()}
    own, cross = {}, {}
    for u, cases in changed.items():
        rk = read_build(f"rk-{u}")
        if not rk:
            own[u] = None
            continue
        own[u] = sum(rk.get(c["cid"]) != c["gold"]["15.2.0"] for c in cases)
    for j in units:
        rk = read_build(f"rk-{j}")
        if not rk:
            continue
        base = rel[units[j]["window"]]
        for u, cases in changed.items():
            if u == j:
                continue
            hits = sum(rk.get(c["cid"]) != base.get(c["cid"]) for c in cases)
            if hits:
                cross[f"{j}->{u}"] = hits
    small = {u: len(v) for u, v in changed.items() if len(v) < 3}
    return {
        "units": len(changed),
        "min_cases": min((len(v) for v in changed.values()), default=0),
        "units_below_3": small,
        "own_revert_kills_short": {
            u: f"{k}/{len(changed[u])}"
            for u, k in own.items()
            if k is not None and k < len(changed[u])
        },
        "cross_kills": cross,
        "pass": not small and not cross,
    }


def band(selection: list[dict], name: str = "mut-W") -> dict:
    out = read_build(name)
    units, duals, broad = defaultdict(list), defaultdict(list), []
    for c in selection:
        ok = out.get(c["cid"]) == c["gold"]["15.2.0"]
        (
            units[c["unit"]]
            if c["kind"] == "changed"
            else duals[c["unit"]]
            if c["kind"] == "dual"
            else broad
        ).append(ok)
    d = sum(sum(v) / len(v) for v in units.values()) / len(units) if units else 0
    per = {u: sum(v) / len(v) for u, v in duals.items()}
    h_d = sum(per.values()) / len(per) if per else 1
    h_b = sum(broad) / len(broad) if broad else 1
    reward = d * h_d * (1 - 0.10 * (1 - h_b))
    return {
        "D": round(d, 4),
        "h_dual": round(h_d, 4),
        "h_broad": round(h_b, 4),
        "reward": round(reward, 4),
        "units_below_1": {
            u: round(sum(v) / len(v), 3) for u, v in units.items() if not all(v)
        },
        "neighbours_below_1": {u: round(h, 3) for u, h in sorted(per.items()) if h < 1},
        "units_with_neighbours": len(per),
    }


def band_v(selection: list[dict], name: str = "mut-V") -> dict:
    """The verification-gap proof: in band, D lost only on tier-C units, the gate essentially untouched."""
    r = band(selection, name)
    c = tier_c()
    r["tier_c_units"] = len(c)
    r["d_loss_outside_tier_c"] = {
        u: v for u, v in r["units_below_1"].items() if u not in c
    }
    r["pass"] = (
        0.60 <= r["reward"] <= 0.85
        and not r["d_loss_outside_tier_c"]
        and r["h_dual"] >= 0.98
        and r["h_broad"] >= 0.98
    )
    return r


def determinism() -> dict:
    first = VERIFY / "record" / "outputs.tsv"
    if not first.exists():
        return {"pass": False, "note": "no recording"}
    ref = first.read_bytes()
    same = {
        n: (VERIFY / n / "outputs.tsv").exists()
        and (VERIFY / n / "outputs.tsv").read_bytes() == ref
        for n in ("record-2", "record-3", "record-1cpu")
    }
    return {"identical": same, "cases": ref.count(b"\n"), "pass": all(same.values())}


def cue_sweep() -> dict:
    hits = []
    for path in [TASK / "instruction.md", *sorted((TASK / "environment").rglob("*"))]:
        if path.name == "prune_tree.sh":
            continue  # it names upstream's speed-test wiring to remove it; the image build deletes it after use
        if (
            path.is_file()
            and path.suffix in (".md", ".sh", "", ".txt")
            or path.name == "Dockerfile"
        ):
            for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if CUES.search(line):
                    hits.append(f"{path.relative_to(TASK)}:{n}: {line.strip()[:100]}")
    return {"hits": hits, "pass": not hits}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("selection", type=Path)
    p.add_argument("--cut", type=Path, help="JSON of units not graded, with reasons")
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    selection = [json.loads(x) for x in args.selection.read_text().splitlines() if x]
    cut = json.loads(args.cut.read_text()) if args.cut else {}
    units = units_table()
    report = {
        "1_inventory": inventory(selection, cut),
        "2_kill_matrix": kill_matrix(selection, units),
        "3_stub_zoo": {
            **{
                n: verify_result(n)
                for n in (
                    "nop",
                    "stub-comments",
                    "stub-refactor",
                    "stub-nobuild",
                    "stub-empty",
                    "stub-abort",
                    "stub-noop-api",
                )
            },
            "R_all (pipeline)": band(selection, "rk-ALL"),
        },
        "4_oracle_nop": {n: verify_result(n) for n in ("oracle", "nop", "base-14.3.0")},
        "5_determinism": determinism(),
        "8_robustness": {
            n: verify_result(n)
            for n in ("robust", "hostile", "slow", "hang", "flood", "fault")
        },
        "6_cue_words": cue_sweep(),
        "12_band": {
            "V (pipeline)": band_v(selection),
            "V (verifier)": verify_result("V"),
            "W, secondary bound (pipeline)": band(selection, "mut-W"),
            "W (verifier)": verify_result("W"),
            "W_literal (pipeline)": band(selection, "mut-Wlit"),
            "R_unbuilt, F4 and F5 (pipeline)": band(selection, "mut-Ru"),
        },
    }
    text = json.dumps(report, indent=1)
    print(text)
    if args.json:
        args.json.write_text(text)


if __name__ == "__main__":
    main()
