"""Authored staging survey roads and distinct closed-loop operation cases."""

from hashlib import blake2s
from math import atan2, ceil, hypot, pi
from typing import Any

Record = dict[str, Any]


def wrap(angle: float) -> float:
    """Take the shortest angular delta in radians."""
    return (angle + pi) % (2 * pi) - pi


def turn(angle: float) -> Record:
    """Commission a pure rotation at a fixed compensated timestep."""
    n = max(1, ceil(abs(angle) / 0.075))
    return {"ticks": n, "v_mps": 0.0, "w_radps": angle / (n * 0.1)}


def format_edge(name: str, start: str, end: str, nodes: Record, *, reverse: bool = False) -> Record:
    """Describe the approach straight with rotations on both ends."""
    a, b, heading = nodes[start]
    x, y, reference = nodes[end]
    length = hypot(x - a, y - b)
    direction = atan2(y - b, x - a) + (pi if reverse else 0.0) if length else heading
    segments = []
    if abs(wrap(direction - heading)) > 1e-10:
        segments.append(turn(wrap(direction - heading)))
    if length:
        n = ceil(length / (0.019 if reverse else 0.032))
        segments.append({"ticks": n, "v_mps": length / (n * 0.1) * (-1 if reverse else 1), "w_radps": 0.0})
    if abs(wrap(reference - direction)) > 1e-10:
        segments.append(turn(wrap(reference - direction)))
    return {"id": name, "source": start, "target": end, "segments": segments}


def navigation(nodes: Record, edges: list[Record], obstacles: list[list[float]]) -> Record:
    """Build the commissioned map geometry with an inflated rectangular footprint."""
    return {"nodes": nodes, "edges": edges, "start": "entry", "staging": "tag-window",
            "footprint": [0.210, 0.135], "margin_m": 0.012,
            "bounds": [-1.48, -1.22, 1.92, 1.31], "obstacles": obstacles,
            "forward_max_mps": 0.34, "reverse_max_mps": 0.21, "angular_max_radps": 0.82,
            "position_tolerance_m": 0.008, "heading_tolerance_rad": 0.018}


def around_charger(case: str) -> Record:
    """Connect a wrong-side start to the staging dock around either of two aisles."""
    nodes = {
        "entry": [-0.94, -0.025, 2.93],
        "west-upper": [-0.94, 0.79, 0.0],
        "east-upper": [0.76, 0.79, -pi / 2],
        "west-lower": [-0.94, -0.76, 0.0],
        "east-lower": [0.76, -0.76, pi / 2],
        "tag-window": [0.74, 0.0, 0.0],
    }
    doorway = [
        ("closed-shortcut", "entry", "tag-window"),
        ("upper-entry", "entry", "west-upper"),
        ("upper-cross", "west-upper", "east-upper"),
        ("upper-exit", "east-upper", "tag-window"),
        ("lower-entry", "entry", "west-lower"),
        ("lower-cross", "west-lower", "east-lower"),
        ("lower-exit", "east-lower", "tag-window"),
    ]
    if case == "no-certified-route":
        doorway = doorway[:1]
    obstacles = [[-0.56, -0.36, -0.29, 0.38]]
    return navigation(nodes, [format_edge(key, start, end, nodes) for key, start, end in doorway], obstacles)


def lateral() -> Record:
    """Add an offset robot facing across the aisle and a blocked direct maneuver."""
    nodes = {"entry": [0.70, 0.95, -2.86], "outer": [1.40, 0.95, -pi / 2],
             "lower": [1.40, -0.03, pi], "tag-window": [0.73, 0.0, 0.0]}
    edges = [format_edge("cross-pallet-footprint", "entry", "tag-window", nodes),
             format_edge("reverse-into-outer-lane", "entry", "outer", nodes, reverse=True),
             format_edge("down-aisle", "outer", "lower", nodes), format_edge("reorient-for-tag", "lower", "tag-window", nodes)]
    return navigation(nodes, edges, [[0.49, 0.40, 0.90, 0.59]])


def curved() -> Record:
    """Provide a true curved primitive and a close rail with a safe alternative."""
    nodes = {"entry": [1.22, 0.65, pi], "arc-end": [0.72, 0.15, -pi / 2],
             "tag-window": [0.72, 0.0, 0.0]}
    angular = (pi / 2) / 3.2
    curve = {"id": "sweep-inner-rail", "source": "entry", "target": "arc-end",
             "segments": [{"ticks": 32, "v_mps": angular / 2, "w_radps": angular}]}
    edges = [curve, format_edge("line-up-with-connector", "arc-end", "tag-window", nodes)]
    return navigation(nodes, edges, [[1.04, 0.15, 1.14, 0.27]])


def swept_corner() -> Record:
    """Put a post outside the endpoint footprint but inside the direct turn sweep."""
    nodes = {"entry": [0.88, 0.56, 0.0], "clear-turn": [0.48, 0.56, -pi / 2],
             "tag-window": [0.74, 0.0, 0.0]}
    edges = [format_edge("straight-to-stage", "entry", "tag-window", nodes),
             format_edge("withdraw-for-turn", "entry", "clear-turn", nodes, reverse=True),
             format_edge("approach-from-clear-turn", "clear-turn", "tag-window", nodes)]
    return navigation(nodes, edges, [[1.120, 0.526, 1.140, 0.559]])


def anonymize(case: Record) -> Record:
    """Preserve topology and fault timing while removing meaningful labels from the bus."""
    nav = case["navigation"]

    def label(value: str) -> str:
        """Derive a stable opaque wire identifier for a fixture element."""
        return blake2s(f"{case['name']}:{value}".encode(), digest_size=5).hexdigest()

    nav["nodes"] = {label(key): pose for key, pose in nav["nodes"].items()}
    nav["start"], nav["staging"] = label(nav["start"]), label(nav["staging"])
    for edge in nav["edges"]:
        for key in ("id", "source", "target"):
            edge[key] = label(edge[key])
    case["holds"] = [(a, b, [label(edge) for edge in edges]) for a, b, edges in case.get("holds", [])]
    if "required_edge" in case:
        case["required_edge"] = label(case["required_edge"])
    case["tag"] = label("dock")
    return case


def cases() -> list[Record]:
    """Return distinct physical positive, guarded, interrupted, and impossible staging missions."""
    suite = [
        {"name": "behind-charger-use-side-aisle", "stage": 5, "navigation": around_charger("both"), "deadline": 335},
        {"name": "lateral-mirrored-camera", "stage": 5, "navigation": lateral(), "deadline": 270,
         "camera": [-0.14, -0.043, -2.89], "tag_offset": [-0.27, -0.067, -0.4], "tag_delay": 4},
        {"name": "both-aisles-held-then-release", "stage": 5, "navigation": around_charger("both"), "deadline": 350,
         "holds": [(0, 23, ["upper-entry", "lower-entry"])], "minimum_wait": 23},
        {"name": "preferred-route-held-take-outer-aisle", "stage": 5, "navigation": around_charger("both"),
         "deadline": 325, "holds": [(0, 150, ["lower-entry"])], "required_edge": "upper-cross"},
        {"name": "curved-lane-outage-and-restart", "stage": 5, "navigation": curved(), "deadline": 195,
         "map_holes": [(13, 24)], "restart_at": 17, "tag_delay": 3, "prestage_echo": True, "required_edge": "sweep-inner-rail"},
        {"name": "swept-body-corner-at-rotation", "stage": 5, "navigation": swept_corner(),
         "deadline": 244, "required_edge": "withdraw-for-turn"},
        {"name": "staging-then-bad-charge-retreat", "stage": 5, "navigation": lateral(), "deadline": 374,
         "contact_count": 2, "charges_on": 2, "front_block_ticks": 5,
         "restart_at": 95, "tag_holes": [(150, 156)]},
        {"name": "all-nominal-endpoints-clear-sweep-blocked", "stage": 5,
         "navigation": around_charger("no-certified-route"), "deadline": 110, "expected": "failed", "no_staging": True},
        {"name": "blocked-aisle-no-release-before-deadline", "stage": 5, "navigation": around_charger("both"), "deadline": 90,
         "holds": [(0, 150, ["upper-entry", "lower-entry"])], "expected": "failed", "no_staging": True},
    ]

    return [anonymize(case) for case in suite]
