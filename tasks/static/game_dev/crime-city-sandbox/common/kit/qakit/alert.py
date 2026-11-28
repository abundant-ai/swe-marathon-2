"""Checks of crime, witnesses, the alert level and the police (design document, chapter 9, with
CB-10).

They read the events of a play's frames (AC-13: `crime` with `type`, `witnesses` and `pos`;
`alert_changed` with `level` and `reason`; `police_dispatched` with `unit` and `from`;
`arrested`, `respawned` with `entity` and `poi`, `teleport`, `damaged`, `died`), the state report
(`player.alert`, `player.money`, `player.weapons`, `player.health`, `player.armour`,
`player.id`), the census (positions; collision shapes when the play asks for them; the metadata
`vehicle` and `hostile`; the in-view flag `iv`) and what the play brings from the plan (roads,
buildings, points of interest).

A police unit (AL-6) is a police vehicle (models `police`, `tactical_van`; not a wreck, nor one
carrying the player) or a police officer on foot (archetypes `police_officer`,
`police_tactical`, not in a vehicle). A unit moves towards the player when its horizontal
distance to the player has fallen by 2 m or more over the last 2 s. Times are frame ticks, at 60
per second. People are named by the id a command answered with: {"step": i, "index": k}, or by
an id.
"""

from __future__ import annotations

import math

from .combat import (
    answer_ids,
    events,
    frames_between,
    player_id,
    player_pos,
    player_state,
    state_of,
)
from .play import PlayRecord, RunRecord

TICK_HZ = 60
Result = tuple[bool | None, dict, str]

POLICE_MODELS = ("police", "tactical_van")
POLICE_PEOPLE = ("police_officer", "police_tactical")
TOWARDS_M = 2.0  # AL-6: a unit moves towards the player when it closed 2 m ...
TOWARDS_S = 2.0  # ... over 2 s
STILL_MPS = 1.0 / 3.6  # 1 km/h


# ------------------------------------------------------------------ reading frames
def level_of(frame: dict | None) -> int | None:
    v = player_state(frame).get("alert")
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def ticks(seconds: float) -> int:
    return round(seconds * TICK_HZ)


def crimes(frames: list[dict], kind: str | None = None) -> list[tuple[int, dict]]:
    return [
        (t, d)
        for t, d in events(frames, "crime")
        if kind is None or d.get("type") == kind
    ]


def changes(frames: list[dict]) -> list[tuple[int, int, str]]:
    """(tick, level, reason) of every alert_changed event."""
    out = []
    for t, d in events(frames, "alert_changed"):
        lv = d.get("level")
        if isinstance(lv, (int, float)) and not isinstance(lv, bool):
            out.append((t, int(lv), str(d.get("reason", ""))))
    return out


def wrecks(frames: list[dict]) -> set:
    return {d.get("vehicle") for _t, d in events(frames, "vehicle_exploded")}


def player_vehicle(frame: dict | None) -> object:
    v = player_state(frame).get("vehicle")
    return v if v not in (None, "", False) else None


def units(frame: dict | None, wrecked: set) -> dict:
    """{id: census row} of the police units in a frame (see the module's docstring)."""
    out = {}
    carrying = player_vehicle(frame)
    for e in (frame or {}).get("census") or []:
        a, k = e.get("a"), e.get("k")
        if k == "vehicle" and a in POLICE_MODELS:
            if e.get("id") in wrecked or e.get("id") == carrying:
                continue
            out[e.get("id")] = e
        elif k == "npc" and a in POLICE_PEOPLE:
            m = e.get("m") or {}
            if m.get("vehicle") in (None, "", False) and m.get("limp") is not True:
                out[e.get("id")] = e
    return out


def horizontal(a: list, b: list) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[2]) - float(b[2]))


def frame_at(frames: list[dict], tick: int) -> int:
    """Index of the last frame at or before `tick` (0 when none)."""
    best = 0
    for k, fr in enumerate(frames):
        if int(fr.get("t", 0)) <= tick:
            best = k
        else:
            break
    return best


def towards(frames: list[dict], k: int, eid: object, wrecked: set) -> bool:
    """Whether unit `eid` moved towards the player over the 2 s up to frame k."""
    fr = frames[k]
    j = frame_at(frames, int(fr.get("t", 0)) - ticks(TOWARDS_S))
    if j >= k:
        return False
    u_now, u_then = units(fr, wrecked).get(eid), units(frames[j], wrecked).get(eid)
    p_now, p_then = player_pos(fr), player_pos(frames[j])
    if not (u_now and u_then and p_now and p_then):
        return False
    return horizontal(u_then["p"], p_then) - horizontal(u_now["p"], p_now) >= TOWARDS_M


def first_rise(frames: list[dict], level: int | None = None) -> tuple[int, int] | None:
    """(tick, level) of the first alert_changed that raises the level (to `level` if given)."""
    prev = level_of(frames[0]) if frames else 0
    prev = prev or 0
    for t, lv, _r in changes(frames):
        if lv > prev and (level is None or lv == level):
            return t, lv
        prev = lv
    return None


def run_of(rec: PlayRecord, args: dict) -> RunRecord:
    return rec.runs[int(args.get("run", 0))]


def ref_id(run: RunRecord, ref: object) -> object:
    return answer_ids(run, [ref])[0] if ref is not None else None


# ------------------------------------------------------------------ crimes (AL-1, AL-5)
def check_crime_event(rec: PlayRecord, args: dict) -> Result:
    """AL-1 (and AL-5 through `witnesses`): between the marks, a `crime` event of `type` comes
    within `within_s` of mark `at` (default the first mark); its `witnesses` list includes every
    person of `seen_by` and none of `not_seen_by` (references); `witnessed: false` asks for an
    empty list. `count` asks for that many events of the type between the marks."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    kind = args["type"]
    at = run.marks.get(args.get("at", args["from"]))
    t0 = (
        int(run.frames[at].get("t", 0))
        if at is not None
        else int(frames[0].get("t", 0))
    )
    found = [(t, d) for t, d in crimes(frames, kind) if t >= t0]
    measured: dict = {"events": len(found)}
    if "count" in args and len(found) != int(args["count"]):
        return False, measured, f"{len(found)} {kind} events, not {args['count']}"
    if not found:
        return False, measured, f"no crime event of type {kind}"
    t, d = found[0]
    after = round((t - t0) / TICK_HZ, 3)
    seen = d.get("witnesses") if isinstance(d.get("witnesses"), list) else None
    measured.update({"after_s": after, "witnesses": seen})
    if after > float(args.get("within_s", 1.0)):
        return False, measured, f"the {kind} event came {after} s after the act"
    if seen is None:
        return False, measured, "the crime event has no witnesses list"
    want = [x for x in answer_ids(run, args.get("seen_by", [])) if x is not None]
    shut = [x for x in answer_ids(run, args.get("not_seen_by", [])) if x is not None]
    missing = [x for x in want if x not in seen]
    extra = [x for x in shut if x in seen]
    if args.get("witnessed") is False and seen:
        return False, measured, f"nobody could witness it, yet {seen[:5]} are listed"
    if missing:
        return False, measured, f"witness {missing[0]} is not listed"
    if extra:
        return False, measured, f"{extra[0]} is listed, but could not witness it"
    return True, measured, ""


# ------------------------------------------------------------------ the level (AL-2, AL-3, AL-4)
def check_alert_rise(rec: PlayRecord, args: dict) -> Result:
    """AL-2: after the first `crime` event of `type` between the marks, the level rises to
    `level` (an alert_changed event, and the state report) from `min_s` to `max_s` after it."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    found = crimes(frames, args["type"])
    if not found:
        return None, {}, f"no crime event of type {args['type']} to time the rise from"
    t0 = found[0][0]
    want = int(args["level"])
    rise = next(
        ((t, lv) for t, lv, _r in changes(frames) if t >= t0 and lv == want), None
    )
    if rise is None:
        lv = level_of(frames[-1])
        return (
            False,
            {"level_at_end": lv},
            f"the level never reached {want} (it ended at {lv})",
        )
    dt = round((rise[0] - t0) / TICK_HZ, 3)
    k = frame_at(frames, rise[0] + ticks(0.5))
    shown = level_of(frames[k])
    measured = {"after_s": dt, "state_level": shown}
    lo, hi = float(args.get("min_s", 0.0)), float(args["max_s"])
    if dt < lo:
        return False, measured, f"the level rose {dt} s after the crime, before {lo} s"
    if dt > hi:
        return (
            False,
            measured,
            f"the level rose {dt} s after the crime, later than {hi} s",
        )
    if shown is not None and shown < want:
        return False, measured, f"the state report still shows level {shown}"
    return True, measured, ""


def check_alert_steady(rec: PlayRecord, args: dict) -> Result:
    """AL-2's dead witness, AL-3: between the marks the level stays `level` (no alert_changed
    event to another level, and the state report agrees)."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    want = int(args.get("level", 0))
    moved = [(t, lv) for t, lv, _r in changes(frames) if lv != want]
    shown = sorted({lv for fr in frames if (lv := level_of(fr)) is not None})
    measured = {"changes": moved[:5], "levels_shown": shown}
    if moved:
        return (
            False,
            measured,
            f"the level changed to {moved[0][1]} at tick {moved[0][0]}",
        )
    if shown and shown != [want]:
        return False, measured, f"the state report shows levels {shown}"
    return True, measured, ""


def check_alert_sequence(rec: PlayRecord, args: dict) -> Result:
    """AL-4: the levels the alert_changed events take between the marks are `levels`, in order."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    got = [lv for _t, lv, _r in changes(frames)]
    want = [int(x) for x in args["levels"]]
    measured = {"levels": got, "reasons": [r for _t, _lv, r in changes(frames)]}
    if got != want:
        return False, measured, f"the level went {got}, not {want}"
    return True, measured, ""


# ------------------------------------------------------------------ the response (AL-6, AL-7)
def check_police_arrival(rec: PlayRecord, args: dict) -> Result:
    """AL-6: the first police unit gets within `reach_m` of the player within `within_s` of the
    level's first rise between the marks (to `level` if given). No unit may be within
    `clear_m` of the player when the level rises (the setup clears the scene)."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    rise = first_rise(frames, args.get("level"))
    if rise is None:
        return None, {}, "the level did not rise"
    wrecked = wrecks(frames)
    k0 = frame_at(frames, rise[0])
    reach, clear = float(args.get("reach_m", 25.0)), float(args.get("clear_m", 100.0))
    pl0 = player_pos(frames[k0])
    near0 = [
        eid
        for eid, e in units(frames[k0], wrecked).items()
        if pl0 and horizontal(e["p"], pl0) < clear
    ]
    if near0:
        return (
            None,
            {"near_at_rise": near0[:5]},
            f"police unit {near0[0]} was already near",
        )
    for fr in frames[k0:]:
        pl = player_pos(fr)
        if pl is None:
            continue
        for eid, e in units(fr, wrecked).items():
            if horizontal(e["p"], pl) <= reach:
                dt = round((int(fr.get("t", 0)) - rise[0]) / TICK_HZ, 3)
                measured = {
                    "after_s": dt,
                    "unit": eid,
                    "kind": e.get("k"),
                    "level": rise[1],
                }
                if dt > float(args["within_s"]):
                    return (
                        False,
                        measured,
                        f"the first unit came within {reach} m after {dt} s",
                    )
                return True, measured, ""
    return False, {"level": rise[1]}, f"no police unit came within {reach} m"


def check_police_count(rec: PlayRecord, args: dict) -> Result:
    """AL-6: within `by_s` of the level's first rise between the marks, the police vehicles
    moving towards the player or within 100 m number at least `count`; from `by_s` on, those
    within 100 m and those named by `police_dispatched` that move towards the player number at
    most `count` + `over` (2)."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    rise = first_rise(frames, args.get("level"))
    if rise is None:
        return None, {}, "the level did not rise"
    wrecked = wrecks(frames)
    dispatched = {d.get("unit") for _t, d in events(frames, "police_dispatched")}
    want, over = int(args["count"]), int(args.get("over", 2))
    by = rise[0] + ticks(float(args.get("by_s", 90.0)))
    best, reached_at, worst = 0, None, 0
    for k, fr in enumerate(frames):
        t = int(fr.get("t", 0))
        if t < rise[0]:
            continue
        pl = player_pos(fr)
        if pl is None:
            continue
        vehicles = {
            eid: e for eid, e in units(fr, wrecked).items() if e.get("k") == "vehicle"
        }
        near = {eid for eid, e in vehicles.items() if horizontal(e["p"], pl) <= 100.0}
        coming = {eid for eid in vehicles if towards(frames, k, eid, wrecked)}
        n = len(near | coming)
        if t <= by:
            best = max(best, n)
            if n >= want and reached_at is None:
                reached_at = round((t - rise[0]) / TICK_HZ, 2)
        else:
            worst = max(worst, len(near | (coming & dispatched)))
    measured = {
        "most_by_then": best,
        "reached_after_s": reached_at,
        "most_after": worst,
    }
    if reached_at is None:
        return False, measured, f"at most {best} police vehicles came, not {want}"
    if worst > want + over:
        return False, measured, f"{worst} police vehicles, more than {want} + {over}"
    return True, measured, ""


def check_police_origin(rec: PlayRecord, args: dict) -> Result:
    """AL-7: every police unit that joins the census after the level's first rise between the
    marks first shows at least `min_m` from the player and outside the camera's view (the
    census's in-view flag); officers riding in a vehicle are judged by their vehicle, and frames
    made by a DevConsole step are let off."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    rise = first_rise(frames)
    if rise is None:
        return None, {}, "the level did not rise"
    k0 = frame_at(frames, rise[0])
    seen: set = set()
    for fr in run.frames[: run.marks[args["from"]]] + frames[: k0 + 1]:
        seen |= {
            e.get("id")
            for e in fr.get("census") or []
            if e.get("a") in POLICE_MODELS + POLICE_PEOPLE
        }
    new, bad = 0, []
    for fr in frames[k0 + 1 :]:
        pl = player_pos(fr)
        for e in fr.get("census") or []:
            if e.get("a") not in POLICE_MODELS + POLICE_PEOPLE or e.get("id") in seen:
                continue
            seen.add(e.get("id"))
            if fr.get("dev") or not isinstance(e.get("p"), list):
                continue
            if e.get("k") == "npc" and (e.get("m") or {}).get("vehicle") not in (
                None,
                "",
                False,
            ):
                continue
            new += 1
            d = horizontal(e["p"], pl) if pl else None
            if d is not None and (
                d < float(args.get("min_m", 100.0)) or e.get("iv") is True
            ):
                bad.append(
                    {
                        "unit": e.get("id"),
                        "at_m": round(d, 1),
                        "in_view": e.get("iv"),
                        "tick": fr.get("t"),
                    }
                )
    measured = {"new_units": new, "bad": bad[:5]}
    if bad:
        b0 = bad[0]
        return (
            False,
            measured,
            f"police unit {b0['unit']} first appeared {b0['at_m']} m from the player"
            + (" in view" if b0["in_view"] else ""),
        )
    return True, measured, ""


def point_in(poly: list, x: float, z: float) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i][0], poly[i][1]
        x2, z2 = poly[(i + 1) % n][0], poly[(i + 1) % n][1]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            inside = not inside
    return inside


def check_police_kinematics(rec: PlayRecord, args: dict) -> Result:
    """AL-7: between the marks every police unit moves continuously: from frame to frame no
    faster than 1.1 times its model's top speed (`top_kmh`, by model) or, on foot, 1.1 times
    FT-1's sprint (`foot_mps`), and never stands inside a building (`buildings`, footprints as
    [x, z] polygons). Frames made by a DevConsole step aside."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    wrecked = wrecks(frames)
    tops = {k: float(v) / 3.6 * 1.1 for k, v in args.get("top_kmh", {}).items()}
    foot = float(args.get("foot_mps", 9.6)) * 1.1
    buildings = args.get("buildings", [])
    fastest, worst, inside = 0.0, None, []
    for k in range(1, len(frames)):
        a, b = frames[k - 1], frames[k]
        if b.get("dev"):
            continue
        dt = (int(b.get("t", 0)) - int(a.get("t", 0))) / TICK_HZ
        if dt <= 0:
            continue
        ua, ub = units(a, wrecked), units(b, wrecked)
        for eid, e in ub.items():
            if eid in ua and ua[eid].get("k") == e.get("k"):
                v = horizontal(ua[eid]["p"], e["p"]) / dt
                cap = foot if e.get("k") == "npc" else tops.get(e.get("a"), 70.0)
                if v / cap > fastest:
                    fastest, worst = (
                        v / cap,
                        {"unit": eid, "mps": round(v, 2), "cap_mps": round(cap, 2)},
                    )
            x, z = float(e["p"][0]), float(e["p"][2])
            if any(point_in(poly, x, z) for poly in buildings):
                inside.append({"unit": eid, "tick": b.get("t")})
    measured = {
        "worst_share_of_cap": round(fastest, 3),
        "worst": worst,
        "inside": inside[:5],
    }
    if fastest > 1.0:
        return (
            False,
            measured,
            f"police unit {worst['unit']} moved at {worst['mps']} m/s, over {worst['cap_mps']}",
        )
    if inside:
        return (
            False,
            measured,
            f"police unit {inside[0]['unit']} stood inside a building",
        )
    return True, measured, ""


# ------------------------------------------------------------------ roadblocks (AL-8)
def box_of(shape: dict) -> tuple[float, float, float, float, float] | None:
    """(x, z, long axis heading in degrees, length, width) of a census collision box."""
    if not isinstance(shape, dict) or shape.get("type") not in (None, "box"):
        return None
    p, size, bz = shape.get("p"), shape.get("size"), shape.get("bz")
    if not (isinstance(p, list) and isinstance(size, list) and isinstance(bz, list)):
        return None
    w, d = float(size[0]), float(size[2])
    back = math.degrees(math.atan2(float(bz[0]), float(bz[2])))
    if w >= d:
        return float(p[0]), float(p[2]), back + 90.0, w, d
    return float(p[0]), float(p[2]), back, d, w


def vehicle_box(row: dict) -> tuple[float, float, float, float, float] | None:
    for sh in row.get("sh") or row.get("shapes") or []:
        b = box_of(sh)
        if b is not None:
            return b
    return None


def on_road(roads: list, x: float, z: float) -> tuple[dict, float, float, tuple] | None:
    """The road (`roads`: {"id", "pts": centreline [[x, z], ...] from end a to end b, "width":
    the carriageway's}) whose carriageway the point is on: (road, along from a, across, (ux, uz))."""
    best = None
    for road in roads:
        pts, run_ = road["pts"], 0.0
        for i in range(len(pts) - 1):
            (ax, az), (bx, bz) = pts[i], pts[i + 1]
            seg = math.hypot(bx - ax, bz - az)
            if seg < 1e-6:
                continue
            ux, uz = (bx - ax) / seg, (bz - az) / seg
            s = max(0.0, min(seg, (x - ax) * ux + (z - az) * uz))
            across = (x - ax) * -uz + (z - az) * ux
            off = abs(across)
            if off <= float(road["width"]) / 2.0 + 0.5 and (
                best is None or off < best[0]
            ):
                best = (off, road, run_ + s, across, (ux, uz))
            run_ += seg
    return best[1:] if best else None


def road_length(road: dict) -> float:
    pts = road["pts"]
    return sum(
        math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        for i in range(len(pts) - 1)
    )


def ahead_by_road(args: dict, player: tuple, block: tuple) -> float | None:
    """Metres by road from the player (road, along, direction "ab" or "ba") to a point on a
    road (road, along), through `reach` ({"road|dir": {road id: [metres from the far end of the
    player's road to the entry end of that road, "a" or "b"]}}); None when not reachable."""
    (rp, sp, dp), (rb, sb) = player, block
    lp = road_length(rp)
    if rb["id"] == rp["id"]:
        d = sb - sp if dp == "ab" else sp - sb
        if d >= 0:
            return d
    hop = (args.get("reach", {}).get(f"{rp['id']}|{dp}") or {}).get(rb["id"])
    if hop is None:
        return None
    left = lp - sp if dp == "ab" else sp
    into = sb if hop[1] == "a" else road_length(rb) - sb
    return left + float(hop[0]) + into


def check_roadblock(rec: PlayRecord, args: dict) -> Result:
    """AL-8: within `within_s` (90) of the level reaching 3 between the marks, while the player
    drives, at least two police vehicles stand below 1 km/h for 2 s on one road's carriageway
    (`roads`, from the plan, not in a junction's box), each box's long axis within 30 degrees
    of square to the road, their middles within 8 m of one cross-section; across the road their
    boxes cover at least 70% of the carriageway; and that cross-section is within `ahead_m`
    (300) ahead of the player by road, from the road the player's vehicle is on and the way it
    faces (`reach` routes onward, from the plan's lane graph)."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    k0 = next((k for k, fr in enumerate(frames) if (level_of(fr) or 0) >= 3), None)
    if k0 is None:
        return None, {}, "the level did not reach 3"
    t_rise = int(frames[k0].get("t", 0))
    wrecked = wrecks(frames)
    roads = args["roads"]
    ahead = float(args.get("ahead_m", 300.0))
    end = t_rise + ticks(float(args.get("within_s", 90.0)))
    still_since: dict = {}
    best: dict = {}
    for k in range(1, len(frames)):
        fr, prev = frames[k], frames[k - 1]
        t = int(fr.get("t", 0))
        dt = (t - int(prev.get("t", 0))) / TICK_HZ
        vs = {
            eid: e for eid, e in units(fr, wrecked).items() if e.get("k") == "vehicle"
        }
        pv = units(prev, wrecked)
        for eid, e in vs.items():
            if (
                eid not in pv
                or dt <= 0
                or horizontal(pv[eid]["p"], e["p"]) / dt >= STILL_MPS
            ):
                still_since.pop(eid, None)
            else:
                still_since.setdefault(eid, t)
        if t < t_rise or t > end:
            continue
        car = player_vehicle(fr)
        prow = next((e for e in fr.get("census") or [] if e.get("id") == car), None)
        if prow is None or not isinstance(prow.get("bz"), list):
            continue
        here = on_road(roads, float(prow["p"][0]), float(prow["p"][2]))
        if here is None:
            continue
        road_p, along_p, _acr, (ux, uz) = here
        fx, fz = -float(prow["bz"][0]), -float(prow["bz"][2])
        dir_p = "ab" if fx * ux + fz * uz >= 0 else "ba"
        groups: dict = {}
        for eid, e in vs.items():
            if t - still_since.get(eid, t) < ticks(2.0):
                continue
            box = vehicle_box(e)
            if box is None:
                continue
            x, z, axis, length, width = box
            hit = on_road(roads, x, z)
            if hit is None:
                continue
            road, along, across, (rx, rz) = hit
            road_deg = math.degrees(math.atan2(rx, -rz))
            off = abs(((axis - road_deg) % 180.0) - 90.0)
            if off > 30.0:
                continue
            o = math.radians(off)
            half_span = (length * math.cos(o) + width * math.sin(o)) / 2.0
            groups.setdefault(road["id"], (road, []))[1].append(
                (along, across - half_span, across + half_span, eid)
            )
        for road, items in groups.values():
            half = float(road["width"]) / 2.0
            for it in items:
                group = [g for g in items if abs(g[0] - it[0]) <= 8.0]
                if len(group) < 2:
                    continue
                cover = union_len(
                    [(max(-half, a), min(half, b)) for _s, a, b, _e in group]
                )
                share = cover / (2.0 * half)
                dist = ahead_by_road(args, (road_p, along_p, dir_p), (road, it[0]))
                cand = {
                    "road": road["id"],
                    "vehicles": [g[3] for g in group],
                    "share": round(share, 3),
                    "ahead_m": None if dist is None else round(dist, 1),
                    "after_s": round((t - t_rise) / TICK_HZ, 2),
                }
                if share >= 0.7 and dist is not None and dist <= ahead:
                    return True, cand, ""
                if share > best.get("share", -1.0):
                    best = cand
    if not best:
        return (
            False,
            {},
            "no two police vehicles stood across a road while the player drove",
        )
    if best["share"] < 0.7:
        return (
            False,
            best,
            f"the police vehicles covered {best['share']:.0%} of the road's width",
        )
    return (
        False,
        best,
        f"the roadblock was not within {ahead:.0f} m ahead of the player by road",
    )


def union_len(spans: list[tuple[float, float]]) -> float:
    total, cur = 0.0, None
    for a, b in sorted(s for s in spans if s[1] > s[0]):
        if cur is None or a > cur[1]:
            if cur is not None:
                total += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur is not None:
        total += cur[1] - cur[0]
    return total


# ------------------------------------------------------------------ arrest, death (AL-9, AL-10)
def check_arrest(rec: PlayRecord, args: dict) -> Result:
    """AL-9: with the level at 1 or 2 and the police officer `officer` standing within `near_m`
    (2.0) of the player standing still (or the player's vehicle below 1 km/h), an `arrested`
    event comes from `min_s` (3.0) to `max_s` after the later of those two moments; with
    `expect: false` (the officer kept farther off), none comes between the marks."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    officer = ref_id(run, args.get("officer"))
    near = float(args.get("near_m", 2.0))
    got = events(frames, "arrested")
    if args.get("expect", True) is False:
        if got:
            return (
                False,
                {"arrested_at": got[0][0]},
                "the player was arrested with no officer within reach",
            )
        return True, {"arrested": False}, ""
    start = None
    for k, fr in enumerate(frames):
        lv = level_of(fr)
        pl = player_pos(fr)
        ofc = next((e for e in fr.get("census") or [] if e.get("id") == officer), None)
        if lv not in (1, 2) or pl is None or ofc is None:
            start = None
            continue
        ok_near = horizontal(ofc["p"], pl) <= near
        still = k > 0 and (
            player_pos(frames[k - 1]) is not None
            and horizontal(player_pos(frames[k - 1]), pl)
            / max(
                1e-6, (int(fr.get("t", 0)) - int(frames[k - 1].get("t", 0))) / TICK_HZ
            )
            < STILL_MPS * 2
        )
        if ok_near and still:
            if start is None:
                start = int(fr.get("t", 0))
        else:
            start = None
        if got and start is not None and got[0][0] >= start:
            break
    if not got:
        return False, {}, "no arrested event"
    if start is None:
        return (
            None,
            {"arrested_at": got[0][0]},
            "the officer never stood within reach of a still player",
        )
    dt = round((got[0][0] - start) / TICK_HZ, 3)
    measured = {"after_s": dt, "entity": got[0][1].get("entity")}
    lo, hi = float(args.get("min_s", 3.0)), float(args.get("max_s", 3.5))
    if dt < lo - 1.0 / TICK_HZ:
        return (
            False,
            measured,
            f"arrested {dt} s after the officer stood by, before {lo} s",
        )
    if dt > hi:
        return (
            False,
            measured,
            f"arrested {dt} s after the officer stood by, later than {hi} s",
        )
    if got[0][1].get("entity") not in (None, player_id(frames)):
        return False, measured, "the arrested event names someone else"
    return True, measured, ""


def check_came_back(rec: PlayRecord, args: dict) -> Result:
    """AL-9, AL-10: within `within_s` (10) of the first `after` event (`arrested` or the
    player's `died`) between the marks, a `teleport` and a `respawned` event naming `poi` (the
    nearest station or hospital) come, the player within `near_m` (2) of `respawn`; a second
    after it the state report shows level 0 and, where given, `money`, `weapons`, `health`
    and `armour`."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    pid = player_id(frames)
    kind = args.get("after", "arrested")
    if kind == "died":
        trig = [(t, d) for t, d in events(frames, "died") if d.get("entity") == pid]
    else:
        trig = events(frames, "arrested")
    if not trig:
        return None, {}, f"no {kind} event"
    t0 = trig[0][0]
    within = ticks(float(args.get("within_s", 10.0)))
    back = [(t, d) for t, d in events(frames, "respawned") if t0 <= t <= t0 + within]
    tele = [t for t, _d in events(frames, "teleport") if t0 <= t <= t0 + within]
    measured: dict = {}
    if not back:
        return (
            False,
            measured,
            f"no respawned event within {args.get('within_s', 10.0)} s of {kind}",
        )
    tb, d = back[0]
    measured.update({"after_s": round((tb - t0) / TICK_HZ, 2), "poi": d.get("poi")})
    if not tele:
        return False, measured, "the player came back without a teleport event"
    if d.get("poi") != args["poi"]:
        return False, measured, f"came back at {d.get('poi')}, not {args['poi']}"
    k = frame_at(frames, tb + ticks(1.0))
    fr = frames[k]
    pl = player_pos(fr)
    where = horizontal(pl, args["respawn"]) if pl else None
    st = player_state(fr)
    measured.update(
        {
            "from_respawn_m": None if where is None else round(where, 2),
            "level": st.get("alert"),
            "money": st.get("money"),
            "weapons": st.get("weapons"),
            "health": st.get("health"),
            "armour": st.get("armour"),
        }
    )
    if where is None or where > float(args.get("near_m", 2.0)):
        return (
            False,
            measured,
            f"the player came back {measured['from_respawn_m']} m from the respawn point",
        )
    if st.get("alert") not in (0, 0.0):
        return False, measured, f"the level is {st.get('alert')} after coming back"
    for key in ("money", "health", "armour"):
        if key in args and st.get(key) != args[key]:
            return False, measured, f"{key} is {st.get(key)}, not {args[key]}"
    if "weapons" in args and sorted(st.get("weapons") or []) != sorted(args["weapons"]):
        return (
            False,
            measured,
            f"weapons are {st.get('weapons')}, not {args['weapons']}",
        )
    return True, measured, ""


# ------------------------------------------------------------------ escape (AL-11)
def check_escape(rec: PlayRecord, args: dict) -> Result:
    """AL-11: the level stays above 0 until `cooling_s` after mark `anchor` (the moment the
    player was last in the zone or in a unit's sight) and drops to 0 by `cooling_s` plus
    `slack_s` (3) after it, with reason `escaped`."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    a = run.marks.get(args["anchor"])
    if not frames or a is None:
        return None, {}, "the marks were not reached"
    t0 = int(run.frames[a].get("t", 0))
    if (level_of(run.frames[a]) or 0) < 1:
        return (
            None,
            {"level_at_anchor": level_of(run.frames[a])},
            "the level was 0 at the anchor",
        )
    drop = next(((t, r) for t, lv, r in changes(frames) if t >= t0 and lv == 0), None)
    cool, slack = float(args["cooling_s"]), float(args.get("slack_s", 3.0))
    if drop is None:
        return (
            False,
            {"level_at_end": level_of(frames[-1])},
            "the level never dropped to 0",
        )
    dt = round((drop[0] - t0) / TICK_HZ, 3)
    measured = {"dropped_after_s": dt, "reason": drop[1]}
    if dt < cool - 1.0 / TICK_HZ:
        return (
            False,
            measured,
            f"the level dropped {dt} s after the player got away, before {cool} s",
        )
    if dt > cool + slack:
        return (
            False,
            measured,
            f"the level dropped {dt} s after the player got away, later than {cool + slack} s",
        )
    if drop[1] != "escaped":
        return False, measured, f"the drop's reason is {drop[1]!r}, not 'escaped'"
    return True, measured, ""


# ------------------------------------------------------------------ CB-10 and AL-12
def check_police_force(rec: PlayRecord, args: dict) -> Result:
    """CB-10: between the marks, while the level is below 3 (and for 2 s after it drops below
    3), no `damaged` event on the player comes from a police officer and no police person is
    `hostile`; with `fight: true`, once the level is 3 or more with a police officer within
    40 m, a police officer lands a hit on the player within `within_s` (15)."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    pid = player_id(frames)
    police_ids = {
        e.get("id")
        for fr in frames
        for e in fr.get("census") or []
        if e.get("a") in POLICE_PEOPLE
    }
    low_until = None
    bad = []
    fight_from, hit_at = None, None
    by_tick = {int(fr.get("t", 0)): fr for fr in frames}
    for fr in frames:
        t = int(fr.get("t", 0))
        lv = level_of(fr) or 0
        if lv >= 3:
            low_until = t + ticks(2.0)
            pl = player_pos(fr)
            if fight_from is None and pl is not None:
                for e in fr.get("census") or []:
                    if e.get("a") in POLICE_PEOPLE and horizontal(e["p"], pl) <= 40.0:
                        fight_from = t
                        break
        calm = lv < 3 and (low_until is None or t > low_until)
        for ev in fr.get("events") or []:
            if ev.get("n") != "damaged":
                continue
            d = ev.get("d") or {}
            if d.get("entity") == pid and d.get("source") in police_ids:
                if calm:
                    bad.append({"tick": t, "level": lv, "by": d.get("source")})
                elif fight_from is not None and hit_at is None:
                    hit_at = t
        if calm:
            for e in fr.get("census") or []:
                if (
                    e.get("a") in POLICE_PEOPLE
                    and (e.get("m") or {}).get("hostile") is True
                ):
                    bad.append({"tick": t, "level": lv, "hostile": e.get("id")})
                    break
    del by_tick
    measured: dict = {"faults": bad[:5]}
    if bad:
        b = bad[0]
        what = (
            f"police officer {b['by']} hit the player"
            if "by" in b
            else f"police officer {b['hostile']} was hostile"
        )
        return False, measured, f"{what} at level {b['level']}"
    if args.get("fight"):
        if fight_from is None:
            return (
                None,
                measured,
                "no police officer came within 40 m at level 3 or more",
            )
        if hit_at is None or hit_at - fight_from > ticks(
            float(args.get("within_s", 15.0))
        ):
            return (
                False,
                measured,
                "no police officer landed a hit within 15 s at level 3 or more",
            )
        measured["hit_after_s"] = round((hit_at - fight_from) / TICK_HZ, 2)
    return True, measured, ""


def check_left_alone(rec: PlayRecord, args: dict) -> Result:
    """AL-12: from 10 s after the level returns to 0 between the marks, no unit that responded
    (named by `police_dispatched`, or within 100 m of the player during the alert) keeps
    moving towards the player for more than 10 s in a row, and no police officer on foot
    stays within 5 m of the player for more than 5 s (officers within `exempt_m` of the points
    in `exempt`, the station's exit and the respawn points, aside)."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    wrecked = wrecks(frames)
    drop = None
    responded = {d.get("unit") for _t, d in events(frames, "police_dispatched")}
    for fr in frames:
        lv = level_of(fr) or 0
        pl = player_pos(fr)
        if lv > 0 and pl is not None:
            for eid, e in units(fr, wrecked).items():
                if horizontal(e["p"], pl) <= 100.0:
                    responded.add(eid)
    for t, lv, _r in changes(frames):
        if lv == 0:
            drop = t
    if drop is None:
        return None, {}, "the level did not return to 0"
    start = drop + ticks(10.0)
    exempt = args.get("exempt", [])
    ex_m = float(args.get("exempt_m", 15.0))
    run_towards: dict = {}
    close_since: dict = {}
    worst_towards, worst_close = 0.0, 0.0
    for k, fr in enumerate(frames):
        t = int(fr.get("t", 0))
        if t < start or (level_of(fr) or 0) != 0:
            run_towards.clear()
            close_since.clear()
            continue
        pl = player_pos(fr)
        if pl is None:
            continue
        us = units(fr, wrecked)
        for eid in list(responded):
            if eid in us and towards(frames, k, eid, wrecked):
                run_towards.setdefault(eid, t)
                worst_towards = max(
                    worst_towards, (t - run_towards[eid]) / TICK_HZ + TOWARDS_S
                )
            else:
                run_towards.pop(eid, None)
        for eid, e in us.items():
            if e.get("k") != "npc":
                continue
            if any(horizontal(e["p"], [q[0], 0.0, q[-1]]) <= ex_m for q in exempt):
                close_since.pop(eid, None)
                continue
            if horizontal(e["p"], pl) <= 5.0:
                close_since.setdefault(eid, t)
                worst_close = max(worst_close, (t - close_since[eid]) / TICK_HZ)
            else:
                close_since.pop(eid, None)
    measured = {
        "longest_towards_s": round(worst_towards, 2),
        "longest_within_5m_s": round(worst_close, 2),
        "responded": len(responded),
    }
    if worst_towards > 10.0:
        return (
            False,
            measured,
            f"a police unit kept moving towards the player for {worst_towards:.1f} s at level 0",
        )
    if worst_close > 5.0:
        return (
            False,
            measured,
            f"a police officer stayed within 5 m of the player for {worst_close:.1f} s at level 0",
        )
    return True, measured, ""


# ------------------------------------------------------------------ inv.alert_honest
CRIME_LEVEL = {
    "red_light": 1,
    "speeding": 1,
    "vehicle_theft": 1,
    "assault": 1,
    "hit_person": 1,
    "shots_fired": 2,
    "murder": 2,
    "vehicle_destroyed": 2,
    "assault_police": 3,
    "kill_police": 4,
}


def check_alert_honest(rec: PlayRecord, args: dict) -> Result:
    """inv.alert_honest (AL-2 to AL-4, AL-9 to AL-11): between the marks every rise of the level
    follows a witnessed crime: one seen by police at most 1.0 s before it, or one seen only by
    others 10-11 s before it; the new level is what AL-4 gives from the level before and that
    crime's level; drops go to 0 only, with reason `escaped`, `arrested` or `died`. The state
    report agrees with the events. `police`: references of the police officers QA placed (the
    census names the rest by archetype)."""
    run = run_of(rec, args)
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    police = {
        e.get("id")
        for fr in frames
        for e in fr.get("census") or []
        if e.get("a") in POLICE_PEOPLE
    }
    police |= {x for x in answer_ids(run, args.get("police", [])) if x is not None}
    pending = []
    for t, d in crimes(frames):
        seen = d.get("witnesses") if isinstance(d.get("witnesses"), list) else []
        if not seen:
            continue
        if any(w in police for w in seen):
            pending.append((t, t + ticks(1.0), d.get("type")))
        else:
            pending.append((t + ticks(10.0) - 1, t + ticks(11.0), d.get("type")))
    prev = level_of(frames[0]) or 0
    bad = []
    for t, lv, reason in changes(frames):
        if lv > prev:
            match = next((p for p in pending if p[0] <= t <= p[1]), None)
            if match is None:
                if reason != "mission":
                    bad.append(
                        {"tick": t, "level": lv, "why": "no witnessed crime before it"}
                    )
            else:
                pending.remove(match)
                cl = CRIME_LEVEL.get(str(match[2]), 1)
                want = cl if prev < cl else min(5, prev + 1)
                if lv != want and reason != "mission":
                    bad.append(
                        {
                            "tick": t,
                            "level": lv,
                            "why": f"AL-4 gives {want} after {match[2]}",
                        }
                    )
        elif lv < prev and (lv != 0 or reason not in ("escaped", "arrested", "died")):
            bad.append(
                {"tick": t, "level": lv, "why": f"a drop with reason {reason!r}"}
            )
        prev = lv
    end_level = level_of(frames[-1])
    if end_level is not None and frames and end_level != prev:
        last_change = changes(frames)
        if last_change and int(frames[-1].get("t", 0)) - last_change[-1][0] > ticks(
            0.5
        ):
            bad.append(
                {
                    "tick": frames[-1].get("t"),
                    "level": end_level,
                    "why": f"the state says {end_level}, the events {prev}",
                }
            )
    measured = {"changes": len(changes(frames)), "faults": bad[:5]}
    if bad:
        b = bad[0]
        return False, measured, f"level {b['level']} at tick {b['tick']}: {b['why']}"
    return True, measured, ""


CHECKS = {
    "crime_event": check_crime_event,
    "alert_rise": check_alert_rise,
    "alert_steady": check_alert_steady,
    "alert_sequence": check_alert_sequence,
    "police_arrival": check_police_arrival,
    "police_count": check_police_count,
    "police_origin": check_police_origin,
    "police_kinematics": check_police_kinematics,
    "roadblock": check_roadblock,
    "arrest": check_arrest,
    "came_back": check_came_back,
    "escape": check_escape,
    "police_force": check_police_force,
    "left_alone": check_left_alone,
    "alert_honest": check_alert_honest,
}

__all__ = ["CHECKS", "state_of"]
