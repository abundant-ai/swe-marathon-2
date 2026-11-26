"""Attribute swept candidates to units, report the per-unit yield, and write the selected cases privately.

Host side (`python3 -I scripts/pipeline/classify.py ...`); it reads only our own driver outputs and candidate
metadata, never downloaded files. Development tooling, never shipped.

Builds: B = 14.3.0, T1 = 15.0.0, T2 = 15.1.0, T3 = 15.2.0; R_k = the release of unit k's window with k's commits
reverted; `regen-14.3.0` = 14.3.0 with its Unicode tables regenerated from the Unicode 18 files (unit 33 adds its
change forward instead of being reverted). Each build's outputs are `RUNS/<build>.out` (shaping driver) and
`RUNS/<build>.<driver>.out` (API drivers), merged by candidate id. `!nobuild` (a probe the build cannot compile) is
an ordinary output value; any other `!` output drops the candidate.

A candidate is
- **changed**, attributed to unit k, when B differs from T3, and in the last window s where the output changes
  (T_{s-1} differs from T_s) exactly one of the window's units explains it: its revert gives T_{s-1} (for unit 33:
  the regenerated base gives T_s), while every other revert of the window gives T_s;
- **held** when B, T1, T2, T3 and every revert agree (a dual when it sits on a named boundary of its unit, broad
  when it came from the broad generator);
- **flapping** when repeated base runs disagree (dropped);
- dropped otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

RELEASES = ("14.3.0", "15.0.0", "15.1.0", "15.2.0")
WINDOW_INDEX = {"A": 1, "B": 2, "C": 3}
ADDERS = {"33": "regen-14.3.0"}  # units attributed by adding their change to the base
# Labels of the spike's generators that mean "inside the stated condition" (newer generators use "in").
LEGACY_INSIDE = {
    "1": {"letter", "mark", "latin"},
    "5": {"start"},
    "21": {"kern-gpos-novkrn-v-ttb-vkrn", "kern-nogpos-v-ttb-vkrn"},
    "22": {"trak-stat-ttb", "trak-stat-btt"},
    "23": {"kerx-gsub-gpos-nokern"},
}


def inside(c: dict) -> bool:
    """True when the candidate sits inside its unit's stated condition (unlabelled candidates count as inside)."""
    nb = c.get("nb", "")
    return nb in ("in", "") or nb in LEGACY_INSIDE.get(c["unit"], ())


def left_out(c: dict) -> bool:
    """Candidates a generator marks `x:...`: swept for the record, never graded either way."""
    return c.get("nb", "").startswith("x:")


def relative_fonts(text: str) -> str:
    return text.replace("/dl/fonts/", "noto/").replace("/work/fonts/", "synth/")


def load_units(path: Path) -> dict[str, dict[str, str]]:
    rows = path.read_text().splitlines()
    head = rows[0].split("\t")
    return {
        r["unit"]: r
        for r in (
            dict(zip(head, row.split("\t"), strict=True)) for row in rows[1:] if row
        )
    }


def read_build(runs: Path, build: str) -> dict[str, str] | None:
    """Every output of one build, all drivers merged; None when the build has no output at all."""
    files = [runs / f"{build}.out", *sorted(runs.glob(f"{build}.*.out"))]
    found = [f for f in files if f.exists()]
    if not found:
        return None
    out: dict[str, str] = {}
    for f in found:
        for line in f.read_text(errors="replace").splitlines():
            cid, _, result = line.partition("\t")
            out[cid] = result
    return out


def classify(
    runs: Path, meta: Path, units: dict[str, dict[str, str]], reverts: list[str]
) -> tuple[list[dict], Counter]:
    rel = [read_build(runs, f"rel-{v}") for v in RELEASES]
    if any(r is None for r in rel):
        raise SystemExit("a release build has no outputs")
    base_reruns = [
        r for r in (read_build(runs, f"rel-14.3.0-run{i}") for i in (2, 3)) if r
    ]
    rk = {u: read_build(runs, f"rk-{u}") for u in reverts}
    missing = sorted(u for u, r in rk.items() if r is None)
    if missing:
        raise SystemExit(f"reverts without outputs: {missing}")
    adders = {u: read_build(runs, b) for u, b in ADDERS.items()}
    by_window: dict[int, list[str]] = defaultdict(list)
    for u in reverts:
        by_window[WINDOW_INDEX[units[u]["window"]]].append(u)
    for u, outputs in adders.items():
        if outputs is not None:
            by_window[WINDOW_INDEX[units[u]["window"]]].append(u)
    stats: Counter = Counter()
    rows = []
    for line in meta.read_text().splitlines():
        c = json.loads(line)
        cid = c["id"]
        outs = [r.get(cid) for r in rel]
        rv = {u: r.get(cid) for u, r in rk.items()}
        ad = {u: (r.get(cid) if r else None) for u, r in adders.items()}
        everything = [*outs, *rv.values()]
        if any(o is None for o in everything) or any(
            o.startswith("!") and o != "!nobuild" for o in everything
        ):
            stats["error-or-missing"] += 1
            continue
        if any(r.get(cid) != outs[0] for r in base_reruns):
            stats["flapping"] += 1
            continue
        c["gold"] = dict(zip(RELEASES, outs, strict=True))
        if len(set(outs)) == 1 and all(v == outs[0] for v in rv.values()):
            c["class"] = "broad" if c["kind"] == "broad" else "held"
        elif outs[0] == outs[3]:
            c["class"] = "returns"  # changes and changes back: nothing to grade
        else:
            s = max(i for i in (1, 2, 3) if outs[i - 1] != outs[i])
            prev, now = outs[s - 1], outs[s]
            explains, spoilers = [], []
            for u in by_window.get(s, []):
                if u in adders:
                    hit = ad[u] == now
                    if hit:
                        explains.append(u)
                    continue
                if rv[u] == prev:
                    explains.append(u)
                elif rv[u] != now:
                    spoilers.append(u)
            if len(explains) == 1 and not spoilers:
                c["class"] = "changed"
                c["attributed"] = explains[0]
                c["window_changed"] = "ABC"[s - 1]
            else:
                c["class"] = "unattributed"
        stats[c["class"]] += 1
        rows.append(c)
    return rows, stats


def yields(rows: list[dict]) -> dict[str, dict[str, int]]:
    table: dict[str, Counter] = defaultdict(Counter)
    for c in rows:
        table[c["unit"]]["candidates"] += 1
        table[c["unit"]][c["class"]] += 1
        if c["class"] == "changed":
            table[c["attributed"]]["attributed"] += 1
            if c["attributed"] != c["unit"]:
                table[c["unit"]]["attributed-elsewhere"] += 1
            elif not inside(c):
                table[c["unit"]]["changed-off-inside"] += 1
        if c["class"] == "held" and not inside(c):
            table[c["unit"]]["boundary-held"] += 1
    return {u: dict(v) for u, v in sorted(table.items())}


def opaque(cid: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{cid}".encode()).hexdigest()[:12]


def spread(items: dict[str, list[dict]], total: int) -> list[dict]:
    """Take about `total` items, as evenly as the strata allow (a stratum short of its share leaves it to others)."""
    pools = {k: list(v) for k, v in sorted(items.items()) if v}
    chosen: list[dict] = []
    while pools and len(chosen) < total:
        for k in list(pools):
            if len(chosen) >= total:
                break
            chosen.append(pools[k].pop())
            if not pools[k]:
                del pools[k]
    return chosen


def select(
    rows: list[dict],
    units: dict[str, dict[str, str]],
    seed: int,
    per_unit: int,
    duals: int,
    broad: int,
    salt: str,
    floor: int,
) -> tuple[list[dict], dict[str, str]]:
    """Changed cases per unit (at most `per_unit`), duals per unit spread over its boundaries, broad cases.

    Units with fewer than `floor` changed cases are not graded; they are returned with the reason.
    """
    rng = random.Random(seed)
    changed: dict[str, list[dict]] = defaultdict(list)
    held: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    broad_rows: list[dict] = []
    for c in rows:
        if left_out(c):
            continue
        if c["class"] == "changed" and inside(c):
            changed[c["attributed"]].append(c)
        elif c["class"] == "held" and not inside(c):
            held[c["unit"]][c["nb"]].append(c)
        elif c["class"] == "broad":
            broad_rows.append(c)
    cut = {
        u: f"{len(changed.get(u, []))} attributable changed cases inside the stated condition"
        for u in units
        if len(changed.get(u, [])) < floor
    }
    chosen: list[tuple[str, dict]] = []
    for u, items in sorted(changed.items()):
        if u in cut:
            continue
        rng.shuffle(items)
        chosen += [("changed", c) for c in items[:per_unit]]
    for u, strata in sorted(held.items()):
        if u in cut:
            continue
        for pool in strata.values():
            rng.shuffle(pool)
        chosen += [("dual", c) for c in spread(strata, duals)]
    rng.shuffle(broad_rows)
    chosen += [("broad", c) for c in broad_rows[:broad]]
    out = []
    for kind, c in chosen:
        unit = c["attributed"] if kind == "changed" else c["unit"]
        out.append(
            {
                "id": opaque(c["id"], salt),
                "cid": c["id"],
                "unit": unit,
                "family": units[unit]["family"] if unit in units else "H",
                "kind": kind,
                "window": units[unit]["window"] if unit in units else "-",
                "drv": c.get("drv", "shape"),
                "font": relative_fonts(c["font"]),
                "idx": c["idx"],
                "opts": relative_fonts(c["opts"]),
                "text": ",".join(f"{v:X}" for v in c["text"]),
                "gold": c["gold"],
                "nb": c.get("nb", ""),
            }
        )
    return out, cut


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("runs", type=Path)
    p.add_argument("meta", type=Path)
    p.add_argument("units", type=Path)
    p.add_argument("--reverts", nargs="+", required=True)
    p.add_argument("--select-to", type=Path)
    p.add_argument("--seed", type=int, default=20261127)
    p.add_argument("--salt", default="")
    p.add_argument(
        "--salt-file", type=Path, help="read the salt from this private file"
    )
    p.add_argument("--per-unit", type=int, default=60)
    p.add_argument("--duals", type=int, default=30)
    p.add_argument("--broad", type=int, default=600)
    p.add_argument("--floor", type=int, default=3)
    p.add_argument("--rows-to", type=Path, help="write every classified row here")
    args = p.parse_args()
    units = load_units(args.units)
    rows, stats = classify(args.runs, args.meta, units, args.reverts)
    report = {"classes": dict(stats), "yield": yields(rows)}
    print(json.dumps(report, indent=1))
    if args.rows_to:
        with args.rows_to.open("w") as fh:
            for c in rows:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
    if args.select_to:
        chosen, cut = select(
            rows,
            units,
            args.seed,
            args.per_unit,
            args.duals,
            args.broad,
            args.salt_file.read_text().strip() if args.salt_file else args.salt,
            args.floor,
        )
        args.select_to.parent.mkdir(parents=True, exist_ok=True)
        with args.select_to.open("w") as fh:
            for c in chosen:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "selected": Counter(c["kind"] for c in chosen),
                    "units_graded": len(
                        {c["unit"] for c in chosen if c["kind"] == "changed"}
                    ),
                    "not_graded": cut,
                    "file": str(args.select_to),
                }
            )
        )


if __name__ == "__main__":
    main()
