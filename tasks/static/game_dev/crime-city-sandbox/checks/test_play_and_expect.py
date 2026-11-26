"""The play format, its runner's pure parts, and the expectation checks (no Godot)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from qakit import expect, play
from qakit.trace import chain

TASK = Path(__file__).resolve().parent.parent
PLAYS = sorted((TASK / "tests/selftest/plays").glob("*.json"))

MINIMAL = {
    "format": "qa-play/1",
    "name": "x/y",
    "template": "x",
    "role": "solo",
    "steps": [{"run": 1}],
}


@pytest.mark.parametrize("path", PLAYS, ids=[p.stem for p in PLAYS])
def test_shipped_plays_load(path: Path) -> None:
    """Every self-test play is valid and every expectation names a known check."""
    p = play.load_play(path)
    assert p.steps and p.expect
    assert all(e["check"] in expect.CHECKS for e in p.expect)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"format": "qa-play/2"}, "not a qa-play/1"),
        ({"steps": [{"jump": 1}]}, "unknown step"),
        ({"steps": [{"run": 0}]}, "at least 1"),
        ({"steps": [{"run": 1, "mark": "a"}]}, "one key"),
        ({"steps": [{"wait_s": 1.0}]}, "real-time plays"),
        ({"steps": [{"files": {"op": "damage", "since": "m"}}]}, "mark not set"),
        ({"steps": [{"dev": [["state"]]}]}, "dev takes"),
        ({"mode": "realtime", "steps": [{"restart": {}}]}, "lockstep plays"),
        ({"expect": [{"check": "moved"}]}, "expect must be"),
    ],
)
def test_malformed_plays_are_refused(change: dict, message: str) -> None:
    """Each malformed play is refused with a message that says what is wrong."""
    obj = dict(copy.deepcopy(MINIMAL), **change)
    with pytest.raises(play.PlayError, match=message):
        play.parse_play(obj)


def test_digest_identifies_the_play() -> None:
    """Two plays differing in one value have different digests."""
    a = play.parse_play(MINIMAL)
    b = play.parse_play(dict(MINIMAL, steps=[{"run": 2}]))
    assert a.digest != b.digest and len(a.digest) == 64


def test_substitute_folders() -> None:
    """{save_dir} and {home} in arguments become the run's folders."""
    out = play.substitute(
        ("--save-dir={save_dir}", "--x"), {"save_dir": Path("/s"), "home": Path("/h")}
    )
    assert out == ("--save-dir=/s", "--x")


def test_damage_only_touches_files_changed_since_the_mark(tmp_path: Path) -> None:
    """Files saved before the mark stay intact; later ones are overwritten."""
    (tmp_path / "slot_1.json").write_text('{"money": 1}')
    snap = play._snapshot(tmp_path)
    (tmp_path / "slot_2.json").write_text('{"money": 2}')
    changed = play.damage_files(tmp_path, snap, "damage", "salt")
    assert changed == ["slot_2.json"]
    assert (tmp_path / "slot_1.json").read_text() == '{"money": 1}'
    assert (tmp_path / "slot_2.json").read_bytes() != b'{"money": 2}'


def test_resolve_observe_maps_roles_to_ids() -> None:
    """A role in the bone observation becomes the id of the first entity of that kind."""
    fr = {"census": [{"id": 4, "k": "npc"}, {"id": 9, "k": "player"}]}
    obs = {"bones": {"ids": ["player", 12, "vehicle"], "names": ["Head"]}}
    assert play.resolve_observe(obs, fr)["bones"]["ids"] == [9, 12]


# ---------------------------------------------------------------- expectations
def record(
    frames: list[dict], expects: list[dict], marks: dict | None = None, runs: int = 1
) -> play.PlayRecord:
    """A PlayRecord around frames (copied per run) with the given expectations."""
    p = play.parse_play(dict(MINIMAL, expect=expects))
    rr = []
    for k in range(runs):
        r = play.RunRecord(
            index=k, pace_ms=0, frames=copy.deepcopy(frames), marks=dict(marks or {})
        )
        r.chain = chain(r.frames)
        rr.append(r)
    return play.PlayRecord(p, rr, 0.0)


def ent(i: int, k: str, p: list[float], a: str = "x", f: str = "civilian") -> dict:
    """A census entry."""
    return {"id": i, "k": k, "a": a, "f": f, "p": p}


def test_dev_answers_tells_refusals_from_unanswered_commands() -> None:
    """{"ok": false, "error": ...} is well formed; a null answer (call failed) is not."""
    good = {
        "t": 2,
        "_step": 0,
        "dev": [{"cmd": "x", "res": {"ok": False, "error": "no"}}],
    }
    bad = {
        "t": 3,
        "_step": 0,
        "dev": [{"cmd": "y", "res": None, "unanswered": "call failed"}],
    }
    rec = record([good, bad], [{"id": "a", "check": "dev_answers"}])
    (o,) = expect.check_play(rec)
    assert o.ok is False and o.measured["malformed_count"] == 1
    (o2,) = expect.check_play(record([good], [{"id": "a", "check": "dev_answers"}]))
    assert o2.ok is True


def test_dev_result_fields_and_substrings() -> None:
    """dev_result compares fields exactly and substrings case-insensitively."""
    fr = {
        "t": 2,
        "_step": 4,
        "dev": [{"cmd": "load", "res": {"ok": False, "error": "Slot 2 is damaged"}}],
    }
    exp = [
        {
            "id": "d",
            "check": "dev_result",
            "args": {
                "step": 4,
                "equals": {"ok": False},
                "contains": {"error": "DAMAGED"},
            },
        }
    ]
    assert expect.check_play(record([fr], exp))[0].ok is True
    exp2 = [
        {"id": "d", "check": "dev_result", "args": {"step": 4, "equals": {"ok": True}}}
    ]
    assert expect.check_play(record([fr], exp2))[0].ok is False


def test_replay_equal_needs_two_identical_runs() -> None:
    """Equal runs pass; a run that differs fails with its first difference."""
    frames = [
        {"t": 1, "census": [ent(1, "npc", [0, 0, 0])]},
        {"t": 2, "census": [ent(1, "npc", [1, 0, 0])]},
    ]
    rec = record(frames, [{"id": "r", "check": "replay_equal"}], runs=2)
    assert expect.check_play(rec)[0].ok is True
    rec.runs[1].frames[1]["census"][0]["p"][0] = 1.5
    rec.runs[1].chain = chain(rec.runs[1].frames)
    o = expect.check_play(rec)[0]
    assert o.ok is False and "first_difference" in o.measured


def test_same_start() -> None:
    """Same variation, same population; another variation, another population."""
    pop_a = [ent(5, "npc", [1, 0, 2]), ent(6, "prop", [0, 3, 0])]
    pop_b = [ent(9, "npc", [1, 0, 2]), ent(10, "prop", [0, 3, 0])]
    pop_c = [ent(13, "npc", [4, 0, 2]), ent(14, "prop", [0, 3, 1])]
    frames = [
        {"t": 1, "census": pop_a},
        {"t": 2, "census": pop_b},
        {"t": 3, "census": pop_c},
    ]
    exp = [
        {
            "id": "s",
            "check": "same_start",
            "args": {
                "same": ["a", "b"],
                "different": ["a", "c"],
                "kinds": ["npc", "prop"],
            },
        }
    ]
    assert (
        expect.check_play(record(frames, exp, {"a": 0, "b": 1, "c": 2}))[0].ok is True
    )
    frames[1]["census"] = pop_c
    assert (
        expect.check_play(record(frames, exp, {"a": 0, "b": 1, "c": 2}))[0].ok is False
    )


def test_moved_and_state_value() -> None:
    """moved measures the distance between marks; state_value reads a dotted path."""
    frames = [
        {
            "t": 10,
            "census": [ent(9, "player", [0, 0, 0])],
            "state": {"ok": True, "player": {"money": 750}},
        },
        {
            "t": 11,
            "census": [ent(9, "player", [0, 0, -0.05])],
            "state": {"ok": True, "state": {"player": {"money": 5}}},
        },
    ]
    exp = [
        {
            "id": "m",
            "check": "moved",
            "args": {
                "from": "b",
                "to": "a",
                "ticks": 1,
                "min_m": 0.0499,
                "max_m": 0.0501,
            },
        },
        {
            "id": "s1",
            "check": "state_value",
            "args": {"mark": "b", "path": "player.money", "equals": 750},
        },
        {
            "id": "s2",
            "check": "state_value",
            "args": {"mark": "a", "path": "player.money", "min": 0, "max": 10},
        },
    ]
    out = expect.check_play(record(frames, exp, {"b": 0, "a": 1}))
    assert [o.ok for o in out] == [True, True, True]


def test_unknown_check_and_malformed_arguments_do_not_hold() -> None:
    """An unknown check, or arguments the check cannot use, never count as held."""
    exp = [{"id": "u", "check": "nope"}, {"id": "m", "check": "moved", "args": {}}]
    out = expect.check_play(record([{"t": 1}], exp))
    assert [o.ok for o in out] == [None, None]


def test_registry_catches_reuse_and_duplicates() -> None:
    """An id that disappears and comes back, or two entities with one id, are reported."""
    frames = [
        {"t": 1, "census": [ent(1, "npc", [0, 0, 0]), ent(2, "npc", [0, 0, 0])]},
        {"t": 2, "census": [ent(2, "npc", [0, 0, 0])]},
        {
            "t": 3,
            "census": [
                ent(1, "vehicle", [0, 0, 0]),
                ent(2, "npc", [0, 0, 0]),
                ent(2, "npc", [0, 0, 0]),
            ],
        },
    ]
    o = expect.standing_registry(record(frames, []))
    assert o.ok is False
    assert any("reused" in p for p in o.measured["problems"])
    assert any("used twice" in p for p in o.measured["problems"])


def test_registry_restarts_with_a_new_process() -> None:
    """Ids start over in a new process (after a restart), which is not reuse."""
    frames = [
        {"t": 1, "_proc": 0, "census": [ent(1, "npc", [0, 0, 0])]},
        {"t": 2, "_proc": 0, "census": []},
        {"t": 1, "_proc": 1, "census": [ent(1, "npc", [0, 0, 0])]},
    ]
    assert expect.standing_registry(record(frames, [])).ok is True


def test_events_need_their_fields_and_tick() -> None:
    """An event without tick, or without a field of AC-13, is reported."""
    ok = {"t": 1, "events": [{"t": 1, "n": "saved", "d": {"slot": "1", "tick": 1}}]}
    bad = {"t": 2, "events": [{"t": 2, "n": "teleport", "d": {"entity": 3}}]}
    assert expect.standing_events(record([ok], [])).ok is True
    o = expect.standing_events(record([ok, bad], []))
    assert o.ok is False and o.measured["count"] == 2


def test_standing_process_and_telemetry_by_error_kind() -> None:
    """A crash fails the process check; a removed telemetry node fails the telemetry check."""
    rec = record([{"t": 1}], [])
    rec.runs[0].error = {"kind": "closed", "message": "x", "step": 3}
    assert (
        expect.standing_process(rec).ok is False
        and expect.standing_telemetry(rec).ok is True
    )
    rec.runs[0].error = {"kind": "gone", "message": "x", "step": 3}
    assert (
        expect.standing_process(rec).ok is True
        and expect.standing_telemetry(rec).ok is False
    )


def test_heartbeat_gap_fails_the_telemetry_check() -> None:
    """A real-time run whose heartbeat skipped ticks or went silent fails."""
    rec = record(
        [{"t": 1}], [{"id": "h", "check": "heartbeat", "args": {"max_gap_s": 1.0}}]
    )
    rec.runs[0].heartbeat = {"count": 120, "skipped": 0, "max_gap_s": 0.05, "gaps": []}
    assert (
        expect.check_play(rec)[0].ok is True
        and expect.standing_telemetry(rec).ok is True
    )
    rec.runs[0].heartbeat = {
        "count": 60,
        "skipped": 0,
        "max_gap_s": 2.5,
        "gaps": [(-1, 2.5)],
    }
    assert (
        expect.check_play(rec)[0].ok is False
        and expect.standing_telemetry(rec).ok is False
    )


def test_plays_round_trip_through_json() -> None:
    """A parsed play keeps its raw JSON (what replays it without the generator)."""
    p = play.load_play(PLAYS[0])
    assert play.parse_play(json.loads(json.dumps(p.raw))).digest == p.digest
