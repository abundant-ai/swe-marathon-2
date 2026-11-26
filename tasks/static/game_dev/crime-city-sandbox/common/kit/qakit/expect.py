"""Expectations: checks run over a recorded play, each reporting what it measured.

A play's "expect" list names checks with explicit arguments:

    {"id": "answers", "check": "dev_answers", "args": {...}, "w": 1.0, "kind": "assert"}

"kind" is "assert" (weighted by "w") or "pre" (a precondition: the situation the play
sets up; when it does not hold, the play's other expectations say nothing useful).
Every check returns whether it held and the values it measured, so a failure says why.

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
    """

    id: str
    check: str
    kind: str
    w: float
    ok: bool | None
    measured: dict = field(default_factory=dict)
    note: str = ""


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
    dist = math.dist(pa, pb)
    measured["moved_m"] = round(dist, 6)
    if "ticks" in args and measured["ticks"] != args["ticks"]:
        return None, measured, f"the marks are {measured['ticks']} ticks apart"
    ok = dist >= float(args.get("min_m", 0.001))
    if "max_m" in args:
        ok = ok and dist <= float(args["max_m"])
    return ok, measured, "" if ok else f"moved {dist:.4f} m"


def check_state_value(rec: PlayRecord, args: dict) -> Result:
    """A state-report value at a mark equals a value or lies in [min, max]."""
    run = rec.runs[int(args.get("run", 0))]
    val = dig(state_of(frame_at_mark(run, args["mark"])), args["path"])
    measured = {"value": val}
    if val is None:
        return None, measured, f"no {args['path']} in the state report"
    if "equals" in args:
        return (
            val == args["equals"],
            measured,
            "" if val == args["equals"] else f"{args['path']} is {val!r}",
        )
    if not isinstance(val, (int, float)):
        return False, measured, f"{args['path']} is not a number"
    lo, hi = args.get("min", -math.inf), args.get("max", math.inf)
    ok = lo <= val <= hi
    return ok, measured, "" if ok else f"{args['path']} is {val}"


def check_event_seen(rec: PlayRecord, args: dict) -> Result:
    """An event with the given name arrived between two marks (or after one)."""
    run = rec.runs[int(args.get("run", 0))]
    lo = run.marks.get(args["after"], len(run.frames)) if "after" in args else 0
    hi = (
        run.marks.get(args["before"], len(run.frames) - 1)
        if "before" in args
        else len(run.frames) - 1
    )
    n = sum(
        1
        for fr in run.frames[lo + 1 : hi + 1]
        for e in fr.get("events") or []
        if isinstance(e, dict) and e.get("n") == args["name"]
    )
    ok = n >= int(args.get("min_count", 1))
    return ok, {"count": n}, "" if ok else f"no {args['name']} event"


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
        if fn is None:
            out.append(Outcome(e["id"], e["check"], kind, w, None, {}, "unknown check"))
            continue
        try:
            ok, measured, note = fn(rec, e.get("args") or {})
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            ok, measured, note = None, {}, f"could not be judged: {exc!r}"
        out.append(Outcome(e["id"], e["check"], kind, w, ok, measured, note))
    return out


# ---------------------------------------------------------------- standing expectations
FATAL_PROCESS = ("closed", "limit", "stalled", "no_link", "play_time")
FATAL_TELEMETRY = ("gone", "out_of_step", "unsigned", "bad_message")


def standing_process(rec: PlayRecord) -> Outcome:
    """The game process stayed up and answered for the whole play (PF-8, PF-7)."""
    errors = [r.error for r in rec.runs if r.error and r.error["kind"] in FATAL_PROCESS]
    measured = {"errors": errors, "exits": [r.exits for r in rec.runs]}
    note = "" if not errors else f"{errors[0]['kind']}: {errors[0]['message']}"
    return Outcome("process", "standing", "standing", 0.0, not errors, measured, note)


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
    )


def standing(rec: PlayRecord) -> list[Outcome]:
    """The standing expectations every play is held to."""
    return [
        standing_process(rec),
        standing_telemetry(rec),
        standing_registry(rec),
        standing_events(rec),
    ]
