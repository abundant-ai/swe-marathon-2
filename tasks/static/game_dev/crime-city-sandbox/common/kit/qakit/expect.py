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

import itertools
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
        ok: Whether it held (None when it could not be measured, which counts as not held).
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


def state_refused(frame: dict | None) -> str:
    """Why the state command gave no report in a frame ("" when it gave one)."""
    st = (frame or {}).get("state")
    if isinstance(st, dict) and st.get("ok") is False:
        return f"the state command answered: {st.get('error', 'no report')}"
    if frame is not None and "state" in frame and not isinstance(st, dict):
        return "the state command gave no answer"
    return ""


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
    frame = frame_at_mark(run, args["mark"])
    val = dig(state_of(frame), args["path"])
    measured = {"value": val}
    if val is None:
        return (
            None,
            measured,
            state_refused(frame) or f"no {args['path']} in the state report",
        )
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
    refused = state_refused(frame)
    if not st or refused:
        return None if frame is None else False, {}, refused or "no state report"
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


# ---------------------------------------------------------------- rays cast by QA
def step_queries(rec: PlayRecord, step: int) -> dict[str, dict]:
    """The queries of a query step, by id."""
    arg = rec.play.steps[step].get("query") if 0 <= step < len(rec.play.steps) else None
    return {str(q.get("id")): q for q in arg or [] if isinstance(q, dict)}


def step_answers(run: RunRecord, step: int) -> dict | None:
    """The answers ("q") recorded for a query step, or None when it was not answered."""
    i = run.step_frame.get(step)
    if i is None or i >= len(run.frames):
        return None
    q = run.frames[i].get("q")
    return q if isinstance(q, dict) else None


def ray_answers(
    rec: PlayRecord, run: RunRecord, args: dict
) -> tuple[list | None, list]:
    """The answers a ray expectation reads, with what each ray was cast at.

    args["query"] names a "down" query of step args["step"] (one answer per point), or
    args["rays"] = {"prefix": p, "count": n} names its "ray" queries p0 .. p(n-1).

    Returns:
        (answers, casts): one answer per ray (None where the game gave none) and, per
        ray, its point [x, z] or its segment [from, to]. answers is None when the step
        was not answered.
    """
    step = int(args["step"])
    got = step_answers(run, step)
    if got is None:
        return None, []
    asked = step_queries(rec, step)
    if "query" in args:
        qid = str(args["query"])
        pts = (asked.get(qid) or {}).get("points") or []
        res = got.get(qid)
        if not isinstance(res, list):
            return [None] * len(pts), list(pts)
        return list(res) + [None] * (len(pts) - len(res)), list(pts)
    prefix, count = str(args["rays"]["prefix"]), int(args["rays"]["count"])
    ids = [f"{prefix}{k}" for k in range(count)]
    casts = [[asked.get(i, {}).get("from"), asked.get(i, {}).get("to")] for i in ids]
    return [got.get(i) for i in ids], casts


def ray_problem(answer: object, args: dict, y: float | None) -> str:
    """Why one ray's answer is off the plan ("" when it is not)."""
    if not isinstance(answer, dict):
        return "the ray was not answered"
    hit = answer.get("hit") is True
    if args.get("clear"):
        if not hit:
            return ""
        return (
            f"hit {answer.get('surface', 'an untagged surface')} at {answer.get('p')}"
        )
    if not hit:
        return "" if args.get("hit_optional") else "the ray hit nothing"
    surface = answer.get("surface")
    want = " or ".join(repr(t) for t in args.get("tags", []))
    if "tags" in args and surface not in args["tags"]:
        got = repr(surface) if surface is not None else "an untagged surface"
        return f"hit {got} at {answer.get('p')}, expected {want}"
    if surface in (args.get("not_tags") or ()):
        return f"hit {surface!r} at {answer.get('p')}"
    if y is not None and "tol_m" in args:
        p = answer.get("p")
        hy = float(p[1]) if isinstance(p, list) and len(p) == 3 else None
        if hy is None or abs(hy - y) > float(args["tol_m"]):
            return (
                f"hit {surface!r} at height {hy}, expected {y} within {args['tol_m']} m"
            )
    return ""


def groups_of(args: dict, n: int) -> list[tuple[str, int, int]] | None:
    """(label, start, end) of each group of consecutive rays; None when they do not add up."""
    spec = args.get("groups") or [["all", n]]
    out, start = [], 0
    for label, count in spec:
        out.append((str(label), start, start + int(count)))
        start += int(count)
    return out if start == n else None


def check_rays(rec: PlayRecord, args: dict) -> Result:
    """Rays QA cast at one step hit what the plan puts there.

    Each ray meets the expectation when it hits a surface tagged as listed ("tags"), not
    one of "not_tags", at the expected height ("y", one number or one per ray) within
    "tol_m"; with "hit_optional", a ray that hits nothing meets it too; with "clear", a ray
    meets it only when it hits nothing. Rays come in groups (consecutive counts,
    "groups"); the expectation holds when in every group at least "min_share" (default
    all) of the rays meet it.
    """
    run = rec.runs[int(args.get("run", 0))]
    answers, casts = ray_answers(rec, run, args)
    if answers is None:
        return None, {}, "the rays were not answered"
    n = len(answers)
    groups = groups_of(args, n)
    if not n or groups is None:
        return None, {"rays": n}, "the expectation names no rays it can read"
    ys = args.get("y")
    min_share = float(args.get("min_share", 1.0))
    why = [
        ray_problem(a, args, float(ys[k]) if isinstance(ys, list) else ys)
        for k, a in enumerate(answers)
    ]
    short, misses = [], []
    for label, a, b in groups:
        met = sum(1 for w in why[a:b] if not w)
        if b > a and met / (b - a) < min_share:
            short.append({"group": label, "share": round(met / (b - a), 4)})
    for k, w in enumerate(why):
        if w and len(misses) < 5:
            misses.append({"at": casts[k] if k < len(casts) else None, "why": w})
    met_all = sum(1 for w in why if not w)
    measured = {
        "rays": n,
        "as_planned": met_all,
        "share": round(met_all / n, 4),
        "groups_below_share": short[:5],
        "groups_below_share_count": len(short),
        "first_off_plan": misses,
    }
    if not short:
        return True, measured, ""
    names = ", ".join(f"{s['group']} ({s['share']:.0%})" for s in short[:3])
    first = misses[0] if misses else {}
    return (
        False,
        measured,
        (
            f"under {min_share:.0%} of the rays as planned in {len(short)} groups ({names}); "
            f"first at {first.get('at')}: {first.get('why')}"
        ),
    )


def check_clear_run(rec: PlayRecord, args: dict) -> Result:
    """An opening is at least min_width_m wide.

    The rays of each group cross the opening side by side, spacing_m apart, in order,
    each standing for a strip spacing_m wide; the widest run of k consecutive rays that
    hit nothing is k * spacing_m wide and must be at least min_width_m (so a measured
    width is within one spacing of the true one).
    """
    run = rec.runs[int(args.get("run", 0))]
    answers, _ = ray_answers(rec, run, args)
    if answers is None:
        return None, {}, "the rays were not answered"
    groups = groups_of(args, len(answers))
    if not answers or groups is None:
        return None, {"rays": len(answers)}, "the expectation names no rays it can read"
    spacing, need = float(args["spacing_m"]), float(args["min_width_m"])
    widths, narrow = {}, []
    for label, a, b in groups:
        best = cur = 0
        for ans in answers[a:b]:
            clear = isinstance(ans, dict) and ans.get("hit") is False
            cur = cur + 1 if clear else 0
            best = max(best, cur)
        widths[label] = round(best * spacing, 3)
        if widths[label] < need - 1e-9:
            narrow.append(label)
    measured = {"clear_width_m": widths}
    if narrow:
        return False, measured, f"narrower than {need} m: {', '.join(narrow[:4])}"
    return True, measured, ""


def check_surface_tags(rec: PlayRecord, args: dict) -> Result:
    """Every ray that hit something, of every query of one step, hit a collider whose
    "surface" metadata is one of the listed tags (AC-8)."""
    run = rec.runs[int(args.get("run", 0))]
    got = step_answers(run, int(args["step"]))
    if got is None:
        return None, {}, "the rays were not answered"
    allowed = set(args["allowed"])
    hits, odd = 0, {}
    for ans in got.values():
        for a in ans if isinstance(ans, list) else [ans]:
            if isinstance(a, dict) and a.get("hit") is True:
                hits += 1
                tag = a.get("surface")
                if tag not in allowed:
                    key = "untagged" if tag is None else str(tag)
                    odd[key] = odd.get(key, 0) + 1
    measured = {"hits": hits, "other_tags": odd}
    if not hits:
        return None, measured, "no ray hit anything"
    if odd:
        return False, measured, f"surfaces outside the list: {sorted(odd)[:5]}"
    return True, measured, ""


def check_none_listed(rec: PlayRecord, args: dict) -> Result:
    """A query that lists things (such as "unregistered") answered with an empty list."""
    run = rec.runs[int(args.get("run", 0))]
    got = step_answers(run, int(args["step"]))
    if got is None:
        return None, {}, "the query was not answered"
    res = got.get(str(args["query"]))
    if not isinstance(res, list):
        return False, {"answer": res}, "the query gave no list"
    return (
        not res,
        {"listed": res[:10], "count": len(res)},
        ("" if not res else f"{len(res)} listed: {res[:3]}"),
    )


def check_skeleton(rec: PlayRecord, args: dict) -> Result:
    """A "skeleton" query found exactly one Skeleton3D with the listed bone names and at
    least min_bound_meshes skinned meshes bound to it (AC-5)."""
    run = rec.runs[int(args.get("run", 0))]
    got = step_answers(run, int(args["step"]))
    if got is None:
        return None, {}, "the query was not answered"
    res = got.get(str(args["query"]))
    if not isinstance(res, dict) or res.get("ok") is not True:
        return False, {"answer": res}, "no entity with the id the query names"
    bones = set(res.get("bones") or [])
    missing = [b for b in args.get("bones", []) if b not in bones]
    measured = {
        "skeletons": res.get("skeletons"),
        "bones": len(bones),
        "missing_bones": missing[:10],
        "bound_meshes": res.get("bound_meshes"),
    }
    if res.get("skeletons") != 1:
        return (
            False,
            measured,
            f"the entity has {res.get('skeletons')} Skeleton3D nodes, not 1",
        )
    if missing:
        return False, measured, f"bones missing: {', '.join(missing[:6])}"
    need = int(args.get("min_bound_meshes", 1))
    if int(res.get("bound_meshes") or 0) < need:
        return (
            False,
            measured,
            f"fewer than {need} skinned meshes are bound to the skeleton",
        )
    return True, measured, ""


# ---------------------------------------------------------------- people and the camera
TICK_HZ = 60


def entity_of(frame: dict | None, args: dict) -> dict | None:
    """The census row of the entity an expectation names: by "kind" (and "archetype")."""
    for e in (frame or {}).get("census") or []:
        if e.get("k") != args.get("kind", "player"):
            continue
        if "archetype" in args and e.get("a") != args["archetype"]:
            continue
        return e
    return None


def bone_of(frame: dict | None, eid: object, bone: str) -> list[float] | None:
    """A bone's world position in a frame's bone observation, or None."""
    b = ((frame or {}).get("bones") or {}).get(str(eid)) or {}
    p = b.get(bone)
    return [float(c) for c in p] if isinstance(p, list) and len(p) == 3 else None


def point_of(frame: dict | None, args: dict) -> list[float] | None:
    """The entity's bone (args["bone"]) or, without one, its position, in a frame."""
    e = entity_of(frame, args)
    if e is None:
        return None
    if args.get("bone"):
        return bone_of(frame, e.get("id"), args["bone"])
    p = e.get("p")
    return [float(c) for c in p] if isinstance(p, list) else None


def frames_between(run: RunRecord, a: str, b: str) -> list[dict]:
    """The frames from mark a to mark b, both included (empty when a mark is missing)."""
    i, j = run.marks.get(a), run.marks.get(b)
    if i is None or j is None:
        return []
    return run.frames[i : j + 1]


def check_pace(rec: PlayRecord, args: dict) -> Result:
    """The horizontal speed of an entity's bone (or position) between two marks lies in
    [min_mps, max_mps]: horizontal distance over the ticks between them, at 60 per second."""
    run = rec.runs[int(args.get("run", 0))]
    fa, fb = frame_at_mark(run, args["from"]), frame_at_mark(run, args["to"])
    pa, pb = point_of(fa, args), point_of(fb, args)
    if fa is None or fb is None or pa is None or pb is None:
        what = args.get("bone") or "position"
        return None, {}, f"no {what} at both marks"
    ticks = int(fb.get("t", 0)) - int(fa.get("t", 0))
    if ticks <= 0:
        return None, {"ticks": ticks}, "the marks are not in order"
    speed = math.dist([pa[0], pa[2]], [pb[0], pb[2]]) * TICK_HZ / ticks
    measured = {"speed_mps": round(speed, 4), "ticks": ticks}
    lo, hi = float(args.get("min_mps", 0.0)), float(args.get("max_mps", math.inf))
    ok = lo <= speed <= hi
    return ok, measured, "" if ok else f"{speed:.3f} m/s, expected {lo}-{hi}"


def quantile(values: list[float], q: float) -> float:
    """The q-quantile of values (linear between neighbours)."""
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def stances(rows: list[tuple[int, list[float]]], contact_m: float) -> list[list]:
    """Runs of consecutive samples with the toe within contact_m of its lowest height."""
    floor = min(p[1] for _, p in rows) + contact_m
    runs, cur = [], []
    for t, p in rows:
        if p[1] <= floor:
            cur.append((t, p))
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


def check_feet(rec: PlayRecord, args: dict) -> Result:
    """Planted feet between two marks (FT-2), from the LeftToes and RightToes bones.

    A stance is a run of samples with the toe within contact_m (default 0.04) of its
    lowest height in the window; a step is the start of a stance that the window did not
    begin in. Slide is the toe's horizontal speed over the middle 60% of each stance.
    Holds when at least min_steps steps were taken, at least min_alternation of
    consecutive steps change foot, and the slide's p95 is at most max_slide_mps.
    """
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    contact = float(args.get("contact_m", 0.04))
    sides: dict[str, list] = {"left": [], "right": []}
    for fr in frames:
        e = entity_of(fr, args)
        if e is None:
            continue
        for side, bone in (("left", "LeftToes"), ("right", "RightToes")):
            p = bone_of(fr, e.get("id"), bone)
            if p is not None:
                sides[side].append((int(fr.get("t", 0)), p))
    if min(len(v) for v in sides.values()) < 10:
        return None, {"samples": len(frames)}, "the toes were not observed"
    steps, slides = [], []
    for side, rows in sides.items():
        runs = stances(rows, contact)
        for k, r in enumerate(runs):
            if k > 0 or r[0][0] != rows[0][0]:
                steps.append((r[0][0], side))
            n = len(r)
            mid = r[int(n * 0.2) : max(int(n * 0.2) + 2, math.ceil(n * 0.8))]
            for (ta, pa), (tb, pb) in itertools.pairwise(mid):
                if tb > ta:
                    d = math.dist([pa[0], pa[2]], [pb[0], pb[2]])
                    slides.append(d * TICK_HZ / (tb - ta))
    steps.sort()
    changes = [1 if a[1] != b[1] else 0 for a, b in itertools.pairwise(steps)]
    alternation = sum(changes) / len(changes) if changes else 0.0
    slide = quantile(slides, 0.95) if slides else None
    measured = {
        "steps": len(steps),
        "alternation": round(alternation, 3),
        "slide_p95_mps": None if slide is None else round(slide, 3),
    }
    need = int(args.get("min_steps", 4))
    if len(steps) < need:
        return (
            False,
            measured,
            (
                f"{len(steps)} steps, at least {need} expected (a step is a toe coming down to "
                f"within {contact} m of its lowest height after being above it)"
            ),
        )
    if alternation < float(args.get("min_alternation", 0.9)):
        return False, measured, f"steps alternate feet {alternation:.0%} of the time"
    if slide is None:
        return False, measured, "no planted samples in the middle of any stance"
    if slide > float(args["max_slide_mps"]):
        return (
            False,
            measured,
            f"planted toes slide at {slide:.3f} m/s (p95), at most {args['max_slide_mps']}",
        )
    return True, measured, ""


def camera_axes(cam: dict) -> tuple[list[float], list[float], list[float]]:
    """(forward, right, up) of a camera from its back axis, for a camera without roll."""
    bz = [float(c) for c in cam["bz"]]
    fwd = [-c for c in bz]
    rx, rz = bz[2], -bz[0]  # world up x back
    norm = math.hypot(rx, rz) or 1.0
    right = [rx / norm, 0.0, rz / norm]
    up = [
        bz[1] * right[2] - bz[2] * right[1],
        bz[2] * right[0] - bz[0] * right[2],
        bz[0] * right[1] - bz[1] * right[0],
    ]
    return fwd, right, up


def view_offset(cam: dict, p: list[float], aspect: float) -> tuple[float, float] | None:
    """Where a point appears in a camera's view: (x, y) from -1 to 1 across the width and
    the height (0 is the middle), with the field of view taken as vertical; None when the
    point is behind the camera."""
    fwd, right, up = camera_axes(cam)
    d = [p[k] - float(cam["p"][k]) for k in range(3)]
    depth = sum(d[k] * fwd[k] for k in range(3))
    if depth <= 0:
        return None
    half = math.tan(math.radians(float(cam["fov"])) / 2.0)
    x = sum(d[k] * right[k] for k in range(3)) / depth / (half * aspect)
    y = sum(d[k] * up[k] for k in range(3)) / depth / half
    return x, y


def check_camera_frame(rec: PlayRecord, args: dict) -> Result:
    """Between two marks the camera stays min_m-max_m from the player's Head bone and the
    player's frame bone (default Hips) inside the middle `middle` (default 0.4) of the view,
    by width and height, for a view of the given aspect (width / height). (CM-1)"""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    aspect, middle = float(args.get("aspect", 16 / 9)), float(args.get("middle", 0.4))
    dists, worst, n = [], 0.0, 0
    far = near = off_tick = None
    for fr in frames:
        cam, e = fr.get("camera"), entity_of(fr, args)
        if not isinstance(cam, dict) or e is None:
            continue
        head = bone_of(fr, e.get("id"), "Head")
        body = bone_of(fr, e.get("id"), args.get("frame_bone", "Hips"))
        if head is None or body is None:
            continue
        n += 1
        d = math.dist(head, [float(c) for c in cam["p"]])
        dists.append(d)
        if far is None or d > far[0]:
            far = (d, fr.get("t"))
        if near is None or d < near[0]:
            near = (d, fr.get("t"))
        off = view_offset(cam, body, aspect)
        o = 2.0 if off is None else max(abs(off[0]), abs(off[1]))
        if o > worst:
            worst, off_tick = o, fr.get("t")
    if not n:
        return None, {}, "the camera and the player's bones were not observed"
    measured = {
        "frames": n,
        "head_distance_m": [round(min(dists), 3), round(max(dists), 3)],
        "farthest_from_middle": round(worst, 3),
    }
    lo, hi = float(args["min_m"]), float(args["max_m"])
    if far[0] > hi:
        return (
            False,
            measured,
            f"at tick {far[1]} the camera is {far[0]:.2f} m from the head (at most {hi})",
        )
    if near[0] < lo:
        return (
            False,
            measured,
            f"at tick {near[1]} the camera is {near[0]:.2f} m from the head (at least {lo})",
        )
    if worst > middle:
        where = (
            "behind the camera"
            if worst >= 2.0
            else f"{worst:.2f} of the way to the view's edge"
        )
        return (
            False,
            measured,
            (
                f"at tick {off_tick} the {args.get('frame_bone', 'Hips')} bone is {where} "
                f"(at most {middle})"
            ),
        )
    return True, measured, ""


def camera_heading(cam: dict) -> float:
    """The heading (degrees clockwise from north) of the camera's horizontal forward."""
    bz = cam["bz"]
    return math.degrees(math.atan2(-float(bz[0]), float(bz[2]))) % 360.0


def camera_pitch(cam: dict) -> float:
    """The camera's pitch in degrees: positive when it looks up."""
    return math.degrees(math.asin(max(-1.0, min(1.0, -float(cam["bz"][1])))))


def check_look_rate(rec: PlayRecord, args: dict) -> Result:
    """Between two marks the camera turns around the player at min_dps-max_dps degrees
    per second (CM-2): the change of its heading, followed frame by frame."""
    run = rec.runs[int(args.get("run", 0))]
    frames = [
        f for f in frames_between(run, args["from"], args["to"]) if f.get("camera")
    ]
    if len(frames) < 2:
        return None, {}, "the camera was not observed"
    turned = 0.0
    for a, b in itertools.pairwise(frames):
        d = camera_heading(b["camera"]) - camera_heading(a["camera"])
        turned += (d + 180.0) % 360.0 - 180.0
    secs = (int(frames[-1]["t"]) - int(frames[0]["t"])) / TICK_HZ
    rate = abs(turned) / secs if secs > 0 else 0.0
    measured = {"turned_deg": round(turned, 2), "seconds": round(secs, 3)}
    measured["rate_dps"] = round(rate, 2)
    lo, hi = float(args["min_dps"]), float(args["max_dps"])
    ok = lo <= rate <= hi
    return ok, measured, "" if ok else f"{rate:.1f} degrees per second"


def check_camera_tilt(rec: PlayRecord, args: dict) -> Result:
    """Between two marks the camera's pitch stays within [min_deg, max_deg] (with tol_deg)
    and, with "rises" or "falls", changes that way by at least min_change_deg (CM-2)."""
    run = rec.runs[int(args.get("run", 0))]
    frames = [
        f for f in frames_between(run, args["from"], args["to"]) if f.get("camera")
    ]
    if len(frames) < 2:
        return None, {}, "the camera was not observed"
    pitches = [camera_pitch(f["camera"]) for f in frames]
    tol = float(args.get("tol_deg", 0.5))
    lo, hi = float(args["min_deg"]), float(args["max_deg"])
    measured = {
        "pitch_deg": [round(min(pitches), 2), round(max(pitches), 2)],
        "change_deg": round(pitches[-1] - pitches[0], 2),
    }
    if min(pitches) < lo - tol or max(pitches) > hi + tol:
        return False, measured, f"the pitch reaches {measured['pitch_deg']} degrees"
    need = float(args.get("min_change_deg", 0.0))
    change = measured["change_deg"] * (-1.0 if args.get("falls") else 1.0)
    if (args.get("rises") or args.get("falls")) and change < need:
        way = "up" if args.get("rises") else "down"
        return (
            False,
            measured,
            (
                f"the camera tilted {measured['change_deg']} degrees, expected at least "
                f"{need} {way}"
            ),
        )
    return True, measured, ""


def check_moves_along_camera(rec: PlayRecord, args: dict) -> Result:
    """Between two marks the player moves within within_deg of the camera's horizontal
    forward direction as it was at the first mark (CM-3)."""
    run = rec.runs[int(args.get("run", 0))]
    fa, fb = frame_at_mark(run, args["from"]), frame_at_mark(run, args["to"])
    pa, pb = point_of(fa, args), point_of(fb, args)
    cam = (fa or {}).get("camera")
    if pa is None or pb is None or not isinstance(cam, dict):
        return None, {}, "the player or the camera was not observed"
    dx, dz = pb[0] - pa[0], pb[2] - pa[2]
    if math.hypot(dx, dz) < 0.05:
        return (
            False,
            {"moved_m": round(math.hypot(dx, dz), 4)},
            "the player did not move",
        )
    moved = math.degrees(math.atan2(dx, -dz)) % 360.0
    off = abs((moved - camera_heading(cam) + 180.0) % 360.0 - 180.0)
    measured = {
        "moved_heading": round(moved, 2),
        "camera_heading": round(camera_heading(cam), 2),
        "off_deg": round(off, 2),
    }
    ok = off <= float(args["within_deg"])
    return ok, measured, "" if ok else f"{off:.1f} degrees off the camera's forward"


LOOK_FIELDS = (
    "body",
    "hair",
    "skin",
    "top",
    "bottom",
    "shoes",
    "hair_colour",
    "props",
    "scale",
)


def rgb(text: object) -> tuple[float, float, float] | None:
    """A "#rrggbb" colour as three channels from 0 to 1, or None."""
    if not isinstance(text, str) or len(text) != 7 or text[0] != "#":
        return None
    try:
        return tuple(int(text[k : k + 2], 16) / 255.0 for k in (1, 3, 5))
    except ValueError:
        return None


def look_at_mark(run: RunRecord, args: dict, mark: str) -> dict | None:
    """The "look" metadata (AC-11) of the entity an expectation names, at a mark."""
    e = entity_of(frame_at_mark(run, mark), args)
    lk = ((e or {}).get("m") or {}).get("look")
    return lk if isinstance(lk, dict) else None


def check_look(rec: PlayRecord, args: dict) -> Result:
    """At a mark the entity's "look" metadata has every field of AC-11 and matches the
    expected look: names equal, colours within colour_tol per channel (0-1 scale)."""
    run = rec.runs[int(args.get("run", 0))]
    lk = look_at_mark(run, args, args["mark"])
    if lk is None:
        return False, {}, "no look metadata"
    missing = [f for f in LOOK_FIELDS if f not in lk]
    measured = {"look": lk}
    if missing:
        return False, measured, f"look lacks {', '.join(missing)}"
    tol = float(args.get("colour_tol", 0.02))
    for key, want in args["expect"].items():
        got = lk.get(key)
        if rgb(want) is not None:
            g = rgb(got)
            if g is None or max(abs(a - b) for a, b in zip(g, rgb(want))) > tol:
                return False, measured, f"{key} is {got!r}, expected {want}"
        elif isinstance(want, (int, float)) and not isinstance(want, bool):
            if not isinstance(got, (int, float)) or abs(float(got) - want) > 1e-6:
                return False, measured, f"{key} is {got!r}, expected {want}"
        elif got != want:
            return False, measured, f"{key} is {got!r}, expected {want!r}"
    return True, measured, ""


def check_looks_distinct(rec: PlayRecord, args: dict) -> Result:
    """The looks at the listed marks differ pairwise in body or hair, and their tops by at
    least min_top_distance (RGB distance, channels 0-1) (CA-2)."""
    run = rec.runs[int(args.get("run", 0))]
    looks = [(m, look_at_mark(run, args, m)) for m in args["marks"]]
    if any(lk is None for _, lk in looks):
        return None, {}, "a look was not observed"
    need = float(args.get("min_top_distance", 0.2))
    close = []
    for i, (ma, a) in enumerate(looks):
        for mb, b in looks[i + 1 :]:
            ta, tb = rgb(a.get("top")), rgb(b.get("top"))
            dist = math.dist(ta, tb) if ta and tb else 0.0
            same_shape = a.get("body") == b.get("body") and a.get("hair") == b.get(
                "hair"
            )
            if same_shape:
                close.append([ma, mb, "same body and hair"])
            elif dist < need:
                close.append([ma, mb, f"tops {dist:.3f} apart"])
    measured = {"looks": len(looks), "too_alike": close[:5]}
    if not close:
        return True, measured, ""
    return (
        False,
        measured,
        f"{close[0][0]} and {close[0][1]}: {close[0][2]} (tops at least {need} apart)",
    )


def check_hips_ratio(rec: PlayRecord, args: dict) -> Result:
    """The bone's height above ground_y at one mark is at most max_ratio of its height at
    another (FT-6: crouched hips at most 75% of standing)."""
    run = rec.runs[int(args.get("run", 0))]
    bone = dict(args, bone=args.get("bone", "Hips"))
    up = point_of(frame_at_mark(run, args["standing"]), bone)
    low = point_of(frame_at_mark(run, args["crouched"]), bone)
    if up is None or low is None:
        return None, {}, "the bone was not observed at both marks"
    g = float(args["ground_y"])
    h_up, h_low = up[1] - g, low[1] - g
    ratio = h_low / h_up if h_up > 0 else math.inf
    measured = {
        "standing_m": round(h_up, 3),
        "crouched_m": round(h_low, 3),
        "ratio": round(ratio, 3),
    }
    ok = ratio <= float(args["max_ratio"])
    return ok, measured, "" if ok else f"the hips stay at {ratio:.0%} of their height"


# ---------------------------------------------------------------- jumping, climbing, vaulting
# A box is a solid placed with prop.spawn: {"p": the middle of its base, "size": [width,
# height, depth], "heading": degrees}. Its depth runs along the heading, its width across.
HANDS = ("LeftHand", "RightHand")


def box_frame(box: dict, p: list[float]) -> tuple[float, float, float]:
    """A world point in a box's own frame: (across, up, along) from the middle of its base."""
    h = math.radians(float(box.get("heading", 0.0)))
    fx, fz = math.sin(h), -math.cos(h)
    rx, rz = math.cos(h), math.sin(h)
    dx, dz = p[0] - float(box["p"][0]), p[2] - float(box["p"][2])
    return dx * rx + dz * rz, p[1] - float(box["p"][1]), dx * fx + dz * fz


def box_half(box: dict) -> tuple[float, float, float]:
    """(half width, height, half depth) of a box."""
    w, h, d = (float(c) for c in box["size"])
    return w / 2.0, h, d / 2.0


def depth_into(box: dict, p: list[float]) -> float:
    """How far a point lies inside a box: its distance to the nearest face (0 outside)."""
    u, w, v = box_frame(box, p)
    hw, height, hd = box_half(box)
    return max(0.0, min(hw - abs(u), hd - abs(v), w, height - w))


def segment_hits_box(box: dict, a: list[float], b: list[float]) -> bool:
    """Whether the segment from a to b passes through the inside of a box."""
    pa, pb = box_frame(box, a), box_frame(box, b)
    hw, height, hd = box_half(box)
    lo, hi = (-hw, 0.0, -hd), (hw, height, hd)
    t0, t1 = 0.0, 1.0
    for k in range(3):
        d = pb[k] - pa[k]
        if abs(d) < 1e-12:
            if not lo[k] < pa[k] < hi[k]:
                return False
            continue
        ta, tb = (lo[k] - pa[k]) / d, (hi[k] - pa[k]) / d
        t0, t1 = max(t0, min(ta, tb)), min(t1, max(ta, tb))
        if t0 >= t1:
            return False
    return True


def segment_distance(p: list[float], a: list[float], b: list[float]) -> float:
    """Distance from a point to the segment a-b."""
    ab = [b[k] - a[k] for k in range(3)]
    n2 = sum(c * c for c in ab)
    t = 0.0
    if n2 > 0:
        t = max(0.0, min(1.0, sum(ab[k] * (p[k] - a[k]) for k in range(3)) / n2))
    return math.dist(p, [a[k] + ab[k] * t for k in range(3)])


def bones_in(frame: dict, args: dict) -> dict[str, list[float]]:
    """{bone: world position} of the named entity's observed bones in a frame."""
    e = entity_of(frame, args)
    if e is None:
        return {}
    raw = ((frame.get("bones") or {}).get(str(e.get("id"))) or {}).items()
    return {
        k: [float(c) for c in v] for k, v in raw if isinstance(v, list) and len(v) == 3
    }


def deepest_bone(
    frames: list[dict], args: dict, box: dict
) -> tuple[float, str, object]:
    """(depth, bone, tick) of the observed bone that went furthest into a box."""
    worst = (0.0, "", None)
    for fr in frames:
        for name, p in bones_in(fr, args).items():
            d = depth_into(box, p)
            if d > worst[0]:
                worst = (d, name, fr.get("t"))
    return worst


def sample_ticks(frames: list[dict]) -> int:
    """The ticks between consecutive samples (the smallest gap seen, at least 1)."""
    ts = [int(f.get("t", 0)) for f in frames]
    gaps = [b - a for a, b in itertools.pairwise(ts) if b > a]
    return min(gaps) if gaps else 1


def check_jump(rec: PlayRecord, args: dict) -> Result:
    """FT-3: between two marks, the first taken standing on level ground before jump is
    pressed, the bone (default Hips) rises min_rise_m-max_rise_m above its height at the
    first mark, and the entity is off the ground (its position more than off_m above
    ground_y) for min_air_s-max_air_s: the longest run of consecutive samples off the
    ground, each sample counting for the ticks between samples."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    bone = dict(args, bone=args.get("bone", "Hips"))
    first = point_of(frames[0], bone) if frames else None
    if first is None:
        return None, {}, f"the {bone['bone']} bone was not observed at {args['from']}"
    heights = [p[1] for p in (point_of(f, bone) for f in frames) if p is not None]
    rise = max(heights) - first[1]
    start = point_of(frames[0], dict(args, bone=None))
    if "ground_y" not in args and start is None:
        return None, {}, f"the entity was not observed at {args['from']}"
    ground_y = float(args["ground_y"]) if "ground_y" in args else start[1]
    off_m = float(args.get("off_m", 0.02))
    ground = ground_y + off_m
    step = sample_ticks(frames)
    best = cur = 0
    for fr in frames:
        e = entity_of(fr, args)
        off = (
            e is not None and isinstance(e.get("p"), list) and float(e["p"][1]) > ground
        )
        cur = cur + 1 if off else 0
        best = max(best, cur)
    air = best * step / TICK_HZ
    measured = {"rise_m": round(rise, 3), "airborne_s": round(air, 3)}
    lo, hi = float(args["min_rise_m"]), float(args["max_rise_m"])
    if not lo <= rise <= hi:
        return False, measured, f"the hips rose {rise:.2f} m, expected {lo}-{hi}"
    lo, hi = float(args["min_air_s"]), float(args["max_air_s"])
    if not lo <= air <= hi:
        return (
            False,
            measured,
            (
                f"off the ground (more than {off_m} m above {ground_y:.2f}) for {air:.2f} s, "
                f"expected {lo}-{hi}"
            ),
        )
    return True, measured, ""


def check_climb(rec: PlayRecord, args: dict) -> Result:
    """FT-4: from the mark where jump is pressed (`from`) to `to`, the entity stands on top
    of the box (its position over the top and within on_top_m of its height) within
    within_s; before that, a hand comes within hand_m of the top edge (the segment `edge`)
    while the Hips bone is below the top; and no observed bone is ever more than max_into_m
    inside the box."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    if not frames:
        return None, {}, "the marks were not reached"
    box, edge = args["box"], args["edge"]
    hw, height, hd = box_half(box)
    top = float(box["p"][1]) + height
    t0 = int(frames[0].get("t", 0))
    on_top = None
    reach = None
    highest = None
    for fr in frames:
        e = entity_of(fr, args)
        if e is None or not isinstance(e.get("p"), list):
            continue
        u, w, v = box_frame(box, [float(c) for c in e["p"]])
        highest = w if highest is None else max(highest, w)
        if (
            abs(u) <= hw
            and abs(v) <= hd
            and abs(w - height) <= float(args.get("on_top_m", 0.1))
        ):
            on_top = int(fr.get("t", 0))
            break
        b = bones_in(fr, args)
        if "Hips" in b and b["Hips"][1] < top:
            near = [segment_distance(b[h], edge[0], edge[1]) for h in HANDS if h in b]
            if near and (reach is None or min(near) < reach):
                reach = min(near)
    depth, which, tick = deepest_bone(frames, args, box)
    measured = {
        "on_top_after_s": None if on_top is None else round((on_top - t0) / TICK_HZ, 3),
        "hand_to_edge_m": None if reach is None else round(reach, 3),
        "deepest_bone_m": round(depth, 3),
    }
    limit = float(args["within_s"])
    if on_top is None or on_top - t0 > limit * TICK_HZ:
        got = "never" if on_top is None else f"after {(on_top - t0) / TICK_HZ:.2f} s"
        up = (
            ""
            if highest is None
            else f", the position at most {highest:.2f} m above its base"
        )
        return (
            False,
            measured,
            (
                f"not on top within {limit} s (on top {got}; the top is {height:.2f} m up{up})"
            ),
        )
    if reach is None or reach > float(args["hand_m"]):
        what = (
            "no hand was observed"
            if reach is None
            else f"the nearest came {reach:.2f} m"
        )
        return (
            False,
            measured,
            (
                f"no hand within {args['hand_m']} m of the top edge while the hips were below it "
                f"({what})"
            ),
        )
    if depth > float(args["max_into_m"]):
        return (
            False,
            measured,
            f"at tick {tick} {which} is {depth:.3f} m inside the obstacle",
        )
    return True, measured, ""


def check_vault(rec: PlayRecord, args: dict) -> Result:
    """FT-5: from the mark where jump is pressed (`from`) to `to`, the entity's position goes
    past the far side of the box (the side away from where it stood at `from`) within
    within_s; whenever the Hips bone is over the top it is at least clear_m above it (and
    it does pass over the top); and no observed bone is ever more than max_into_m inside the
    box."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    e0 = entity_of(frames[0], args) if frames else None
    if e0 is None or not isinstance(e0.get("p"), list):
        return None, {}, "the entity was not observed at the first mark"
    box = args["box"]
    hw, height, hd = box_half(box)
    top = float(box["p"][1]) + height
    side = 1.0 if box_frame(box, [float(c) for c in e0["p"]])[2] >= 0 else -1.0
    t0 = int(frames[0].get("t", 0))
    over = None
    clear = None
    furthest = None
    for fr in frames:
        e = entity_of(fr, args)
        if e is not None and isinstance(e.get("p"), list):
            along = -box_frame(box, [float(c) for c in e["p"]])[2] * side
            furthest = along if furthest is None else max(furthest, along)
        past = (
            e is not None
            and isinstance(e.get("p"), list)
            and box_frame(box, [float(c) for c in e["p"]])[2] * side < -hd
        )
        if over is None and past:
            over = int(fr.get("t", 0))
        hips = bones_in(fr, args).get("Hips")
        if hips is not None:
            u, _w, v = box_frame(box, hips)
            if abs(u) <= hw and abs(v) <= hd:
                c = hips[1] - top
                clear = c if clear is None else min(clear, c)
    depth, which, tick = deepest_bone(frames, args, box)
    measured = {
        "over_after_s": None if over is None else round((over - t0) / TICK_HZ, 3),
        "hips_clearance_m": None if clear is None else round(clear, 3),
        "deepest_bone_m": round(depth, 3),
    }
    limit = float(args["within_s"])
    if over is None or over - t0 > limit * TICK_HZ:
        short = (
            ""
            if furthest is None
            else f"; it got {hd - furthest:.2f} m short of the far side"
        )
        if over is not None:
            short = f"; it was past after {(over - t0) / TICK_HZ:.2f} s"
        return False, measured, f"not past the obstacle within {limit} s{short}"
    if clear is None:
        return False, measured, "the hips never passed over the obstacle"
    if clear < float(args["clear_m"]):
        return (
            False,
            measured,
            (
                f"the hips crossed {clear:.2f} m above the top, at least {args['clear_m']} expected"
            ),
        )
    if depth > float(args["max_into_m"]):
        return (
            False,
            measured,
            f"at tick {tick} {which} is {depth:.3f} m inside the obstacle",
        )
    return True, measured, ""


def check_camera_clear(rec: PlayRecord, args: dict) -> Result:
    """CM-4: between two marks, in at least min_share of the samples the segment from the
    entity's Head bone to the camera passes through none of the listed boxes."""
    run = rec.runs[int(args.get("run", 0))]
    frames = frames_between(run, args["from"], args["to"])
    n = blocked = 0
    first = None
    for fr in frames:
        cam = fr.get("camera")
        head = bones_in(fr, args).get("Head")
        if not isinstance(cam, dict) or head is None:
            continue
        n += 1
        p = [float(c) for c in cam["p"]]
        if any(segment_hits_box(box, head, p) for box in args["boxes"]):
            blocked += 1
            if first is None:
                first = (fr.get("t"), math.dist(head, p))
    if not n:
        return None, {}, "the camera and the Head bone were not observed"
    share = (n - blocked) / n
    measured = {"samples": n, "through_a_wall": blocked, "clear_share": round(share, 4)}
    need = float(args.get("min_share", 0.99))
    if share < need:
        return (
            False,
            measured,
            (
                f"the camera is behind a wall in {blocked} of {n} samples, first at tick "
                f"{first[0]}, {first[1]:.2f} m from the head"
            ),
        )
    return True, measured, ""


def check_fall_damage(rec: PlayRecord, args: dict) -> Result:
    """FT-8: between two marks, the first standing on the ground the player falls from and
    the second standing (or lying) on the ground it landed on, the entity's position drops
    h metres and the state report's player.health falls by: nothing when h is under safe_m
    (3.0); 100 * (h - safe_m) / (fatal_m - safe_m) within tol (a share of that, 0.10) up to
    fatal_m (15.0); to 0 from fatal_m."""
    run = rec.runs[int(args.get("run", 0))]
    fa, fb = frame_at_mark(run, args["from"]), frame_at_mark(run, args["to"])
    pa, pb = point_of(fa, args), point_of(fb, args)
    ha = dig(state_of(fa), "player.health")
    hb = dig(state_of(fb), "player.health")
    if pa is None or pb is None:
        return None, {}, "the entity was not observed at both marks"
    if not _is_num(ha) or not _is_num(hb):
        return None, {}, "player.health was not in the state report at both marks"
    drop = pa[1] - pb[1]
    loss = float(ha) - float(hb)
    safe, fatal = float(args.get("safe_m", 3.0)), float(args.get("fatal_m", 15.0))
    measured = {"fall_m": round(drop, 3), "health_before": ha, "health_after": hb}
    if drop < safe:
        ok = abs(loss) < 0.5
        return (
            ok,
            measured,
            "" if ok else f"a {drop:.2f} m fall took {loss:g} health, expected none",
        )
    if drop >= fatal:
        ok = float(hb) <= 0.0
        return (
            ok,
            measured,
            "" if ok else f"a {drop:.2f} m fall left {hb:g} health, expected 0",
        )
    want = 100.0 * (drop - safe) / (fatal - safe)
    tol = float(args.get("tol", 0.1))
    measured["expected_loss"] = round(want, 2)
    ok = abs(loss - want) <= tol * want
    note = (
        ""
        if ok
        else f"a {drop:.2f} m fall took {loss:g} health, expected {want:.1f} (within {tol:.0%})"
    )
    return ok, measured, note


# ---------------------------------------------------------------- signals
# A program, as a check reads it (plan/FORMAT.md, in ticks of 1/60 s): {"offset": ticks,
# "cycle": ticks, "phases": [{"start", "green_end", "amber_end", "green": [approach ids],
# "walk": [crosswalk ids]}]}, phases in order from program time 0.
LIGHTS = ("red", "amber", "green")
WALKS = ("walk", "dont_walk")


def signals_seen(frame: dict | None) -> dict[tuple[str, str], list[str]]:
    """{(intersection, approach or crosswalk id): [states]} of the signal entities in a
    frame's census (the metadata observed with census {"meta": [...]})."""
    out: dict[tuple[str, str], list[str]] = {}
    for e in (frame or {}).get("census") or []:
        if e.get("k") != "signal":
            continue
        m = e.get("m") or {}
        key = m.get("approach", m.get("crosswalk"))
        if isinstance(m.get("intersection"), str) and isinstance(key, str):
            out.setdefault((m["intersection"], key), []).append(m.get("state"))
    return out


def program_states(prog: dict, k: int) -> dict[str, str]:
    """The state of every approach and crosswalk of a program at program tick k."""
    pos = (k + int(prog["offset"])) % int(prog["cycle"])
    out: dict[str, str] = {}
    for ph in prog["phases"]:
        for c in ph["walk"]:
            out.setdefault(c, "dont_walk")
    for ph in prog["phases"]:
        green = int(ph["start"]) <= pos < int(ph["green_end"])
        amber = int(ph["green_end"]) <= pos < int(ph["amber_end"])
        for a in ph["green"]:
            out[a] = "green" if green else ("amber" if amber else "red")
        if green:
            for c in ph["walk"]:
                out[c] = "walk"
    return out


def check_signal_entities(rec: PlayRecord, args: dict) -> Result:
    """AC-7: at a mark, every listed signalised approach ([intersection, approach]) has
    exactly one signal entity with that intersection and approach and a state of red,
    amber or green; every listed crosswalk ([intersection, crosswalk]) exactly one with
    that crosswalk and a state of walk or dont_walk."""
    run = rec.runs[int(args.get("run", 0))]
    frame = frame_at_mark(run, args["mark"])
    if frame is None:
        return None, {}, "the mark was not reached"
    seen = signals_seen(frame)
    problems = []
    for kind, states in (("approaches", LIGHTS), ("crosswalks", WALKS)):
        for inter, key in args[kind]:
            got = seen.get((inter, key), [])
            if len(got) != 1:
                problems.append(f"{key} at {inter}: {len(got)} signal entities")
            elif got[0] not in states:
                problems.append(f"{key} at {inter}: state {got[0]!r}")
    measured = {
        "signals": sum(len(v) for v in seen.values()),
        "problems": problems[:5],
        "problem_count": len(problems),
    }
    return not problems, measured, problems[0] if problems else ""


def reset_tick(run: RunRecord, step: int) -> int | None:
    """The tick the DevConsole commands of a step ran at."""
    for fr in run.frames:
        if fr.get("_step") == step:
            for d in fr.get("dev") or []:
                if isinstance(d.get("t"), int):
                    return int(d["t"])
    return None


def check_signal_program(rec: PlayRecord, args: dict) -> Result:
    """TR-4: between two marks every signal of the listed programs shows its program's
    state within one tick. Program ticks count from the tick the world.reset command of
    step reset_step ran in; a frame taken at tick t shows what the game did in tick t - 1,
    so it must show the program's state at t - 1 - reset, or one tick either side."""
    run = rec.runs[int(args.get("run", 0))]
    frames = [
        f for f in frames_between(run, args["from"], args["to"]) if signals_seen(f)
    ]
    t_reset = reset_tick(run, int(args["reset_step"]))
    if not frames or t_reset is None:
        return None, {}, "no signals were observed after the reset"
    progs = args["programs"]
    wrong = []
    for fr in frames:
        k = int(fr["t"]) - 1 - t_reset
        seen = signals_seen(fr)
        for inter, prog in progs.items():
            want = [program_states(prog, k + d) for d in (-1, 0, 1)]
            for key, expected in want[1].items():
                got = seen.get((inter, key))
                if got and len(got) == 1 and all(got[0] != w.get(key) for w in want):
                    wrong.append(
                        {"tick": fr["t"], "program_tick": k, "at": inter, "signal": key,
                         "shows": got[0], "program": expected}
                    )  # fmt: skip
    measured = {
        "frames": len(frames),
        "off_program": len(wrong),
        "first_off_program": wrong[:3],
    }
    if wrong:
        w = wrong[0]
        return (
            False,
            measured,
            (
                f"at tick {w['tick']}, {w['program_tick']} ticks after the reset, "
                f"{w['signal']} at {w['at']} shows {w['shows']}; its program shows "
                f"{w['program']} then"
            ),
        )
    return True, measured, ""


def changing(prog: dict, k: int) -> bool:
    """Whether a program changes any state within one tick of program tick k."""
    return program_states(prog, k - 1) != program_states(prog, k + 1)


def signal_frames(rec: PlayRecord, args: dict) -> tuple[list[dict], int | None]:
    """The frames between the marks that show signals, and the reset tick (when the args
    name reset_step: frames within one tick of a phase change are then let off, as TR-4
    allows a tick either way)."""
    run = rec.runs[int(args.get("run", 0))]
    frames = [
        f for f in frames_between(run, args["from"], args["to"]) if signals_seen(f)
    ]
    t_reset = reset_tick(run, int(args["reset_step"])) if "reset_step" in args else None
    return frames, t_reset


def check_signal_greens(rec: PlayRecord, args: dict) -> Result:
    """TR-4: between two marks, the approaches of an intersection that show green at the
    same time all belong to one phase of its program (with reset_step, not counting the
    tick on either side of a phase change)."""
    frames, t_reset = signal_frames(rec, args)
    if not frames:
        return None, {}, "no signals were observed"
    clash = []
    for fr in frames:
        seen = signals_seen(fr)
        for inter, prog in args["programs"].items():
            if t_reset is not None and changing(prog, int(fr["t"]) - 1 - t_reset):
                continue
            green = {k for (i, k), v in seen.items() if i == inter and "green" in v}
            if green and not any(green <= set(ph["green"]) for ph in prog["phases"]):
                clash.append({"tick": fr.get("t"), "at": inter, "green": sorted(green)})
    measured = {"frames": len(frames), "conflicts": len(clash), "first": clash[:3]}
    if clash:
        c = clash[0]
        return (
            False,
            measured,
            (
                f"at tick {c['tick']} {', '.join(c['green'])} at {c['at']} are green "
                "together, and no phase of its program has them all"
            ),
        )
    return True, measured, ""


def check_signal_walks(rec: PlayRecord, args: dict) -> Result:
    """TR-4: between two marks, while a crosswalk shows walk, every approach of its
    intersection is red except those green in the phase that lists it, and none shows
    amber (with reset_step, not counting the tick on either side of a phase change)."""
    frames, t_reset = signal_frames(rec, args)
    if not frames:
        return None, {}, "no signals were observed"
    wrong = []
    for fr in frames:
        seen = signals_seen(fr)
        for inter, prog in args["programs"].items():
            if t_reset is not None and changing(prog, int(fr["t"]) - 1 - t_reset):
                continue
            lit = {k: v[0] for (i, k), v in seen.items() if i == inter and len(v) == 1}
            for cw, st in lit.items():
                if st != "walk":
                    continue
                phases = [ph for ph in prog["phases"] if cw in ph["walk"]]
                moving = {k: s for k, s in lit.items() if s in ("green", "amber")}
                if not any(
                    all(s == "green" and k in ph["green"] for k, s in moving.items())
                    for ph in phases
                ):
                    wrong.append({"tick": fr.get("t"), "at": inter, "crosswalk": cw,
                                  "lit": sorted(moving.items())})  # fmt: skip
    measured = {
        "frames": len(frames),
        "walks_out_of_phase": len(wrong),
        "first": wrong[:3],
    }
    if wrong:
        w = wrong[0]
        lit = ", ".join(f"{k} is {st}" for k, st in w["lit"])
        why = f"while {lit}" if lit else "outside the phases that list it"
        return (
            False,
            measured,
            f"at tick {w['tick']} {w['crosswalk']} at {w['at']} shows walk {why}",
        )
    return True, measured, ""


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
    "rays": check_rays,
    "clear_run": check_clear_run,
    "surface_tags": check_surface_tags,
    "none_listed": check_none_listed,
    "skeleton": check_skeleton,
    "pace": check_pace,
    "feet": check_feet,
    "camera_frame": check_camera_frame,
    "look_rate": check_look_rate,
    "camera_tilt": check_camera_tilt,
    "moves_along_camera": check_moves_along_camera,
    "look": check_look,
    "looks_distinct": check_looks_distinct,
    "hips_ratio": check_hips_ratio,
    "jump": check_jump,
    "climb": check_climb,
    "vault": check_vault,
    "camera_clear": check_camera_clear,
    "fall_damage": check_fall_damage,
    "signal_entities": check_signal_entities,
    "signal_program": check_signal_program,
    "signal_greens": check_signal_greens,
    "signal_walks": check_signal_walks,
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
            ok, measured, note = None, {}, f"could not be measured: {exc!r}"
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
