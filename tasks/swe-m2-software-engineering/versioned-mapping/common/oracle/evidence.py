"""Reconcile persistent changes with independent per-visit witnesses."""

from collections import defaultdict
import hashlib
from pathlib import Path

from .maps import OCCUPIED, FREE, json_bytes, observations, parse_cell, read_map, read_object, read_visit, vector, write_bytes


def propose(base: Path, evidence: Path, output: Path) -> None:
    """Write a deterministic site update whose votes can be inspected per cell."""
    grid, cells = read_map(base)
    config = read_object(evidence)
    entries, protected_cells = config.get("visits"), config.get("protected_cells")
    if not isinstance(entries, list) or not isinstance(protected_cells, list):
        raise ValueError("Provide visits and protected_cells arrays")
    protected = {parse_cell(cell, grid) for cell in protected_cells}
    seen: set[str] = set()
    support = defaultdict(lambda: {FREE: [], OCCUPIED: []})
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("visit"), str) or not entry["visit"]:
            raise ValueError("Invalid registered visit")
        placement = vector(entry.get("world_from_visit"), 3, "world_from_visit")
        visit = read_visit(evidence.parent / entry["visit"])
        if visit.id in seen:
            raise ValueError("Duplicate visit ID")
        seen.add(visit.id)
        free, occupied = observations(grid, visit, placement)
        for cell in free - occupied - protected:
            support[cell][FREE].append(visit.id)
        for cell in occupied - free - protected:
            support[cell][OCCUPIED].append(visit.id)

    changes = []
    for cell, votes in sorted(support.items(), key=lambda row: (row[0][1], row[0][0])):
        before = cells.get(cell, "unknown")
        for after, opposite in ((FREE, OCCUPIED), (OCCUPIED, FREE)):
            if before != after and len(votes[after]) >= 2 and not votes[opposite]:
                changes.append({"cell": list(cell), "from": before, "to": after, "support": sorted(votes[after])})
    write_bytes(output, json_bytes({
        "schema_version": 1, "base_sha256": hashlib.sha256(base.read_bytes()).hexdigest(), "changes": changes,
    }))
