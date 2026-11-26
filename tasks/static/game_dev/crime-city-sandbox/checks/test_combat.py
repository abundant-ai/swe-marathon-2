"""The kit's combat expectations (chapter 8, FT-11, FT-12, CM-5 and TR-13's gunshots) over
hand-made frames, and the aiming bot's turn (no Godot). Each expectation holds on a
well-behaved fight and fails on the broken one next to it."""

from __future__ import annotations

import copy
import math

from qakit import expect, play

BASE = {"format": "qa-play/1", "name": "x/y", "template": "x", "role": "solo"}
ME = 1
SPAN = {"from": "a", "to": "b"}


def record(frames: list[dict], marks: dict | None = None) -> play.PlayRecord:
    raw = dict(BASE, steps=[{"run": 1}])
    r = play.RunRecord(index=0, pace_ms=0, frames=copy.deepcopy(frames))
    r.marks = marks or {"a": 0, "b": len(frames) - 1}
    return play.PlayRecord(play.parse_play(raw), [r], 0.0)


def outcome(rec: play.PlayRecord, check: str, args: dict) -> expect.Outcome:
    raw = dict(rec.play.raw, expect=[{"id": "e", "check": check, "args": args}])
    return expect.check_play(play.PlayRecord(play.parse_play(raw), rec.runs, 0.0))[0]


def frame(t: int, mag: int = 12, res: int = 24, weapon: str = "pistol", **kw) -> dict:
    pl = {"id": ME, "health": kw.pop("health", 100), "armour": kw.pop("armour", 0),
          "weapon": weapon, "ammo": {"magazine": mag, "reserve": res},
          "aim": kw.pop("aim", None), "cover": kw.pop("cover", False)}  # fmt: skip
    fr = {
        "t": t,
        "state": {"player": pl},
        "census": kw.pop("census", []),
        "_proc": kw.pop("proc", 0),
    }
    fr.update(kw)
    return fr


def hit(
    entity: int, amount: int, health: int, source: int = ME, armour: int = 0
) -> dict:
    return {"n": "damaged", "d": {"entity": entity, "source": source, "amount": amount,
                                  "health": health, "armour": armour}}  # fmt: skip


def died(entity: int) -> dict:
    return {"n": "died", "d": {"entity": entity, "cause": "shot"}}


# ------------------------------------------------------------------ CB-1, CB-2
def pistol_burst(every: int = 20, kill_at: int = 4, amount: int = 25) -> list[dict]:
    frames = [frame(0)]
    health = 100
    for k in range(12):
        t = 1 + every * k
        evs = []
        if k < kill_at:
            health = max(0, health - amount)
            evs.append(hit(7, amount, health))
            if health == 0:
                evs.append(died(7))
        frames.append(frame(t, mag=11 - k, events=evs))
    return frames


def test_hits_amounts_health_and_death() -> None:
    args = dict(SPAN, targets=[7], damage=25, min_hits=4)
    assert outcome(record(pistol_burst()), "hits", args).ok is True
    assert outcome(record(pistol_burst(amount=20, kill_at=5)), "hits", args).ok is False
    early = pistol_burst()
    early[2]["events"].append(died(7))  # dies at 75 health
    assert outcome(record(early), "hits", args).ok is False
    wrong = pistol_burst()
    wrong[2]["events"][0]["d"]["health"] = 70  # lost 30 on a hit of 25
    assert outcome(record(wrong), "hits", args).ok is False


def test_hits_per_round_for_pellets() -> None:
    frames = [frame(0, mag=6, res=12, weapon="shotgun")]
    frames.append(frame(1, mag=5, res=12, weapon="shotgun",
                        events=[hit(7, 10, 100 - 10 * (k + 1)) for k in range(8)]))  # fmt: skip
    args = dict(SPAN, targets=[7], damage=10, min_hits=4, per_round=8)
    assert outcome(record(frames), "hits", args).ok is True
    frames[1]["events"].append(hit(7, 10, 10))
    assert outcome(record(frames), "hits", args).ok is False


def test_fire_rate_rounds_and_blows() -> None:
    args = dict(SPAN, rate=3.0, tol=0.05, min_count=3)
    assert outcome(record(pistol_burst(every=20)), "fire_rate", args).ok is True
    assert outcome(record(pistol_burst(every=22)), "fire_rate", args).ok is False
    blows = [frame(0, weapon="fists", mag=0, res=0)]
    for k in range(6):
        blows.append(
            frame(
                1 + 30 * k,
                weapon="fists",
                mag=0,
                res=0,
                events=[hit(8, 10, 90 - 10 * k)],
            )
        )
    out = outcome(
        record(blows), "fire_rate", dict(SPAN, blows=[8], rate=2.0, min_count=4)
    )
    assert out.ok is True and out.measured["rate_per_s"] == 2.0


def reload_frames(refill_at: int, mag_after: int = 12) -> list[dict]:
    frames = [frame(0, mag=1, res=24), frame(10, mag=0, res=24)]
    frames += [frame(t, mag=0, res=24) for t in range(20, refill_at, 10)]
    frames.append(frame(refill_at, mag=mag_after, res=24 - mag_after))
    return frames


def test_reload_time_and_amounts() -> None:
    args = dict(SPAN, start="empty", reload_s=1.6, tol=0.1, magazine=12)
    assert outcome(record(reload_frames(106)), "reload", args).ok is True
    assert outcome(record(reload_frames(140)), "reload", args).ok is False
    assert outcome(record(reload_frames(106, mag_after=10)), "reload", args).ok is False
    fired_at_refill = reload_frames(106)
    fired_at_refill[-1]["state"]["player"]["ammo"]["magazine"] = (
        11  # a round in that tick
    )
    assert outcome(record(fired_at_refill), "reload", args).ok is True
    flow = outcome(
        record(fired_at_refill), "ammo_flow", dict(SPAN, min_rounds=1, min_reloads=1)
    )
    assert flow.ok is True and flow.measured == {"rounds": 2, "reloads": 1}


def test_ammo_flow_and_dry_fire() -> None:
    good = reload_frames(106)
    assert (
        outcome(record(good), "ammo_flow", dict(SPAN, min_rounds=1, min_reloads=1)).ok
        is True
    )
    bad = copy.deepcopy(good)
    bad[-1]["state"]["player"]["ammo"]["reserve"] = (
        20  # the magazine gained 12, the reserve gave 4
    )
    assert outcome(record(bad), "ammo_flow", dict(SPAN, min_rounds=1)).ok is False
    empty = [frame(t, mag=0, res=0) for t in range(0, 60, 6)]
    assert outcome(record(empty), "dry_fire", SPAN).ok is True
    fired = copy.deepcopy(empty)
    fired[3]["events"] = [hit(9, 25, 75)]
    assert outcome(record(fired), "dry_fire", SPAN).ok is False


# ------------------------------------------------------------------ FT-11, CM-5, CB-4
def arm(
    t: int, hand_dy: float = 0.0, fore_deg: float = 0.0, aim: object = True
) -> dict:
    shoulder = [0.2, 1.45, 0.0]
    hand = [0.2, 1.45 + hand_dy, -0.55]
    a = math.radians(fore_deg)
    elbow = [hand[0] - 0.27 * math.sin(a), hand[1], hand[2] + 0.27 * math.cos(a)]
    target = [0.2, 1.45 + hand_dy, -15.0]
    return frame(t, aim=target if aim else None,
                 bones={str(ME): {"RightHand": hand, "RightLowerArm": elbow, "RightUpperArm": shoulder}})  # fmt: skip


def test_aim_pose() -> None:
    args = dict(SPAN, hand_m=0.25, max_deg=20.0, min_frames=5)
    assert outcome(record([arm(t) for t in range(10)]), "aim_pose", args).ok is True
    assert (
        outcome(record([arm(t, hand_dy=-0.4) for t in range(10)]), "aim_pose", args).ok
        is False
    )
    assert (
        outcome(record([arm(t, fore_deg=30) for t in range(10)]), "aim_pose", args).ok
        is False
    )
    assert (
        outcome(record([arm(t, aim=False) for t in range(10)]), "aim_pose", args).ok
        is False
    )


def locked(t: int, aim_off: float = 0.0, chest_side: float = 0.0) -> dict:
    chest = [chest_side, 1.3, -12.0]
    cam = {"p": [0.0, 1.8, 4.0], "bz": [0.0, 0.0, 1.0], "fov": 75.0}
    return frame(t, aim=[chest[0] + aim_off, 1.3, -12.0], camera=cam,
                 bones={"7": {"Chest": chest}})  # fmt: skip


def test_lock_on() -> None:
    args = dict(SPAN, target=7, aim_m=0.3, middle=0.3, min_frames=5)
    assert outcome(record([locked(t) for t in range(10)]), "lock_on", args).ok is True
    assert (
        outcome(record([locked(t, aim_off=0.5) for t in range(10)]), "lock_on", args).ok
        is False
    )
    assert (
        outcome(
            record([locked(t, chest_side=8.0) for t in range(10)]), "lock_on", args
        ).ok
        is False
    )


def single_rounds(hits: int) -> tuple[list[dict], dict, list[dict]]:
    frames, marks, bursts = [], {}, []
    mag = 12
    for k in range(6):
        marks[f"a{k}"] = len(frames)
        frames.append(frame(100 * k, mag=mag))
        mag -= 1
        evs = [hit(20 + k, 25, 75)] if k < hits else []
        frames.append(frame(100 * k + 1, mag=mag, events=evs))
        marks[f"b{k}"] = len(frames)
        frames.append(frame(100 * k + 20, mag=mag))
        bursts.append({"from": f"a{k}", "to": f"b{k}", "target": 20 + k})
    return frames, marks, bursts


def test_hit_rate() -> None:
    frames, marks, bursts = single_rounds(4)
    args = {"bursts": bursts, "min_share": 0.6, "min_rounds": 6}
    out = outcome(record(frames, marks), "hit_rate", args)
    assert out.ok is True and out.measured["share"] == round(4 / 6, 3)
    frames, marks, bursts = single_rounds(3)
    assert (
        outcome(record(frames, marks), "hit_rate", dict(args, bursts=bursts)).ok
        is False
    )


def test_untouched() -> None:
    frames = pistol_burst(kill_at=0)
    assert (
        outcome(record(frames), "untouched", dict(SPAN, targets=[7], min_rounds=3)).ok
        is True
    )
    frames[3]["events"] = [hit(7, 25, 75)]
    assert (
        outcome(record(frames), "untouched", dict(SPAN, targets=[7], min_rounds=3)).ok
        is False
    )
    still = [frame(t) for t in range(5)]
    assert (
        outcome(record(still), "untouched", dict(SPAN, targets=[7], min_rounds=1)).ok
        is None
    )


# ------------------------------------------------------------------ FT-12, CB-8
WALL = {"p": [0.0, 0.0, 0.0], "size": [2.0, 1.1, 0.5], "heading": 0}


def in_cover(
    t: int, z: float, hips: float, cover: bool, head: float = 0.9, **kw
) -> dict:
    return frame(t, cover=cover, census=[{"id": ME, "k": "player", "p": [0.0, 0.0, z]}],
                 bones={str(ME): {"Hips": [0.0, hips, z], "Head": [0.0, head, z]}}, **kw)  # fmt: skip


def test_cover_enter_hold_and_leave() -> None:
    frames = [in_cover(0, 1.65, 0.95, False)]
    frames += [
        in_cover(t, 1.65 - t / 60, 0.95 - t / 120, False) for t in range(6, 30, 6)
    ]
    frames += [in_cover(t, 0.7, 0.52, True) for t in range(30, 120, 6)]
    rec = record(frames, {"press": 0, "a": 6, "b": len(frames) - 1})
    args = {
        "from": "press",
        "within_s": 1.0,
        "box": WALL,
        "near_m": 0.6,
        "ratio": 0.75,
        "ground_y": 0.0,
    }
    assert outcome(rec, "cover_enter", args).ok is True
    slow = (
        [frames[0]]
        + [in_cover(t, 1.65, 0.95, False) for t in range(6, 90, 6)]
        + [in_cover(90, 0.7, 0.52, True)]
    )
    assert outcome(record(slow, {"press": 0}), "cover_enter", args).ok is False
    hold = {"from": "a", "to": "b", "box": WALL, "near_m": 0.6, "ratio": 0.75, "ground_y": 0.0,
            "standing_mark": "press"}  # fmt: skip
    rec = record(frames, {"press": 0, "a": 6, "b": len(frames) - 1})
    hold["from"] = "c"
    rec.runs[0].marks["c"] = 6
    assert outcome(rec, "cover_hold", hold).ok is True
    high = copy.deepcopy(frames)
    high[-1]["bones"][str(ME)]["Hips"][1] = 0.85
    rec2 = record(high, {"press": 0, "c": 6, "b": len(high) - 1})
    assert outcome(rec2, "cover_hold", hold).ok is False
    leave = [
        in_cover(0, 0.7, 0.52, True),
        in_cover(12, 1.0, 0.95, False),
        in_cover(60, 2.5, 0.95, False),
    ]
    lv = {"from": "a", "to": "b", "box": WALL, "within_s": 0.5, "near_m": 0.6}
    assert outcome(record(leave), "cover_leave", lv).ok is True
    stuck = [
        in_cover(0, 0.7, 0.52, True),
        in_cover(12, 0.7, 0.52, True),
        in_cover(60, 0.7, 0.52, True),
    ]
    assert outcome(record(stuck), "cover_leave", lv).ok is False


def test_lean_out() -> None:
    frames = [in_cover(0, 0.7, 0.52, True, head=0.95)]
    frames += [in_cover(t, 0.7, 0.9, True, head=1.6, mag=12) for t in range(6, 60, 6)]
    frames += [
        in_cover(60 + t, 0.7, 0.9, True, head=1.6, mag=12 - t // 20)
        for t in range(0, 41, 10)
    ]
    marks = {"lean": 0, "fa": 10, "fb": len(frames) - 1}
    args = {
        "from": "lean",
        "within_s": 1.0,
        "rise_m": 0.3,
        "fire_from": "fa",
        "fire_to": "fb",
    }
    assert outcome(record(frames, marks), "lean_out", args).ok is True
    low = [in_cover(t, 0.7, 0.52, True, head=1.1) for t in range(0, 120, 6)]
    assert (
        outcome(record(low, marks | {"fb": len(low) - 1}), "lean_out", args).ok is False
    )


def window(proc: int, hits: int, t0: int = 100) -> list[dict]:
    frames = [frame(t0, proc=proc)]
    for k in range(hits):
        frames.append(
            frame(
                t0 + 10 + 60 * k, proc=proc, events=[hit(ME, 25, 90, source=30 + k % 2)]
            )
        )
    frames.append(frame(t0 + 900, proc=proc))
    return frames


def test_cover_cuts() -> None:
    def run_of(open_hits: int, cover_hits: int, same: bool = False) -> play.PlayRecord:
        a = window(0, open_hits)
        b = window(0 if same else 1, cover_hits)
        return record(
            a + b, {"oa": 0, "ob": len(a) - 1, "ca": len(a), "cb": len(a) + len(b) - 1}
        )

    args = {"open": {"from": "oa", "to": "ob", "attackers": [30, 31]},
            "cover": {"from": "ca", "to": "cb", "attackers": [30, 31]},
            "max_ratio": 0.4, "min_open_hits": 8}  # fmt: skip
    assert outcome(run_of(10, 2), "cover_cuts", args).ok is True
    assert outcome(run_of(10, 5), "cover_cuts", args).ok is False
    assert outcome(run_of(10, 2, same=True), "cover_cuts", args).ok is None
    assert outcome(run_of(5, 0), "cover_cuts", args).ok is None


# ------------------------------------------------------------------ CB-5
def test_armour_split() -> None:
    hits = [(25, 90, 25), (25, 80, 10), (25, 65, 0), (25, 40, 0)]
    frames = [frame(0, health=100, armour=40)]
    frames += [
        frame(60 * (k + 1), events=[hit(ME, a, h, source=30, armour=ar)])
        for k, (a, h, ar) in enumerate(hits)
    ]
    args = dict(SPAN, share=0.6, min_armoured=2, min_bare=1)
    assert outcome(record(frames), "armour_split", args).ok is True
    wrong = copy.deepcopy(frames)
    wrong[1]["events"][0]["d"].update(health=80, armour=35)  # armour took 5, health 20
    assert outcome(record(wrong), "armour_split", args).ok is False


# ------------------------------------------------------------------ CB-9
def crew_frame(t: int, hostile_from: dict, pos_of: dict | None = None, **kw) -> dict:
    census = [{"id": ME, "k": "player", "p": [0.0, 0.0, 0.0]}]
    for m, (x, z) in (pos_of or {40: (0.0, -20.0), 41: (5.0, -22.0)}).items():
        census.append({"id": m, "k": "npc", "p": [x, 0.0, z],
                       "m": {"hostile": t >= hostile_from.get(m, 10**9)}})  # fmt: skip
    return frame(t, census=census, **kw)


def test_turn_hostile_aim_and_hit() -> None:
    args = dict(SPAN, members=[40, 41], trigger="aim", after_s=5.0, within_s=2.0)
    on_time = [crew_frame(t, {40: 306, 41: 306}) for t in range(0, 600, 6)]
    assert outcome(record(on_time), "turn_hostile", args).ok is True
    early = [crew_frame(t, {40: 180, 41: 306}) for t in range(0, 600, 6)]
    assert outcome(record(early), "turn_hostile", args).ok is False
    late = [crew_frame(t, {40: 306, 41: 480}) for t in range(0, 600, 6)]
    assert outcome(record(late), "turn_hostile", args).ok is False
    hit_args = dict(SPAN, members=[40, 41], trigger="hit", within_s=2.0)
    frames = [
        crew_frame(t, {40: 66, 41: 72}, events=[hit(40, 10, 90)] if t == 60 else [])
        for t in range(0, 300, 6)
    ]
    assert outcome(record(frames), "turn_hostile", hit_args).ok is True


def test_flee_away_reach_cover_retreat_and_fires_at() -> None:
    def runner(gain: float) -> list[dict]:
        return [
            crew_frame(t, {40: 60}, {40: (0.0, -20.0 - max(0, t - 60) / 600 * gain)})
            for t in range(0, 720, 6)
        ]

    args = dict(SPAN, people=[40], min_m=20.0, within_s=10.0)
    assert outcome(record(runner(30.0)), "flee_away", args).ok is True
    assert outcome(record(runner(10.0)), "flee_away", args).ok is False
    walls = [{"p": [0.0, 0.0, -25.0], "size": [2.0, 1.1, 0.5], "heading": 0}]
    to_cover = [crew_frame(t, {40: 60, 41: 60}, {40: (0.0, -20.0 - min(5.5, max(0, t - 60) / 60)), 41: (5.0, -22.0)})
                for t in range(0, 720, 6)]  # fmt: skip
    rc = dict(
        SPAN,
        crew=[40, 41],
        enforcers=[40, 41],
        boxes=walls,
        within_s=10.0,
        near_m=1.0,
        min_share=0.5,
    )
    assert outcome(record(to_cover), "reach_cover", rc).ok is True
    assert outcome(record(to_cover), "reach_cover", dict(rc, min_share=1.0)).ok is False
    back = [crew_frame(t, {40: 0}, {40: (0.0, -20.0 - min(15.0, max(0, t - 60) / 30))},
                       events=[hit(40, 25, 25)] if t == 60 else []) for t in range(0, 720, 6)]  # fmt: skip
    rt = dict(SPAN, enforcers=[40], below=30, within_s=10.0, min_m=10.0)
    assert outcome(record(back), "retreat", rt).ok is True
    stay = [crew_frame(t, {40: 0}, {40: (0.0, -20.0)}, events=[hit(40, 25, 25)] if t == 60 else [])
            for t in range(0, 720, 6)]  # fmt: skip
    assert outcome(record(stay), "retreat", rt).ok is False
    shots = [crew_frame(t, {40: 0, 41: 0}, events=[hit(ME, 25, 75, source=40), hit(ME, 25, 50, source=41)] if t == 60 else [])
             for t in range(0, 120, 6)]  # fmt: skip
    fa = dict(SPAN, attackers=[40, 41], max_m=40.0, min_hits=1)
    assert outcome(record(shots), "fires_at", fa).ok is True
    one = [
        crew_frame(
            t, {40: 0, 41: 0}, events=[hit(ME, 25, 75, source=40)] if t == 60 else []
        )
        for t in range(0, 120, 6)
    ]
    assert outcome(record(one), "fires_at", fa).ok is False


# ------------------------------------------------------------------ TR-13
def flight(stop_at: float | None = None) -> list[dict]:
    frames = []
    for t in range(0, 13 * 60, 3):
        run_s = max(0.0, (t - 30) / 60)
        if stop_at is not None:
            run_s = min(run_s, stop_at)
        census = [{"id": ME, "k": "player", "p": [0.0, 0.0, 0.0]},
                  {"id": 50, "k": "npc", "p": [8.0 + 5.0 * run_s, 0.0, 0.0], "m": {"limp": False, "vehicle": None}}]  # fmt: skip
        frames.append(frame(t, mag=12 if t < 10 else 11, census=census))
    return frames


def test_gunshot_flee() -> None:
    args = dict(SPAN, people=[50], near_m=28.0, start_s=2.0, end_s=12.0, min_mps=3.0,
                min_gain_m=20.0, min_share=0.9, min_people=1)  # fmt: skip
    assert outcome(record(flight()), "gunshot_flee", args).ok is True
    assert outcome(record(flight(stop_at=4.0)), "gunshot_flee", args).ok is False


# ------------------------------------------------------------------ QA's aiming bot
def test_aim_turn() -> None:
    fr = {
        "camera": {"p": [0.0, 1.8, 4.0], "bz": [0.0, 0.0, 1.0], "fov": 75.0},
        "state": {"player": {"aim": [0.0, 1.3, -20.0]}},
        "bones": {"7": {"Chest": [2.0, 1.3, -20.0]}},
    }
    yaw, pitch = play._aim_turn(fr, 7, "Chest")
    assert yaw > 4.0 and abs(pitch) < 0.1  # the target is to the right: turn right
    fr["bones"]["7"]["Chest"] = [0.0, 3.3, -20.0]
    yaw, pitch = play._aim_turn(fr, 7, "Chest")
    assert abs(yaw) < 1e-9 and pitch > 4.0  # above: tilt up
    assert play._aim_turn({"camera": fr["camera"], "state": {}}, 7, "Chest") is None


def test_aim_at_step_is_checked() -> None:
    good = dict(
        BASE, steps=[{"aim_at": {"entity": {"id": 7}, "bone": "Chest", "ticks": 30}}]
    )
    assert play.parse_play(good).steps
    bad = dict(BASE, steps=[{"aim_at": {"entity": {"kind": "npc"}, "ticks": 30}}])
    try:
        play.parse_play(bad)
    except play.PlayError:
        return
    raise AssertionError("an aim_at without an entity id was accepted")
