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


def judge_ray(answer: object, args: dict, y: float | None) -> str:
    """Why one ray's answer does not meet the expectation ("" when it does)."""
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
        return "the ray hit nothing"
    surface = answer.get("surface")
    if "tags" in args and surface not in args["tags"]:
        return f"hit {surface!r}" if surface is not None else "hit an untagged surface"
    if surface in (args.get("not_tags") or ()):
        return f"hit {surface!r}"
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
    "tol_m"; or, with "clear", when it hits nothing. Rays come in groups (consecutive
    counts, "groups"); the expectation holds when in every group at least "min_share"
    (default all) of the rays meet it.
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
        judge_ray(a, args, float(ys[k]) if isinstance(ys, list) else ys)
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
        "groups_short": short[:5],
        "groups_short_count": len(short),
        "first_misses": misses,
    }
    if not short:
        return True, measured, ""
    names = ", ".join(f"{s['group']} ({s['share']})" for s in short[:3])
    return False, measured, f"below {min_share} of the rays: {names}"


def check_clear_run(rec: PlayRecord, args: dict) -> Result:
    """An opening is at least min_width_m wide.

    The rays of each group cross the opening side by side, spacing_m apart, in order;
    the widest run of consecutive rays that hit nothing must span min_width_m (the run of
    k clear rays spans (k - 1) * spacing_m).
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
        widths[label] = round(max(best - 1, 0) * spacing, 3)
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
        return False, {"answer": res}, "no such entity"
    bones = set(res.get("bones") or [])
    missing = [b for b in args.get("bones", []) if b not in bones]
    measured = {
        "skeletons": res.get("skeletons"),
        "bones": len(bones),
        "missing_bones": missing[:10],
        "bound_meshes": res.get("bound_meshes"),
    }
    if res.get("skeletons") != 1:
        return False, measured, f"{res.get('skeletons')} skeletons"
    if missing:
        return False, measured, f"bones missing: {', '.join(missing[:6])}"
    if int(res.get("bound_meshes") or 0) < int(args.get("min_bound_meshes", 1)):
        return False, measured, "no skinned mesh is bound to the skeleton"
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
    if len(steps) < int(args.get("min_steps", 4)):
        return False, measured, f"{len(steps)} steps"
    if alternation < float(args.get("min_alternation", 0.9)):
        return False, measured, f"steps alternate feet {alternation:.0%} of the time"
    if slide is None or slide > float(args["max_slide_mps"]):
        return False, measured, f"planted toes slide at {slide} m/s (p95)"
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
    for fr in frames:
        cam, e = fr.get("camera"), entity_of(fr, args)
        if not isinstance(cam, dict) or e is None:
            continue
        head = bone_of(fr, e.get("id"), "Head")
        body = bone_of(fr, e.get("id"), args.get("frame_bone", "Hips"))
        if head is None or body is None:
            continue
        n += 1
        dists.append(math.dist(head, [float(c) for c in cam["p"]]))
        off = view_offset(cam, body, aspect)
        worst = max(worst, 2.0 if off is None else max(abs(off[0]), abs(off[1])))
    if not n:
        return None, {}, "the camera and the player's bones were not observed"
    measured = {
        "frames": n,
        "head_distance_m": [round(min(dists), 3), round(max(dists), 3)],
        "farthest_from_middle": round(worst, 3),
    }
    lo, hi = float(args["min_m"]), float(args["max_m"])
    if min(dists) < lo or max(dists) > hi:
        return (
            False,
            measured,
            f"the camera is {measured['head_distance_m']} m from the head",
        )
    if worst > middle:
        return False, measured, f"the player leaves the middle {middle:.0%} of the view"
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
        return False, measured, "the camera does not tilt that way"
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
            if same_shape or dist < need:
                close.append([ma, mb, round(dist, 3)])
    measured = {"looks": len(looks), "too_alike": close[:5]}
    return not close, measured, "" if not close else f"too alike: {close[:2]}"


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
