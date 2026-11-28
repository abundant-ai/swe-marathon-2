"""What the working machine's hand-off hook recorded, checked against what arrived here.

The hook runs as root once the session is over: it stops and ends every process of `dev`, lists
them, probes whether public hosts answer, records every entry of /app/dogwood-rebuild with the
times it had then, applies the brief's copy rules to the tree (`listing.py`), and writes a
manifest of what is left, which is what the copy must deliver. Both files travel in their own
folder, apart from the tree.

Here, a missing manifest, or a tree that differs from it, means the copy did not deliver the
project: that is the evaluation's failure, never a score. An entry that changed at or after the
end of the work (the earlier of the moment public hosts answered again and the work's start plus
its time limit) is listed for review; it does not change the score.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import listing
from .contracts import EvaluationError

RECORDS = Path("/var/lib/dogwood-handoff/out")
SKEW = 0.5  # an entry this close before the end of the work counts as late
SHOWN = 50


@dataclass
class Handoff:
    state: str  # "listed", or why nothing is to be built ("refused", "missing")
    reason: str | None
    entries: int
    files: int
    bytes: int
    summary: dict = field(default_factory=dict)


def _load(path: Path) -> dict | None:
    try:
        with open(path, "rb") as f:
            data = json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def close(path: Path) -> None:
    """Make the record folder root's alone (the copy into this machine leaves it open)."""
    for p in (path.parent, path):
        try:
            os.lchown(p, 0, 0)
            os.chmod(p, 0o700)
        except OSError:
            pass


def _late(record: dict) -> dict:
    bound, origin = record.get("end_bound"), record.get("end_from")
    before = record.get("before") or []
    if not isinstance(bound, (int, float)):
        return {"end_bound": None, "end_from": origin, "late_entries": None}
    late = [
        e[0]
        for e in before
        if isinstance(e, list)
        and len(e) >= 5
        and isinstance(e[3], (int, float))
        and isinstance(e[4], (int, float))
        and max(e[3], e[4]) >= bound - SKEW
    ]
    return {
        "end_bound": bound,
        "end_from": origin,
        "late_entries": len(late),
        "late_paths": late[:SHOWN],
    }


def check(tree: Path, records: Path = RECORDS) -> Handoff:
    """Compare the arrived tree with the hook's manifest; summarise the hook's record."""
    manifest = _load(records / "manifest.json")
    record = _load(records / "record.json")
    if manifest is None:
        raise EvaluationError(
            f"no hand-off manifest arrived ({records / 'manifest.json'}): the delivery was not "
            "copied as recorded"
        )
    summary: dict = {"record": record is not None}
    if record is not None:
        summary.update(_late(record))
        for key in ("work_started", "netcheck", "kill", "egress_after", "changes_made"):
            if key in record:
                summary[key] = record[key]
        processes = record.get("processes")
        if isinstance(processes, list):
            summary["processes_found"] = len(processes)
            summary["processes"] = processes[:SHOWN]
    state = manifest.get("state")
    reason = manifest.get("reason")
    if state != "listed":
        return Handoff(str(state), reason, 0, 0, 0, summary)
    want = manifest.get("digest")
    entries = listing.listing(os.fsencode(tree)) if tree.is_dir() else []
    if listing.digest(entries) != want:
        listed = {e[0]: e for e in manifest.get("listing") or [] if isinstance(e, list)}
        here = {e[0]: e for e in entries}
        missing = sorted(set(listed) - set(here))
        extra = sorted(set(here) - set(listed))
        changed = sorted(p for p in set(listed) & set(here) if listed[p] != here[p])
        raise EvaluationError(
            "the delivered tree differs from the hand-off manifest: "
            f"{len(missing)} entries missing (e.g. {missing[:5]}), {len(extra)} extra "
            f"(e.g. {extra[:5]}), {len(changed)} changed (e.g. {changed[:5]})"
        )
    files, size = listing.totals(entries)
    return Handoff("listed", None, len(entries), files, size, summary)
