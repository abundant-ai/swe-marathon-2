"""The signed link's framing and the trace hashing (no Godot)."""

from __future__ import annotations

import hashlib
import hmac
import json
import socket
import struct
from pathlib import Path

import pytest
from qakit import link, trace

KEY = bytes(range(32))


def test_encode_then_decode_round_trips() -> None:
    """A message signed with the key decodes to the same object."""
    data = link.encode(KEY, {"run": 3, "n": 0})
    (length,) = struct.unpack(">I", data[:4])
    assert length == len(data) - 4
    assert link.decode_body(KEY, data[4:]) == {"run": 3, "n": 0}


def test_wrong_key_is_unsigned() -> None:
    """A tag made with another key is refused as unsigned."""
    data = link.encode(bytes(32), {"n": 0})
    with pytest.raises(link.LinkError) as err:
        link.decode_body(KEY, data[4:])
    assert err.value.kind == "unsigned"


def test_tag_is_hmac_sha256_of_the_payload() -> None:
    """The framing is length, HMAC-SHA256(payload), payload (what the C core expects)."""
    data = link.encode(KEY, {"a": 1, "n": 5})
    tag, payload = data[4:36], data[36:]
    assert tag == hmac.new(KEY, payload, hashlib.sha256).digest()
    assert json.loads(payload) == {"a": 1, "n": 5}


def test_sequence_numbers_are_checked() -> None:
    """A received message with the wrong sequence number is refused."""
    a, b = socket.socketpair()
    try:
        sender = link.Link(a, KEY)
        receiver = link.Link(b, KEY)
        sender.send({"x": 1})
        assert receiver.recv(2.0)["x"] == 1
        a.sendall(link.encode(KEY, {"x": 2, "n": 7}))
        with pytest.raises(link.LinkError) as err:
            receiver.recv(2.0)
        assert err.value.kind == "bad_message"
    finally:
        a.close()
        b.close()


def test_silence_is_reported() -> None:
    """No message within the wait gives the "silent" kind."""
    a, b = socket.socketpair()
    try:
        with pytest.raises(link.LinkError) as err:
            link.Link(b, KEY).recv(0.05)
        assert err.value.kind == "silent"
    finally:
        a.close()
        b.close()


def frame(t: int, x: float, reset: bool = False, ms: int = 0) -> dict:
    """A small frame: one entity at x, optionally answering a world.reset."""
    dev = (
        [{"cmd": "world.reset", "res": {"ok": True, "ms": ms}, "t": t - 1}]
        if reset
        else []
    )
    return {
        "t": t,
        "ticks": 1,
        "dev": dev,
        "census": [{"id": 1, "k": "npc", "p": [x, 0.0, 0.0]}],
        "perf": {"wall_us": t * 17},
    }


def test_chain_restarts_at_world_reset() -> None:
    """Each successful world.reset answer starts a new segment."""
    frames = [
        frame(1, 0.0),
        frame(2, 1.0, reset=True),
        frame(3, 2.0),
        frame(4, 3.0, reset=True),
    ]
    c = trace.chain(frames)
    assert c.frames_per_segment == [1, 2, 1]
    assert c.segment_of == [0, 1, 1, 2]


def test_replay_hash_ignores_timing_and_answers() -> None:
    """Perf numbers and command answers (which may carry timing) are not hashed."""
    a = [frame(1, 0.0), frame(2, 1.0, reset=True, ms=12), frame(3, 2.0)]
    b = [frame(1, 0.0), frame(2, 1.0, reset=True, ms=97), frame(3, 2.0)]
    b[2]["perf"] = {"wall_us": 1}
    assert trace.chain(a).replay_hash == trace.chain(b).replay_hash


def test_replay_hash_sees_one_bit_of_position() -> None:
    """A position that differs in the last bit changes the hash and is located."""
    a = [frame(1, 0.0), frame(2, 1.0, reset=True), frame(3, 2.0)]
    b = [frame(1, 0.0), frame(2, 1.0, reset=True), frame(3, 2.0000000000000004)]
    assert trace.chain(a).replay_hash != trace.chain(b).replay_hash
    div = trace.first_divergence(a, b)
    assert div is not None and div.tick_a == 3 and "entity 1" in div.detail


def test_start_up_is_outside_the_replay_hash() -> None:
    """Frames before the first world.reset do not enter the replay hash."""
    a = [frame(1, 5.0), frame(2, 1.0, reset=True), frame(3, 2.0)]
    b = [frame(1, 9.0), frame(2, 1.0, reset=True), frame(3, 2.0)]
    assert trace.chain(a).replay_hash == trace.chain(b).replay_hash
    assert trace.first_divergence(a, b) is None


def test_canonical_json_is_order_free_and_refuses_nan() -> None:
    """Key order does not matter; NaN is refused."""
    assert trace.canonical({"b": 1, "a": [1.5, 2]}) == trace.canonical(
        {"a": [1.5, 2], "b": 1}
    )
    with pytest.raises(ValueError):
        trace.canonical({"x": float("nan")})


def test_trace_file_round_trips(tmp_path: Path) -> None:
    """write_trace then read_trace gives back the frames and the header's replay hash."""
    frames = [frame(1, 0.0), frame(2, 1.0, reset=True)]
    c = trace.chain(frames)
    trace.write_trace(tmp_path / "t.jsonl.gz", {"play": "p", "run": 0}, frames, c)
    header, back = trace.read_trace(tmp_path / "t.jsonl.gz")
    assert back == frames
    assert header["replay"] == c.replay_hash and header["format"] == trace.FORMAT
