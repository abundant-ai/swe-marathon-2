"""Expectations: checks run over a recorded play, each reporting what it measured.

A play's "expect" list names checks with explicit arguments:

    {"id": "answers", "check": "dev_answers", "args": {...}, "rule": "AC-2",
     "says": "every command gets an answer of the contract's form"}

"rule" names the design document's rule and "says" what the expectation means in a
sentence; both are optional. "kind" is "assert" (the default) or "pre" (a precondition:
the situation the play sets up; when it does not hold, the play's other expectations say
nothing useful). Every check returns whether it held and the values it measured, so a
failure says why.

Besides a play's own expectations, every run is held to the standing ones in
standing(): the process stayed up and answered, the telemetry node was left alone,
entity ids are unique and never reused, and every event carries its fields and tick.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from .play import PlayRecord, RunRecord

# AC-13: the fields each event carries (every event also carries "tick").
EVENT_FIELDS = {
    "crime": ("type", "witnesses", "pos"),
    "alert_changed": ("level", "reason"),
    "police_dispatched": ("unit", "from"),
    "vehicle_entered": ("entity", "vehicle", "seat"),
    "vehicle_exited": ("entity", "vehicle", "seat"),
    "damaged": ("entity", "source", "amount", "health", "armour"),
    "died": ("entity", "cause"),
    "arrested": (),
    "respawned": ("entity", "poi"),
    "mission": ("id", "state", "stage"),
    "money_changed": ("amount", "reason", "balance"),
    "phone_message": ("from", "text"),
    "vehicle_exploded": ("vehicle",),
    "part_detached": ("vehicle", "debris"),
    "saved": ("slot",),
    "loaded": ("slot",),
    "map_transition": ("from", "to", "vehicle"),
    "teleport": ("entity", "reason"),
}
ENTITY_KINDS = (
    "player",
    "npc",
    "vehicle",
    "signal",
    "pickup",
    "marker",
    "debris",
    "light",
    "prop",
)


@dataclass
class Outcome:
    """The result of one expectation.

    Attributes:
        id: The expectation's id.
        check: The check's name.
        kind: "assert", "pre" or "standing".
        w: Weight (asserts only).
        ok: Whether it held (None when it could not be judged, which counts as not held).
        measured: The values the check measured.
        note: A short explanation when it did not hold.
        rule: The design document's rule id, when the expectation names one.
        says: What the expectation means, in a sentence, when it says.
    """

    id: str
    check: str
    kind: str
    w: float
    ok: bool | None
    measured: dict = field(default_factory=dict)
    note: str = ""
    rule: str = ""
    says: str = ""


Result = tuple[bool | None, dict, str]


def state_of(frame: dict | None) -> dict:
    """The state report in a frame, whether the game nests it under "state" or not."""
    st = (frame or {}).get("state")
    if not isinstance(st, dict):
        return {}
    inner = st.get("state")
    if isinstance(inner, dict):
        return inner
    return {k: v for k, v in st.items() if k != "ok"}


def dig(obj: object, path: str) -> object:
    """Follow a dotted path ("player.money") through nested dicts; None when absent."""
    for part in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def dev_answers_of(run: RunRecord, steps: list[int] | None) -> list[tuple[int, dict]]:
    """(step, answer) pairs of the DevConsole answers recorded in a run's frames."""
    out = []
    for fr in run.frames:
        if steps is not None and fr.get("_step") not in steps:
            continue
        for d in fr.get("dev") or []:
            out.append((fr.get("_step"), d))
    return out


def well_formed_answer(res: object) -> bool:
    """AC-2: {"ok": true, ...} or {"ok": false, "error": "<text>"}."""
    if not isinstance(res, dict) or not isinstance(res.get("ok"), bool):
        return False
    if res["ok"] is False:
        return isinstance(res.get("error"), str) and res["error"] != ""
    return True


def check_dev_answers(rec: PlayRecord, args: dict) -> Result:
    """Every DevConsole command (of the listed steps) got a well-formed answer."""
    run = rec.runs[int(args.get("run", 0))]
    steps = args.get("steps")
    answers = dev_answers_of(run, steps)
    bad = [
        {"step": s, "cmd": d.get("cmd"), "res": d.get("res")}
        for s, d in answers
        if not well_formed_answer(d.get("res"))
    ]
    measured = {
        "answers": len(answers),
        "malformed": bad[:5],
        "malformed_count": len(bad),
    }
    if not answers:
        return None, measured, "no answers were recorded"
    return not bad, measured, "" if not bad else f"{len(bad)} malformed answers"


def check_dev_result(rec: PlayRecord, args: dict) -> Result:
    """The answer to one command matches the given fields and substrings."""
    run = rec.runs[int(args.get("run", 0))]
    want_step, index = int(args["step"]), int(args.get("index", 0))
    answers = [d for s, d in dev_answers_of(run, None) if s == want_step]
    if index >= len(answers):
        return None, {"answers": len(answers)}, "the command was not answered"
    res = answers[index].get("res")
    measured = {"answer": res}
    if not isinstance(res, dict):
        return False, measured, "the answer is not an object"
    for k, v in (args.get("equals") or {}).items():
        if res.get(k) != v:
            return False, measured, f"{k} is {res.get(k)!r}, expected {v!r}"
    for k, sub in (args.get("contains") or {}).items():
        if not isinstance(res.get(k), str) or sub.lower() not in res[k].lower():
            return False, measured, f"{k} does not mention {sub!r}"
    return True, measured, ""


def check_replay_equal(rec: PlayRecord, args: dict) -> Result:
    """All runs of the play did the same thing tick for tick (equal replay hashes)."""
    from .trace import first_divergence

    hashes = [r.chain.replay_hash if r.chain else None for r in rec.runs]
    frames = [
        sum(r.chain.frames_per_segment[1:] or r.chain.frames_per_segment)
        if r.chain
        else 0
        for r in rec.runs
    ]
    measured: dict = {"replay_hashes": hashes, "frames": frames}
    if len(rec.runs) < 2 or any(r.error for r in rec.runs):
        return None, measured, "fewer than two complete runs"
    if len(set(hashes)) == 1:
        return True, measured, ""
    div = first_divergence(rec.runs[0].frames, rec.runs[1].frames)
    if div:
        measured["first_difference"] = div.__dict__
    return (
        False,
        measured,
        "the runs differ" + (f" at tick {div.tick_a}: {div.detail}" if div else ""),
    )


def population(frame: dict | None, kinds: tuple[str, ...]) -> list[list]:
    """[kind, archetype, x, y, z] of the entities of the given kinds, in id order (rounded to 0.1 mm)."""
    rows = []
    for e in (frame or {}).get("census") or []:
        if e.get("k") in kinds and isinstance(e.get("p"), list):
            rows.append(
                (
                    e.get("id"),
                    [e.get("k"), e.get("a"), *[round(float(c), 4) for c in e["p"]]],
                )
            )
    rows.sort(key=lambda r: r[0] if isinstance(r[0], (int, float)) else math.inf)
    return [r[1] for r in rows]


def frame_at_mark(run: RunRecord, mark: str) -> dict | None:
    """The latest frame when a mark was set, or None when the mark was not reached."""
    i = run.marks.get(mark)
    return run.frames[i] if i is not None and i < len(run.frames) else None


def check_same_start(rec: PlayRecord, args: dict) -> Result:
    """Equal variations give equal starting populations; different ones differ (AC-16)."""
    run = rec.runs[int(args.get("run", 0))]
    kinds = tuple(args.get("kinds", ("player", "npc", "vehicle")))
    a, b = args["same"]
    c, d = args["different"]
    pa, pb = (
        population(frame_at_mark(run, a), kinds),
        population(frame_at_mark(run, b), kinds),
    )
    pc, pd = (
        population(frame_at_mark(run, c), kinds),
        population(frame_at_mark(run, d), kinds),
    )
    measured = {
        "entities": [len(pa), len(pb), len(pc), len(pd)],
        "same_equal": pa == pb,
        "different_equal": pc == pd,
    }
    if not pa or not pc:
        return None, measured, "no population was observed"
    if pa != pb:
        return False, measured, "the same variation gave a different population"
    if pc == pd:
        return False, measured, "a different variation gave the same population"
    return True, measured, ""


def entity_pos(frame: dict | None, kind: str) -> list[float] | None:
    """Position of the first entity of a kind in a frame's census."""
    for e in (frame or {}).get("census") or []:
        if e.get("k") == kind and isinstance(e.get("p"), list):
            return [float(c) for c in e["p"]]
    return None


def check_moved(rec: PlayRecord, args: dict) -> Result:
    """An entity moved at least min_m between two marks that are `ticks` ticks apart."""
    run = rec.runs[int(args.get("run", 0))]
    fa, fb = frame_at_mark(run, args["from"]), frame_at_mark(run, args["to"])
    kind = args.get("kind", "player")
    pa, pb = entity_pos(fa, kind), entity_pos(fb, kind)
    measured: dict = {
        "ticks": (fb or {}).get("t", 0) - (fa or {}).get("t", 0) if fa and fb else None
    }
    if pa is None or pb is None:
        return None, measured, f"no {kind} at both marks"
    if args.get("horizontal"):
        pa, pb = [pa[0], pa[2]], [pb[0], pb[2]]
    dist = math.dist(pa, pb)
    measured["moved_m"] = round(dist, 6)
    if "ticks" in args and measured["ticks"] != args["ticks"]:
        return None, measured, f"the marks are {measured['ticks']} ticks apart"
    ok = dist >= float(args.get("min_m", 0.001))
    if "max_m" in args:
        ok = ok and dist <= float(args["max_m"])
    return ok, measured, "" if ok else f"moved {dist:.4f} m"


def clock_minutes(value: object) -> int | None:
    """Minutes after midnight of an "hh:mm" clock reading, or None for anything else."""
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return None
    hh, mm = value[:2], value[3:]
    if not (hh.isdigit() and mm.isdigit()) or int(hh) > 23 or int(mm) > 59:
        return None
    return int(hh) * 60 + int(mm)


def check_state_value(rec: PlayRecord, args: dict) -> Result:
    """A state-report value at a mark equals a value (or the id a command's answer gave,
    "equals_answer": {"step", "index"}), contains an item, or lies in [min, max].

    "as": "minutes" reads an "hh:mm" clock as minutes after midnight before comparing.
    """
    run = rec.runs[int(args.get("run", 0))]
    val = dig(state_of(frame_at_mark(run, args["mark"])), args["path"])
    measured = {"value": val}
    if val is None:
        return None, measured, f"no {args['path']} in the state report"
    if "equals_answer" in args:
        want = answer_id(run, args["equals_answer"])
        measured["expected"] = want
        ok = want is not None and val == want
        return (
            ok,
            measured,
            "" if ok else f"{args['path']} is {val!r}, the command gave {want!r}",
        )
    if "equals" in args:
        return (
            val == args["equals"],
            measured,
            "" if val == args["equals"] else f"{args['path']} is {val!r}",
        )
    if "contains" in args:
        ok = isinstance(val, list) and args["contains"] in val
        return ok, measured, "" if ok else f"{args['path']} lacks {args['contains']!r}"
    if args.get("as") == "minutes":
        val = clock_minutes(val)
        measured["minutes"] = val
        if val is None:
            return False, measured, f"{args['path']} is not an hh:mm clock"
    if not isinstance(val, (int, float)):
        return False, measured, f"{args['path']} is not a number"
    lo, hi = args.get("min", -math.inf), args.get("max", math.inf)
    ok = lo <= val <= hi
    return ok, measured, "" if ok else f"{args['path']} is {val}"


def check_event_seen(rec: PlayRecord, args: dict) -> Result:
    """Events with the given name (and the given field values, "where") arrived between
    two marks (or after one): at least min_count (default 1), at most max_count."""
    run = rec.runs[int(args.get("run", 0))]
    lo = run.marks.get(args["after"], len(run.frames)) if "after" in args else 0
    hi = (
        run.marks.get(args["before"], len(run.frames) - 1)
        if "before" in args
        else len(run.frames) - 1
    )
    where = args.get("where") or {}
    found = [
        e.get("d")
        for fr in run.frames[lo + 1 : hi + 1]
        for e in fr.get("events") or []
        if isinstance(e, dict)
        and e.get("n") == args["name"]
        and all(
            isinstance(e.get("d"), dict) and e["d"].get(k) == v
            for k, v in where.items()
        )
    ]
    n = len(found)
    low, high = int(args.get("min_count", 1)), args.get("max_count")
    ok = n >= low and (high is None or n <= int(high))
    measured = {"count": n, "first": found[0] if found else None}
    if ok:
        return True, measured, ""
    what = args["name"] + (f" {where}" if where else "")
    return False, measured, f"{n} {what} events" if n else f"no {what} event"


def answer_id(run: RunRecord, ref: dict) -> object:
    """The "id" field of the answer to the command at {"step", "index"} (None when absent)."""
    answers = [d for s, d in dev_answers_of(run, None) if s == ref.get("step")]
    i = int(ref.get("index", 0))
    res = answers[i].get("res") if i < len(answers) else None
    return res.get("id") if isinstance(res, dict) else None


def check_entity_near(rec: PlayRecord, args: dict) -> Result:
    """At a mark, an entity of a kind (and archetype, or the id a command's answer gave,
    "id_from": {"step", "index"}) stands within max_m of a point (horizontally by default)."""
    run = rec.runs[int(args.get("run", 0))]
    frame = frame_at_mark(run, args["mark"])
    want_id = None
    measured: dict = {}
    if "id_from" in args:
        want_id = answer_id(run, args["id_from"])
        measured["id"] = want_id
        if not isinstance(want_id, int) or isinstance(want_id, bool):
            return False, measured, "the command's answer gave no entity id"
    point = [float(c) for c in args["p"]]
    flat = args.get("horizontal", True)
    best = None
    for e in (frame or {}).get("census") or []:
        if e.get("k") != args.get("kind", e.get("k")):
            continue
        if "archetype" in args and e.get("a") != args["archetype"]:
            continue
        if want_id is not None and e.get("id") != want_id:
            continue
        if not isinstance(e.get("p"), list):
            continue
        p = [float(c) for c in e["p"]]
        d = (
            math.dist([p[0], p[2]], [point[0], point[2]])
            if flat
            else math.dist(p, point)
        )
        best = d if best is None else min(best, d)
    measured["distance_m"] = None if best is None else round(best, 4)
    if frame is None:
        return None, measured, "the mark was not reached"
    if best is None:
        return False, measured, "no such entity in the census"
    ok = best <= float(args["max_m"])
    return ok, measured, "" if ok else f"the nearest is {best:.3f} m away"


# AC-12: the state report's fields, with the values other rules give them.
WEATHERS = ("clear", "overcast", "rain", "fog")
MISSIONS = ("D1", "C1", "R1", "D2", "C2", "R2", "H1", "H2")
MISSION_STATES = ("locked", "available", "active", "passed", "failed")
GARAGES = ("garage_downtown", "garage_port", "garage_hills")
ROLES = ("solo", "server", "client")


def _is_int(v: object) -> bool:
    return (
        isinstance(v, int)
        and not isinstance(v, bool)
        or (isinstance(v, float) and v.is_integer())
    )


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def state_problems(st: dict, player: bool) -> list[str]:
    """What is missing or malformed in a state report (AC-12), in plain words."""
    probs = []

    def need(ok: bool, what: str) -> None:
        if not ok:
            probs.append(what)

    need(_is_int(st.get("tick")), "tick is not a whole number")
    need(isinstance(st.get("map"), str), "map is not a name")
    need(clock_minutes(st.get("clock")) is not None, "clock is not hh:mm")
    need(st.get("weather") in WEATHERS, "weather is not clear, overcast, rain or fog")
    need(_is_int(st.get("variation")), "variation is not a whole number")
    pl = st.get("player")
    if player or pl is not None:
        if not isinstance(pl, dict):
            probs.append("player is missing")
        else:
            for k in ("id", "money"):
                need(_is_int(pl.get(k)), f"player.{k} is not a whole number")
            for k in ("health", "armour"):
                need(_is_num(pl.get(k)), f"player.{k} is not a number")
            need(
                _is_int(pl.get("alert")) and 0 <= pl.get("alert", -1) <= 5,
                "player.alert is not 0-5",
            )
            for k in ("lead", "weapon", "outfit"):
                need(isinstance(pl.get(k), str), f"player.{k} is not a name")
            for k in ("weapons", "outfits", "leads_unlocked"):
                need(isinstance(pl.get(k), list), f"player.{k} is not a list")
            ammo = pl.get("ammo")
            need(
                isinstance(ammo, dict)
                and _is_int(ammo.get("magazine"))
                and _is_int(ammo.get("reserve")),
                "player.ammo is not {magazine, reserve}",
            )
            aim = pl.get("aim", "missing")
            need(
                aim is None or (isinstance(aim, list) and len(aim) == 3),
                "player.aim is not a point or null",
            )
            need(isinstance(pl.get("cover"), bool), "player.cover is not true or false")
            for k in ("vehicle", "seat"):
                need(
                    k in pl and (pl[k] is None or _is_int(pl[k])),
                    f"player.{k} is not an id or null",
                )
    ms = st.get("missions")
    if not isinstance(ms, dict):
        probs.append("missions is missing")
    else:
        for m in MISSIONS:
            row = ms.get(m)
            need(
                isinstance(row, dict)
                and row.get("state") in MISSION_STATES
                and "stage" in row,
                f"missions.{m} is not {{state, stage}}",
            )
    gs = st.get("garages")
    if not isinstance(gs, dict):
        probs.append("garages is missing")
    else:
        for g in GARAGES:
            need(isinstance(gs.get(g), list), f"garages.{g} is not a list")
    ui = st.get("ui")
    need(
        isinstance(ui, dict)
        and all(isinstance(ui.get(k), bool) for k in ("phone", "map", "paused"))
        and "menu" in ui,
        "ui is not {phone, map, paused, menu}",
    )
    net = st.get("network")
    need(
        isinstance(net, dict)
        and net.get("role") in ROLES
        and _is_int(net.get("peers"))
        and _is_int(net.get("id")),
        "network is not {role, peers, id}",
    )
    return probs


def check_state_fields(rec: PlayRecord, args: dict) -> Result:
    """The state report at a mark has every field of AC-12 in its form."""
    run = rec.runs[int(args.get("run", 0))]
    frame = frame_at_mark(run, args["mark"])
    st = state_of(frame)
    if not st:
        return None if frame is None else False, {}, "no state report"
    probs = state_problems(st, bool(args.get("player", True)))
    return (
        not probs,
        {"problems": probs[:8], "count": len(probs)},
        probs[0] if probs else "",
    )


def check_heartbeat(rec: PlayRecord, args: dict) -> Result:
    """Real time: a heartbeat every tick, no silence longer than allowed."""
    run = rec.runs[int(args.get("run", 0))]
    hb = run.heartbeat or {}
    measured = {k: hb.get(k) for k in ("count", "skipped", "max_gap_s", "gaps")}
    if not hb.get("count"):
        return False, measured, "no heartbeat"
    limit = float(args.get("max_gap_s", 1.0))
    ok = hb.get("skipped") == 0 and float(hb.get("max_gap_s", 0)) <= limit
    return ok, measured, "" if ok else "heartbeat missed"


CHECKS: dict[str, Callable[[PlayRecord, dict], Result]] = {
    "dev_answers": check_dev_answers,
    "dev_result": check_dev_result,
    "replay_equal": check_replay_equal,
    "same_start": check_same_start,
    "moved": check_moved,
    "state_value": check_state_value,
    "event_seen": check_event_seen,
    "heartbeat": check_heartbeat,
    "entity_near": check_entity_near,
    "state_fields": check_state_fields,
}


def check_play(rec: PlayRecord) -> list[Outcome]:
    """Check a play's own expectations over its record.

    A check that raises (malformed values from the game) does not hold; the error is
    its note.

    Returns:
        One Outcome per expectation, in the play's order.
    """
    out = []
    for e in rec.play.expect:
        fn = CHECKS.get(e["check"])
        kind = e.get("kind", "assert")
        w = float(e.get("w", 1.0))
        rule, says = str(e.get("rule", "")), str(e.get("says", ""))
        if fn is None:
            out.append(
                Outcome(
                    e["id"], e["check"], kind, w, None, {}, "unknown check", rule, says
                )
            )
            continue
        try:
            ok, measured, note = fn(rec, e.get("args") or {})
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            ok, measured, note = None, {}, f"could not be judged: {exc!r}"
        out.append(
            Outcome(e["id"], e["check"], kind, w, ok, measured, note, rule, says)
        )
    return out


# ---------------------------------------------------------------- standing expectations
FATAL_PROCESS = ("closed", "limit", "stalled", "no_link", "play_time")
FATAL_TELEMETRY = ("gone", "out_of_step", "unsigned", "bad_message")


LIMIT_VIOLATIONS = ("memory", "disk", "cpu", "file_size", "wall")


def standing_process(rec: PlayRecord) -> Outcome:
    """The game process stayed up, answered and kept within its limits (PF-8, PF-7)."""
    errors = [r.error for r in rec.runs if r.error and r.error["kind"] in FATAL_PROCESS]
    for r in rec.runs:
        for ex in r.exits:
            if ex.get("violation") in LIMIT_VIOLATIONS and not any(
                e is r.error for e in errors
            ):
                errors.append(
                    {
                        "kind": "limit",
                        "message": f"passed its {ex['violation']} limit",
                        "step": None,
                    }
                )
    measured = {"errors": errors, "exits": [r.exits for r in rec.runs]}
    note = "" if not errors else f"{errors[0]['kind']}: {errors[0]['message']}"
    return Outcome(
        "process",
        "standing",
        "standing",
        0.0,
        not errors,
        measured,
        note,
        "PF-8",
        "the game keeps running and answering, within 1.5 GB of memory (PF-7)",
    )


def standing_telemetry(rec: PlayRecord) -> Outcome:
    """The telemetry node was left alone (AC-18): no removal, no skipped ticks."""
    errors = [
        r.error for r in rec.runs if r.error and r.error["kind"] in FATAL_TELEMETRY
    ]
    hb_bad = []
    for r in rec.runs:
        hb = r.heartbeat
        if hb is not None and (
            not hb.get("count")
            or hb.get("skipped")
            or float(hb.get("max_gap_s", 0))
            > float(rec.play.limits.get("heartbeat_gap_s", 1.0))
        ):
            hb_bad.append(
                {
                    "run": r.index,
                    **{k: hb.get(k) for k in ("count", "skipped", "max_gap_s")},
                }
            )
    ok = not errors and not hb_bad
    note = errors[0]["message"] if errors else ("heartbeat missed" if hb_bad else "")
    return Outcome(
        "telemetry",
        "standing",
        "standing",
        0.0,
        ok,
        {"errors": errors, "heartbeat": hb_bad},
        note,
        "AC-18",
        "QA's telemetry node keeps running every tick",
    )


def standing_registry(rec: PlayRecord) -> Outcome:
    """Entity ids are unique, never reused, with their metadata (AC-4)."""
    problems: list[str] = []
    for r in rec.runs:
        retired: set = set()
        live_prev: dict = {}
        proc_prev = None
        for fr in r.frames:
            if fr.get("_proc") != proc_prev:
                retired, live_prev, proc_prev = set(), {}, fr.get("_proc")
            if "census" not in fr:
                continue
            live: dict = {}
            for e in fr["census"]:
                eid = e.get("id")
                if not isinstance(eid, int) or isinstance(eid, bool):
                    problems.append(
                        f"tick {fr.get('t')}: an entity without an integer entity_id"
                    )
                    continue
                if eid in live:
                    problems.append(f"tick {fr.get('t')}: id {eid} used twice")
                if e.get("k") not in ENTITY_KINDS:
                    problems.append(
                        f"tick {fr.get('t')}: id {eid} has kind {e.get('k')!r}"
                    )
                if not isinstance(e.get("a"), str) or not isinstance(e.get("f"), str):
                    problems.append(
                        f"tick {fr.get('t')}: id {eid} lacks archetype or faction"
                    )
                if eid in retired:
                    problems.append(f"tick {fr.get('t')}: id {eid} reused")
                live[eid] = e.get("k")
            retired |= set(live_prev) - set(live)
            live_prev = live
            if len(problems) > 20:
                break
    return Outcome(
        "registry",
        "standing",
        "standing",
        0.0,
        not problems,
        {"problems": problems[:10], "count": len(problems)},
        problems[0] if problems else "",
        "AC-4",
        "entities carry their metadata; ids are whole numbers, unique, never reused",
    )


def standing_events(rec: PlayRecord) -> Outcome:
    """Every event carries its fields and a tick (AC-13)."""
    problems: list[str] = []
    for r in rec.runs:
        for fr in r.frames:
            for e in fr.get("events") or []:
                if not isinstance(e, dict):
                    problems.append("an event that is not an object")
                    continue
                d = e.get("d")
                name = e.get("n")
                if not isinstance(d, dict):
                    problems.append(f"event {name!r} at tick {e.get('t')}: no data")
                    continue
                if not isinstance(d.get("tick"), (int, float)) or isinstance(
                    d.get("tick"), bool
                ):
                    problems.append(f"event {name!r} at tick {e.get('t')}: no tick")
                for f in EVENT_FIELDS.get(name, ()):
                    if f not in d:
                        problems.append(f"event {name!r} at tick {e.get('t')}: no {f}")
    return Outcome(
        "events",
        "standing",
        "standing",
        0.0,
        not problems,
        {"problems": problems[:10], "count": len(problems)},
        problems[0] if problems else "",
        "AC-13",
        "every event carries its fields and its tick",
    )


def standing(rec: PlayRecord) -> list[Outcome]:
    """The standing expectations every play is held to."""
    return [
        standing_process(rec),
        standing_telemetry(rec),
        standing_registry(rec),
        standing_events(rec),
    ]
