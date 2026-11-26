"""QA's playtests, the expectations they use, and the qa command's text (no Godot)."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from qakit import expect, play
from qakit.cli import describe

TASK = Path(__file__).resolve().parent.parent
PLAYTESTS = sorted((TASK / "common/kit/playtests").glob("*.json"))
GDD = (TASK / "common/design/GDD.md").read_text()
RULE_IDS = set(re.findall(r"\*\*([A-Z]{2}-\d+)\*\*", GDD))
sys.path.insert(0, str(TASK / "scripts"))

from check_agent_text import PATTERN

MINIMAL = {
    "format": "qa-play/1",
    "name": "x/y",
    "template": "x",
    "role": "solo",
    "steps": [{"run": 1}],
}


@pytest.mark.parametrize("path", PLAYTESTS, ids=[p.stem for p in PLAYTESTS])
def test_playtests_are_valid_and_cite_rules(path: Path) -> None:
    """Every playtest loads; every expectation names a known check, a real rule and a sentence;
    no weights or family letters anywhere."""
    p = play.load_play(path)
    raw = json.loads(path.read_text())
    assert p.expect and p.rules and raw.get("about")
    assert set(p.rules) <= RULE_IDS
    for e in p.expect:
        assert e["check"] in expect.CHECKS
        assert e.get("rule") in RULE_IDS and e.get("says")
        assert "w" not in e
    assert "family" not in json.dumps(raw)


def test_playtests_are_current() -> None:
    """The files on disk are what scripts/make_playtests.py writes."""
    out = subprocess.run(
        [sys.executable, str(TASK / "scripts/make_playtests.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stdout


def test_fill_answers_and_plan_dir() -> None:
    """{"$answer": [step, key]} takes the field of an earlier answer; plans add --plan-dir."""
    answers = {
        4: [{"cmd": "vehicle.spawn", "res": {"ok": True, "id": 17}}, {"res": {"id": 3}}]
    }
    args = {
        "seat": {"vehicle": {"$answer": [4, "id"]}, "index": 1},
        "x": {"$answer": [4, 1, "id"]},
    }
    got = play.fill_answers(args, answers)
    assert got == {"seat": {"vehicle": 17, "index": 1}, "x": 3}
    assert play.fill_answers({"$answer": [9, "id"]}, answers) is None
    out = play.substitute(("--role=solo",), {"plans": Path("/p")})
    assert out == ("--role=solo", "--plan-dir=/p")
    kept = play.substitute(("--plan-dir={plans}",), {"plans": Path("/p")})
    assert kept == ("--plan-dir=/p",)


def record(frames: list[dict], expects: list[dict], marks: dict) -> play.PlayRecord:
    """A one-run PlayRecord around frames."""
    p = play.parse_play(dict(MINIMAL, expect=expects))
    r = play.RunRecord(
        index=0, pace_ms=0, frames=copy.deepcopy(frames), marks=dict(marks)
    )
    return play.PlayRecord(p, [r], 0.0)


def outcome(frames: list[dict], e: dict, marks: dict) -> expect.Outcome:
    """The single outcome of one expectation over frames."""
    (o,) = expect.check_play(record(frames, [dict(e, id="e")], marks))
    return o


def test_entity_near_by_kind_archetype_and_answer_id() -> None:
    """entity_near finds the entity a command answered with, within the distance, flat."""
    frames = [
        {"t": 1, "_step": -1},
        {"t": 2, "_step": 3, "dev": [{"cmd": "prop.spawn", "res": {"ok": True, "id": 9}}]},
        {"t": 3, "_step": 4, "census": [
            {"id": 9, "k": "prop", "a": "crate", "f": "none", "p": [10.3, 5.0, 0.0]},
            {"id": 8, "k": "prop", "a": "crate", "f": "none", "p": [10.0, 0.0, 0.0]},
        ]},
    ]  # fmt: skip
    base = {
        "check": "entity_near",
        "args": {"mark": "m", "kind": "prop", "p": [10.0, 0.0, 0.0], "max_m": 0.5},
    }
    assert outcome(frames, base, {"m": 2}).ok is True
    by_id = copy.deepcopy(base)
    by_id["args"]["id_from"] = {"step": 3}
    o = outcome(frames, by_id, {"m": 2})
    assert o.ok is True and o.measured["distance_m"] == 0.3
    by_id["args"]["max_m"] = 0.2
    assert outcome(frames, by_id, {"m": 2}).ok is False
    by_id["args"]["id_from"] = {"step": 7}
    assert outcome(frames, by_id, {"m": 2}).ok is False


def test_event_seen_where_and_counts() -> None:
    """Field filters pick events; max_count 0 asserts none came."""
    ev = {
        "n": "money_changed",
        "t": 5,
        "d": {"amount": 250, "reason": "setup", "balance": 750, "tick": 5},
    }
    frames = [{"t": 1}, {"t": 2, "events": [ev]}, {"t": 3}]
    e = {
        "check": "event_seen",
        "args": {"name": "money_changed", "where": {"reason": "setup", "amount": 250}},
    }
    assert outcome(frames, e, {}).ok is True
    e["args"]["where"]["amount"] = 100
    assert outcome(frames, e, {}).ok is False
    none = {
        "check": "event_seen",
        "args": {"name": "money_changed", "min_count": 0, "max_count": 0},
    }
    assert outcome(frames, none, {}).ok is False
    quiet = {
        "check": "event_seen",
        "args": {"name": "teleport", "min_count": 0, "max_count": 0},
    }
    assert outcome(frames, quiet, {}).ok is True


def state_frame(**state: object) -> dict:
    """A frame carrying a state report."""
    return {"t": 4, "state": {"ok": True, **state}}


def test_state_value_contains_minutes_and_answer_ids() -> None:
    """Lists contain items, hh:mm clocks compare as minutes, ids compare with an answer."""
    frames = [
        {
            "t": 1,
            "_step": 2,
            "dev": [{"cmd": "vehicle.spawn", "res": {"ok": True, "id": 31}}],
        },
        state_frame(clock="10:59", player={"weapons": ["fists", "bat"], "vehicle": 31}),
    ]
    marks = {"m": 1}

    def holds(args: dict) -> bool | None:
        return outcome(
            frames, {"check": "state_value", "args": dict(args, mark="m")}, marks
        ).ok

    assert holds({"path": "player.weapons", "contains": "bat"}) is True
    assert holds({"path": "player.weapons", "contains": "pistol"}) is False
    assert holds({"path": "clock", "as": "minutes", "min": 659, "max": 660}) is True
    assert holds({"path": "clock", "as": "minutes", "min": 660, "max": 661}) is False
    assert holds({"path": "player.vehicle", "equals_answer": {"step": 2}}) is True
    assert holds({"path": "player.vehicle", "equals_answer": {"step": 5}}) is False
    assert (
        expect.clock_minutes("24:00") is None and expect.clock_minutes("08:05") == 485
    )


GOOD_STATE = {
    "tick": 10, "map": "downtown", "clock": "08:00", "weather": "clear", "variation": 1,
    "player": {
        "id": 1, "lead": "lead_1", "health": 100, "armour": 0, "money": 500, "alert": 0,
        "weapon": "fists", "weapons": ["fists"], "ammo": {"magazine": 0, "reserve": 0},
        "aim": None, "cover": False, "vehicle": None, "seat": None, "outfit": "default",
        "outfits": ["default"], "leads_unlocked": ["lead_1"],
    },
    "missions": {m: {"state": "locked", "stage": None} for m in expect.MISSIONS},
    "garages": {g: [] for g in expect.GARAGES},
    "ui": {"phone": False, "map": False, "paused": False, "menu": None},
    "network": {"role": "solo", "peers": 0, "id": 1},
}  # fmt: skip


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({}, None),
        ({"clock": "8:00"}, "clock is not hh:mm"),
        ({"weather": "snow"}, "weather"),
        ({"missions": {}}, "missions.D1"),
        ({"network": {"role": "host", "peers": 0, "id": 1}}, "network"),
        ({"player": None}, "player is missing"),
    ],
)
def test_state_fields(change: dict, problem: str | None) -> None:
    """A complete report holds; each broken field is named."""
    st = dict(copy.deepcopy(GOOD_STATE), **change)
    probs = expect.state_problems(st, player=True)
    if problem is None:
        assert probs == []
    else:
        assert any(problem in p for p in probs), probs


def test_qa_text_reads_like_a_studio_tool() -> None:
    """qa's help, its list and a failure's description use none of the listed words, and
    nothing it prints is a total."""
    qa = [sys.executable, str(TASK / "common/kit/qa")]
    texts = []
    for args in (["--help"], ["run", "--help"], ["list"]):
        out = subprocess.run(qa + args, capture_output=True, text=True, check=False)
        assert out.returncode == 0, out.stderr
        texts.append(out.stdout)
    o = expect.Outcome(
        "money_given",
        "state_value",
        "assert",
        1.0,
        False,
        {"value": 500},
        "player.money is 500",
    )
    o.rule, o.says = "AC-3", "player.give adds the money given"
    texts += describe(o)
    for text in texts:
        assert not PATTERN.search(text), PATTERN.search(text)
        assert not re.search(r"\b\d+ of \d+\b|\btotal\b|\bpassed\b", text), text
