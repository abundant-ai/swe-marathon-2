"""Window-edge coverage of a private case set (QA pass 02's check).

For every replay case, read the windows its policy files name (`within <n><unit>`; a template
slot such as `?w` is left out) and the times in its trace, and count the pairs of events whose gap
is within one second of a window: the past event at the window's edge, the later one a decision
event of the bundle's event schema. Reports, per bundle group, how many bundles with a window have
at least one such pair, and how many have a decision past the end of a window (the window lapses).

Usage: python3 -I window_edges.py PRIVATE_DIR [REPORT.json]
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
WINDOW = re.compile(r"\bwithin\s+(\d{1,12})([smhdw])\b")
STAMP = re.compile(r"^@(-?\d+)\s")
KIND = re.compile(r'"::(\w+)\(')
DECISION = re.compile(r"\bdecision\s+event\s+\S*?::(\w+)")
# Longer windows are overflow probes, not edges a trace could reach.
LONGEST = 30 * 86400


def group(bundle: str) -> str:
    if re.match(r"g\d+_", bundle):
        return "generated " + bundle.split("_", 1)[1]
    return re.match(r"[a-z]*", bundle).group(0) or bundle


def windows(folder: Path, names: list[str]) -> set[int]:
    found: set[int] = set()
    for name in names:
        path = folder / name
        if path.suffix == ".dw" and path.is_file():
            for n, unit in WINDOW.findall(path.read_text(errors="replace")):
                seconds = int(n) * UNITS[unit]
                if 0 < seconds <= LONGEST:
                    found.add(seconds)
    return found


def decisions(folder: Path, names: list[str]) -> set[str]:
    kinds: set[str] = set()
    for name in names:
        path = folder / name
        if path.suffix == ".dwschema" and path.is_file():
            kinds.update(DECISION.findall(path.read_text(errors="replace")))
    return kinds or {"request", "attempt"}


def events(path: Path) -> list[tuple[int, str]]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        m = STAMP.match(line)
        if m:
            kinds = KIND.findall(line)
            out.append((int(m.group(1)), kinds[-1] if kinds else ""))
    return out


def main() -> int:
    private = Path(sys.argv[1])
    cases = [
        json.loads(x)
        for x in (private / "cases.jsonl").read_text().splitlines()
        if x.strip()
    ]
    per_bundle: dict[str, dict] = {}
    for c in cases:
        if c["args"][:1] != ["replay"] or "--trace" not in c["args"]:
            continue
        trace = c["args"][c["args"].index("--trace") + 1]
        if trace == "-":
            continue
        folder = private / "bundles" / c["bundle"]
        names = c.get("files") or [p.name for p in folder.iterdir()]
        wins = windows(folder, names)
        if not wins or not (folder / trace).is_file():
            continue
        decide = decisions(folder, names)
        evs = events(folder / trace)
        edge = lapsed = 0
        for j, (tj, kind) in enumerate(evs):
            if kind not in decide:
                continue
            for ti, _ in evs[:j]:
                gap = tj - ti
                if any(abs(gap - w) <= 1 for w in wins):
                    edge += 1
                if gap > min(wins):
                    lapsed += 1
        b = per_bundle.setdefault(
            c["bundle"], {"edge": 0, "lapsed": 0, "windows": set()}
        )
        b["edge"] = max(b["edge"], edge)
        b["lapsed"] = max(b["lapsed"], lapsed)
        b["windows"] |= wins
    groups: dict[str, dict] = defaultdict(
        lambda: {"bundles": 0, "with_edge": 0, "with_lapse": 0}
    )
    for bundle, b in per_bundle.items():
        g = groups[group(bundle)]
        g["bundles"] += 1
        g["with_edge"] += b["edge"] > 0
        g["with_lapse"] += b["lapsed"] > 0
    report = {
        "groups": dict(sorted(groups.items())),
        "without_edge": sorted(k for k, b in per_bundle.items() if not b["edge"]),
    }
    text = json.dumps(report, indent=1)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text + "\n")
    print(json.dumps(report["groups"], indent=1))
    print(f"bundles with a window and no edge pair: {len(report['without_edge'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
