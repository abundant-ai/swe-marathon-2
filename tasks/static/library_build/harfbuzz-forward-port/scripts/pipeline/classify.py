"""Attribute swept candidates to units, report the per-unit yield, and write the selected cases privately.

Host side (`python3 -I scripts/pipeline/classify.py ...`); it reads only our own driver outputs and candidate
metadata, never downloaded files. Development tooling, never shipped.

A window-C candidate is a changed case of unit k when 15.1.0 and 15.2.0 differ, the base differs from 15.2.0, the
revert R_k gives 15.1.0's output, and every other built revert gives 15.2.0's. It is held fixed when the base and all
releases and reverts agree. Everything else is dropped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

FAMILY = {}


def load_units(path: Path) -> dict[str, dict[str, str]]:
    rows = path.read_text().splitlines()
    head = rows[0].split("\t")
    return {
        r["unit"]: r
        for r in (
            dict(zip(head, row.split("\t"), strict=True)) for row in rows[1:] if row
        )
    }


def read_out(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        cid, _, result = line.partition("\t")
        out[cid] = result
    return out


def classify(runs: Path, meta: Path, reverts: list[str]) -> tuple[list[dict], Counter]:
    base, t1, t2, t3 = (
        read_out(runs / f"rel-{v}.out")
        for v in ("14.3.0", "15.0.0", "15.1.0", "15.2.0")
    )
    rk = {u: read_out(runs / f"rk-{u}.out") for u in reverts}
    stats: Counter = Counter()
    rows = []
    for line in meta.read_text().splitlines():
        c = json.loads(line)
        cid = c["id"]
        outs = [base.get(cid), t1.get(cid), t2.get(cid), t3.get(cid)]
        if any(o is None or o.startswith("!") for o in outs):
            stats["error-or-missing"] += 1
            continue
        b, o1, o2, o3 = outs
        rv = {u: r.get(cid) for u, r in rk.items()}
        if b == o1 == o2 == o3 and all(v == o3 for v in rv.values()):
            c["class"] = "held" if c["kind"] != "broad" else "broad"
        elif o2 != o3 and b != o3:
            explains = [u for u, v in rv.items() if v == o2]
            others_ok = [u for u, v in rv.items() if u not in explains and v != o3]
            if len(explains) == 1 and not others_ok:
                c["class"] = "changed"
                c["attributed"] = explains[0]
            else:
                c["class"] = "unattributed"
        else:
            c["class"] = "other-window" if b != o3 else "unstable"
        c["gold"] = {"14.3.0": b, "15.0.0": o1, "15.1.0": o2, "15.2.0": o3}
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
    return {u: dict(v) for u, v in sorted(table.items())}


def opaque(cid: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{cid}".encode()).hexdigest()[:12]


def select(
    rows: list[dict],
    units: dict,
    seed: int,
    per_unit: int,
    duals: int,
    broad: int,
    salt: str,
) -> list[dict]:
    rng = random.Random(seed)
    by: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in rows:
        if c["class"] == "changed":
            by[("changed", c["attributed"])].append(c)
        elif c["class"] == "held":
            by[("dual", c["unit"])].append(c)
        elif c["class"] == "broad":
            by[("broad", "broad")].append(c)
    chosen = []
    for (kind, unit), items in sorted(by.items()):
        cap = {"changed": per_unit, "dual": duals, "broad": broad}[kind]
        rng.shuffle(items)
        for c in items[:cap]:
            fam = units[unit]["family"] if unit in units else "H"
            chosen.append(
                {
                    "id": opaque(c["id"], salt),
                    "cid": c["id"],
                    "unit": unit,
                    "family": fam,
                    "kind": kind,
                    "window": units[unit]["window"] if unit in units else "-",
                    "font": c["font"]
                    .replace("/dl/fonts/", "noto/")
                    .replace("/work/fonts/", "synth/"),
                    "idx": c["idx"],
                    "opts": c["opts"]
                    .replace("/dl/fonts/", "")
                    .replace("/work/fonts/", ""),
                    "text": ",".join(f"{cp:X}" for cp in c["text"]),
                    "gold": c["gold"],
                    "nb": c.get("nb", ""),
                }
            )
    return chosen


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
    p.add_argument("--duals", type=int, default=50)
    p.add_argument("--broad", type=int, default=600)
    args = p.parse_args()
    units = load_units(args.units)
    rows, stats = classify(args.runs, args.meta, args.reverts)
    report = {"classes": dict(stats), "yield": yields(rows)}
    print(json.dumps(report, indent=1))
    if args.select_to:
        chosen = select(
            rows,
            units,
            args.seed,
            args.per_unit,
            args.duals,
            args.broad,
            args.salt_file.read_text().strip() if args.salt_file else args.salt,
        )
        args.select_to.parent.mkdir(parents=True, exist_ok=True)
        with args.select_to.open("w") as fh:
            for c in chosen:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "selected": Counter(c["kind"] for c in chosen),
                    "file": str(args.select_to),
                }
            )
        )


if __name__ == "__main__":
    main()
