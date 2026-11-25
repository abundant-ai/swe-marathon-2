#!/usr/bin/env python3
"""Generate the hidden lidar field missions for stages 4 and 5.

Cylinder layouts come from local copies of BARN dataset worlds, checked
against pinned SHA-256 digests. Each mission slot below fixes a world, a
variant, a clearance tier, a sensor profile and, for stage 5, where movers
cross the robot's way. A seeded generator draws everything else. A draw is
kept only if the reference navigator finishes it under the verifier's own
command, certification and motion checks, and the mission deadline is set
from that run. A stage 5 draw must also make the same navigator run into a
mover when it uses the tracks only to read its scans and picks its speeds as
if nothing moved. The report also runs the stage 4 navigator, which ignores
the tracks altogether, on every stage 5 mission.

    python3 -I -B scripts/generate_worlds.py --barn-dir DIR [--jobs N]

DIR holds world_<id>.world for every world in DIGESTS, copied from SOURCE.
The script rewrites common/verifier/courses.py and the two practice files in
environment/example/, and prints a calibration report.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from math import ceil, floor, pi, sqrt
import os
from pathlib import Path
import random
import re
import sys
import tempfile
from time import perf_counter
import types

TASK = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(TASK / "common"), str(TASK / "common" / "verifier")]
# The verifier's field module imports the mission table this script writes;
# give it an empty one so generation never depends on its own output.
sys.modules["courses"] = types.SimpleNamespace(MISSIONS={})

import field  # noqa: E402
from oracle.arena import Arena  # noqa: E402
from oracle.movers import Tracker  # noqa: E402
from oracle.pilot import ROUTE_MARGIN, Pilot  # noqa: E402
from oracle.routing import Router  # noqa: E402
from transport import Violation, require  # noqa: E402

SEED = 20261125
SOURCE = "https://github.com/Daffan/the-barn-challenge/tree/main/jackal_helper/worlds/BARN"
DIGESTS = {
    0: "a7a8129423b0b8fcb20b042646e929115b7dba18215f1c99ff8fa1adaec42d5c",
    10: "d7f8a7af941f74c2f526768b5843dc38076fb14e22527617c1ead9063b35ff2f",
    30: "22201c60928f95651f4a17b8363519cb78ff02ec1fb8603dcdb957a73cf1bdeb",
    80: "af2ddccf04b56671d4aa882f660f7df03d51eeaff5f8ba8ca06ccaa9a19ba5e9",
    100: "588beb7218242f40ed487aba58d3f4cb8e76d857bc6c33b657cc5c7cfce3edc7",
    120: "ee2cc4fbcb0c7fa5e46923e3c632d0fa04b931ec158d19b6bcd35f9b93863828",
    140: "e02c991f7e0320ace2479c737a6976338e842e9b30e1fdd03ec8bed2de959f07",
    180: "aed833da4047c6282469d7a1be249d7f0bae475a3f25587bf066174f1d79d7e0",
    210: "dff71cd124873f63b36111c2ec5a6bd4e00faf16ffd99a396261b36c3cdcdddf",
    230: "e19f7720c8ca3ccee7d556909ec056d602eebd8477ed58d8719ca11f4a110229",
    250: "e21e954a9e33926bcb094f953886d8c521da0fbc8abadbd34b29ba4c9bda47be",
    260: "aba5322a7131437a6e157cf922f9f5205e966c85877b0b3cef13e0a426f6c381",
    280: "80209faff1bae4c40ecb8c664e209c8ed395526934281126d0749012842c98fb",
    290: "5c28dc1c39b8ad2596f3a429e882ce77af459e74c05a239e50ed668ad162607a",
}
PUBLIC_WORLD = 0       # already shown to candidates; used only for the practice files
WALL_CYLINDERS = 96    # BARN cylinders below the lattice that wall in the start area
SHIFT = complex(4.5, -3.6)  # BARN world frame to arena frame

# Clearance tiers: how far the inflated body (radius_m + margin_m) stays below
# the largest body the reference router can still take from start to goal.
TIERS = {"easy": (0.08, 0.15), "medium": (0.03, 0.06), "hard": (0.012, 0.025)}
SCANS = {
    "full": {},
    "short": {"range_max_m": 2.0},
    "sparse": {"angle_increment_rad": 1.5 * pi / 180, "count": 181},
    "narrow": {"angle_min_rad": -0.5 * pi, "angle_increment_rad": pi / 180, "count": 181},
}
VARIANTS = {"plain": (False, False), "mirror": (True, False),
            "reverse": (False, True), "mirror-reverse": (True, True)}

# (world, variant, tier, scan profile)
STAGE4 = (
    (10, "plain", "easy", "full"),
    (30, "mirror", "medium", "full"),
    (100, "reverse", "hard", "full"),
    (10, "mirror-reverse", "hard", "short"),
    (30, "reverse", "easy", "sparse"),
    (100, "mirror", "medium", "narrow"),
    (80, "plain", "medium", "full"),
    (120, "mirror", "hard", "full"),
    (210, "reverse", "easy", "short"),
    (260, "mirror-reverse", "medium", "full"),
    (290, "plain", "hard", "sparse"),
    (80, "reverse", "easy", "narrow"),
    (140, "plain", "easy", "full"),
    (180, "mirror", "medium", "full"),
    (230, "reverse", "hard", "full"),
    (250, "mirror-reverse", "easy", "narrow"),
    (280, "plain", "medium", "short"),
    (210, "mirror", "hard", "full"),
)
# (world, variant, tier, scan profile, where each mover crosses the reference path)
STAGE5 = (
    (10, "plain", "easy", "full", ("goal",)),
    (30, "reverse", "easy", "full", ("start", "goal")),
    (100, "mirror", "medium", "full", ("lane", "goal")),
    (10, "mirror-reverse", "medium", "short", ("start", "lane")),
    (30, "mirror", "medium", "full", ("lane", "lane")),
    (100, "plain", "easy", "sparse", ("start", "goal", "lane")),
    (80, "reverse", "easy", "full", ("start", "goal")),
    (120, "plain", "hard", "full", ("goal",)),
    (210, "mirror", "easy", "narrow", ("start",)),
    (260, "plain", "medium", "full", ("start", "goal")),
    (290, "mirror-reverse", "medium", "full", ("goal", "lane")),
    (140, "reverse", "hard", "full", ("start", "goal")),
)
PRACTICE = (
    (4, (PUBLIC_WORLD, "plain", "easy", "full"), "field-world-0.json"),
    (5, (PUBLIC_WORLD, "plain", "easy", "full", ("start", "goal")), "movers-world-0.json"),
)

LIMIT = 4000     # ticks a calibration run may take
ATTEMPTS = 12    # draws per slot before the slot is reported as infeasible
TRIES = 6        # mover layouts tried on each draw the reference finishes
PLACEMENTS = 24  # phasings tried for each mover
CLEAR = 0.01     # clearance every mover keeps from cylinders and walls
CONTACT = "moving robot body touched a moving obstacle"
LANE = 0.9       # shortest straight lane a mover may patrol
LOWER = field.ORIGIN.imag - field.CYLINDER                                    # 1.5
UPPER = field.ORIGIN.imag + field.PITCH * (field.ROWS - 1) + field.CYLINDER   # 6.0

# A cylinder's pose appears in its model definition and again in the saved world state.
MODEL = re.compile(r"<model name=['\"]unit_cylinder_(\d+)['\"]>\s*(?:<static>[^<]*</static>\s*)?"
                   r"<pose[^>]*>([^<]+)</pose>")
RADIUS = re.compile(r"<radius>([^<]*)</radius>")


def load(directory: Path, world: int) -> tuple:
    """Lattice rows of one BARN world after checking its digest and geometry."""
    path = directory / f"world_{world}.world"
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == DIGESTS[world], f"{path.name}: digest mismatch")
    text = data.decode()
    require({float(value) for value in RADIUS.findall(text)} == {field.CYLINDER},
            f"{path.name}: unexpected radius")
    poses = {}
    for number, pose in MODEL.findall(text):
        x, y = (float(value) for value in pose.split()[:2])
        require(poses.setdefault(number, (x, y)) == (x, y), f"{path.name}: cylinder {number} moved")
    sites, walls = set(), 0
    for x, y in poses.values():
        offset = (complex(x, y) + SHIFT - field.ORIGIN) / field.PITCH
        i, j = round(offset.real), round(offset.imag)
        require(abs(offset - complex(i, j)) < 1e-6, f"{path.name}: cylinder off the lattice")
        if 0 <= i < field.COLUMNS and 0 <= j < field.ROWS:
            sites.add((i, j))
        else:
            require(j < 0, f"{path.name}: cylinder outside the lattice away from the start")
            walls += 1
    require(walls == WALL_CYLINDERS and len(sites) + walls == len(poses),
            f"{path.name}: unexpected cylinder count")
    return tuple("".join("#" if (i, j) in sites else "." for i in range(field.COLUMNS))
                 for j in range(field.ROWS))


def mirrored(rows: tuple) -> tuple:
    """The same field reflected across the arena's long axis."""
    return tuple(row[::-1] for row in rows)


def centers(rows) -> list:
    """Cylinder centers of a lattice."""
    return [field.ORIGIN + field.PITCH * complex(i, j) for j, row in enumerate(rows)
            for i, cell in enumerate(row) if cell == "#"]


def geometry(start: complex, goal: complex, body: float) -> dict:
    """Public geometry for a body of the given inflated radius."""
    return {"bounds_m": [field.WIDTH, field.HEIGHT],
            "lattice": {"origin_m": [field.ORIGIN.real, field.ORIGIN.imag], "pitch_m": field.PITCH,
                        "columns": field.COLUMNS, "rows": field.ROWS},
            "obstacle_radius_m": field.CYLINDER, "radius_m": body, "margin_m": 0.0,
            "start_m": [start.real, start.imag], "goal_m": [goal.real, goal.imag]}


def router_bottleneck(rows, start: complex, goal: complex) -> float:
    """Largest inflated body the reference router takes from start to goal, all sites known."""
    occupied = [(i, j) for j, row in enumerate(rows) for i, cell in enumerate(row) if cell == "#"]

    def passes(body: float) -> bool:
        arena = Arena(geometry(start, goal, body))
        router = Router(arena, ROUTE_MARGIN)
        for site in occupied:
            router.block(site)
        return router.plan(arena.start, arena.goal) is not None

    low, high = 0.1, 0.6
    require(passes(low) and not passes(high), "bottleneck search bracket")
    for _ in range(20):
        middle = 0.5 * (low + high)
        low, high = (middle, high) if passes(middle) else (low, middle)
    return low


def exact_bottleneck(rows) -> float:
    """Largest disc clearance that can cross the lattice, from the wall-to-wall chain."""
    discs = centers(rows)
    left, right = len(discs), len(discs) + 1
    edges = [(field.WIDTH / 2, left, right)]
    for a, p in enumerate(discs):
        edges += [((p.real - field.CYLINDER) / 2, a, left),
                  ((field.WIDTH - p.real - field.CYLINDER) / 2, a, right)]
        edges += [(abs(p - q) / 2 - field.CYLINDER, a, b) for b, q in enumerate(discs) if b > a]
    parent = list(range(len(discs) + 2))

    def find(k: int) -> int:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for clearance, a, b in sorted(edges):
        parent[find(a)] = find(b)
        if find(left) == find(right):
            return clearance
    raise AssertionError("the walls always join")


class Reckless(Tracker):
    """The reference navigator using mover tracks only to interpret its scans."""

    def drive(self, z: complex, heading: complex, along: float, v0: float, movers: list) -> float:
        """Pick the straight speed as if no mover were there."""
        return super().drive(z, heading, along, v0, [])


def run(mission: dict, navigator=Tracker) -> dict:
    """Drive a reference navigator through a mission under the verifier's checks."""
    world = field.Field(mission)
    pilot = navigator(json.loads(json.dumps(world.public(), allow_nan=False)))
    z, yaw = world.start, mission["start_yaw"]
    v0 = w0 = 0.0
    track, costs = [z], []
    tick = 0
    try:
        for tick in range(mission["deadline"] + 1):
            observation = json.loads(json.dumps(world.observe(tick, z, yaw, v0, w0), allow_nan=False))
            begin = perf_counter()
            try:
                reply = pilot.tick(observation)
            except Exception as error:  # the verifier fails a navigator that crashes
                raise Violation(f"navigator raised {type(error).__name__}: {error}") from None
            costs.append(perf_counter() - begin)
            status, v, w = world.command(json.loads(json.dumps(reply, allow_nan=False)), v0, w0)
            require(status != "timeout", "navigator reported timeout")
            if status == "succeeded":
                require(abs(z - world.goal) <= mission["goal_tolerance_m"] + 1e-9,
                        "reported success outside the goal tolerance")
                return {"ok": True, "ticks": tick, "track": track, "costs": costs}
            if v > 0:
                world.certify(tick, z, yaw, v, w)
            z, yaw = world.advance(z, yaw, v, w)
            v0, w0 = v, w
            track.append(z)
        raise Violation("deadline")
    except Violation as error:
        return {"ok": False, "ticks": tick, "reason": str(error), "track": track, "costs": costs}


def draw(rng: random.Random, stage: int, slot: tuple, rows: tuple, bottleneck: float) -> dict:
    """Sample the body, limits and sensor of one mission."""
    world, variant, tier, profile = slot[:4]
    reverse = VARIANTS[variant][1]
    start, goal = (field.GOAL, field.START) if reverse else (field.START, field.GOAL)
    margin = round(rng.uniform(0.01, 0.06), 3)
    radius = floor((bottleneck - rng.uniform(*TIERS[tier]) - margin) * 1e4) / 1e4
    mission = {"stage": stage, "world": world, "variant": variant, "tier": tier, "sensor": profile,
               "rows": rows, "start_m": list(start), "goal_m": list(goal),
               "start_yaw": round(rng.uniform(-pi, pi), 4),
               "radius_m": radius, "margin_m": margin,
               "dt": rng.choice((0.1, 0.15, 0.2)),
               "max_v": round(rng.uniform(0.5, 1.0), 3),
               "max_w": round(rng.uniform(1.0, 2.0), 3),
               "max_accel": round(rng.uniform(0.5, 1.5), 3),
               "max_alpha": round(rng.uniform(1.5, 4.0), 3),
               "goal_tolerance_m": round(rng.uniform(0.12, 0.2), 3),
               "deadline": LIMIT}
    if SCANS[profile]:
        mission["scan"] = dict(SCANS[profile])
    return mission


def lane(sites: list, p: complex, radius: float, horizontal: bool):
    """Longest axis-parallel segment through p that a mover of this radius may patrol."""
    need = radius + field.CYLINDER + CLEAR
    across, along = (p.imag, p.real) if horizontal else (p.real, p.imag)
    span, width = (field.WIDTH, field.HEIGHT) if horizontal else (field.HEIGHT, field.WIDTH)
    if not radius + CLEAR <= across <= width - radius - CLEAR:
        return None
    low, high = radius + CLEAR, span - radius - CLEAR
    for c in sites:
        a, b = (c.real, c.imag) if horizontal else (c.imag, c.real)
        if abs(b - across) >= need:
            continue
        half = sqrt(need * need - (b - across) ** 2)
        if a + half <= along:
            low = max(low, a + half)
        elif a - half >= along:
            high = min(high, a - half)
        else:
            return None
    low, high = low + 1e-3, high - 1e-3
    if high - low < LANE:
        return None
    ends = [complex(low, across), complex(high, across)] if horizontal else \
        [complex(across, low), complex(across, high)]
    return [[round(q.real, 4), round(q.imag, 4)] for q in ends]


def crossings(kind: str, track: list, mission: dict, radius: float) -> list:
    """Ticks and patrol routes where a mover of this kind meets the reference path."""
    start, goal = complex(*mission["start_m"]), complex(*mission["goal_m"])
    sites = centers(mission["rows"])
    out = []
    for tick, p in enumerate(track):
        if kind == "lane":
            if not LOWER < p.imag < UPPER:
                continue
            for horizontal in (True, False):
                route = lane(sites, p, radius, horizontal)
                if route:
                    out.append((tick, p, route))
            continue
        anchor = start if kind == "start" else goal
        if (p.imag < LOWER) != (anchor.imag < LOWER) or LOWER <= p.imag <= UPPER:
            continue
        if kind == "start" and abs(p - start) < 0.25 or kind == "goal" and abs(p - goal) > 1.0:
            continue
        route = lane(sites, p, radius, True)
        if route:
            out.append((tick, p, route))
    return out


def place(rng: random.Random, mission: dict, kinds: tuple, track: list):
    """Movers phased to meet the reference path, or None if no placement fits."""
    body = mission["radius_m"] + mission["margin_m"]
    start = complex(*mission["start_m"])
    movers = []
    for kind in kinds:
        radius = round(rng.uniform(0.1, 0.2) if kind == "lane" else rng.uniform(0.15, 0.3), 3)
        options = crossings(kind, track, mission, radius)
        if not options and kind == "lane":
            # No straight lane between the cylinders crosses the path; use an
            # open end of the arena this layout has not used yet.
            for other in ("goal", "start"):
                if other not in kinds:
                    kind, options = other, crossings(other, track, mission, radius)
                    if options:
                        break
        for _ in range(PLACEMENTS):
            if not options:
                return None
            tick, p, route = rng.choice(options)
            record = {"kind": kind, "radius_m": radius, "route": route,
                      "speed_mps": round(rng.uniform(0.3, 0.7) * mission["max_v"], 3),
                      "dwell": rng.randint(0, 8), "offset": 0}
            cycle = field.Patrol(record, mission["dt"]).cycle
            nearest = min(abs(q - p) for q in cycle)
            index = rng.choice([k for k, q in enumerate(cycle) if abs(q - p) <= nearest + 1e-9])
            record["offset"] = (index - tick) % len(cycle)
            if abs(cycle[record["offset"]] - start) >= body + radius + 0.1:
                movers.append(record)
                break
        else:
            return None
    return movers


def calibrate(stage: int, index: int, slot: tuple, rows: tuple, bottleneck: float,
              exact: float, seed: int) -> dict:
    """Draw a slot until the reference navigator finishes it; set its deadline."""
    rng = random.Random(f"{seed}:{stage}:{index}")
    notes = []
    for attempt in range(1, ATTEMPTS + 1):
        mission = draw(rng, stage, slot, rows, bottleneck)
        begin = perf_counter()
        static = run(mission)
        if not static["ok"]:
            notes.append(f"draw {attempt}: reference failed: {static['reason']} at {static['ticks']}")
            continue
        result, control, blind = static, None, None
        if stage == 5:
            result = None
            for _ in range(TRIES):
                movers = place(rng, mission, slot[4], static["track"])
                if movers is None:
                    notes.append(f"draw {attempt}: no mover placement")
                    continue
                trial = dict(mission, movers=movers, max_track_speed_mps=round(
                    max(m["speed_mps"] for m in movers) + rng.uniform(0.0, 0.05), 3))
                control = run(trial, navigator=Reckless)
                if control["ok"] or control["reason"] != CONTACT:
                    notes.append(f"draw {attempt}: speeds ignoring movers: "
                                 f"{'finished' if control['ok'] else control['reason']}")
                    continue
                aware = run(trial)
                if not aware["ok"]:
                    notes.append(f"draw {attempt}: reference failed with movers: "
                                 f"{aware['reason']} at {aware['ticks']}")
                    continue
                mission, result = trial, aware
                break
            if result is None:
                continue
        mission["deadline"] = ceil(result["ticks"] * rng.uniform(2.2, 2.6) + rng.uniform(60, 80))
        if stage == 5:
            blind = run(mission, navigator=Pilot)
        body = mission["radius_m"] + mission["margin_m"]
        costs = result["costs"]
        return {"stage": stage, "index": index, "mission": mission, "attempts": attempt, "notes": notes,
                "report": {"ticks": result["ticks"], "deadline": mission["deadline"],
                           "router_bottleneck_m": round(bottleneck, 4),
                           "exact_bottleneck_m": round(exact, 4), "body_m": round(body, 4),
                           "slack_m": round(bottleneck - body, 4),
                           "mean_reply_s": round(sum(costs) / len(costs), 5),
                           "max_reply_s": round(max(costs), 4),
                           "kinds": [m["kind"] for m in mission.get("movers", ())],
                           "reckless": outcome(control), "blind": outcome(blind),
                           "calibration_s": round(perf_counter() - begin, 1)}}
    return {"stage": stage, "index": index, "mission": None, "attempts": ATTEMPTS, "notes": notes}


def outcome(result) -> str:
    """One-line summary of a control run."""
    if result is None:
        return None
    return f"{'finished' if result['ok'] else result['reason']} at tick {result['ticks']}"


def bottlenecks(task: tuple) -> tuple:
    """Router and exact bottlenecks of one oriented field."""
    rows, reverse = task
    start, goal = (field.GOAL, field.START) if reverse else (field.START, field.GOAL)
    return router_bottleneck(rows, complex(*start), complex(*goal)), exact_bottleneck(rows)


def name(stage: int, index: int, mission: dict) -> str:
    """Stable mission identifier."""
    return f"s{stage}-{index:02d}-w{mission['world']:03d}-{mission['variant']}-{mission['tier']}"


def render(seed: int, worlds: dict, missions: list) -> str:
    """Source text of the hidden mission table."""
    notice = (TASK / "environment" / "example" / "NOTICE.txt").read_text()
    license_text = notice[notice.index("MIT License"):].rstrip()
    used = sorted({m["world"] for m in missions})
    lines = ['"""Hidden lidar field missions for stages 4 and 5.', "",
             f"Generated by scripts/generate_worlds.py with seed {seed}; do not edit by hand.", "",
             "WORLDS holds the 30 x 30 cylinder lattice of BARN dataset worlds: rows[j][i] is",
             '"#" when site (i, j) holds a cylinder, with j counting rows away from the start',
             f"side. The {WALL_CYLINDERS} cylinders that wall in the BARN start area are dropped; the",
             "closed rectangular arena replaces them.", "",
             f"Source: {SOURCE}", "SHA-256 of the source files:"]
    lines += [f"    world_{world}.world {DIGESTS[world]}" for world in used]
    lines += ["", license_text.replace("\\", "\\\\"), '"""', "", "",
              "def mirrored(rows: tuple) -> tuple:",
              '    """The same field reflected across the arena\'s long axis."""',
              "    return tuple(row[::-1] for row in rows)", "", "",
              "WORLDS = {"]
    for world in used:
        lines.append(f"    {world}: (")
        lines += [f'        "{row}",' for row in worlds[world]]
        lines.append("    ),")
    lines += ["}", "", "MISSIONS = {"]
    for m in missions:
        lines.append(f'    "{name(m["stage"], m["index"], m)}": {{')
        for key, value in m.items():
            if key == "index":
                continue
            if key == "rows":
                text = f"WORLDS[{m['world']}]"
                text = f"mirrored({text})" if VARIANTS[m["variant"]][0] else text
            else:
                text = json.dumps(value)
            lines.append(f'        "{key}": {text},')
        lines.append("    },")
    lines += ["}", ""]
    return "\n".join(lines)


def practice(mission: dict) -> dict:
    """A practice field: the navigator's spec plus the ground truth behind it."""
    world = field.Field(mission)
    truth = {"start_yaw": mission["start_yaw"],
             "cylinders_m": [[round(c.real, 4), round(c.imag, 4)] for c in world.sites]}
    if mission.get("movers"):
        truth["movers"] = mission["movers"]
    return {"spec": world.public(), "truth": truth}


def publish(path: Path, text: str) -> None:
    """Replace a file atomically with a copy everyone can read (mode 0644)."""
    handle = tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", delete=False)
    try:
        with handle:
            handle.write(text)
        os.chmod(handle.name, 0o644)
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def main() -> int:
    """Generate, calibrate and write the missions."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--barn-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument("--report", type=Path, help="also write the calibration report as JSON")
    parser.add_argument("--dry-run", action="store_true", help="calibrate without writing files")
    parser.add_argument("--only", nargs="+", metavar="SLOT",
                        help="calibrate only these slots, such as s4-01 or s5-00 (implies --dry-run)")
    args = parser.parse_args()

    worlds = {world: load(args.barn_dir, world) for world in DIGESTS}
    slots = [(4, k, slot) for k, slot in enumerate(STAGE4, 1)] + \
            [(5, k, slot) for k, slot in enumerate(STAGE5, 1)] + \
            [(stage, 0, slot) for stage, slot, _ in PRACTICE]
    if args.only:
        slots = [s for s in slots if f"s{s[0]}-{s[1]:02d}" in args.only]
        args.dry_run = True
    oriented = sorted({(slot[0], *VARIANTS[slot[1]]) for _, _, slot in slots})
    fields = {key: mirrored(worlds[key[0]]) if key[1] else worlds[key[0]] for key in oriented}
    with ProcessPoolExecutor(args.jobs) as pool:
        limits = dict(zip(oriented, pool.map(bottlenecks, [(fields[k], k[2]) for k in oriented])))
        futures = [pool.submit(calibrate, stage, index, slot, fields[key], *limits[key], args.seed)
                   for stage, index, slot in slots
                   for key in [(slot[0], *VARIANTS[slot[1]])]]
        results = [future.result() for future in futures]

    failed = [r for r in results if r["mission"] is None]
    for r in results:
        label = name(r["stage"], r["index"], r["mission"]) if r["mission"] else f"s{r['stage']}-{r['index']:02d}"
        print(json.dumps({"mission": label, "attempts": r["attempts"], **r.get("report", {}),
                          "notes": r["notes"]}))
    if args.report:
        args.report.write_text(json.dumps(
            [{"mission": name(r["stage"], r["index"], r["mission"]), **r["report"]}
             for r in results if r["mission"]], indent=1))
    if failed:
        print(f"{len(failed)} slot(s) found no feasible draw", file=sys.stderr)
        return 1
    if args.dry_run:
        return 0
    hidden = [{"index": r["index"], **r["mission"]} for r in results if r["index"]]
    publish(TASK / "common" / "verifier" / "courses.py", render(args.seed, worlds, hidden))
    for (_, _, filename), r in zip(PRACTICE, [r for r in results if not r["index"]]):
        mission = {key: value for key, value in r["mission"].items() if key != "index"}
        publish(TASK / "environment" / "example" / filename,
                json.dumps(practice(mission), indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
