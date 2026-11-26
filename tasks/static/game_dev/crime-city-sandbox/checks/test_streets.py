"""The kit's street expectations (traffic and people on foot, chapter 7) over hand-made
frames, the census selectors of bone and seat reads, and shared expectation values (no
Godot). Each expectation holds on a well-behaved street and fails on the broken one next to
it."""

from __future__ import annotations

import copy

from qakit import expect, play

BASE = {"format": "qa-play/1", "name": "x/y", "template": "x", "role": "solo"}


def record(
    frames: list[dict], steps: list[dict] | None = None, shared: dict | None = None
) -> play.PlayRecord:
    raw = dict(BASE, steps=steps or [{"run": 1}])
    if shared:
        raw["shared"] = shared
    r = play.RunRecord(index=0, pace_ms=0, frames=copy.deepcopy(frames))
    r.marks = {"a": 0, "b": len(frames) - 1}
    return play.PlayRecord(play.parse_play(raw), [r], 0.0)


def outcome(rec: play.PlayRecord, check: str, args: dict) -> expect.Outcome:
    raw = dict(rec.play.raw, expect=[{"id": "e", "check": check, "args": args}])
    return expect.check_play(play.PlayRecord(play.parse_play(raw), rec.runs, 0.0))[0]


SPAN = {"from": "a", "to": "b"}


def box(x: float, z: float, along_z: bool = True) -> list[float]:
    """A 2.0 m wide, 1.5 m high, 4.4 m long car's collision box centred at (x, 0.75, z)."""
    if along_z:
        return [x, 0.75, z, 1.0, 0, 0, 0, 0.75, 0, 0, 0, 2.2]
    return [x, 0.75, z, 0, 0, 1.0, 0, 0.75, 0, 2.2, 0, 0]


def vehicle(vid: int, x: float, z: float, along_z: bool = True, **m: object) -> dict:
    row = {
        "id": vid,
        "k": "vehicle",
        "a": "sedan",
        "p": [x, 0.0, z],
        "bz": [0, 0, 1],
        "sh": [box(x, z, along_z)],
    }
    if not along_z:
        row["bz"] = [-1, 0, 0]
    if m:
        row["m"] = dict(m)
    return row


def person(pid: int, x: float, z: float, arch: str = "tourist", **m: object) -> dict:
    meta = {"vehicle": None, "seat": None, "limp": False}
    meta.update(m)
    return {"id": pid, "k": "npc", "a": arch, "p": [x, 0.0, z], "m": meta}


def player(x: float = 0.0, z: float = 0.0) -> dict:
    return {"id": 1, "k": "player", "a": "lead_1", "p": [x, 0.0, z]}


# ------------------------------------------------------------------ TR-16
def drive_frames(driver_arch: str | None, hips_off: float = 0.0) -> list[dict]:
    frames = []
    for k in range(10):
        z = -k * 1.0
        census = [player(50, 0), vehicle(10, 0.0, z)]
        if driver_arch:
            census.append({"id": 11, "k": "npc", "a": driver_arch, "p": [0.0, 0.3, z],
                           "m": {"vehicle": 10, "seat": 0, "limp": False}})  # fmt: skip
        frames.append({
            "t": k * 6, "census": census,
            "bones": {"11": {"Hips": [hips_off, 0.8, z]}} if driver_arch else {},
            "seats": {"10": [{"index": 0, "p": [0.0, 0.8, z], "door": None, "wheel": None}]},
        })  # fmt: skip
    return frames


def test_drivers_seated_of_a_driving_archetype() -> None:
    args = {**SPAN, "archetypes": ["commuter_driver"], "min_kmh": 1.0, "hips_m": 0.35}
    assert outcome(record(drive_frames("commuter_driver")), "drivers", args).ok is True
    assert outcome(record(drive_frames(None)), "drivers", args).ok is False
    assert outcome(record(drive_frames("tourist")), "drivers", args).ok is False
    off = outcome(
        record(drive_frames("commuter_driver", hips_off=0.6)), "drivers", args
    )
    assert off.ok is False and off.measured["worst_hips_m"] > 0.5


# ------------------------------------------------------------------ TR-1
def density_frames(n_vehicles: int, n_people: int) -> list[dict]:
    frames = []
    for k in range(0, 3700, 30):
        census = [player()]
        for i in range(n_vehicles):
            census.append(vehicle(100 + i, 10.0 * i, 20.0 - k / 30 * 0.5))
        for i in range(n_people):
            census.append(person(300 + i, -20.0, 2.0 * i))
        frames.append({"t": k, "census": census})
    return frames


def test_density_medians_inside_the_band() -> None:
    args = {**SPAN, "within_m": 150.0, "vehicles": [10, 30], "people": [20, 60]}
    good = outcome(record(density_frames(12, 30)), "density", args)
    assert good.ok is True and good.measured["minutes"][0]["vehicles"] == 12
    assert outcome(record(density_frames(5, 30)), "density", args).ok is False
    assert outcome(record(density_frames(12, 10)), "density", args).ok is False


# ------------------------------------------------------------------ TR-5
APPROACH = {
    "intersection": "j",
    "approach": "j<n",
    "line": [[0.0, 0.0], [3.25, 0.0]],
    "toward": [0.0, -1.0],
}


def light(state: str) -> dict:
    return {"id": 50, "k": "signal", "a": "traffic_light", "p": [4, 0, 0],
            "m": {"intersection": "j", "approach": "j<n", "state": state}}  # fmt: skip


def crossing(states: list[str], v: float = 10.0) -> list[dict]:
    """A vehicle driving north (-z) from z = 30 at v m/s, frames every 6 ticks, the light's
    state per frame."""
    frames = []
    for k, st in enumerate(states):
        z = 30.0 - v * k * 0.1
        frames.append(
            {"t": k * 6, "census": [player(40, 40), vehicle(10, 1.6, z), light(st)]}
        )
    return frames


def test_red_entries_and_amber() -> None:
    args = {**SPAN, "approaches": [APPROACH], "grace_s": 0.5, "amber_mps2": 4.0}
    green = outcome(record(crossing(["green"] * 40)), "red_entries", args)
    assert green.ok is True and green.measured["crossings"] == 1
    red = outcome(record(crossing(["green"] * 5 + ["red"] * 35)), "red_entries", args)
    assert red.ok is False and red.measured["on_red"] == 1
    # amber 30 m before the line at 10 m/s needed 1.7 m/s^2: it should have stopped
    amber = outcome(record(crossing(["green"] + ["amber"] * 39)), "red_entries", args)
    assert amber.ok is False and amber.measured["could_have_stopped"] == 1
    # amber 1 m before the line at 10 m/s would need 50 m/s^2: going on is right
    late = crossing(["green"] * 29 + ["amber"] * 11)
    assert outcome(record(late), "red_entries", args).ok is True


def test_green_flow_counts_entries() -> None:
    args = {**SPAN, "approaches": [APPROACH], "min_vehicles": 1}
    assert outcome(record(crossing(["green"] * 40)), "green_flow", args).ok is True
    args["min_vehicles"] = 3
    assert outcome(record(crossing(["green"] * 40)), "green_flow", args).ok is False


# ------------------------------------------------------------------ TR-7, TR-8
LANE = {
    "id": "e:ab0",
    "pts": [[0.0, 0.0], [100.0, 0.0]],
    "width": 3.25,
    "limit_kmh": 40.0,
}


def along_lane(z: float, v: float, reverse: bool = False, n: int = 60) -> list[dict]:
    frames = []
    for k in range(n):
        x = 90.0 - v * k * 0.1 if reverse else 10.0 + v * k * 0.1
        row = vehicle(10, x, z, along_z=False)
        if reverse:
            row["bz"] = [1, 0, 0]
        frames.append({"t": k * 6, "census": [player(0, 50), row]})
    return frames


def test_lane_keeping() -> None:
    args = {
        **SPAN,
        "lanes": [LANE],
        "max_offset_m": 1.0,
        "max_heading_deg": 15.0,
        "min_share": 0.98,
    }
    assert outcome(record(along_lane(0.2, 10.0)), "lane_keeping", args).ok is True
    wide = outcome(record(along_lane(1.4, 10.0)), "lane_keeping", args)
    assert wide.ok is False and wide.measured["offset_p95_m"] > 1.0
    wrong = outcome(record(along_lane(0.0, 10.0, reverse=True)), "lane_keeping", args)
    assert wrong.ok is False and wrong.measured["against"] > 0


def test_lane_speeds() -> None:
    args = {**SPAN, "lanes": [LANE], "window": 6, "share": 1.1}
    assert outcome(record(along_lane(0.0, 11.0)), "lane_speeds", args).ok is True
    assert outcome(record(along_lane(0.0, 13.0)), "lane_speeds", args).ok is False


# ------------------------------------------------------------------ TR-9, TR-10, TR-11
# A road along x (z from -3.25 to 3.25), a crosswalk band across it at x 10-13, blocks on
# both sides, a building on the north block.
AREA = {
    "centre": [10.0, 0.0], "radius_m": 60.0,
    "lanes": [LANE],
    "roads": [[[-50, -3.25], [60, -3.25], [60, 3.25], [-50, 3.25]]],
    "crosswalks": [{"id": "cw", "intersection": "j", "control": "stop", "walk_signals": False,
                    "poly": [[10, -3.25], [13, -3.25], [13, 3.25], [10, 3.25]]}],
    "blocks": [[[-50, 3.25], [60, 3.25], [60, 40], [-50, 40]], [[-50, -40], [60, -40], [60, -3.25], [-50, -3.25]]],
    "buildings": [[[20, 10], [40, 10], [40, 30], [20, 30]]],
    "rooms": [],
}  # fmt: skip


def walker(
    path: list[tuple[float, float]], extra: list[dict] | None = None, step: int = 6
) -> list[dict]:
    frames = []
    for k, (x, z) in enumerate(path):
        frames.append(
            {
                "t": k * step,
                "census": [player(0, 30), person(20, x, z)] + list(extra or []),
            }
        )
    return frames


def straight_path(
    x0: float, z0: float, x1: float, z1: float, n: int
) -> list[tuple[float, float]]:
    return [
        (x0 + (x1 - x0) * k / (n - 1), z0 + (z1 - z0) * k / (n - 1)) for k in range(n)
    ]


def test_walkable_ground() -> None:
    args = {**SPAN, "area": {"$shared": "area"}, "min_share": 0.95}
    on_walk = walker(straight_path(0, 6, 15, 6, 40))
    assert outcome(record(on_walk, shared={"area": AREA}), "walkable", args).ok is True
    in_road = walker(straight_path(0, 0.5, 8, 0.5, 40))
    assert outcome(record(in_road, shared={"area": AREA}), "walkable", args).ok is False
    in_building = walker(straight_path(25, 15, 30, 15, 40))
    assert (
        outcome(record(in_building, shared={"area": AREA}), "walkable", args).ok
        is False
    )


def test_crosswalk_use() -> None:
    args = {**SPAN, "area": AREA, "min_share": 0.9, "gap_m": 15.0}
    zebra = walker(straight_path(11.5, 6, 11.5, -6, 60))
    good = outcome(record(zebra), "crosswalk_use", args)
    assert good.ok is True and good.measured["crossings"] == 1
    jay = walker(straight_path(30, 6, 30, -6, 60))
    assert outcome(record(jay), "crosswalk_use", args).ok is False
    # at an all-way stop: a car 10 m from the band coming towards it when the person starts
    cars = [vehicle(10, 0.0 + 0.5 * k, 1.6, along_z=False) for k in range(60)]
    traffic = walker(straight_path(11.5, 6, 11.5, -6, 60))
    for fr, car in zip(traffic, cars, strict=True):
        fr["census"].append(car)
    assert outcome(record(traffic), "crosswalk_use", args).ok is False
    # at a signal: starting while the crosswalk shows don't walk
    signal_area = copy.deepcopy(AREA)
    signal_area["crosswalks"][0].update(control="signal", walk_signals=True)
    walk_sign = {"id": 51, "k": "signal", "a": "walk_signal", "p": [0, 0, 0],
                 "m": {"intersection": "j", "crosswalk": "cw", "state": "dont_walk"}}  # fmt: skip
    red_man = walker(straight_path(11.5, 6, 11.5, -6, 60), extra=[walk_sign])
    assert (
        outcome(record(red_man), "crosswalk_use", dict(args, area=signal_area)).ok
        is False
    )
    walk_sign = copy.deepcopy(walk_sign)
    walk_sign["m"]["state"] = "walk"
    on_walk = walker(straight_path(11.5, 6, 11.5, -6, 60), extra=[walk_sign])
    assert (
        outcome(record(on_walk), "crosswalk_use", dict(args, area=signal_area)).ok
        is True
    )


def test_crosswalk_hits() -> None:
    args = {**SPAN, "area": AREA, "clear_m": 0.3}
    near = walker([(11.5, 0.0)] * 10, extra=[vehicle(10, 11.5, 1.1, along_z=False)])
    assert outcome(record(near), "crosswalk_hits", args).ok is False
    clear = walker([(11.5, 0.0)] * 10, extra=[vehicle(10, 4.0, 1.6, along_z=False)])
    assert outcome(record(clear), "crosswalk_hits", args).ok is True


# ------------------------------------------------------------------ TR-12
def two_cars(touch_at: int | None) -> list[dict]:
    frames = []
    for k in range(600):
        x2 = 2.0 if touch_at is not None and touch_at <= k < touch_at + 20 else 6.0
        frames.append({"t": k * 6, "census": [player(0, 50), vehicle(10, 0.0, -k * 0.5),
                                              vehicle(11, x2, -k * 0.5)]})  # fmt: skip
    return frames


def test_vehicle_contacts_rate() -> None:
    args = {**SPAN, "max_rate": 0.02, "touch_m": 0.02, "apart_s": 1.0}
    calm = outcome(record(two_cars(None)), "vehicle_contacts", args)
    assert calm.ok is True and calm.measured["collisions"] == 0
    bump = outcome(record(two_cars(100)), "vehicle_contacts", args)
    assert bump.ok is False and bump.measured["collisions"] == 1


def test_stop_short() -> None:
    barrier = {"p": [0.0, 0.0, -40.0], "size": [3.0, 0.8, 0.4], "heading": 0.0}
    frames_ok, frames_hit = [], []
    for k in range(100):
        z_ok = max(-35.0, -k * 0.6)
        z_hit = max(-38.5, -k * 0.6)
        frames_ok.append(
            {"t": k * 6, "census": [player(20, 0), vehicle(10, 0.0, z_ok)]}
        )
        frames_hit.append(
            {"t": k * 6, "census": [player(20, 0), vehicle(10, 0.0, z_hit)]}
        )
    args = {
        **SPAN,
        "props": [barrier],
        "drivers": [10],
        "touch_m": 0.02,
        "stop_within_m": 30.0,
    }
    assert outcome(record(frames_ok), "stop_short", args).ok is True
    assert outcome(record(frames_hit), "stop_short", args).ok is False


# ------------------------------------------------------------------ TR-13, TR-14
def test_horn_clear() -> None:
    lane = {"id": "e:ab0", "pts": [[0.0, 0.0], [100.0, 0.0]], "width": 3.25}
    args = {
        **SPAN,
        "vehicle": 10,
        "lane": lane,
        "people": [20],
        "ahead_m": 20.0,
        "within_s": 3.0,
    }
    steps_aside = [(25.0, min(3.0, 0.05 * k)) for k in range(240)]
    car = vehicle(10, 10.0, 0.0, along_z=False)
    car["bz"] = [-1, 0, 0]
    frames = [
        {"t": k, "census": [player(0, 30), car, person(20, x, z)]}
        for k, (x, z) in enumerate(steps_aside)
    ]
    assert outcome(record(frames), "horn_clear", args).ok is True
    stays = [
        {"t": k, "census": [player(0, 30), car, person(20, 25.0, 0.0)]}
        for k in range(240)
    ]
    assert outcome(record(stays), "horn_clear", args).ok is False


def test_sidewalk_dodge() -> None:
    blocks = [[[-50, 3.25], [60, 3.25], [60, 40], [-50, 40]]]
    args = {
        **SPAN,
        "vehicle": 10,
        "blocks": blocks,
        "min_kmh": 20.0,
        "ahead_m": 60.0,
        "clear_m": 0.3,
    }
    good, bad = [], []
    for k in range(60):
        x = 0.0 + 7.0 * k * 0.1
        car = vehicle(10, x, 6.0, along_z=False)
        side = 6.0 + min(3.5, max(0.0, (k - 5) * 0.5))
        good.append(
            {"t": k * 6, "census": [player(0, 30), car, person(20, 30.0, side)]}
        )
        bad.append({"t": k * 6, "census": [player(0, 30), car, person(20, 30.0, 6.0)]})
    assert outcome(record(good), "sidewalk_dodge", args).ok is True
    assert outcome(record(bad), "sidewalk_dodge", args).ok is False


# ------------------------------------------------------------------ TR-15
def pop(appear_at: float, in_view: bool, setup: bool) -> play.PlayRecord:
    frames = [
        {"t": 0, "_step": 0, "census": [player()]},
        {"t": 6, "_step": 0, "census": [player()]},
    ]
    row = person(30, appear_at, 0.0)
    row["iv"] = in_view
    frames.append({"t": 12, "_step": 1 if setup else 0, "census": [player(), row]})
    frames.append({"t": 18, "_step": 0, "census": [player(), dict(row)]})
    steps = [{"run": 1}, {"dev": [["npc.spawn", {}]]}]
    return record(frames, steps=steps)


def test_no_pop_in() -> None:
    args = {**SPAN, "near_m": 80.0, "view_m": 200.0}
    assert outcome(pop(120.0, False, False), "no_pop_in", args).ok is True
    assert outcome(pop(50.0, False, False), "no_pop_in", args).ok is False
    assert outcome(pop(120.0, True, False), "no_pop_in", args).ok is False
    assert outcome(pop(50.0, True, True), "no_pop_in", args).ok is True


# ------------------------------------------------------------------ TR-6
# Approach "s" arrives from the south travelling north (-z), approach "e" from the east
# travelling west (-x); "e" is on the right of "s". The box is the square |x|, |z| < 6.
STOP_APPROACHES = [
    {"intersection": "j", "approach": "s", "line": [[-3.25, 9.0], [0.0, 9.0]], "toward": [0.0, -1.0]},
    {"intersection": "j", "approach": "e", "line": [[9.0, 0.0], [9.0, -3.25]], "toward": [-1.0, 0.0]},
]  # fmt: skip
STOP_BOX = [[-6, -6], [6, -6], [6, 6], [-6, 6]]


def south_car(t: int, go: int, wait_until: int) -> tuple[float, float]:
    """Position at tick t of a car from the south: stands 2 m before the line from tick 0 to
    `go`, then drives north through the box at 5 m/s."""
    if t < go:
        return (-1.6, 11.0)
    return (-1.6, 11.0 - 5.0 * (t - go) / 60)


def east_car(t: int, arrive: int, go: int) -> tuple[float, float]:
    if t < arrive:
        return (11.0 + (arrive - t) * 0.2, -1.6)
    if t < go:
        return (11.0, -1.6)
    return (11.0 - 5.0 * (t - go) / 60, -1.6)


def stop_frames(
    s_go: int, e_arrive: int, e_go: int, rolling: bool = False
) -> list[dict]:
    frames = []
    for t in range(0, 900, 6):
        sx, sz = south_car(t, s_go, 0)
        if rolling:
            sz = 11.0 - 5.0 * t / 60
        ex, ez = east_car(t, e_arrive, e_go)
        frames.append(
            {
                "t": t,
                "census": [
                    player(30, 30),
                    vehicle(10, sx, sz),
                    vehicle(11, ex, ez, along_z=False),
                ],
            }
        )
    return frames


STOP_ARGS = {**SPAN, "approaches": STOP_APPROACHES, "box": STOP_BOX, "zone_m": 4.0}


def test_stop_full_and_wait() -> None:
    good = stop_frames(s_go=120, e_arrive=300, e_go=480)
    assert outcome(record(good), "stop_full", STOP_ARGS).ok is True
    assert (
        outcome(
            record(stop_frames(120, 300, 480, rolling=True)), "stop_full", STOP_ARGS
        ).ok
        is False
    )
    assert outcome(record(good), "stop_wait", dict(STOP_ARGS, max_s=30.0)).ok is True
    assert outcome(record(good), "stop_wait", dict(STOP_ARGS, max_s=2.0)).ok is False


def test_stop_order_and_box() -> None:
    args = dict(STOP_ARGS, late_s=1.2, tie_s=0.8, right_of={"s": "e"})
    in_order = stop_frames(s_go=120, e_arrive=300, e_go=480)
    assert outcome(record(in_order), "stop_order", args).ok is True
    # the east car arrived 5 s later but went first
    jumped = stop_frames(s_go=500, e_arrive=300, e_go=360)
    assert outcome(record(jumped), "stop_order", args).ok is False
    assert outcome(record(in_order), "box_clear", STOP_ARGS).ok is True
    together = stop_frames(s_go=300, e_arrive=60, e_go=300)
    assert outcome(record(together), "box_clear", STOP_ARGS).ok is False


def test_a_second_pass_is_a_new_visit() -> None:
    """A car that goes through, round the block and back is two visits, not one long stay in
    the box overlapping everyone who crossed in between."""
    frames = []
    for t in range(0, 1800, 6):
        census = [player(30, 30)]
        # the south car: through at 120-260, away, back at the line from 1200 and through at 1300
        if t < 1200:
            sx, sz = south_car(t, 120, 0)
            if sz < -40.0:
                sx, sz = (60.0, 60.0)  # round the block, far off
        else:
            sx, sz = south_car(t - 1080, 220, 0)
        census.append(vehicle(10, sx, sz))
        ex, ez = east_car(t, 500, 600)
        census.append(vehicle(11, ex, ez, along_z=False))
        frames.append({"t": t, "census": census})
    rec = record(frames)
    assert outcome(rec, "box_clear", STOP_ARGS).ok is True
    assert outcome(rec, "stop_full", STOP_ARGS).ok is True
    assert outcome(rec, "stop_order", dict(STOP_ARGS, late_s=1.2, tie_s=0.8)).ok is True


# ------------------------------------------------------------------ selectors and shared values
def test_selectors_pick_the_nearest_of_a_kind() -> None:
    frame = {"census": [player(), person(5, 3.0, 0.0, seat=0, vehicle=9), person(6, 1.0, 0.0, seat=0, vehicle=8),
                        person(7, 2.0, 0.0), person(8, 500.0, 0.0, seat=0, vehicle=7)]}  # fmt: skip
    sel = {"kind": "npc", "meta": {"seat": 0}, "within_m": 100.0, "max": 5}
    assert play.selected(frame, sel) == [6, 5]
    obs = play.resolve_observe(
        {"bones": {"ids": [sel, "player"], "names": ["Hips"]}}, frame
    )
    assert obs["bones"]["ids"] == [6, 5, 1]


def test_shared_values_fill_arguments() -> None:
    assert expect.shared(
        {"a": {"$shared": "x"}, "b": [{"$shared": "x"}]}, {"x": 3}
    ) == {"a": 3, "b": [3]}


def test_three_arriving_together_may_go_in_any_order() -> None:
    """A third car arriving with the two lets the right-hand rule off (TR-6)."""
    args = dict(STOP_ARGS, late_s=1.2, tie_s=0.8, right_of={"s": "e"})
    # the south car goes before the east car although the east car came from its right
    frames = stop_frames(s_go=120, e_arrive=0, e_go=480)
    assert outcome(record(frames), "stop_order", args).ok is False
    west = {
        "intersection": "j",
        "approach": "w",
        "line": [[-9.0, 3.25], [-9.0, 0.0]],
        "toward": [1.0, 0.0],
    }
    for fr in frames:
        fr["census"].append(vehicle(12, -11.0, 1.6, along_z=False))
    three = dict(args, approaches=[*STOP_APPROACHES, west])
    assert outcome(record(frames), "stop_order", three).ok is True


def test_lane_keeping_leaves_out_the_first_metres_of_a_lane() -> None:
    """A car still turning in a lane's first 10 m is let off with skip_start_m."""
    frames = []
    for k in range(60):
        x = 1.0 + 0.15 * k
        row = vehicle(10, x, 0.0, along_z=False)
        row["bz"] = [-0.5, 0, -0.866] if x < 8.0 else [-1, 0, 0]
        frames.append({"t": k * 6, "census": [player(0, 50), row]})
    args = {
        **SPAN,
        "lanes": [LANE],
        "max_offset_m": 1.0,
        "max_heading_deg": 15.0,
        "min_share": 0.98,
    }
    assert outcome(record(frames), "lane_keeping", args).ok is False
    assert (
        outcome(record(frames), "lane_keeping", dict(args, skip_start_m=10.0)).ok
        is True
    )


def test_a_vehicle_going_past_a_crosswalk_does_not_hold_people() -> None:
    """At an all-way stop only a vehicle whose line of travel enters the band holds people."""
    args = {**SPAN, "area": AREA, "min_share": 0.9, "gap_m": 15.0}
    away = [vehicle(10, 2.0 - 0.5 * k, 1.6, along_z=False) for k in range(60)]
    crossing = walker(straight_path(11.5, 6, 11.5, -6, 60))
    for fr, car in zip(crossing, away, strict=True):
        car["bz"] = [1, 0, 0]
        fr["census"].append(car)
    assert outcome(record(crossing), "crosswalk_use", args).ok is True


def test_pop_in_lets_off_a_world_reset_while_it_settles() -> None:
    """People placed in the second after a world.reset are let off (it may take up to 3 s)."""
    frames = [
        {"t": 0, "_step": 0, "census": [player()]},
        {"t": 6, "_step": 1, "census": [player()]},
    ]
    row = person(30, 20.0, 0.0)
    frames.append({"t": 66, "_step": 2, "census": [player(), row]})
    frames.append({"t": 72, "_step": 2, "census": [player(), dict(row)]})
    steps = [{"run": 1}, {"dev": [["world.reset", {}]]}, {"run": 120}]
    args = {**SPAN, "near_m": 80.0, "view_m": 200.0}
    assert outcome(record(frames, steps=steps), "no_pop_in", args).ok is True
    assert (
        outcome(record(frames, steps=steps), "no_pop_in", dict(args, settle_s=0.5)).ok
        is False
    )
