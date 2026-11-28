"""Checks of weapons, aiming, cover and fights (design document, chapter 8, with FT-11, FT-12,
CM-5 and TR-13's gunshots).

They read the state report of a play's frames (`player.weapon`, `player.ammo`, `player.aim`,
`player.cover`, `player.health`, `player.armour`, `player.id`), its `damaged` and `died` events
(AC-13: one `damaged` event per hit, `amount` the hit's damage before armour, `health` and
`armour` the values after it, `source` the attacker's id), the census (positions, and the
metadata `hostile` and `limp` when a play observes them), bones and the camera.

A round is a drop of the magazine in the state report (one round per round dropped). Times are
frame ticks, at 60 per second. People are named by the id a command answered with:
{"step": i, "index": k} (the k-th answer of step i), or by an id.
"""

from __future__ import annotations

import math

from .play import PlayRecord, RunRecord

TICK_HZ = 60
Result = tuple[bool | None, dict, str]


# ------------------------------------------------------------------ reading frames
def frames_between(run: RunRecord, a: str, b: str) -> list[dict]:
    """The frames from mark a to mark b, both included (empty when a mark is missing)."""
    i, j = run.marks.get(a), run.marks.get(b)
    if i is None or j is None:
        return []
    return run.frames[i : j + 1]


def frames_from(run: RunRecord, a: str, seconds: float) -> list[dict]:
    """The frames from mark a until `seconds` of play after it (same game process)."""
    i = run.marks.get(a)
    if i is None:
        return []
    t0, proc = int(run.frames[i].get("t", 0)), run.frames[i].get("_proc")
    out = []
    for fr in run.frames[i:]:
        if fr.get("_proc") != proc or int(fr.get("t", 0)) - t0 > seconds * TICK_HZ:
            break
        out.append(fr)
    return out


def state_of(frame: dict | None) -> dict:
    st = (frame or {}).get("state")
    if not isinstance(st, dict):
        return {}
    inner = st.get("state")
    return inner if isinstance(inner, dict) else st


def player_state(frame: dict | None) -> dict:
    pl = state_of(frame).get("player")
    return pl if isinstance(pl, dict) else {}


def player_id(frames: list[dict]) -> object:
    for fr in frames:
        pid = player_state(fr).get("id")
        if pid is not None:
            return pid
    return None


def events(frames: list[dict], name: str) -> list[tuple[int, dict]]:
    """(frame tick, data) of every event `name` in the frames."""
    out = []
    for fr in frames:
        for ev in fr.get("events") or []:
            if isinstance(ev, dict) and ev.get("n") == name:
                d = ev.get("d") if isinstance(ev.get("d"), dict) else ev
                out.append((int(fr.get("t", 0)), d))
    return out


def died_at(frames: list[dict]) -> dict:
    """{entity id: frame tick of its died event}."""
    out: dict = {}
    for t, d in events(frames, "died"):
        out.setdefault(d.get("entity"), t)
    return out


def answer_ids(run: RunRecord, refs: list) -> list:
    """Ids named by references: {"step": i, "index": k} or a plain id."""
    by_step: dict = {}
    for fr in run.frames:
        for d in fr.get("dev") or []:
            by_step.setdefault(fr.get("_step"), []).append(d)
    out = []
    for ref in refs:
        if isinstance(ref, dict):
            answers = by_step.get(ref.get("step"), [])
            k = int(ref.get("index", 0))
            res = answers[k].get("res") if k < len(answers) else None
            out.append(res.get("id") if isinstance(res, dict) else None)
        else:
            out.append(ref)
    return out


def row(frame: dict | None, eid: object) -> dict | None:
    for e in (frame or {}).get("census") or []:
        if e.get("id") == eid:
            return e
    return None


def pos(frame: dict | None, eid: object) -> list[float] | None:
    e = row(frame, eid)
    p = (e or {}).get("p")
    return [float(c) for c in p] if isinstance(p, list) and len(p) == 3 else None


def player_pos(frame: dict | None) -> list[float] | None:
    for e in (frame or {}).get("census") or []:
        if e.get("k") == "player" and isinstance(e.get("p"), list):
            return [float(c) for c in e["p"]]
    return None


def meta(frame: dict | None, eid: object, key: str) -> object:
    return (((row(frame, eid) or {}).get("m")) or {}).get(key)


def bone(frame: dict | None, eid: object, name: str) -> list[float] | None:
    b = ((frame or {}).get("bones") or {}).get(str(eid)) or {}
    p = b.get(name)
    return [float(c) for c in p] if isinstance(p, list) and len(p) == 3 else None


def flat(a: list[float], b: list[float]) -> float:
    return math.hypot(a[0] - b[0], a[2] - b[2])


def ammo_of(frame: dict | None) -> tuple[object, int, int] | None:
    """(weapon, magazine, reserve) in a frame's state report, or None."""
    pl = player_state(frame)
    a = pl.get("ammo")
    if not isinstance(a, dict):
        return None
    try:
        return pl.get("weapon"), int(a["magazine"]), int(a["reserve"])
    except (KeyError, TypeError, ValueError):
        return None


def rounds(frames: list[dict]) -> list[int]:
    """Ticks at which rounds left the magazine: one entry per round the magazine dropped by,
    with the same weapon in hand and the reserve unchanged."""
    out: list[int] = []
    prev = None
    for fr in frames:
        cur = ammo_of(fr)
        if cur is None:
            continue
        if (
            prev is not None
            and prev[0] == cur[0]
            and cur[1] < prev[1]
            and cur[2] == prev[2]
        ):
            out += [int(fr.get("t", 0))] * (prev[1] - cur[1])
        prev = cur
    return out


def hits_on(frames: list[dict], targets: set, source: object) -> list[tuple[int, dict]]:
    """(tick, data) of the damaged events on the targets dealt by `source`."""
    return [
        (t, d)
        for t, d in events(frames, "damaged")
        if d.get("entity") in targets and d.get("source") == source
    ]


def angle_deg(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(c * c for c in a))
    nb = math.sqrt(sum(c * c for c in b))
    if na < 1e-9 or nb < 1e-9:
        return 180.0
    cos = sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def view_offset(cam: dict, p: list[float], aspect: float) -> tuple[float, float] | None:
    """Where a point appears in a camera's view: (x, y) from -1 to 1 across the width and
    the height (0 is the middle), the field of view taken as vertical; None when behind."""
    bz = [float(c) for c in cam["bz"]]
    fwd = [-c for c in bz]
    rx, rz = bz[2], -bz[0]
    norm = math.hypot(rx, rz) or 1.0
    right = [rx / norm, 0.0, rz / norm]
    up = [
        bz[1] * right[2] - bz[2] * right[1],
        bz[2] * right[0] - bz[0] * right[2],
        bz[0] * right[1] - bz[1] * right[0],
    ]
    d = [p[k] - float(cam["p"][k]) for k in range(3)]
    depth = sum(d[k] * fwd[k] for k in range(3))
    if depth <= 0:
        return None
    half = math.tan(math.radians(float(cam["fov"])) / 2.0)
    x = sum(d[k] * right[k] for k in range(3)) / depth / (half * aspect)
    y = sum(d[k] * up[k] for k in range(3)) / depth / half
    return x, y


def box_distance(box: dict, p: list[float]) -> float:
    """Horizontal distance from a point to a box's footprint (0 inside). A box is
    {"p": the middle of its base, "size": [width, height, depth], "heading": degrees}."""
    h = math.radians(float(box.get("heading", 0.0)))
    fx, fz = math.sin(h), -math.cos(h)
    rx, rz = math.cos(h), math.sin(h)
    dx, dz = p[0] - float(box["p"][0]), p[2] - float(box["p"][2])
    u, v = dx * rx + dz * rz, dx * fx + dz * fz
    hw, hd = float(box["size"][0]) / 2.0, float(box["size"][2]) / 2.0
    return math.hypot(max(0.0, abs(u) - hw), max(0.0, abs(v) - hd))


# ------------------------------------------------------------------ weapons (CB-1 to CB-3)
def check_hits(rec: PlayRecord, args: dict) -> Result:
    """CB-1 with AC-13: between two marks, every damaged event on the listed people dealt by
    the player has `amount` equal to `damage`; at least `min_hits` of them; on every hit that
    does not kill (whoever dealt it), the person's health falls by the amount (from
    `start_health`, 100 by default, then from event to event); the person dies (its died event)
    on exactly the hit that takes its health to 0 and takes no hit after it; with `per_round`,
    no round lands more than that many hits."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    targets = answer_ids(run, args["targets"])
    me = player_id(run.frames)
    want = int(args["damage"])
    hits = hits_on(frames, set(targets), me)
    died = died_at(frames)
    health = {t: int(args.get("start_health", 100)) for t in targets}
    off, problems = [], []
    # health is followed through every hit on them, whoever dealt it
    every = [(t, d) for t, d in events(frames, "damaged") if d.get("entity") in health]
    for t, d in every:
        eid = d.get("entity")
        amount, left = d.get("amount"), d.get("health")
        if d.get("source") == me and amount != want:
            off.append(amount)
        if eid in died and died[eid] < t:
            problems.append(f"entity {eid} took a hit after its died event")
        if isinstance(left, (int, float)):
            if left > 0 and health[eid] - left != amount:
                problems.append(
                    f"entity {eid}'s health fell {health[eid] - left} on a hit of {amount}"
                )
            if left <= 0 and eid not in died:
                problems.append(f"entity {eid} reached 0 health with no died event")
            health[eid] = int(left)
    for eid, t in died.items():
        if eid in health and health[eid] > 0:
            problems.append(f"entity {eid} died with {health[eid]} health left")
    per = args.get("per_round")
    most = 0
    if per is not None:
        rs = rounds(frames)
        counts: dict = {}
        for t, _d in hits:
            past = [r for r in rs if r <= t]
            if past:
                counts[past[-1]] = counts.get(past[-1], 0) + 1
        most = max(counts.values(), default=0)
        if most > int(per):
            problems.append(f"one round landed {most} hits (at most {per})")
    measured = {
        "hits": len(hits),
        "amounts": sorted({d.get("amount") for _t, d in hits}, key=str),
        "died": len([e for e in died if e in targets]),
    }
    if per is not None:
        measured["most_hits_in_a_round"] = most
    if len(hits) < int(args.get("min_hits", 1)):
        return False, measured, f"{len(hits)} hits (at least {args.get('min_hits', 1)})"
    if off:
        return False, measured, f"a hit's amount was {off[0]} (the table: {want})"
    if problems:
        return False, measured, problems[0]
    return True, measured, ""


def check_fire_rate(rec: PlayRecord, args: dict) -> Result:
    """CB-1: between two marks with `attack` held, the rate of rounds leaving the magazine (or,
    with `blows`, of the damaged events the player deals to the listed people) is `rate` per
    second within `tol` (a share): the count less one over the time from the first to the
    last, at least `min_count` of them."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    if args.get("blows"):
        targets = set(answer_ids(run, args["blows"]))
        ticks = [t for t, _d in hits_on(frames, targets, player_id(run.frames))]
    else:
        ticks = rounds(frames)
    measured: dict = {"count": len(ticks)}
    if len(ticks) < int(args.get("min_count", 3)):
        return None, measured, f"only {len(ticks)} rounds or blows were seen"
    span = (ticks[-1] - ticks[0]) / TICK_HZ
    rate = (len(ticks) - 1) / span if span > 0 else math.inf
    measured["rate_per_s"] = round(rate, 3)
    want, tol = float(args["rate"]), float(args.get("tol", 0.05))
    ok = abs(rate - want) <= want * tol
    return ok, measured, "" if ok else f"{rate:.2f} per second (the table: {want})"


def check_reload(rec: PlayRecord, args: dict) -> Result:
    """CB-1, CB-2: a reload starts at the first mark (`start` "mark": reload pressed there) or
    at the first tick after it with the magazine empty (`start` "empty"); the magazine rises
    `reload_s` later within `tol` (a share), to the magazine size or by the whole reserve (one
    less when a round leaves in the same tick), with the reserve falling by what the reload
    moved."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    first = ammo_of(frames[0])
    if first is None:
        return None, {}, "the state report has no ammo"
    t_start, before = int(frames[0].get("t", 0)), first
    if args.get("start", "mark") == "empty":
        t_start = None
        for fr in frames:
            a = ammo_of(fr)
            if a is not None and a[1] == 0:
                t_start, before = int(fr.get("t", 0)), a
                break
        if t_start is None:
            return None, {}, "the magazine never ran empty"
    after, t_end = None, None
    for fr in frames:
        a = ammo_of(fr)
        if a is not None and int(fr.get("t", 0)) > t_start and a[1] > before[1]:
            after, t_end = a, int(fr.get("t", 0))
            break
    if after is None:
        return False, {"before": list(before)}, "the magazine was not refilled"
    secs = (t_end - t_start) / TICK_HZ
    size = int(args["magazine"])
    want = min(size, before[1] + before[2])
    measured = {
        "seconds": round(secs, 3),
        "magazine": [before[1], after[1]],
        "reserve": [before[2], after[2]],
    }
    rel, tol = float(args["reload_s"]), float(args.get("tol", 0.1))
    if abs(secs - rel) > rel * tol:
        return False, measured, f"the reload took {secs:.2f} s (the table: {rel} s)"
    # a round fired in the tick the magazine refills (attack held) shows as one less
    if after[1] not in (want, want - 1):
        return False, measured, f"the magazine holds {after[1]} after the reload"
    if before[2] - after[2] != want - before[1]:
        return False, measured, "the reserve did not give what the magazine gained"
    return True, measured, ""


def check_ammo_flow(rec: PlayRecord, args: dict) -> Result:
    """CB-2: between two marks (the weapon in hand unchanged), every change of the state
    report's ammo is a round (the magazine down by one, the reserve unchanged) or a reload
    (the magazine up, the reserve down by as much, or by one less when a round leaves in the
    same tick); at least `min_rounds` rounds and `min_reloads` reloads."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    n_rounds = n_reloads = 0
    odd = []
    prev = None
    for fr in frames:
        cur = ammo_of(fr)
        if cur is None:
            continue
        if prev is not None and prev[0] == cur[0] and cur[1:] != prev[1:]:
            dm, dr = cur[1] - prev[1], cur[2] - prev[2]
            if dm < 0 and dr == 0:
                n_rounds += -dm
            elif dr < 0 and dm in (-dr, -dr - 1):
                # a reload, with a round fired in the same tick when attack is held
                n_reloads += 1
                n_rounds += -dr - dm
            else:
                odd.append((int(fr.get("t", 0)), list(prev[1:]), list(cur[1:])))
        prev = cur
    measured = {"rounds": n_rounds, "reloads": n_reloads}
    if odd:
        t, a, b = odd[0]
        return False, measured, f"at tick {t} the ammo went from {a} to {b}"
    if n_rounds < int(args.get("min_rounds", 1)) or n_reloads < int(
        args.get("min_reloads", 0)
    ):
        return None, measured, "too few rounds or reloads were seen"
    return True, measured, ""


def check_dry_fire(rec: PlayRecord, args: dict) -> Result:
    """CB-2: with the magazine and the reserve empty at the first mark, holding `attack` until
    the second does nothing: the ammo stays empty and nobody takes a hit from the player."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    first = ammo_of(frames[0])
    if first is None or first[1:] != (0, 0):
        return None, {"ammo": list(first or [])}, "the gun was not empty at the start"
    changed = [
        int(f.get("t", 0)) for f in frames if (ammo_of(f) or first)[1:] != (0, 0)
    ]
    me = player_id(run.frames)
    dealt = [t for t, d in events(frames, "damaged") if d.get("source") == me]
    measured = {"ammo_changes": len(changed), "hits": len(dealt)}
    if changed:
        return False, measured, f"the ammo changed at tick {changed[0]}"
    if dealt:
        return False, measured, f"someone took a hit at tick {dealt[0]}"
    return True, measured, ""


# ------------------------------------------------------------------ aiming and lock-on
def check_aim_pose(rec: PlayRecord, args: dict) -> Result:
    """FT-11: between two marks (`aim` held with a gun), on every frame with the player's
    bones and the state report's aim point: the gun hand (`RightHand`) is within `hand_m` of
    shoulder height (`RightUpperArm`) and the forearm (`RightLowerArm` to `RightHand`) points
    within `max_deg` of the direction from the gun hand to the aim point."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    worst_h, worst_a, n, no_aim = 0.0, 0.0, 0, 0
    for fr in frames:
        me = player_state(fr).get("id")
        hand = bone(fr, me, "RightHand")
        elbow = bone(fr, me, "RightLowerArm")
        shoulder = bone(fr, me, "RightUpperArm")
        aim = player_state(fr).get("aim")
        if hand is None or elbow is None or shoulder is None:
            continue
        if not (isinstance(aim, list) and len(aim) == 3):
            no_aim += 1
            continue
        n += 1
        worst_h = max(worst_h, abs(hand[1] - shoulder[1]))
        fore = [hand[k] - elbow[k] for k in range(3)]
        to = [float(aim[k]) - hand[k] for k in range(3)]
        worst_a = max(worst_a, angle_deg(fore, to))
    measured = {
        "frames": n,
        "hand_from_shoulder_height_m": round(worst_h, 3),
        "forearm_off_deg": round(worst_a, 2),
    }
    if no_aim:
        return False, measured, f"the state report had no aim point on {no_aim} frames"
    if n < int(args.get("min_frames", 5)):
        return None, measured, "the arm and the aim point were not observed"
    if worst_h > float(args.get("hand_m", 0.25)):
        return False, measured, f"the gun hand is {worst_h:.2f} m from shoulder height"
    if worst_a > float(args.get("max_deg", 20.0)):
        return False, measured, f"the forearm points {worst_a:.1f} degrees off the aim"
    return True, measured, ""


def check_lock_on(rec: PlayRecord, args: dict) -> Result:
    """CM-5: between two marks (`lock_target` held), on every frame: the state report's aim
    point is within `aim_m` of the target's `Chest` bone and that bone lies inside the middle
    `middle` of the view (by width and height, the camera's `fov` vertical, the view's
    `aspect`)."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    (target,) = answer_ids(run, [args["target"]])
    aspect, middle = float(args.get("aspect", 16 / 9)), float(args.get("middle", 0.3))
    worst_d, worst_o, n = 0.0, 0.0, 0
    for fr in frames:
        chest = bone(fr, target, "Chest")
        cam = fr.get("camera")
        if chest is None or not isinstance(cam, dict):
            continue
        n += 1
        aim = player_state(fr).get("aim")
        d = (
            math.dist(chest, [float(c) for c in aim])
            if isinstance(aim, list)
            else math.inf
        )
        worst_d = max(worst_d, d)
        off = view_offset(cam, chest, aspect)
        o = 2.0 if off is None else max(abs(off[0]), abs(off[1]))
        worst_o = max(worst_o, o)
    measured = {
        "frames": n,
        "aim_from_chest_m": round(worst_d, 3) if math.isfinite(worst_d) else None,
        "farthest_from_middle": round(worst_o, 3),
    }
    if n < int(args.get("min_frames", 5)):
        return None, measured, "the target's Chest and the camera were not observed"
    if worst_d > float(args.get("aim_m", 0.3)):
        return False, measured, "the aim point left the target's Chest"
    if worst_o > middle:
        return (
            False,
            measured,
            f"the target was {worst_o:.2f} of the way to the view's edge",
        )
    return True, measured, ""


def check_hit_rate(rec: PlayRecord, args: dict) -> Result:
    """CB-4: over `bursts` ([{"from", "to", "target"}]), the rounds that left the magazine
    while the burst's target stood (alive and not limp) and the hits the player dealt it
    (counted until `grace_s` after the burst); hits over rounds is at least `min_share`."""
    run = rec.runs[int(args.get("run", 0))]
    shots = hits = 0
    for b in args["bursts"]:
        frames = frames_between(run, b["from"], b["to"])
        if not frames:
            return None, {}, "the marks were not reached"
        (target,) = answer_ids(run, [b["target"]])
        died = died_at(run.frames).get(target)
        standing = {
            int(fr.get("t", 0))
            for fr in frames
            if meta(fr, target, "limp") is not True
            and (died is None or int(fr.get("t", 0)) <= died)
        }
        rs = [t for t in rounds(frames) if t in standing]
        shots += len(rs)
        t1 = int(frames[-1].get("t", 0)) + int(
            float(args.get("grace_s", 0.5)) * TICK_HZ
        )
        later = [
            f
            for f in run.frames
            if int(frames[0].get("t", 0)) <= int(f.get("t", 0)) <= t1
            and f.get("_proc") == frames[0].get("_proc")
        ]
        hits += min(len(rs), len(hits_on(later, {target}, player_id(run.frames))))
    measured = {"rounds": shots, "hits": hits}
    if shots < int(args.get("min_rounds", 6)):
        return None, measured, f"only {shots} rounds were fired at standing people"
    share = hits / shots
    measured["share"] = round(share, 3)
    ok = share >= float(args["min_share"])
    return ok, measured, "" if ok else f"{share:.0%} of the rounds hit"


def check_untouched(rec: PlayRecord, args: dict) -> Result:
    """CB-6: between two marks the player fires at least `min_rounds` rounds and none of the
    listed people takes a hit."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    targets = set(answer_ids(run, args["targets"]))
    n = len(rounds(frames))
    hit = [
        d.get("entity")
        for _t, d in events(frames, "damaged")
        if d.get("entity") in targets
    ]
    measured = {"rounds": n, "hits": len(hit)}
    if n < int(args.get("min_rounds", 1)):
        return None, measured, f"only {n} rounds were fired"
    if hit:
        return False, measured, f"entity {hit[0]} took a hit"
    return True, measured, ""


# ------------------------------------------------------------------ cover (FT-12, CB-8)
def hips_ratio(frame: dict, ground_y: float, standing: float) -> float | None:
    me = player_state(frame).get("id")
    hips = bone(frame, me, "Hips")
    if hips is None or standing <= 0:
        return None
    return (hips[1] - ground_y) / standing


def check_cover_enter(rec: PlayRecord, args: dict) -> Result:
    """FT-12: from the mark where `cover` is pressed (standing, within reach of the box),
    within `within_s` the state report's `cover` is true, the player's position is within
    `near_m` of the box (horizontally) and the `Hips` are at most `ratio` of their standing
    height (at the mark) above `ground_y`."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_from(run, args["from"], float(args.get("within_s", 1.0)))
    if not frames:
        return None, {}, "the mark was not reached"
    box, ground = args["box"], float(args["ground_y"])
    me = player_state(frames[0]).get("id")
    h0 = bone(frames[0], me, "Hips")
    p0 = player_pos(frames[0])
    if h0 is None or p0 is None:
        return None, {}, "the player's hips were not observed at the press"
    standing = h0[1] - ground
    measured = {"from_box_m_at_press": round(box_distance(box, p0), 3)}
    for fr in frames[1:]:
        p = player_pos(fr)
        r = hips_ratio(fr, ground, standing)
        if p is None or r is None:
            continue
        if (
            player_state(fr).get("cover") is True
            and box_distance(box, p) <= float(args.get("near_m", 0.6))
            and r <= float(args.get("ratio", 0.75))
        ):
            measured.update(
                seconds=round(
                    (int(fr.get("t", 0)) - int(frames[0].get("t", 0))) / TICK_HZ, 3
                ),
                from_box_m=round(box_distance(box, p), 3),
                hips_ratio=round(r, 3),
            )
            return True, measured, ""
    last = frames[-1]
    p = player_pos(last)
    measured.update(
        cover=player_state(last).get("cover"),
        from_box_m=round(box_distance(box, p), 3) if p else None,
        hips_ratio=hips_ratio(last, ground, standing),
    )
    return False, measured, f"not in cover within {args.get('within_s', 1.0)} s"


def check_cover_hold(rec: PlayRecord, args: dict) -> Result:
    """FT-12: between two marks (in cover, `aim` not held) on every frame the state report's
    `cover` is true, the player is within `near_m` of the box and the `Hips` are at most
    `ratio` of their standing height above `ground_y`, read at `standing_mark` (where the
    player stands)."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    i = run.marks.get(args["standing_mark"])
    if not frames or i is None:
        return None, {}, "the marks were not reached"
    box, ground = args["box"], float(args["ground_y"])
    stand_fr = run.frames[i]
    hips0 = bone(stand_fr, player_state(stand_fr).get("id"), "Hips")
    if hips0 is None:
        return None, {}, "the player's hips were not observed standing"
    standing = hips0[1] - ground
    worst_d, worst_r, n = 0.0, 0.0, 0
    for fr in frames:
        if player_state(fr).get("cover") is not True:
            return (
                False,
                {"tick": fr.get("t")},
                f"cover was false at tick {fr.get('t')}",
            )
        p = player_pos(fr)
        r = hips_ratio(fr, ground, standing)
        if p is None or r is None:
            continue
        n += 1
        worst_d, worst_r = max(worst_d, box_distance(box, p)), max(worst_r, r)
    measured = {
        "frames": n,
        "from_box_m": round(worst_d, 3),
        "hips_ratio": round(worst_r, 3),
    }
    if n == 0:
        return None, measured, "the player was not observed"
    if worst_d > float(args.get("near_m", 0.6)):
        return False, measured, f"the player was {worst_d:.2f} m from the obstacle"
    if worst_r > float(args.get("ratio", 0.75)):
        return False, measured, f"the hips rose to {worst_r:.0%} of standing height"
    return True, measured, ""


def check_cover_leave(rec: PlayRecord, args: dict) -> Result:
    """FT-12: from the mark where a move away from the obstacle is pressed, the state report's
    `cover` is false within `within_s` and stays false until the second mark, by when the
    player is more than `near_m` from the box."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    t0 = int(frames[0].get("t", 0))
    off = None
    for fr in frames:
        c = player_state(fr).get("cover")
        if c is False and off is None:
            off = int(fr.get("t", 0))
        if c is True and off is not None:
            return False, {}, f"cover came back at tick {fr.get('t')}"
    p = player_pos(frames[-1])
    d = box_distance(args["box"], p) if p else None
    measured = {
        "seconds": None if off is None else round((off - t0) / TICK_HZ, 3),
        "from_box_m": d,
    }
    if off is None or off - t0 > float(args.get("within_s", 0.5)) * TICK_HZ:
        return False, measured, "cover did not end in time"
    if d is None or d <= float(args.get("near_m", 0.6)):
        return False, measured, "the player did not move away from the obstacle"
    return True, measured, ""


def check_lean_out(rec: PlayRecord, args: dict) -> Result:
    """CB-8: from the mark where `aim` is pressed in cover, within `within_s` the `Head` bone
    rises at least `rise_m` above its height at the mark with `cover` still true; and between
    `fire_from` and `fire_to` (attack held, still in cover) at least one round leaves the
    magazine."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_from(run, args["from"], float(args.get("within_s", 1.0)))
    if not frames:
        return None, {}, "the mark was not reached"
    me = player_state(frames[0]).get("id")
    h0 = bone(frames[0], me, "Head")
    if h0 is None:
        return None, {}, "the Head bone was not observed"
    rise = 0.0
    for fr in frames:
        head = bone(fr, me, "Head")
        if head is not None and player_state(fr).get("cover") is True:
            rise = max(rise, head[1] - h0[1])
    fired = frames_between(run, args["fire_from"], args["fire_to"])
    in_cover = all(player_state(f).get("cover") is True for f in fired)
    n = len(rounds(fired))
    measured = {"head_rise_m": round(rise, 3), "rounds_from_cover": n}
    if rise < float(args.get("rise_m", 0.30)):
        return False, measured, f"the head rose {rise:.2f} m"
    if not fired or not in_cover:
        return False, measured, "the player was not in cover while firing"
    if n < 1:
        return False, measured, "no round left the magazine from cover"
    return True, measured, ""


def damage_from(frames: list[dict], victim: object, sources: set) -> tuple[int, int]:
    """(sum of amounts, number of hits) of the damaged events on `victim` from `sources`."""
    total = n = 0
    for _t, d in events(frames, "damaged"):
        if d.get("entity") == victim and d.get("source") in sources:
            total += int(d.get("amount") or 0)
            n += 1
    return total, n


def check_cover_cuts(rec: PlayRecord, args: dict) -> Result:
    """CB-8: two windows of equal length from one start, `open` and `cover` ({"from", "to",
    "attackers"}), each in its own game process: the damage the listed attackers deal the
    player in the cover window is at most `max_ratio` of what they deal in the open one,
    which holds at least `min_open_hits` hits."""
    run = rec.runs[int(args.get("run", 0))]
    out: dict = {}
    for part in ("open", "cover"):
        w = args[part]
        frames = frames_between(run, w["from"], w["to"])
        if not frames:
            return None, {}, f"the {part} window's marks were not reached"
        me = player_state(frames[0]).get("id") or player_id(frames)
        total, n = damage_from(frames, me, set(answer_ids(run, w["attackers"])))
        out[part] = {
            "damage": total,
            "hits": n,
            "ticks": int(frames[-1].get("t", 0)) - int(frames[0].get("t", 0)),
            "proc": frames[0].get("_proc"),
        }
    measured = {
        k: {kk: vv for kk, vv in v.items() if kk != "proc"} for k, v in out.items()
    }
    if out["open"]["proc"] == out["cover"]["proc"]:
        return None, measured, "the two windows ran in the same game process"
    if abs(out["open"]["ticks"] - out["cover"]["ticks"]) > 2:
        return None, measured, "the two windows differ in length"
    if out["open"]["hits"] < int(args.get("min_open_hits", 8)):
        return None, measured, f"only {out['open']['hits']} hits in the open"
    ratio = out["cover"]["damage"] / max(1, out["open"]["damage"])
    measured["ratio"] = round(ratio, 3)
    ok = ratio <= float(args.get("max_ratio", 0.4))
    return (
        ok,
        measured,
        "" if ok else f"cover let through {ratio:.0%} of the open damage",
    )


# ------------------------------------------------------------------ armour (CB-5)
def check_armour_split(rec: PlayRecord, args: dict) -> Result:
    """CB-5: between two marks, for every damaged event on the player: armour absorbs 60% of
    the hit's amount (rounded; within a point) until it runs out, and health takes the rest
    (within a point), from the values before the hit (the state report at the first mark,
    then event to event); at least `min_armoured` hits while armour lasted and
    `min_bare` after it ran out."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    pl = player_state(frames[0])
    me = pl.get("id")
    try:
        health, armour = int(pl["health"]), int(pl["armour"])
    except (KeyError, TypeError, ValueError):
        return None, {}, "the state report has no health or armour"
    share = float(args.get("share", 0.6))
    armoured = bare = 0
    worst = 0
    for _t, d in events(frames, "damaged"):
        if d.get("entity") != me:
            continue
        amount, h1, a1 = int(d["amount"]), int(d["health"]), int(d["armour"])
        absorbed = min(armour, amount * share)
        if armour > 0:
            armoured += 1
        else:
            bare += 1
        da = abs((armour - a1) - absorbed)
        dh = abs((health - h1) - min(health, amount - absorbed))
        worst = max(worst, da, dh)
        if da > 1.0 or dh > 1.0:
            return (
                False,
                {"hit": amount, "before": [health, armour], "after": [h1, a1]},
                f"a hit of {amount} on health {health}, armour {armour} left {h1} and {a1}",
            )
        health, armour = h1, a1
        if health <= 0:
            break
    measured = {
        "armoured_hits": armoured,
        "bare_hits": bare,
        "worst_off": round(worst, 2),
    }
    if armoured < int(args.get("min_armoured", 2)) or bare < int(
        args.get("min_bare", 1)
    ):
        return None, measured, "too few hits with and without armour"
    return True, measured, ""


# ------------------------------------------------------------------ crews (CB-9)
def hostile_tick(frames: list[dict], eid: object) -> int | None:
    for fr in frames:
        if meta(fr, eid, "hostile") is True:
            return int(fr.get("t", 0))
    return None


def check_turn_hostile(rec: PlayRecord, args: dict) -> Result:
    """CB-9, AC-5: the listed crew members' `hostile` metadata turns true within `within_s` of
    the trigger: with `trigger` "hit", the first damaged event the player deals one of them
    after the first mark; with "aim", `after_s` after the first mark (where the player starts
    aiming a gun inside the turf), and none turns hostile before that (a tick allowed)."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    members = answer_ids(run, args["members"])
    t0 = int(frames[0].get("t", 0))
    if args.get("trigger") == "hit":
        hits = hits_on(frames, set(members), player_id(run.frames))
        if not hits:
            return None, {}, "the player did not hit a member"
        start = hits[0][0]
    else:
        start = t0 + round(float(args.get("after_s", 5.0)) * TICK_HZ)
    within = float(args.get("within_s", 2.0)) * TICK_HZ
    turned = {m: hostile_tick(frames, m) for m in members}
    measured = {
        str(m): None if t is None else round((t - start) / TICK_HZ, 3)
        for m, t in turned.items()
    }
    for m, t in turned.items():
        if t is None or t - start > within:
            return False, measured, f"entity {m} was not hostile in time"
        if args.get("trigger") != "hit" and t < start - 1:
            return (
                False,
                measured,
                f"entity {m} turned hostile before {args.get('after_s', 5.0)} s",
            )
    return True, measured, ""


def check_flee_away(rec: PlayRecord, args: dict) -> Result:
    """CB-9: each listed person, from the tick its `hostile` metadata turns true (after the
    first mark), ends at least `min_m` farther from the player (horizontally) within
    `within_s`, with `hostile` still true then."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    measured = {}
    for m in answer_ids(run, args["people"]):
        t_on = hostile_tick(frames, m)
        if t_on is None:
            return False, measured, f"entity {m} never turned hostile"
        win = [
            f
            for f in frames
            if t_on
            <= int(f.get("t", 0))
            <= t_on + float(args.get("within_s", 10.0)) * TICK_HZ
        ]
        d0 = None
        best = -math.inf
        for fr in win:
            p, q = pos(fr, m), player_pos(fr)
            if p is None or q is None:
                continue
            d = flat(p, q)
            if d0 is None:
                d0 = d
            if meta(fr, m, "hostile") is not True:
                return (
                    False,
                    measured,
                    f"entity {m}'s hostile metadata went false while fleeing",
                )
            best = max(best, d - d0)
        measured[str(m)] = round(best, 2) if math.isfinite(best) else None
        if not math.isfinite(best) or best < float(args.get("min_m", 20.0)):
            return (
                False,
                measured,
                f"entity {m} got {best:.1f} m farther from the player",
            )
    return True, measured, ""


def check_reach_cover(rec: PlayRecord, args: dict) -> Result:
    """CB-9: within `within_s` of the fight starting (the first listed crew member turning
    hostile, after the first mark), at least `min_share` of the hostile enforcers listed
    stand, at some moment, within `near_m` of a listed box (horizontally)."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    crew = answer_ids(run, args["crew"])
    starts = [t for t in (hostile_tick(frames, m) for m in crew) if t is not None]
    if not starts:
        return None, {}, "no crew member turned hostile"
    start = min(starts)
    end = start + float(args.get("within_s", 10.0)) * TICK_HZ
    enforcers = answer_ids(run, args["enforcers"])
    hostile = [m for m in enforcers if (hostile_tick(frames, m) or math.inf) <= end]
    reached = []
    for m in hostile:
        for fr in frames:
            t = int(fr.get("t", 0))
            p = pos(fr, m)
            if (
                start <= t <= end
                and p is not None
                and any(
                    box_distance(b, p) <= float(args.get("near_m", 1.0))
                    for b in args["boxes"]
                )
            ):
                reached.append(m)
                break
    measured = {"hostile_enforcers": len(hostile), "in_cover": len(reached)}
    if not hostile:
        return False, measured, "no enforcer turned hostile"
    ok = len(reached) >= float(args.get("min_share", 0.5)) * len(hostile)
    return ok, measured, "" if ok else f"{len(reached)} of {len(hostile)} reached cover"


def check_retreat(rec: PlayRecord, args: dict) -> Result:
    """CB-9: each listed enforcer whose health drops below `below` (a damaged event), alive,
    ends at least `min_m` farther from the player (horizontally) within `within_s` of the
    drop; at least one of them drops."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    people = set(answer_ids(run, args["enforcers"]))
    drops: dict = {}
    for t, d in events(frames, "damaged"):
        m = d.get("entity")
        if (
            m in people
            and m not in drops
            and 0 < int(d.get("health") or 0) < int(args.get("below", 30))
        ):
            drops[m] = t
    measured = {}
    if not drops:
        return None, measured, "no enforcer dropped below the mark alive"
    died = died_at(frames)
    for m, t0 in drops.items():
        if m in died and died[m] <= t0 + float(args.get("within_s", 10.0)) * TICK_HZ:
            continue
        win = [
            f
            for f in frames
            if t0
            <= int(f.get("t", 0))
            <= t0 + float(args.get("within_s", 10.0)) * TICK_HZ
        ]
        ds = [
            flat(p, q)
            for f in win
            if (p := pos(f, m)) is not None and (q := player_pos(f)) is not None
        ]
        gain = (max(ds) - ds[0]) if ds else -math.inf
        measured[str(m)] = round(gain, 2) if ds else None
        if gain < float(args.get("min_m", 10.0)):
            return (
                False,
                measured,
                f"entity {m} got {gain:.1f} m farther from the player",
            )
    return True, measured, ""


def check_fires_at(rec: PlayRecord, args: dict) -> Result:
    """CB-9: between two marks, each listed attacker, hostile with the player within `max_m`
    (horizontally) and in sight, lands at least `min_hits` hits on the player."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    me = player_id(run.frames)
    measured = {}
    for m in answer_ids(run, args["attackers"]):
        near = [
            fr
            for fr in frames
            if (p := pos(fr, m)) is not None
            and (q := player_pos(fr)) is not None
            and flat(p, q) <= float(args.get("max_m", 40.0))
        ]
        if not near:
            return (
                None,
                measured,
                f"entity {m} never came within {args.get('max_m', 40.0)} m",
            )
        _total, n = damage_from(frames, me, {m})
        measured[str(m)] = n
        if n < int(args.get("min_hits", 1)):
            return False, measured, f"entity {m} landed {n} hits"
    return True, measured, ""


# ------------------------------------------------------------------ gunshots (TR-13)
def check_gunshot_flee(rec: PlayRecord, args: dict) -> Result:
    """TR-13: the first round after the first mark is the shot. Each listed person on foot
    within `near_m` of the player when it is fired (and not limp, dead or seated in the
    window), from `start_s` to `end_s` after the shot, runs at least `min_mps` on average, ends
    at least `min_gain_m` farther from where the player stood at the shot, and gets farther
    from it over at least `min_share` of the half-second steps."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    rs = rounds(frames)
    if not rs:
        return None, {}, "no round was fired"
    shot = rs[0]
    at_shot = next((f for f in frames if int(f.get("t", 0)) >= shot), None)
    origin = player_pos(at_shot)
    if origin is None:
        return None, {}, "the player was not observed at the shot"
    a, b = (
        shot + float(args.get("start_s", 2.0)) * TICK_HZ,
        shot + float(args.get("end_s", 12.0)) * TICK_HZ,
    )
    died = died_at(run.frames)
    measured: dict = {"watched": 0}
    for m in answer_ids(run, args["people"]):
        p0 = pos(at_shot, m)
        if p0 is None or flat(p0, origin) > float(args.get("near_m", 28.0)):
            continue
        win = [f for f in frames if a <= int(f.get("t", 0)) <= b]
        if any(
            meta(f, m, "limp") is True or meta(f, m, "vehicle") is not None for f in win
        ) or (m in died and died[m] <= b):
            continue
        samples = []
        next_t = a
        for fr in win:
            t = int(fr.get("t", 0))
            p = pos(fr, m)
            if p is not None and t >= next_t:
                samples.append((t, p))
                next_t = t + TICK_HZ // 2
        if len(samples) < 10:
            return None, measured, f"entity {m} was not observed through the run"
        dist = [flat(p, origin) for _t, p in samples]
        path = sum(
            flat(samples[k][1], samples[k + 1][1]) for k in range(len(samples) - 1)
        )
        secs = (samples[-1][0] - samples[0][0]) / TICK_HZ
        mps = path / secs if secs > 0 else 0.0
        growing = sum(1 for k in range(len(dist) - 1) if dist[k + 1] > dist[k]) / (
            len(dist) - 1
        )
        gain = dist[-1] - flat(p0, origin)
        measured["watched"] += 1
        measured[str(m)] = {
            "mps": round(mps, 2),
            "gain_m": round(gain, 1),
            "growing": round(growing, 2),
        }
        if mps < float(args.get("min_mps", 3.0)):
            return False, measured, f"entity {m} ran {mps:.1f} m/s on average"
        if gain < float(args.get("min_gain_m", 20.0)):
            return (
                False,
                measured,
                f"entity {m} ended {gain:.1f} m farther from the shot",
            )
        if growing < float(args.get("min_share", 0.9)):
            return (
                False,
                measured,
                f"entity {m} got farther on {growing:.0%} of the half seconds",
            )
    if measured["watched"] < int(args.get("min_people", 1)):
        return None, measured, "nobody stood within reach of the shot"
    return True, measured, ""


CHECKS = {
    "hits": check_hits,
    "fire_rate": check_fire_rate,
    "reload": check_reload,
    "ammo_flow": check_ammo_flow,
    "dry_fire": check_dry_fire,
    "aim_pose": check_aim_pose,
    "lock_on": check_lock_on,
    "hit_rate": check_hit_rate,
    "untouched": check_untouched,
    "cover_enter": check_cover_enter,
    "cover_hold": check_cover_hold,
    "cover_leave": check_cover_leave,
    "lean_out": check_lean_out,
    "cover_cuts": check_cover_cuts,
    "armour_split": check_armour_split,
    "turn_hostile": check_turn_hostile,
    "flee_away": check_flee_away,
    "reach_cover": check_reach_cover,
    "retreat": check_retreat,
    "fires_at": check_fires_at,
    "gunshot_flee": check_gunshot_flee,
}
