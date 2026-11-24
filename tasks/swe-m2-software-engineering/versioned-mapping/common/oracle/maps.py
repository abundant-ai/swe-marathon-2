"""Parse visits and integrate exact ray evidence into a metric occupancy grid."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import tempfile
from typing import Any


Cell = tuple[int, int]
Pose = tuple[float, float, float]
FREE, OCCUPIED = "free", "occupied"


@dataclass(frozen=True)
class Grid:
    """Half-open rectangular grid with metric origin and square cells."""

    width: int
    height: int
    resolution: float
    origin: tuple[float, float]

    def contains(self, cell: Cell) -> bool:
        """Return whether column and row address a cell inside this grid."""
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def as_json(self) -> dict[str, Any]:
        """Export the four public geometry fields."""
        return {
            "width": self.width, "height": self.height,
            "resolution_m": self.resolution, "origin_m": list(self.origin),
        }

    def center(self, cell: Cell) -> tuple[float, float]:
        """Return the center of a cell in site metres."""
        return tuple(self.origin[axis] + (coordinate + 0.5) * self.resolution
                     for axis, coordinate in enumerate(cell))


@dataclass(frozen=True)
class Scan:
    """One sensor pose and the scan's relative beam directions."""

    pose: Pose
    beams: tuple[tuple[float, float, bool], ...]


@dataclass(frozen=True)
class Visit:
    """Named set of scans sharing the same coordinate frame."""

    id: str
    scans: tuple[Scan, ...]


def read_object(path: Path) -> dict[str, Any]:
    """Read a JSON object without interpreting any path fields."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def write_bytes(path: Path, content: bytes) -> None:
    """Atomically replace an output in its own filesystem."""
    with tempfile.TemporaryDirectory(dir=path.parent, prefix=".mapping-") as temporary:
        staged = Path(temporary) / "output"
        staged.write_bytes(content)
        staged.replace(path)


def json_bytes(value: object) -> bytes:
    """Encode a stable, finite JSON object followed by a newline."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def finite(value: object, label: str) -> float:
    """Read an ordinary finite JSON number, rejecting Boolean values."""
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be finite")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def vector(value: object, length: int, label: str) -> tuple[float, ...]:
    """Read exactly length finite coordinates in their given order."""
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"Expected {length} coordinates for {label}")
    return tuple(finite(piece, label) for piece in value)


def parse_grid(value: dict[str, Any]) -> Grid:
    """Read the shared grid geometry from an input or map object."""
    width, height = value.get("width"), value.get("height")
    if type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise ValueError("Grid dimensions must be positive integers")
    resolution = finite(value.get("resolution_m"), "resolution_m")
    if resolution <= 0:
        raise ValueError("resolution_m must be positive")
    return Grid(width, height, resolution, vector(value.get("origin_m"), 2, "origin_m"))


def parse_cell(value: object, grid: Grid) -> Cell:
    """Read a pair of integer coordinates within this grid."""
    if not isinstance(value, list) or len(value) != 2 or any(type(x) is not int for x in value):
        raise ValueError("Expected a column and row")
    cell = tuple(value)
    if not grid.contains(cell):
        raise ValueError("Cell outside grid")
    return cell


def read_map(path: Path) -> tuple[Grid, dict[Cell, str]]:
    """Load a version-one map and reject repeated or malformed cells."""
    value = read_object(path)
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported map schema")
    grid = parse_grid(value)
    entries = value.get("cells")
    if not isinstance(entries, list):
        raise ValueError("Expected map cells")
    cells = {}
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 3 or entry[2] not in (FREE, OCCUPIED):
            raise ValueError("Invalid map cell")
        cell = parse_cell(entry[:2], grid)
        if cell in cells:
            raise ValueError("Duplicate map cell")
        cells[cell] = entry[2]
    return grid, cells


def parse_beam(value: object) -> tuple[float, float, bool]:
    """Read a beam angle, positive finite range and hit flag."""
    if not isinstance(value, list) or len(value) != 3 or type(value[2]) is not bool:
        raise ValueError("Expected one angle, one range and a Boolean hit")
    angle, distance = finite(value[0], "angle"), finite(value[1], "range")
    if distance <= 0:
        raise ValueError("Beam range must be positive")
    return angle, distance, value[2]


def read_visit(path: Path) -> Visit:
    """Read scans in their original visit order."""
    value = read_object(path)
    id_, items = value.get("id"), value.get("scans")
    if not isinstance(id_, str) or not id_ or not isinstance(items, list) or not items:
        raise ValueError("A visit needs an ID and at least one scan")
    scans = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("beams"), list) or not item["beams"]:
            raise ValueError("A scan needs a pose and beams")
        scans.append(Scan(vector(item.get("pose"), 3, "pose"), tuple(map(parse_beam, item["beams"]))))
    return Visit(id_, tuple(scans))


def to_site(pose: Pose, x: float, y: float) -> tuple[float, float]:
    """Apply a local-to-site rotation and translation to one planar point."""
    u, v, yaw = pose
    co, si = math.cos(yaw), math.sin(yaw)
    return u + co * x - si * y, v + si * x + co * y


def ray_cells(grid: Grid, x: float, y: float, dx: float, dy: float) -> set[Cell]:
    """Find grid cell interiors crossed by a finite ray.

    Clip to the grid in parametric coordinates, split at its grid lines, and
    classify an interior representative of each open interval.
    """
    beginnings = ((x - grid.origin[0]) / grid.resolution, (y - grid.origin[1]) / grid.resolution)
    directions = (dx / grid.resolution, dy / grid.resolution)
    begin, end = 0.0, 1.0
    for axis, limit in enumerate((grid.width, grid.height)):
        origin, delta = beginnings[axis], directions[axis]
        if abs(delta) <= math.ulp(origin):
            if not 0 <= origin < limit or origin == math.floor(origin):
                return set()
            continue
        times = sorted((-origin / delta, (limit - origin) / delta))
        begin, end = max(begin, times[0]), min(end, times[1])
    if begin >= end:
        return set()

    cuts = [begin, end]
    for origin, delta in zip(beginnings, directions, strict=True):
        if abs(delta) <= math.ulp(origin):
            continue
        low, high = sorted((origin + begin * delta, origin + end * delta))
        cuts.extend((line - origin) / delta for line in range(math.floor(low) + 1, math.ceil(high)))
    cuts.sort()
    cells = set()
    for first, last in zip(cuts, cuts[1:]):
        if not begin <= first < last <= end or last - first <= 4 * math.ulp(last):
            continue
        middle = (first + last) / 2
        cell = tuple(math.floor(origin + middle * delta)
                     for origin, delta in zip(beginnings, directions, strict=True))
        if grid.contains(cell):
            cells.add(cell)
    return cells


def observations(grid: Grid, visit: Visit, placement: Pose = (0, 0, 0)) -> tuple[set[Cell], set[Cell]]:
    """Return separate free and occupied witnesses for a registered visit."""
    free: set[Cell] = set()
    hits: set[Cell] = set()
    for scan in visit.scans:
        x, y = to_site(placement, *scan.pose[:2])
        for beam_angle, distance, hit in scan.beams:
            angle = scan.pose[2] + placement[2] + beam_angle
            dx, dy = distance * math.cos(angle), distance * math.sin(angle)
            observed = ray_cells(grid, x, y, dx, dy)
            if hit:
                cell = (
                    math.floor((x + dx - grid.origin[0]) / grid.resolution),
                    math.floor((y + dy - grid.origin[1]) / grid.resolution),
                )
                if grid.contains(cell):
                    hits.add(cell)
                    observed.discard(cell)
            free.update(observed)
    return free, hits


def map_document(grid: Grid, cells: dict[Cell, str]) -> dict[str, Any]:
    """Serialize observed cells in row-major order, leaving unknown cells implicit."""
    return {"schema_version": 1, **grid.as_json(),
            "cells": [[x, y, cells[x, y]] for x, y in sorted(cells, key=lambda cell: (cell[1], cell[0]))]}


def build(grid_path: Path, visit_path: Path, output: Path) -> None:
    """Build and atomically save a map from one surveyed visit."""
    grid = parse_grid(read_object(grid_path))
    free, occupied = observations(grid, read_visit(visit_path))
    cells = dict.fromkeys(free, FREE) | dict.fromkeys(occupied, OCCUPIED)
    write_bytes(output, json_bytes(map_document(grid, cells)))
