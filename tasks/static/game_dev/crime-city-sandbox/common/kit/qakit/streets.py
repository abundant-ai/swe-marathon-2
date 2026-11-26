"""Checks of traffic and people in the streets (design document, chapter 7).

They read the entity census of a play's frames. Census rows carry each entity's id ("id"),
kind ("k"), archetype ("a"), position ("p"), back axis ("bz"), the metadata a play observes
("m": for these checks "vehicle", "seat", "limp", "state", "intersection", "approach",
"crosswalk") and, with census {"view": true}, whether the point 1 m above its position is
inside the camera's view ("iv"). With census {"shapes": [kinds]}, entities of those kinds
also list their collision shapes ("sh"): each the box of one CollisionShape3D of the entity,
as its centre and its three half-axis vectors in world space.

Speeds come from positions: the horizontal distance between two frames over the ticks
between them, at 60 ticks per second. "NPC vehicles" are vehicles that carry no player (the
state report's player.vehicle); "people on foot" are NPCs whose `vehicle` metadata is null.

Places on the map come with the play (worked out from the plan): an "area" is
{"lanes": [{"id", "pts": [[x, z], ...] in the direction of travel, from the lane's start box
to its stop line, "width", "limit_kmh"}], "roads": [polygons of carriageways and junction
boxes], "crosswalks": [{"id", "intersection", "control", "walk_signals", "poly"}],
"blocks": [polygons], "buildings": [footprint polygons], "rooms": [interior room polygons]};
a polygon is a list of [x, z] corners.
"""

from __future__ import annotations

import itertools
import math
from statistics import median

from .play import PlayRecord, RunRecord

TICK_HZ = 60
KMH = 1 / 3.6

Result = tuple[bool | None, dict, str]


# ------------------------------------------------------------------ frames
def frames_between(run: RunRecord, a: str, b: str) -> list[dict]:
    """The frames from mark a to mark b, both included (empty when a mark is missing)."""
    i, j = run.marks.get(a), run.marks.get(b)
    if i is None or j is None:
        return []
    return run.frames[i : j + 1]


def rows(frame: dict) -> dict:
    """{id: census row} of a frame."""
    return {e.get("id"): e for e in frame.get("census") or [] if "id" in e}


def flat(p: list) -> tuple[float, float]:
    return float(p[0]), float(p[2])


def player_of(frame: dict) -> dict | None:
    for e in frame.get("census") or []:
        if e.get("k") == "player":
            return e
    return None


def player_vehicle(frame: dict) -> object:
    """The id of the vehicle the player sits in, from the frame's state report, or None."""
    st = frame.get("state")
    if isinstance(st, dict):
        inner = st.get("state") if isinstance(st.get("state"), dict) else st
        pl = inner.get("player")
        if isinstance(pl, dict):
            return pl.get("vehicle")
    return None


def meta(row: dict, key: str) -> object:
    return (row.get("m") or {}).get(key)


def on_foot(row: dict, dead: set) -> bool:
    """An NPC that is alive and sits in no vehicle."""
    return (
        row.get("k") == "npc"
        and meta(row, "vehicle") is None
        and row.get("id") not in dead
    )


def dead_ids(frames: list[dict]) -> dict:
    """{entity id: tick of its died event} over the frames."""
    out: dict = {}
    for fr in frames:
        for ev in fr.get("events") or []:
            if isinstance(ev, dict) and ev.get("n") == "died":
                d = ev.get("d") if isinstance(ev.get("d"), dict) else ev
                eid = d.get("entity")
                if eid is not None and eid not in out:
                    out[eid] = int(fr.get("t", 0))
    return out


def speed(
    prev: dict | None,
    cur: dict,
    eid: object,
    rp: dict | None = None,
    rc: dict | None = None,
) -> float | None:
    """An entity's horizontal speed (m/s) from its positions in two frames, or None."""
    if prev is None:
        return None
    a = (rp or rows(prev)).get(eid)
    b = (rc or rows(cur)).get(eid)
    if (
        not a
        or not b
        or not isinstance(a.get("p"), list)
        or not isinstance(b.get("p"), list)
    ):
        return None
    dt = int(cur.get("t", 0)) - int(prev.get("t", 0))
    if dt <= 0:
        return None
    (ax, az), (bx, bz) = flat(a["p"]), flat(b["p"])
    return math.hypot(bx - ax, bz - az) * TICK_HZ / dt


def setup_frames(rec: PlayRecord, run: RunRecord, settle_s: float = 3.0) -> set[int]:
    """Indices of the frames produced by DevConsole steps (the tick a setup command ran), and
    of the frames up to `settle_s` after a step whose commands include world.reset or load
    (they may take up to 3 s, AC-3)."""
    dev_steps = {i for i, s in enumerate(rec.play.steps) if "dev" in s}
    long_steps = {
        i
        for i, s in enumerate(rec.play.steps)
        if "dev" in s and any(c[0] in ("world.reset", "load") for c in s["dev"])
    }
    out = {k for k, fr in enumerate(run.frames) if fr.get("_step") in dev_steps}
    for k, fr in enumerate(run.frames):
        if fr.get("_step") in long_steps:
            t0 = int(fr.get("t", 0))
            out.update(
                j
                for j in range(k, len(run.frames))
                if int(run.frames[j].get("t", 0)) - t0 <= settle_s * TICK_HZ
            )
    return out


# ------------------------------------------------------------------ geometry
def inside(poly: list, x: float, z: float) -> bool:
    """Whether (x, z) lies inside a polygon (even-odd rule)."""
    n = len(poly)
    hit = False
    j = n - 1
    for i in range(n):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z):
            xc = xi + (z - zi) * (xj - xi) / (zj - zi)
            if x < xc:
                hit = not hit
        j = i
    return hit


def seg_dist(x: float, z: float, a: list, b: list) -> float:
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (z - a[1]) * dz) / l2))
    return math.hypot(x - (a[0] + t * dx), z - (a[1] + t * dz))


def poly_dist(poly: list, x: float, z: float) -> float:
    """Distance from (x, z) to a polygon (0 inside it)."""
    if inside(poly, x, z):
        return 0.0
    return min(
        seg_dist(x, z, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))
    )


def segments_cross(p1, p2, q1, q2) -> bool:
    """Whether segments p1-p2 and q1-q2 cross or touch."""

    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2 = orient(q1, q2, p1), orient(q1, q2, p2)
    d3, d4 = orient(p1, p2, q1), orient(p1, p2, q2)
    return (d1 >= 0) != (d2 > 0) and (d3 >= 0) != (d4 > 0)


def path_enters(
    poly: list, x: float, z: float, dx: float, dz: float, length: float
) -> bool:
    """Whether the straight path from (x, z) along (dx, dz) (a unit vector) for `length`
    metres starts in or enters a polygon."""
    if inside(poly, x, z):
        return True
    e = (x + dx * length, z + dz * length)
    n = len(poly)
    return any(segments_cross((x, z), e, poly[i], poly[(i + 1) % n]) for i in range(n))


def hull(points: list) -> list:
    """Convex hull (x, z) of points, anticlockwise (monotone chain)."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def box_footprint(sh: list) -> tuple[list, float, float]:
    """A shape box ([centre, x, y and z half-axis vectors]) as (its outline seen from above,
    lowest height, highest height)."""
    c = sh[0:3]
    axes = (sh[3:6], sh[6:9], sh[9:12])
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                corners.append(
                    [
                        c[i] + sx * axes[0][i] + sy * axes[1][i] + sz * axes[2][i]
                        for i in range(3)
                    ]
                )
    ys = [p[1] for p in corners]
    return hull([(round(p[0], 6), round(p[2], 6)) for p in corners]), min(ys), max(ys)


def outline_gap(a: list, b: list) -> float:
    """The separation of two convex outlines along their edge normals: positive when they
    are apart (a lower bound of their distance), zero or negative when they overlap."""
    best = -math.inf
    for poly in (a, b):
        n = len(poly)
        for i in range(n):
            p, q = poly[i], poly[(i + 1) % n]
            ex, ez = q[0] - p[0], q[1] - p[1]
            ln = math.hypot(ex, ez)
            if ln < 1e-9:
                continue
            nx, nz = ez / ln, -ex / ln
            pa = [v[0] * nx + v[1] * nz for v in a]
            pb = [v[0] * nx + v[1] * nz for v in b]
            gap = max(min(pb) - max(pa), min(pa) - max(pb))
            best = max(best, gap)
    return best


def shapes_of(row: dict) -> list:
    """The footprints of an entity's collision boxes: [(outline, y low, y high)]."""
    out = []
    for sh in row.get("sh") or []:
        if isinstance(sh, list) and len(sh) == 12:
            out.append(box_footprint([float(v) for v in sh]))
    return out


def shapes_gap(a: list, b: list) -> float:
    """The smallest gap between two entities' footprints that overlap in height (inf if none)."""
    best = math.inf
    for oa, la, ha in a:
        for ob, lb, hb in b:
            if la > hb or lb > ha:
                continue
            best = min(best, outline_gap(oa, ob))
    return best


def point_gap(shapes: list, x: float, z: float) -> float:
    """Horizontal distance from (x, z) to the nearest footprint (0 inside)."""
    best = math.inf
    for outline, _lo, _hi in shapes:
        best = min(best, poly_dist(outline, x, z))
    return best


def prop_outline(box: dict) -> list:
    """The outline seen from above of a box placed with prop.spawn: {"p", "size", "heading"}."""
    x, _y, z = box["p"]
    w, _h, d = box["size"]
    r = math.radians(float(box.get("heading", 0.0)))
    fx, fz = math.sin(r), -math.cos(r)
    rx, rz = -fz, fx
    out = []
    for a, b in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
        out.append(
            (x + fx * a * d / 2 + rx * b * w / 2, z + fz * a * d / 2 + rz * b * w / 2)
        )
    return hull(out)


# ------------------------------------------------------------------ lanes and the area
class Lane:
    """A lane's centre line, from its start box to its stop line."""

    def __init__(self, data: dict) -> None:
        self.id = str(data.get("id", ""))
        self.pts = [(float(a), float(b)) for a, b in data["pts"]]
        self.width = float(data.get("width", 3.25))
        self.limit = float(data.get("limit_kmh", 0.0))
        self.cum = [0.0]
        for p, q in itertools.pairwise(self.pts):
            self.cum.append(self.cum[-1] + math.dist(p, q))
        self.length = self.cum[-1]
        xs = [p[0] for p in self.pts]
        zs = [p[1] for p in self.pts]
        m = self.width
        self.lo = (min(xs) - m, min(zs) - m)
        self.hi = (max(xs) + m, max(zs) + m)

    def project(
        self, x: float, z: float
    ) -> tuple[float, float, tuple[float, float]] | None:
        """(s along the lane, offset to the right of travel, unit direction there) of the
        nearest point of the centre line, or None when the point lies beyond the lane's
        start or end (or outside its bounds). The offset is the true distance to that point,
        signed by the side."""
        if not (self.lo[0] <= x <= self.hi[0] and self.lo[1] <= z <= self.hi[1]):
            return None
        best = None
        last = len(self.pts) - 2
        for i, (p, q) in enumerate(itertools.pairwise(self.pts)):
            dx, dz = q[0] - p[0], q[1] - p[1]
            ln = math.hypot(dx, dz)
            if ln < 1e-9:
                continue
            ux, uz = dx / ln, dz / ln
            raw = (x - p[0]) * ux + (z - p[1]) * uz
            beyond = (i == 0 and raw < 0) or (i == last and raw > ln)
            t = max(0.0, min(ln, raw))
            cx, cz = p[0] + ux * t, p[1] + uz * t
            dist = math.hypot(x - cx, z - cz)
            side = (x - p[0]) * (-uz) + (z - p[1]) * ux
            if best is None or dist < best[0]:
                best = (
                    dist,
                    beyond,
                    self.cum[i] + t,
                    math.copysign(dist, side),
                    (ux, uz),
                )
        if best is None or best[1]:
            return None
        return best[2], best[3], best[4]


def lane_at(lanes: list, x: float, z: float) -> tuple[Lane, float, tuple] | None:
    """(lane, offset, lane direction) of the lane band (within half its width of its centre
    line) that holds (x, z), the one with the smallest offset, or None."""
    best = None
    for ln in lanes:
        pr = ln.project(x, z)
        if pr is None or abs(pr[1]) > ln.width / 2:
            continue
        if best is None or abs(pr[1]) < abs(best[1]):
            best = (ln, pr[1], pr[2])
    return best


class Area:
    """The places of an "area" (see the module docstring)."""

    def __init__(self, data: dict) -> None:
        self.lanes = [Lane(d) for d in data.get("lanes", [])]
        self.roads = [p for p in data.get("roads", [])]
        self.crosswalks = list(data.get("crosswalks", []))
        self.blocks = [p for p in data.get("blocks", [])]
        self.buildings = [p for p in data.get("buildings", [])]
        self.rooms = [p for p in data.get("rooms", [])]
        self.centre = data.get("centre", [0.0, 0.0])
        self.radius = float(data.get("radius_m", 1e9))

    def near(self, x: float, z: float) -> bool:
        return math.hypot(x - self.centre[0], z - self.centre[1]) <= self.radius

    def on_road(self, x: float, z: float) -> bool:
        return any(inside(p, x, z) for p in self.roads)

    def crosswalk(self, x: float, z: float) -> dict | None:
        for c in self.crosswalks:
            if inside(c["poly"], x, z):
                return c
        return None

    def walkable(self, x: float, z: float) -> bool:
        """TR-9's walkable ground: a crosswalk band; a block outside every building's
        footprint, or a room of an interior; anywhere off the road network otherwise."""
        if self.crosswalk(x, z) is not None:
            return True
        if any(inside(p, x, z) for p in self.rooms):
            return True
        if any(inside(p, x, z) for p in self.buildings):
            return False
        if any(inside(p, x, z) for p in self.blocks):
            return True
        return not self.on_road(x, z)


def shared_area(args: dict) -> Area:
    return Area(args["area"])


# ------------------------------------------------------------------ TR-16 drivers
def check_drivers(rec: PlayRecord, args: dict) -> Result:
    """TR-16: between two marks, every vehicle moving faster than `min_kmh` (from its positions
    in two frames) that carries no player has a driver: a person whose `vehicle` metadata names
    it and whose `seat` is 0, of one of the `archetypes`. Where a frame also has that person's
    `Hips` bone and the vehicle's seat points, the hips are within `hips_m` of seat 0's point
    (FT-10). No two people name the same seat of one vehicle."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    archetypes = set(args["archetypes"])
    min_v = float(args.get("min_kmh", 1.0)) * KMH
    hips_m = float(args.get("hips_m", 0.35))
    moving = without = wrong_arch = shared = checked = 0
    worst = 0.0
    first = ""
    prev, rp = None, None
    for fr in frames:
        rc = rows(fr)
        pv = player_vehicle(fr)
        seats: dict = {}
        drivers: dict = {}
        for e in rc.values():
            if e.get("k") in ("npc", "player"):
                vid, seat = meta(e, "vehicle"), meta(e, "seat")
                if vid is None or seat is None:
                    continue
                seats.setdefault((vid, seat), []).append(e)
                if seat == 0:
                    drivers[vid] = e
        for (vid, seat), who in seats.items():
            if len(who) > 1:
                shared += 1
                first = (
                    first
                    or f"at tick {fr.get('t')} {len(who)} people name seat {seat} of vehicle {vid}"
                )
        if prev is not None:
            for vid, e in rc.items():
                if e.get("k") != "vehicle" or vid == pv:
                    continue
                v = speed(prev, fr, vid, rp, rc)
                if v is None or v <= min_v:
                    continue
                moving += 1
                d = drivers.get(vid)
                if d is None:
                    without += 1
                    first = (
                        first
                        or f"vehicle {vid} moved at {v * 3.6:.1f} km/h at tick {fr.get('t')} with nobody in seat 0"
                    )
                    continue
                if d.get("k") == "npc" and d.get("a") not in archetypes:
                    wrong_arch += 1
                    first = (
                        first
                        or f"vehicle {vid}'s driver at tick {fr.get('t')} is a {d.get('a')}"
                    )
        bones = fr.get("bones") or {}
        seat_reads = fr.get("seats") or {}
        for vid, d in drivers.items():
            hips = (bones.get(str(d.get("id"))) or {}).get("Hips")
            marks = seat_reads.get(str(vid)) or []
            s0 = next((m for m in marks if m.get("index") == 0), None)
            if isinstance(hips, list) and s0 and isinstance(s0.get("p"), list):
                checked += 1
                gap = math.dist([float(c) for c in hips], [float(c) for c in s0["p"]])
                worst = max(worst, gap)
                if gap > hips_m:
                    first = (
                        first
                        or f"at tick {fr.get('t')} the driver of vehicle {vid} has its Hips {gap:.2f} m from seat 0's point"
                    )
        prev, rp = fr, rc
    measured = {
        "moving_samples": moving, "without_driver": without, "other_archetype": wrong_arch,
        "shared_seats": shared, "hips_checked": checked, "worst_hips_m": round(worst, 3),
    }  # fmt: skip
    if moving == 0:
        return None, measured, "no NPC vehicle moved between the marks"
    ok = without == 0 and wrong_arch == 0 and shared == 0 and worst <= hips_m
    return ok, measured, "" if ok else first


# ------------------------------------------------------------------ TR-1 density
def check_density(rec: PlayRecord, args: dict) -> Result:
    """Chapter 7, TR-1: between two marks, once a second, the moving NPC vehicles (faster than
    1 km/h since the frame before) and the NPC people on foot within `within_m` of the player
    (horizontally) are counted; the median of every full minute lies within `vehicles` and
    within `people` ([min, max])."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    within = float(args.get("within_m", 150.0))
    dead = dead_ids(run.frames)
    t0 = int(frames[0].get("t", 0))
    samples: list[tuple[int, int, int]] = []
    next_t = t0
    prev, rp = None, None
    for fr in frames:
        rc = rows(fr)
        t = int(fr.get("t", 0))
        if t >= next_t and prev is not None:
            pl = player_of(fr)
            if pl is not None and isinstance(pl.get("p"), list):
                px, pz = flat(pl["p"])
                pv = player_vehicle(fr)
                nv = npl = 0
                for eid, e in rc.items():
                    if not isinstance(e.get("p"), list):
                        continue
                    x, z = flat(e["p"])
                    if math.hypot(x - px, z - pz) > within:
                        continue
                    if e.get("k") == "vehicle" and eid != pv:
                        v = speed(prev, fr, eid, rp, rc)
                        if v is not None and v > KMH:
                            nv += 1
                    elif on_foot(e, {k for k, dt in dead.items() if dt <= t}):
                        npl += 1
                samples.append((t, nv, npl))
            next_t = t0 + TICK_HZ * (len(samples) + 1)
        prev, rp = fr, rc
    minute = TICK_HZ * 60
    windows: list[dict] = []
    if samples:
        full = (samples[-1][0] - samples[0][0] + TICK_HZ) // minute
        for w in range(full):
            lo = samples[0][0] + minute * w
            group = [s for s in samples if lo <= s[0] < lo + minute]
            if len(group) >= 50:
                windows.append(
                    {
                        "from_tick": lo,
                        "vehicles": median(g[1] for g in group),
                        "people": median(g[2] for g in group),
                        "samples": len(group),
                    }
                )
    measured = {"minutes": windows}
    if not windows:
        return None, measured, "less than a minute of samples"
    vlo, vhi = args["vehicles"]
    plo, phi = args["people"]
    for w in windows:
        if not (vlo <= w["vehicles"] <= vhi):
            return (
                False,
                measured,
                f"a minute's median of moving NPC vehicles is {w['vehicles']} (band {vlo}-{vhi})",
            )
        if not (plo <= w["people"] <= phi):
            return (
                False,
                measured,
                f"a minute's median of NPC people on foot is {w['people']} (band {plo}-{phi})",
            )
    return True, measured, ""


# ------------------------------------------------------------------ stop lines
def line_crossings(
    frames: list[dict], approaches: list[dict], skip: object = None
) -> list[dict]:
    """Every crossing of a listed stop line by a vehicle travelling towards its junction:
    [{"vehicle", "approach", "tick" (interpolated), "frame" (index of the frame after)}].
    A line is [[x, z], [x, z]] across the approach's lanes; "toward" is the direction of
    travel towards the junction."""
    out = []
    prev, rp = None, None
    for fi, fr in enumerate(frames):
        rc = rows(fr)
        if prev is not None:
            for eid, e in rc.items():
                if e.get("k") != "vehicle" or eid == skip:
                    continue
                a = rp.get(eid)
                if (
                    not a
                    or not isinstance(a.get("p"), list)
                    or not isinstance(e.get("p"), list)
                ):
                    continue
                (ax, az), (bx, bz) = flat(a["p"]), flat(e["p"])
                for ap in approaches:
                    (l0x, l0z), (l1x, l1z) = ap["line"]
                    tx, tz = ap["toward"]
                    da = (l0x - ax) * tx + (l0z - az) * tz
                    db = (l0x - bx) * tx + (l0z - bz) * tz
                    if not (da > 0 >= db):
                        continue
                    k = da / (da - db)
                    cx, cz = ax + (bx - ax) * k, az + (bz - az) * k
                    lx, lz = l1x - l0x, l1z - l0z
                    ln = math.hypot(lx, lz)
                    u = ((cx - l0x) * lx + (cz - l0z) * lz) / ln if ln else 0.0
                    if -0.5 <= u <= ln + 0.5:
                        t0, t1 = int(prev.get("t", 0)), int(fr.get("t", 0))
                        out.append({"vehicle": eid, "approach": ap["approach"],
                                    "tick": t0 + (t1 - t0) * k, "frame": fi})  # fmt: skip
        prev, rp = fr, rc
    return out


def light_runs(frames: list[dict], approaches: list[dict]) -> dict:
    """{approach: [(tick, state)]} of the signal each listed approach shows in each frame."""
    want = {(ap["intersection"], ap["approach"]) for ap in approaches}
    out: dict = {ap["approach"]: [] for ap in approaches}
    for fr in frames:
        for e in fr.get("census") or []:
            if e.get("k") != "signal":
                continue
            key = (meta(e, "intersection"), meta(e, "approach"))
            if key in want:
                out[key[1]].append((int(fr.get("t", 0)), meta(e, "state")))
    return out


def state_at(run_: list, tick: float) -> tuple[str | None, int | None]:
    """(the state shown in the last frame at or before tick, the tick that state began)."""
    state, since = None, None
    for t, s in run_:
        if t > tick:
            break
        if s != state:
            since = t
        state = s
    return state, since


def check_red_entries(rec: PlayRecord, args: dict) -> Result:
    """TR-5: between two marks no NPC vehicle crosses a listed stop line (its position passing
    the line towards the junction) once the approach's light has shown red for `grace_s`
    (plus one frame for sampling); and no NPC vehicle crosses at amber, or in red's first
    `grace_s`, when at the first frame of that amber it could have stopped before the line
    braking at `amber_mps2` or less (with 10% to spare)."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    approaches = args["approaches"]
    grace = float(args.get("grace_s", 0.5)) * TICK_HZ
    amber_dec = float(args.get("amber_mps2", 4.0)) * 0.9
    pv = player_vehicle(frames[-1])
    crossings = line_crossings(frames, approaches, pv)
    lights = light_runs(frames, approaches)
    step = max(
        (
            int(b.get("t", 0)) - int(a.get("t", 0))
            for a, b in itertools.pairwise(frames)
        ),
        default=1,
    )
    on_red = []
    for c in crossings:
        st, since = state_at(lights.get(c["approach"], []), c["tick"])
        if st == "red" and since is not None and c["tick"] - since >= grace + step:
            on_red.append(c)
    # amber: who could have stopped
    could_stop = []
    by_ap = {ap["approach"]: ap for ap in approaches}
    for apid, seq in lights.items():
        ap = by_ap[apid]
        for (_ta, sa), (tb, sb) in itertools.pairwise(seq):
            if sb != "amber" or sa == "amber":
                continue
            fi = next(
                (i for i, f in enumerate(frames) if int(f.get("t", 0)) == tb), None
            )
            if fi is None or fi == 0:
                continue
            fr, prev = frames[fi], frames[fi - 1]
            rc, rp = rows(fr), rows(prev)
            green_again = next((t for t, s in seq if t > tb and s == "green"), math.inf)
            (l0x, l0z), (l1x, l1z) = ap["line"]
            tx, tz = ap["toward"]
            for eid, e in rc.items():
                if (
                    e.get("k") != "vehicle"
                    or eid == pv
                    or not isinstance(e.get("p"), list)
                ):
                    continue
                x, z = flat(e["p"])
                d = (l0x - x) * tx + (l0z - z) * tz
                lx, lz = l1x - l0x, l1z - l0z
                ln = math.hypot(lx, lz)
                u = ((x - l0x) * lx + (z - l0z) * lz) / ln if ln else 0.0
                if d <= 0.3 or d > 80 or not (-0.5 <= u <= ln + 0.5):
                    continue
                a = rp.get(eid)
                if not a or not isinstance(a.get("p"), list):
                    continue
                ax, az = flat(a["p"])
                dt = int(fr.get("t", 0)) - int(prev.get("t", 0))
                v = ((x - ax) * tx + (z - az) * tz) * TICK_HZ / dt if dt > 0 else 0.0
                if v <= 0.3 or v * v / (2 * d) > amber_dec:
                    continue
                for c in crossings:
                    if (
                        c["vehicle"] == eid
                        and c["approach"] == apid
                        and tb <= c["tick"] < green_again
                    ):
                        could_stop.append(
                            {
                                **c,
                                "amber_tick": tb,
                                "needed_mps2": round(v * v / (2 * d), 2),
                            }
                        )
                        break
    measured = {"crossings": len(crossings), "on_red": len(on_red), "could_have_stopped": len(could_stop),
                "first": (on_red + could_stop)[:3]}  # fmt: skip
    if on_red:
        c = on_red[0]
        return (
            False,
            measured,
            f"vehicle {c['vehicle']} crossed the stop line of {c['approach']} at tick {c['tick']:.0f}, its light red by then",
        )
    if could_stop:
        c = could_stop[0]
        return (
            False,
            measured,
            f"vehicle {c['vehicle']} crossed {c['approach']} at tick {c['tick']:.0f} after amber came at {c['amber_tick']}, when stopping took {c['needed_mps2']} m/s^2",
        )
    return True, measured, ""


def check_green_flow(rec: PlayRecord, args: dict) -> Result:
    """TR-5: between two marks at least `min_vehicles` NPC vehicles cross each listed stop line
    towards its junction."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    approaches = args["approaches"]
    crossings = line_crossings(frames, approaches, player_vehicle(frames[-1]))
    counts = {ap["approach"]: 0 for ap in approaches}
    for c in crossings:
        counts[c["approach"]] += 1
    need = int(args.get("min_vehicles", 3))
    measured = {"entered": counts}
    low = [a for a, n in counts.items() if n < need]
    if low:
        return (
            False,
            measured,
            f"{counts[low[0]]} NPC vehicles entered from {low[0]} (at least {need})",
        )
    return True, measured, ""


# ------------------------------------------------------------------ TR-7 lanes
def check_lane_keeping(rec: PlayRecord, args: dict) -> Result:
    """TR-7: between two marks, over the samples of NPC vehicles whose position lies on a
    listed lane (`lanes`, or the lanes of `area`) (within half its width of its centre line, between its start box and its stop
    line): the offset from the centre line is at most `max_offset_m` at the 95th percentile;
    on samples where they move, their heading (the forward axis) is within `max_heading_deg`
    of the lane's on at least `min_share` of samples, and none moves (faster than 1 km/h)
    more than 90 degrees off its lane's direction; both leave out each lane's first
    `skip_start_m`, where vehicles finish turning out of a junction."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    lanes = [
        Lane(d) for d in (args["lanes"] if "lanes" in args else args["area"]["lanes"])
    ]
    offsets: list[float] = []
    headed = within = against = 0
    first_against = ""
    max_h = math.radians(float(args.get("max_heading_deg", 15.0)))
    skip = float(args.get("skip_start_m", 0.0))
    prev, rp = None, None
    for fr in frames:
        rc = rows(fr)
        pv = player_vehicle(fr)
        for eid, e in rc.items():
            if e.get("k") != "vehicle" or eid == pv or not isinstance(e.get("p"), list):
                continue
            x, z = flat(e["p"])
            got = lane_at(lanes, x, z)
            if got is None:
                continue
            ln, off, (ux, uz) = got
            offsets.append(abs(off))
            s_on = ln.project(x, z)
            late_turn = s_on is not None and s_on[0] < skip
            a = rp.get(eid) if rp else None
            if not a or not isinstance(a.get("p"), list):
                continue
            ax, az = flat(a["p"])
            dt = int(fr.get("t", 0)) - int(prev.get("t", 0))
            if dt <= 0:
                continue
            mx, mz = x - ax, z - az
            v = math.hypot(mx, mz) * TICK_HZ / dt
            if v <= KMH:
                continue
            if (mx * ux + mz * uz) / math.hypot(mx, mz) < 0.0 and not late_turn:
                against += 1
                first_against = (
                    first_against
                    or f"vehicle {eid} moved against {ln.id} at tick {fr.get('t')}"
                )
            bz = e.get("bz")
            if isinstance(bz, list) and not late_turn:
                fx, fz = -float(bz[0]), -float(bz[2])
                fl = math.hypot(fx, fz)
                if fl > 1e-6:
                    headed += 1
                    ang = math.acos(max(-1.0, min(1.0, (fx * ux + fz * uz) / fl)))
                    if ang <= max_h:
                        within += 1
        prev, rp = fr, rc
    if not offsets:
        return None, {}, "no NPC vehicle was seen on the listed lanes"
    offsets.sort()
    p95 = offsets[min(len(offsets) - 1, math.ceil(0.95 * len(offsets)) - 1)]
    share = within / headed if headed else 1.0
    measured = {"samples": len(offsets), "offset_p95_m": round(p95, 3), "heading_share": round(share, 4),
                "against": against}  # fmt: skip
    if against:
        return False, measured, first_against
    if p95 > float(args.get("max_offset_m", 1.0)):
        return (
            False,
            measured,
            f"the 95th percentile offset from the lane centre is {p95:.2f} m",
        )
    if share < float(args.get("min_share", 0.98)):
        return (
            False,
            measured,
            f"the heading is within {args.get('max_heading_deg', 15.0)} degrees of the lane's on {share:.1%} of samples",
        )
    return True, measured, ""


def check_lane_speeds(rec: PlayRecord, args: dict) -> Result:
    """TR-8: between two marks, NPC vehicles on the listed lanes (`lanes`, or the lanes of
    `area`; each with its `limit_kmh`)
    keep to the limit plus 10%: their speed over every `window` ticks (from positions, the
    lane taken at the window's end) never exceeds the limit times `share`."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    lanes = [
        Lane(d) for d in (args["lanes"] if "lanes" in args else args["area"]["lanes"])
    ]
    window = int(args.get("window", 6))
    share = float(args.get("share", 1.1))
    tracks: dict = {}
    pv = player_vehicle(frames[-1])
    for fr in frames:
        for e in fr.get("census") or []:
            if (
                e.get("k") == "vehicle"
                and e.get("id") != pv
                and isinstance(e.get("p"), list)
            ):
                tracks.setdefault(e["id"], []).append(
                    (int(fr.get("t", 0)), flat(e["p"]))
                )
    worst, samples, over = 0.0, 0, []
    for eid, tr in tracks.items():
        j = 0
        for i in range(len(tr)):
            while j < i and tr[i][0] - tr[j][0] > window:
                j += 1
            if tr[i][0] - tr[j][0] < window:
                continue
            got = lane_at(lanes, *tr[i][1])
            if got is None or got[0].limit <= 0:
                continue
            v = math.dist(tr[i][1], tr[j][1]) * TICK_HZ / (tr[i][0] - tr[j][0]) * 3.6
            samples += 1
            ratio = v / got[0].limit
            worst = max(worst, ratio)
            if ratio > share:
                over.append({"vehicle": eid, "tick": tr[i][0], "kmh": round(v, 1), "lane": got[0].id,
                             "limit_kmh": got[0].limit})  # fmt: skip
    measured = {
        "samples": samples,
        "worst_share_of_limit": round(worst, 3),
        "over": over[:3],
    }
    if samples == 0:
        return None, measured, "no NPC vehicle was seen on the listed lanes"
    if over:
        o = over[0]
        return (
            False,
            measured,
            f"vehicle {o['vehicle']} drove {o['kmh']} km/h on {o['lane']} (limit {o['limit_kmh']})",
        )
    return True, measured, ""


# ------------------------------------------------------------------ TR-9, TR-10, TR-11 people
def check_walkable(rec: PlayRecord, args: dict) -> Result:
    """TR-9: between two marks, at least `min_share` of the samples of NPC people on foot
    within the area stand on walkable ground: a crosswalk band; a block outside every
    building's footprint (sidewalks, plazas, parks, parking lots, forecourts) or a room of an
    interior; or ground off the road network (outside every carriageway and junction box)."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    area = Area(args["area"])
    dead = set(dead_ids(run.frames))
    total = good = 0
    first = ""
    for fr in frames:
        for e in fr.get("census") or []:
            if (
                not on_foot(e, dead)
                or meta(e, "limp")
                or not isinstance(e.get("p"), list)
            ):
                continue
            x, z = flat(e["p"])
            if not area.near(x, z):
                continue
            total += 1
            if area.walkable(x, z):
                good += 1
            else:
                first = (
                    first
                    or f"person {e.get('id')} at ({x:.1f}, {z:.1f}), tick {fr.get('t')}"
                )
    if total == 0:
        return None, {}, "nobody on foot was seen in the area"
    share = good / total
    measured = {"samples": total, "walkable_share": round(share, 4), "first_off": first}
    ok = share >= float(args.get("min_share", 0.95))
    return (
        ok,
        measured,
        "" if ok else f"{share:.1%} of samples on walkable ground ({first})",
    )


def road_crossings(frames: list[dict], area: Area, dead: set) -> list[dict]:
    """The road crossings of NPC people on foot: runs of samples on a carriageway or junction
    box between samples off the road, as {"person", "start", "end" (positions), "start_frame",
    "end_frame"}; runs cut by the ends of the frames are left out."""
    on: dict = {}
    out = []
    for fi, fr in enumerate(frames):
        seen = set()
        for e in fr.get("census") or []:
            if (
                not on_foot(e, dead)
                or meta(e, "limp")
                or not isinstance(e.get("p"), list)
            ):
                continue
            eid = e.get("id")
            seen.add(eid)
            x, z = flat(e["p"])
            road = area.near(x, z) and area.on_road(x, z)
            cur = on.get(eid)
            if road:
                if cur is None:
                    on[eid] = {"person": eid, "start": (x, z), "start_frame": fi, "last": (x, z),
                               "clean": fi > 0}  # fmt: skip
                else:
                    cur["last"] = (x, z)
            elif cur is not None:
                if cur["clean"]:
                    out.append({"person": eid, "start": cur["start"], "end": cur["last"],
                                "start_frame": cur["start_frame"], "end_frame": fi})  # fmt: skip
                del on[eid]
        for eid in list(on):
            if eid not in seen:
                del on[eid]
    return out


def check_crosswalk_use(rec: PlayRecord, args: dict) -> Result:
    """TR-10: between two marks, of the road crossings of NPC people on foot in the area (from
    the first sample on a carriageway or junction box to the last before stepping off it), at
    least `min_share` start and end on a crosswalk band; a crossing that starts on a band with
    walk signals starts while it shows walk (in that frame or the one before); one that starts
    on a band at an all-way stop starts with no NPC vehicle approaching the band: moving
    faster than 1 km/h with its line of travel (from its position, `gap_m` long) entering
    the band."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    area = Area(args["area"])
    dead = set(dead_ids(run.frames))
    gap_m = float(args.get("gap_m", 15.0))
    crossings = road_crossings(frames, area, dead)
    in_bands = 0
    off_walk, too_close = [], []
    walk_of: list[dict] = []
    for fr in frames:
        w = {}
        for e in fr.get("census") or []:
            if e.get("k") == "signal" and meta(e, "crosswalk") is not None:
                w[meta(e, "crosswalk")] = meta(e, "state")
        walk_of.append(w)
    for c in crossings:
        a = area.crosswalk(*c["start"])
        b = area.crosswalk(*c["end"])
        if a is not None and b is not None:
            in_bands += 1
        if a is None:
            continue
        fi = c["start_frame"]
        if a.get("walk_signals"):
            states = [
                walk_of[fi].get(a["id"]),
                walk_of[fi - 1].get(a["id"]) if fi > 0 else None,
            ]
            if "walk" not in states:
                off_walk.append(
                    {
                        "person": c["person"],
                        "crosswalk": a["id"],
                        "tick": frames[fi].get("t"),
                    }
                )
        elif a.get("control") == "stop":
            fr, prev = frames[fi], frames[fi - 1] if fi > 0 else None
            rc = rows(fr)
            rp = rows(prev) if prev else {}
            for eid, e in rc.items():
                if e.get("k") != "vehicle" or not isinstance(e.get("p"), list):
                    continue
                x, z = flat(e["p"])
                if poly_dist(a["poly"], x, z) > gap_m:
                    continue
                p0 = rp.get(eid)
                if not p0 or not isinstance(p0.get("p"), list):
                    continue
                ax, az = flat(p0["p"])
                dt = int(fr.get("t", 0)) - int(prev.get("t", 0))
                mx, mz = x - ax, z - az
                mv = math.hypot(mx, mz)
                if dt <= 0 or mv * TICK_HZ / dt <= KMH:
                    continue
                if path_enters(a["poly"], x, z, mx / mv, mz / mv, gap_m):
                    too_close.append({"person": c["person"], "crosswalk": a["id"], "vehicle": eid,
                                      "tick": fr.get("t")})  # fmt: skip
                    break
    share = in_bands / len(crossings) if crossings else 1.0
    measured = {"crossings": len(crossings), "on_bands_share": round(share, 4),
                "started_off_walk": off_walk[:3], "started_with_traffic": too_close[:3]}  # fmt: skip
    if not crossings:
        return None, measured, "nobody crossed a road in the area"
    if share < float(args.get("min_share", 0.9)):
        return (
            False,
            measured,
            f"{share:.0%} of road crossings started and ended on a crosswalk band",
        )
    if off_walk:
        o = off_walk[0]
        return (
            False,
            measured,
            f"person {o['person']} started across {o['crosswalk']} at tick {o['tick']} while it showed don't walk",
        )
    if too_close:
        o = too_close[0]
        return (
            False,
            measured,
            f"person {o['person']} started across {o['crosswalk']} at tick {o['tick']} with vehicle {o['vehicle']} within {gap_m:g} m coming towards it",
        )
    return True, measured, ""


def check_crosswalk_hits(rec: PlayRecord, args: dict) -> Result:
    """TR-11: between two marks no NPC vehicle touches a person standing on a crosswalk band:
    the vehicle's collision boxes never come within `clear_m` of the person's position; and
    nobody goes limp on a crosswalk band."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    area = Area(args["area"])
    clear = float(args.get("clear_m", 0.3))
    hits, limp, on_bands, boxed = [], [], 0, 0
    for fr in frames:
        rc = rows(fr)
        pv = player_vehicle(fr)
        people = []
        for e in rc.values():
            if (
                e.get("k") in ("npc", "player")
                and meta(e, "vehicle") is None
                and isinstance(e.get("p"), list)
            ):
                x, z = flat(e["p"])
                if area.crosswalk(x, z) is not None:
                    people.append((e, x, z))
                    if meta(e, "limp"):
                        limp.append({"person": e.get("id"), "tick": fr.get("t")})
        if not people:
            continue
        on_bands += len(people)
        for vid, v in rc.items():
            if v.get("k") != "vehicle" or vid == pv:
                continue
            shp = shapes_of(v)
            if not shp:
                continue
            boxed += 1
            for e, x, z in people:
                if point_gap(shp, x, z) <= clear:
                    hits.append(
                        {"vehicle": vid, "person": e.get("id"), "tick": fr.get("t")}
                    )
    measured = {"samples_on_bands": on_bands, "vehicle_boxes_read": boxed, "touches": hits[:3],
                "limp_on_bands": limp[:3]}  # fmt: skip
    if on_bands == 0:
        return None, measured, "nobody was seen on a crosswalk band"
    if hits:
        h = hits[0]
        return (
            False,
            measured,
            f"vehicle {h['vehicle']} touched person {h['person']} on a crosswalk at tick {h['tick']}",
        )
    if limp:
        return (
            False,
            measured,
            f"person {limp[0]['person']} went limp on a crosswalk at tick {limp[0]['tick']}",
        )
    return True, measured, ""


# ------------------------------------------------------------------ TR-12 collisions and obstacles
def check_vehicle_contacts(rec: PlayRecord, args: dict) -> Result:
    """TR-12: between two marks, NPC vehicles collide with each other at most `max_rate` times
    per vehicle per minute of moving NPC vehicles. A collision starts in a frame where the
    collision boxes of two NPC vehicles touch (within `touch_m`) after a frame where they did
    not; it counts once for each of the two, and the same two count again only after being
    apart for `apart_s`."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    touch = float(args.get("touch_m", 0.02))
    apart = float(args.get("apart_s", 1.0)) * TICK_HZ
    last_touch: dict = {}
    counted: dict = {}
    events = []
    moving_ticks = 0.0
    prev, rp = None, None
    for fr in frames:
        rc = rows(fr)
        pv = player_vehicle(fr)
        t = int(fr.get("t", 0))
        vs = [
            (vid, shapes_of(v), v)
            for vid, v in rc.items()
            if v.get("k") == "vehicle" and vid != pv
        ]
        if prev is not None:
            dt = t - int(prev.get("t", 0))
            for vid, _s, _v in vs:
                sp = speed(prev, fr, vid, rp, rc)
                if sp is not None and sp > KMH:
                    moving_ticks += dt
        boxes = [(vid, s, v) for vid, s, v in vs if s]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                pa, pb = a[2].get("p"), b[2].get("p")
                if (
                    isinstance(pa, list)
                    and isinstance(pb, list)
                    and math.dist(flat(pa), flat(pb)) > 15.0
                ):
                    continue
                key = (min(a[0], b[0]), max(a[0], b[0]))
                if shapes_gap(a[1], b[1]) <= touch:
                    lt = last_touch.get(key)
                    if lt is None or t - lt > apart:
                        if key not in counted or t - counted[key] > apart:
                            events.append({"vehicles": list(key), "tick": t})
                        counted[key] = t
                    last_touch[key] = t
        prev, rp = fr, rc
    minutes = moving_ticks / TICK_HZ / 60.0
    rate = (2 * len(events)) / minutes if minutes > 0 else 0.0
    measured = {"collisions": len(events), "moving_vehicle_minutes": round(minutes, 2),
                "per_vehicle_minute": round(rate, 4), "first": events[:3]}  # fmt: skip
    if minutes <= 0:
        return None, measured, "no NPC vehicle moved between the marks"
    ok = rate <= float(args.get("max_rate", 0.02))
    return (
        ok,
        measured,
        ""
        if ok
        else f"{len(events)} collisions between NPC vehicles over {minutes:.1f} vehicle-minutes",
    )


def check_stop_short(rec: PlayRecord, args: dict) -> Result:
    """TR-12: between two marks no NPC vehicle touches a stationary obstacle: its collision
    boxes never come within `touch_m` of a listed prop's box (`props`, placed with
    prop.spawn), of a listed vehicle's collision boxes (`vehicles`, ids), or within `person_m`
    of a listed person's position (`people`, ids); and each listed driving vehicle (`drivers`,
    ids) comes to a stand (1 km/h or less) while it is within `stop_within_m` of one of them."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    answers = _answers(run)
    props = [prop_outline(b) for b in args.get("props", [])]
    obst_v = [_ref(x, answers) for x in args.get("vehicles", [])]
    obst_p = [_ref(x, answers) for x in args.get("people", [])]
    drivers = [_ref(x, answers) for x in args.get("drivers", [])]
    touch = float(args.get("touch_m", 0.02))
    person_m = float(args.get("person_m", 0.3))
    within = float(args.get("stop_within_m", 30.0))
    touches = []
    nearest = {d: math.inf for d in drivers}
    stood = {d: False for d in drivers}
    prev, rp = None, None
    pv = player_vehicle(frames[-1])
    for fr in frames:
        rc = rows(fr)
        for vid, v in rc.items():
            if v.get("k") != "vehicle" or vid == pv or vid in obst_v:
                continue
            shp = shapes_of(v)
            if not shp:
                continue
            gaps = [shapes_gap(shp, [(o, -1e9, 1e9)]) for o in props]
            gaps += [shapes_gap(shp, shapes_of(rc[o])) for o in obst_v if o in rc]
            gaps += [
                point_gap(shp, *flat(rc[o]["p"])) - person_m
                for o in obst_p
                if o in rc and isinstance(rc[o].get("p"), list)
            ]
            g = min(gaps, default=math.inf)
            if vid in nearest:
                nearest[vid] = min(nearest[vid], g)
                sp = speed(prev, fr, vid, rp, rc)
                if sp is not None and sp <= KMH and g <= within:
                    stood[vid] = True
            if g <= touch:
                touches.append(
                    {"vehicle": vid, "tick": fr.get("t"), "gap_m": round(g, 3)}
                )
        prev, rp = fr, rc
    measured = {"touches": touches[:3], "closest_m": {str(k): round(v, 2) for k, v in nearest.items()},
                "stood": {str(k): v for k, v in stood.items()}}  # fmt: skip
    if touches:
        t = touches[0]
        return (
            False,
            measured,
            f"vehicle {t['vehicle']} touched an obstacle at tick {t['tick']}",
        )
    missing = [d for d, s in stood.items() if not s]
    if missing:
        return (
            False,
            measured,
            f"vehicle {missing[0]} never stood still within {within:g} m of the obstacle",
        )
    return True, measured, ""


def _answers(run: RunRecord) -> dict:
    out: dict = {}
    for fr in run.frames:
        for d in fr.get("dev") or []:
            out.setdefault(fr.get("_step"), []).append(d)
    return out


def _ref(x: object, answers: dict) -> object:
    """An id given as a number, or as {"step", "index"} (the id a command answered with)."""
    if isinstance(x, dict) and "step" in x:
        got = answers.get(int(x["step"])) or []
        k = int(x.get("index", 0))
        res = got[k].get("res") if k < len(got) else None
        return res.get("id") if isinstance(res, dict) else None
    return x


# ------------------------------------------------------------------ TR-13, TR-14 reactions
def check_horn_clear(rec: PlayRecord, args: dict) -> Result:
    """TR-14: the people listed (`people`, ids) who stand in the lane (`lane`: its centre line
    and width) within `ahead_m` ahead of the vehicle (`vehicle`, id) at the first mark, where
    `horn` is pressed, are out of the lane's band (more than half its width from its centre
    line) within `within_s`."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    answers = _answers(run)
    lane = Lane(args["lane"])
    vid = _ref(args["vehicle"], answers)
    people = [_ref(x, answers) for x in args["people"]]
    t0 = int(frames[0].get("t", 0))
    r0 = rows(frames[0])
    v = r0.get(vid)
    if not v or not isinstance(v.get("p"), list):
        return None, {}, "the honking vehicle was not seen at the first mark"
    vx, vz = flat(v["p"])
    bz = v.get("bz") or [0, 0, 1]
    fx, fz = -float(bz[0]), -float(bz[2])
    fl = math.hypot(fx, fz) or 1.0
    fx, fz = fx / fl, fz / fl
    ahead = float(args.get("ahead_m", 20.0))
    subjects = []
    for pid in people:
        e = r0.get(pid)
        if not e or not isinstance(e.get("p"), list):
            continue
        x, z = flat(e["p"])
        along = (x - vx) * fx + (z - vz) * fz
        pr = lane.project(x, z)
        if 0 < along <= ahead and pr is not None and abs(pr[1]) <= lane.width / 2:
            subjects.append(pid)
    if not subjects:
        return (
            None,
            {},
            "nobody stood in the lane ahead of the vehicle when the horn sounded",
        )
    limit = float(args.get("within_s", 3.0)) * TICK_HZ
    out_at: dict = {}
    for fr in frames:
        t = int(fr.get("t", 0))
        rc = rows(fr)
        for pid in subjects:
            if pid in out_at:
                continue
            e = rc.get(pid)
            if not e or not isinstance(e.get("p"), list):
                continue
            pr = lane.project(*flat(e["p"]))
            if pr is None or abs(pr[1]) > lane.width / 2:
                out_at[pid] = t - t0
    measured = {
        "in_lane": subjects,
        "out_after_s": {str(k): round(v / TICK_HZ, 2) for k, v in out_at.items()},
    }
    late = [p for p in subjects if p not in out_at or out_at[p] > limit]
    if late:
        return (
            False,
            measured,
            f"person {late[0]} was still in the lane {args.get('within_s', 3.0)} s after the horn",
        )
    return True, measured, ""


def check_sidewalk_dodge(rec: PlayRecord, args: dict) -> Result:
    """TR-13: while the vehicle (`vehicle`, id) drives on a sidewalk (its position inside a
    listed block) at `min_kmh` or more, the people on foot standing in its path (within half
    its width plus `clear_m` of its line of travel) anywhere up to `ahead_m` ahead of it step
    out of the path before it reaches them: its collision boxes never come within `clear_m` of
    their positions, and none of them goes limp. (A person who stays in the path until the
    vehicle is 8 m away is run into.)"""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    answers = _answers(run)
    vid = _ref(args["vehicle"], answers)
    blocks = args["blocks"]
    min_v = float(args.get("min_kmh", 20.0)) * KMH
    ahead = float(args.get("ahead_m", 60.0))
    clear = float(args.get("clear_m", 0.3))
    on_walk = 0
    subjects: set = set()
    touches, limp = [], []
    prev, rp = None, None
    for fr in frames:
        rc = rows(fr)
        v = rc.get(vid)
        sp = speed(prev, fr, vid, rp, rc)
        if v and isinstance(v.get("p"), list) and sp is not None and sp >= min_v:
            vx, vz = flat(v["p"])
            if any(inside(b, vx, vz) for b in blocks):
                on_walk += 1
                a = rp.get(vid)
                ax, az = flat(a["p"])
                fx, fz = vx - ax, vz - az
                fl = math.hypot(fx, fz) or 1.0
                fx, fz = fx / fl, fz / fl
                shp = shapes_of(v)
                half = max(
                    (
                        max(abs((p[0] - vx) * -fz + (p[1] - vz) * fx) for p in o)
                        for o, _l, _h in shp
                    ),
                    default=1.0,
                )
                for e in rc.values():
                    if (
                        e.get("k") != "npc"
                        or meta(e, "vehicle") is not None
                        or not isinstance(e.get("p"), list)
                    ):
                        continue
                    x, z = flat(e["p"])
                    along = (x - vx) * fx + (z - vz) * fz
                    lat = (x - vx) * -fz + (z - vz) * fx
                    if 0 < along <= ahead and abs(lat) <= half + clear:
                        subjects.add(e.get("id"))
        if v:
            shp = shapes_of(v)
            for pid in subjects:
                e = rc.get(pid)
                if not e or not isinstance(e.get("p"), list):
                    continue
                if shp and point_gap(shp, *flat(e["p"])) <= clear:
                    touches.append({"person": pid, "tick": fr.get("t")})
                if meta(e, "limp"):
                    limp.append({"person": pid, "tick": fr.get("t")})
        prev, rp = fr, rc
    measured = {"frames_on_sidewalk": on_walk, "people_ahead": sorted(subjects), "touches": touches[:3],
                "limp": limp[:3]}  # fmt: skip
    if on_walk == 0:
        return (
            None,
            measured,
            f"the vehicle never drove on the sidewalk at {args.get('min_kmh', 20.0)} km/h or more",
        )
    if not subjects:
        return None, measured, "nobody stood ahead of the vehicle on the sidewalk"
    if touches:
        return (
            False,
            measured,
            f"the vehicle touched person {touches[0]['person']} at tick {touches[0]['tick']}",
        )
    if limp:
        return (
            False,
            measured,
            f"person {limp[0]['person']} went limp at tick {limp[0]['tick']}",
        )
    return True, measured, ""


# ------------------------------------------------------------------ TR-15 pop-in
def check_no_pop_in(rec: PlayRecord, args: dict) -> Result:
    """TR-15: between two marks, NPC people and vehicles that join the census are at least
    `near_m` from the player (less the distance they could have covered since the frame
    before, at their speed in the next frame) and, nearer than `view_m`, outside the camera's
    view (the census's in-view flag); those that leave it are held to the same in the last
    frame that shows them. A frame made by a DevConsole step (a setup command's tick) is let
    off, as TR-15 allows, and so are the frames up to `settle_s` after a world.reset or a
    load."""
    run = rec.runs[int(args.get("run", 0))]
    i, j = run.marks.get(args["from"]), run.marks.get(args["to"])
    if i is None or j is None:
        return None, {}, "the marks were not reached"
    setups = setup_frames(rec, run, float(args.get("settle_s", 3.0)))
    near_m = float(args.get("near_m", 80.0))
    view_m = float(args.get("view_m", 200.0))
    kinds = set(args.get("kinds", ["npc", "vehicle"]))
    appeared = vanished = 0
    bad = []
    for k in range(i + 1, j + 1):
        before, fr = run.frames[k - 1], run.frames[k]
        if k in setups:
            continue
        rb, rf = rows(before), rows(fr)
        pl = player_of(fr) or player_of(before)
        if pl is None or not isinstance(pl.get("p"), list):
            continue
        px, pz = flat(pl["p"])
        dt = max(1, int(fr.get("t", 0)) - int(before.get("t", 0)))
        nxt = run.frames[k + 1] if k + 1 < len(run.frames) else None
        rn = rows(nxt) if nxt is not None else {}
        for eid, e in rf.items():
            if eid in rb or e.get("k") not in kinds or not isinstance(e.get("p"), list):
                continue
            appeared += 1
            x, z = flat(e["p"])
            d = math.hypot(x - px, z - pz)
            sp = speed(fr, nxt, eid, rf, rn) if nxt is not None else None
            allow = (sp or 0.0) * dt / TICK_HZ + 0.5
            if d < near_m - allow or (d < view_m - allow and e.get("iv") is True):
                bad.append(
                    {
                        "entity": eid,
                        "appeared_at_m": round(d, 1),
                        "in_view": e.get("iv"),
                        "tick": fr.get("t"),
                    }
                )
        for eid, e in rb.items():
            if eid in rf or e.get("k") not in kinds or not isinstance(e.get("p"), list):
                continue
            vanished += 1
            x, z = flat(e["p"])
            bpl = player_of(before) or pl
            bx, bz = flat(bpl["p"])
            d = math.hypot(x - bx, z - bz)
            if d < near_m - 0.5 or (d < view_m - 0.5 and e.get("iv") is True):
                bad.append(
                    {
                        "entity": eid,
                        "left_at_m": round(d, 1),
                        "in_view": e.get("iv"),
                        "tick": before.get("t"),
                    }
                )
    measured = {
        "appeared": appeared,
        "left": vanished,
        "too_near": bad[:5],
        "too_near_count": len(bad),
    }
    if bad:
        b = bad[0]
        where = b.get("appeared_at_m", b.get("left_at_m"))
        what = "appeared" if "appeared_at_m" in b else "left"
        return (
            False,
            measured,
            f"entity {b['entity']} {what} {where} m from the player at tick {b['tick']}"
            + (" in view" if b["in_view"] else ""),
        )
    return True, measured, ""


# ------------------------------------------------------------------ TR-6 all-way stops
PASS_GAP = 10 * TICK_HZ  # ticks out of the box before a vehicle's next pass begins


def _stop_events(
    frames: list[dict], approaches: list[dict], box: list, zone_m: float, pv: object
) -> dict:
    """For each pass of an NPC vehicle through the all-way stop: {"arrive": tick,
    "approach", "go": tick (its line crossing), "box_in": tick, "box_out": tick, "entry":
    (x, z), "exit": (x, z), "stood": bool (it stood within zone_m before the line before
    crossing)}, keyed by the vehicle's id (a later pass, when it comes back to a listed
    approach more than PASS_GAP ticks after it was last in the box, by "id#2", "id#3"...). A vehicle arrives the first frame it
    stands (1 km/h or less) within zone_m before a listed line with no vehicle between it and
    the line in the approach's lanes."""
    ev: dict = {}
    cur: dict = {}  # vehicle id -> the key of its current pass
    passes: dict = {}  # vehicle id -> passes so far
    prev, rp = None, None
    for fr in frames:
        rc = rows(fr)
        t = int(fr.get("t", 0))
        here: dict = {}
        for eid, e in rc.items():
            if e.get("k") != "vehicle" or eid == pv or not isinstance(e.get("p"), list):
                continue
            x, z = flat(e["p"])
            for ap in approaches:
                (l0x, l0z), (l1x, l1z) = ap["line"]
                tx, tz = ap["toward"]
                d = (l0x - x) * tx + (l0z - z) * tz
                lx, lz = l1x - l0x, l1z - l0z
                ln = math.hypot(lx, lz)
                u = ((x - l0x) * lx + (z - l0z) * lz) / ln if ln else 0.0
                if -0.5 <= u <= ln + 0.5 and -1.0 < d <= 40.0:
                    here[eid] = (ap["approach"], d, u)
        for eid, (apid, d, u) in here.items():
            key = cur.get(eid)
            if key is not None and t - ev[key].get("box_out", t) > PASS_GAP:
                # back at the junction a while after leaving its box: a new pass
                passes[eid] = passes.get(eid, 1) + 1
                key = f"{eid}#{passes[eid]}"
            if key is None:
                key = eid
            cur[eid] = key
            rec_ = ev.setdefault(key, {"approach": apid})
            sp = speed(prev, fr, eid, rp, rc)
            if 0 < d <= zone_m and sp is not None and sp <= KMH and "go" not in rec_:
                rec_["stood"] = True
                ahead = any(o != eid and oa == apid and 0 < od < d and abs(ou - u) < 2.0
                            for o, (oa, od, ou) in here.items())  # fmt: skip
                if "arrive" not in rec_ and not ahead:
                    rec_["arrive"] = t
        for eid, e in rc.items():
            if eid not in cur or not isinstance(e.get("p"), list):
                continue
            x, z = flat(e["p"])
            r = ev[cur[eid]]
            if eid in here and "go" not in r and here[eid][1] <= 0:
                r["go"] = t
            if inside(box, x, z):
                r.setdefault("box_in", t)
                r.setdefault("entry", (x, z))
                r["box_out"] = t
                r["exit"] = (x, z)
        prev, rp = fr, rc
    return ev


def _paths_cross(a: dict, b: dict) -> bool:
    """Whether two vehicles' straight paths through the box (from where each entered it to
    where it left) meet, or end within 1.5 m of each other (they left by the same lane)."""
    if "entry" not in a or "entry" not in b:
        return False
    (p1, p2), (q1, q2) = (a["entry"], a["exit"]), (b["entry"], b["exit"])
    if math.dist(p2, q2) < 1.5:
        return True

    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1, d2 = orient(q1, q2, p1), orient(q1, q2, p2)
    d3, d4 = orient(p1, p2, q1), orient(p1, p2, q2)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def _stop_args(rec: PlayRecord, args: dict):
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    pv = player_vehicle(frames[-1]) if frames else None
    ev = _stop_events(
        frames, args["approaches"], args["box"], float(args.get("zone_m", 4.0)), pv
    )
    return frames, ev


def check_stop_full(rec: PlayRecord, args: dict) -> Result:
    """TR-6: every NPC vehicle that crosses a listed stop line of the all-way stop between the
    marks first stood (1 km/h or less) with its position within `zone_m` before that line."""
    frames, ev = _stop_args(rec, args)
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    went = {k: v for k, v in ev.items() if "go" in v}
    rolled = [k for k, v in went.items() if not v.get("stood")]
    measured = {"crossed": len(went), "without_stopping": rolled[:5]}
    if not went:
        return None, measured, "no NPC vehicle crossed a stop line"
    if rolled:
        return (
            False,
            measured,
            f"vehicle {rolled[0]} crossed its stop line without standing within {args.get('zone_m', 4.0)} m before it",
        )
    return True, measured, ""


def check_stop_order(rec: PlayRecord, args: dict) -> Result:
    """TR-6: NPC vehicles at the all-way stop go in order of arrival. A vehicle arrives the
    first frame it stands (1 km/h or less) within `zone_m` before its stop line with no vehicle
    ahead of it in its approach's lanes, and goes when it crosses the line. Of two vehicles on
    different approaches whose paths through the box cross: when they arrived `late_s` or more
    apart, the earlier crosses first; when exactly two vehicles arrived within `tie_s` of each
    other (no third within `tie_s` of either) and one came from the other's right
    (`right_of`: {approach: the approach on its right}), that one crosses first. Other pairs,
    and three or four arriving together, may go in any order."""
    frames, ev = _stop_args(rec, args)
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    late = float(args.get("late_s", 1.2)) * TICK_HZ
    tie = float(args.get("tie_s", 0.8)) * TICK_HZ
    right_of = args.get("right_of", {})
    done = [(k, v) for k, v in ev.items() if "arrive" in v and "go" in v]
    arrived = [v["arrive"] for v in ev.values() if "arrive" in v]

    def crowd(t0: int) -> int:
        return sum(1 for t in arrived if abs(t - t0) <= tie)

    wrong, pairs = [], 0
    for x in range(len(done)):
        for y in range(x + 1, len(done)):
            (ka, a), (kb, b) = done[x], done[y]
            if a["approach"] == b["approach"] or not _paths_cross(a, b):
                continue
            pairs += 1
            gap = b["arrive"] - a["arrive"]
            if abs(gap) >= late:
                first, second = (a, b) if gap > 0 else (b, a)
                if second["go"] < first["go"]:
                    wrong.append(
                        {
                            "earlier": ka if first is a else kb,
                            "later": kb if first is a else ka,
                        }
                    )
            elif (
                abs(gap) <= tie and crowd(a["arrive"]) == 2 and crowd(b["arrive"]) == 2
            ):
                if right_of.get(a["approach"]) == b["approach"] and a["go"] < b["go"]:
                    wrong.append({"right": kb, "went_after": ka})
                elif right_of.get(b["approach"]) == a["approach"] and b["go"] < a["go"]:
                    wrong.append({"right": ka, "went_after": kb})
    measured = {
        "vehicles": len(done),
        "crossing_pairs": pairs,
        "out_of_order": wrong[:3],
    }
    if not done:
        return None, measured, "no NPC vehicle arrived and went"
    if wrong:
        return False, measured, f"out of order: {wrong[0]}"
    return True, measured, ""


def check_box_clear(rec: PlayRecord, args: dict) -> Result:
    """TR-6: between the marks no two NPC vehicles whose paths through the junction box cross
    (see stop_order) are in the box at the same time."""
    frames, ev = _stop_args(rec, args)
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    inside_ = [(k, v) for k, v in ev.items() if "box_in" in v]
    both = []
    for x in range(len(inside_)):
        for y in range(x + 1, len(inside_)):
            (ka, a), (kb, b) = inside_[x], inside_[y]
            overlap = a["box_in"] <= b["box_out"] and b["box_in"] <= a["box_out"]
            if (
                overlap
                and a.get("approach") != b.get("approach")
                and _paths_cross(a, b)
            ):
                both.append([ka, kb])
    measured = {"through_box": len(inside_), "together": both[:3]}
    if not inside_:
        return None, measured, "no NPC vehicle went through the box"
    if both:
        return (
            False,
            measured,
            f"vehicles {both[0][0]} and {both[0][1]} were in the box at once on crossing paths",
        )
    return True, measured, ""


def check_stop_wait(rec: PlayRecord, args: dict) -> Result:
    """TR-6: no NPC vehicle waits more than `max_s` at a stop line: from its arrival to
    crossing the line (one still waiting at the second mark counts until then)."""
    frames, ev = _stop_args(rec, args)
    if len(frames) < 2:
        return None, {}, "the marks were not reached"
    t_end = int(frames[-1].get("t", 0))
    waits = {
        k: (v.get("go", t_end) - v["arrive"]) / TICK_HZ
        for k, v in ev.items()
        if "arrive" in v
    }
    worst = max(waits.values(), default=0.0)
    measured = {"arrivals": len(waits), "longest_wait_s": round(worst, 2)}
    if not waits:
        return None, measured, "no NPC vehicle arrived at a stop line"
    if worst > float(args.get("max_s", 30.0)):
        return False, measured, f"a vehicle waited {worst:.1f} s at a stop line"
    return True, measured, ""


CHECKS = {
    "drivers": check_drivers,
    "density": check_density,
    "red_entries": check_red_entries,
    "green_flow": check_green_flow,
    "lane_keeping": check_lane_keeping,
    "lane_speeds": check_lane_speeds,
    "walkable": check_walkable,
    "crosswalk_use": check_crosswalk_use,
    "crosswalk_hits": check_crosswalk_hits,
    "vehicle_contacts": check_vehicle_contacts,
    "stop_short": check_stop_short,
    "horn_clear": check_horn_clear,
    "sidewalk_dodge": check_sidewalk_dodge,
    "no_pop_in": check_no_pop_in,
    "stop_full": check_stop_full,
    "stop_order": check_stop_order,
    "box_clear": check_box_clear,
    "stop_wait": check_stop_wait,
}
