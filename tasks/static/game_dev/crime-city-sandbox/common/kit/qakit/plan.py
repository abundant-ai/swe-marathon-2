"""Read a city plan (city-plan/1, design/plan/FORMAT.md) and resolve anchors to points.

The kit reads the plan on its own, so where things should be is known without asking the
game. Supported anchors: a point [x, y, z]; {"poi": id} and {"poi": id, "front_m": d};
{"lane": id, "s": s}; {"sidewalk": id, "s": s}; {"intersection": id, "approach": k,
"before_m": d, "lane_index": i}. Headings are degrees clockwise from north (north is -z,
east is +x).
"""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path


class AnchorError(ValueError):
    """An anchor that the plan cannot resolve (unknown id, out of range, unsupported kind)."""


@dataclass(frozen=True)
class Placement:
    """Where an anchor puts something.

    Attributes:
        p: World position [x, y, z].
        heading_deg: Heading in degrees clockwise from north, or None when the anchor
            gives none (a bare point).
    """

    p: tuple[float, float, float]
    heading_deg: float | None


def heading_of(dx: float, dz: float) -> float:
    """Heading in degrees (0 north = -z, 90 east = +x) of a horizontal direction."""
    return math.degrees(math.atan2(dx, -dz)) % 360.0


class Plan:
    """A loaded plan with lane geometry."""

    def __init__(self, data: dict) -> None:
        """Index a parsed plan.

        Args:
            data: The plan's JSON object (format "city-plan/1").

        Raises:
            ValueError: The format is not city-plan/1.
        """
        if data.get("format") != "city-plan/1":
            raise ValueError("not a city-plan/1 plan")
        self.data = data
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = {e["id"]: e for e in data["edges"]}
        self.pois = {p["id"]: p for p in data["pois"]}
        self.intersections = {i["id"]: i for i in data["intersections"]}
        self.sidewalks = {s["id"]: s for s in data.get("sidewalks", [])}
        self.lanes = {}
        for e in data["edges"]:
            for ln in e["lanes"]:
                self.lanes[ln["id"]] = (e, ln)

    @classmethod
    def load(cls, path: Path) -> Plan:
        """Read a plan file."""
        return cls(json.loads(Path(path).read_text()))

    def centreline(self, edge: dict) -> list[tuple[float, float, float]]:
        """The edge's centreline from node a to node b, through its points."""
        a = self.nodes[edge["a"]]["p"]
        b = self.nodes[edge["b"]]["p"]
        pts = [tuple(a)] + [tuple(p) for p in edge.get("points", [])] + [tuple(b)]
        return [(float(x), float(y), float(z)) for x, y, z in pts]

    def _leg(self, node: str, edge_id: str) -> dict:
        """The leg of node's intersection that belongs to an edge."""
        for leg in self.intersections[node]["legs"]:
            if leg["edge"] == edge_id:
                return leg
        raise AnchorError(f"intersection {node} has no leg on {edge_id}")

    def lane_offset(self, edge: dict, lane: dict) -> float:
        """Signed sideways offset of a lane centre, to the right of its direction of travel."""
        w = float(edge["lane_width_m"])
        if edge.get("oneway"):
            n = len(edge["lanes"])
            return (lane["index"] + 0.5 - n / 2.0) * w
        return (lane["index"] + 0.5) * w

    def lane_length(self, lane_id: str) -> float:
        """Length of a lane from the start box to the stop line, in metres."""
        edge, lane = self.lanes[lane_id]
        pts = self.centreline(edge)
        total = sum(
            math.dist((p[0], p[2]), (q[0], q[2])) for p, q in itertools.pairwise(pts)
        )
        start, end = (
            (edge["a"], edge["b"]) if lane["dir"] == "ab" else (edge["b"], edge["a"])
        )
        box = float(self._leg(start, edge["id"])["box_m"])
        stop = float(self._leg(end, edge["id"])["approach"]["stop_line_m"])
        return total - box - stop

    def lane_point(self, lane_id: str, s: float) -> Placement:
        """The lane point at s (metres from the lane start) and the lane heading there.

        Raises:
            AnchorError: Unknown lane, or s outside [0, lane length].
        """
        if lane_id not in self.lanes:
            raise AnchorError(f"unknown lane {lane_id}")
        edge, lane = self.lanes[lane_id]
        length = self.lane_length(lane_id)
        if not -1e-6 <= s <= length + 1e-6:
            raise AnchorError(f"s={s} outside lane {lane_id} (length {length:.2f})")
        pts = self.centreline(edge)
        if lane["dir"] == "ba":
            pts = pts[::-1]
        start = edge["a"] if lane["dir"] == "ab" else edge["b"]
        along = float(self._leg(start, edge["id"])["box_m"]) + s
        for p, q in itertools.pairwise(pts):
            seg = math.dist((p[0], p[2]), (q[0], q[2]))
            if along <= seg or q == pts[-1]:
                t = 0.0 if seg == 0 else min(1.0, along / seg)
                dx, dz = (q[0] - p[0]) / seg, (q[2] - p[2]) / seg
                off = self.lane_offset(edge, lane)
                # right of travel: rotate the direction 90 degrees clockwise seen from above
                rx, rz = -dz, dx
                x = p[0] + (q[0] - p[0]) * t + rx * off
                y = p[1] + (q[1] - p[1]) * t
                z = p[2] + (q[2] - p[2]) * t + rz * off
                return Placement((x, y, z), heading_of(dx, dz))
            along -= seg
        raise AnchorError(f"lane {lane_id} has no geometry")

    def sidewalk_point(self, sidewalk_id: str, s: float) -> Placement:
        """The point at s along a sidewalk ring (wrapping), at its elevation, and the ring heading.

        Raises:
            AnchorError: Unknown sidewalk.
        """
        sw = self.sidewalks.get(sidewalk_id)
        if sw is None:
            raise AnchorError(f"unknown sidewalk {sidewalk_id}")
        ring = [(float(x), float(z)) for x, z in sw["ring"]]
        pairs = list(zip(ring, ring[1:] + ring[:1]))
        total = sum(math.dist(a, b) for a, b in pairs)
        along = s % total
        for i, (a, b) in enumerate(pairs):
            seg = math.dist(a, b)
            if along <= seg or i == len(pairs) - 1:
                t = 0.0 if seg == 0 else min(1.0, along / seg)
                dx, dz = (b[0] - a[0]) / seg, (b[1] - a[1]) / seg
                x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                return Placement((x, float(sw["elevation_m"]), z), heading_of(dx, dz))
            along -= seg
        raise AnchorError(f"sidewalk {sidewalk_id} has no geometry")

    def resolve(self, anchor: object) -> Placement:
        """Resolve an anchor (see the module docstring).

        Raises:
            AnchorError: The anchor is malformed, unknown or not supported here.
        """
        if isinstance(anchor, list) and len(anchor) == 3:
            return Placement(tuple(float(c) for c in anchor), None)
        if not isinstance(anchor, dict):
            raise AnchorError(f"not an anchor: {anchor!r}")
        if "poi" in anchor:
            poi = self.pois.get(anchor["poi"])
            if poi is None:
                raise AnchorError(f"unknown point of interest {anchor['poi']}")
            h = float(poi.get("heading_deg", 0.0))
            x, y, z = (float(c) for c in poi["p"])
            d = float(anchor.get("front_m", 0.0))
            r = math.radians(h)
            return Placement((x + math.sin(r) * d, y, z - math.cos(r) * d), h)
        if "lane" in anchor:
            return self.lane_point(anchor["lane"], float(anchor.get("s", 0.0)))
        if "sidewalk" in anchor:
            return self.sidewalk_point(anchor["sidewalk"], float(anchor.get("s", 0.0)))
        if "intersection" in anchor:
            inter = self.intersections.get(anchor["intersection"])
            if inter is None:
                raise AnchorError(f"unknown intersection {anchor['intersection']}")
            k = anchor.get("approach", 0)
            legs = [lg for lg in inter["legs"] if lg.get("approach")]
            leg = (
                legs[k]
                if isinstance(k, int)
                else next(lg for lg in legs if lg["approach"]["id"] == k)
            )
            edge = self.edges[leg["edge"]]
            idx = int(anchor.get("lane_index", 0))
            lanes = [
                ln
                for ln in edge["lanes"]
                if ln["dir"] == leg["approach"]["dir"] and ln["index"] == idx
            ]
            if not lanes:
                raise AnchorError(f"no lane {idx} on approach {leg['approach']['id']}")
            lane_id = lanes[0]["id"]
            return self.lane_point(
                lane_id, self.lane_length(lane_id) - float(anchor.get("before_m", 0.0))
            )
        raise AnchorError(f"anchor kind not supported here: {sorted(anchor)}")
