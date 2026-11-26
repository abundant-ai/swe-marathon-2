"""Traces: canonical frames, segments and a running SHA-256 chain.

A trace is the list of frames one run of a game produced. Two runs did the same thing
when their traces hash the same. What is hashed of each frame is its tick and the
physical record: the entity census (ids, kinds, positions, orientations, velocities,
metadata asked for), the bone positions, the seat points, and the name and tick of each
event. Command answers, the state report, query answers and timing are kept in the trace
file but not hashed (they may carry incidental values such as how long a command took).

Each world.reset starts a new segment (the frame after a successful world.reset
answer is the first frame of the new segment), so a run can be compared from the
moment its world was rebuilt; segment 0 is start-up. A run's replay hash covers every
segment after the first world.reset (or segment 0 when there was none).

Canonical JSON: keys sorted, no spaces, floats in their shortest round-trip form, NaN
and infinities refused (the telemetry node never sends them).
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

FORMAT = "qa-trace/1"
CHAIN_START = hashlib.sha256(FORMAT.encode()).digest()


def canonical(obj: object) -> bytes:
    """Canonical JSON bytes of a value (sorted keys, compact, shortest floats).

    Args:
        obj: A JSON-compatible value.

    Returns:
        UTF-8 bytes.

    Raises:
        ValueError: The value contains NaN or an infinity.
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def physical(frame: dict) -> dict:
    """The part of a frame that a replay must reproduce exactly.

    Args:
        frame: A frame as the telemetry node sent it.

    Returns:
        {"t", "census", "bones", "seats", "ev"} where "ev" lists [name, tick] of each
        event. Missing parts are left out.
    """
    out: dict = {"t": frame.get("t")}
    if "census" in frame:
        out["census"] = frame["census"]
    if "bones" in frame:
        out["bones"] = frame["bones"]
    if "seats" in frame:
        out["seats"] = frame["seats"]
    events = frame.get("events") or []
    if events:
        out["ev"] = [[e.get("n"), e.get("t")] for e in events if isinstance(e, dict)]
    return out


def starts_segment(frame: dict) -> bool:
    """Whether a frame is the first after a successful world.reset.

    Args:
        frame: A frame; its "dev" lists the answers to the commands of the step
            that led to it.

    Returns:
        True when one of those answers is a world.reset whose answer has "ok": true.
    """
    for d in frame.get("dev") or []:
        if not isinstance(d, dict) or d.get("cmd") != "world.reset":
            continue
        res = d.get("res")
        if isinstance(res, dict) and res.get("ok") is True:
            return True
    return False


def link(previous: bytes, frame: dict) -> bytes:
    """One step of the chain: SHA-256(previous digest + canonical physical frame)."""
    return hashlib.sha256(previous + canonical(physical(frame))).digest()


@dataclass
class Chain:
    """Hashes of one run's frames, by segment.

    Attributes:
        segments: Final digest (hex) of each segment, in order; segment 0 is start-up.
        frames_per_segment: Number of frames in each segment.
        digests: Digest (hex) after each frame, aligned with the frames.
        segment_of: Segment index of each frame.
    """

    segments: list[str] = field(default_factory=list)
    frames_per_segment: list[int] = field(default_factory=list)
    digests: list[str] = field(default_factory=list)
    segment_of: list[int] = field(default_factory=list)

    @property
    def replay_hash(self) -> str:
        """Hash of every segment after the first world.reset (all of start-up when none)."""
        parts = self.segments[1:] if len(self.segments) > 1 else self.segments
        return hashlib.sha256("".join(parts).encode()).hexdigest()


def chain(frames: list[dict]) -> Chain:
    """Hash a run's frames, restarting the chain at each world.reset.

    Args:
        frames: The run's frames in order (the first is the start-up frame).

    Returns:
        The chain.
    """
    c = Chain()
    digest = CHAIN_START
    seg = 0
    count = 0
    for i, fr in enumerate(frames):
        if i > 0 and starts_segment(fr):
            c.segments.append(digest.hex())
            c.frames_per_segment.append(count)
            digest, count, seg = CHAIN_START, 0, seg + 1
        digest = link(digest, fr)
        count += 1
        c.digests.append(digest.hex())
        c.segment_of.append(seg)
    c.segments.append(digest.hex())
    c.frames_per_segment.append(count)
    return c


@dataclass(frozen=True)
class Divergence:
    """Where two runs first differ.

    Attributes:
        segment: Segment index (counting from the first world.reset as 1).
        index: Frame index within the segment.
        tick_a: Tick of that frame in run A (None when run A has fewer frames).
        tick_b: Tick of that frame in run B.
        detail: A short description of the first differing part.
    """

    segment: int
    index: int
    tick_a: int | None
    tick_b: int | None
    detail: str


def first_divergence(frames_a: list[dict], frames_b: list[dict]) -> Divergence | None:
    """Locate the first frame where two runs differ physically (from segment 1 on).

    Args:
        frames_a: Frames of run A.
        frames_b: Frames of run B.

    Returns:
        The first difference, or None when the compared segments are identical.
    """

    def by_segment(frames: list[dict]) -> list[list[dict]]:
        segs: list[list[dict]] = [[]]
        for i, fr in enumerate(frames):
            if i > 0 and starts_segment(fr):
                segs.append([])
            segs[-1].append(fr)
        return segs[1:] if len(segs) > 1 else segs

    sa, sb = by_segment(frames_a), by_segment(frames_b)
    for s in range(max(len(sa), len(sb))):
        fa = sa[s] if s < len(sa) else []
        fb = sb[s] if s < len(sb) else []
        for i in range(max(len(fa), len(fb))):
            a = physical(fa[i]) if i < len(fa) else None
            b = physical(fb[i]) if i < len(fb) else None
            if a != b:
                return Divergence(
                    s + 1,
                    i,
                    a.get("t") if a else None,
                    b.get("t") if b else None,
                    describe_difference(a, b),
                )
    return None


def describe_difference(a: dict | None, b: dict | None) -> str:
    """A short description of how two physical frames differ."""
    if a is None or b is None:
        return "one run has fewer frames"
    if a.get("t") != b.get("t"):
        return f"tick {a.get('t')} against {b.get('t')}"
    ca, cb = a.get("census") or [], b.get("census") or []
    if len(ca) != len(cb):
        return f"{len(ca)} entities against {len(cb)}"
    for ea, eb in zip(ca, cb):
        if ea != eb:
            keys = sorted(k for k in set(ea) | set(eb) if ea.get(k) != eb.get(k))
            return f"entity {ea.get('id')}: {', '.join(keys)}"
    if a.get("bones") != b.get("bones"):
        return "bone positions"
    if a.get("seats") != b.get("seats"):
        return "seat points"
    return "events"


def write_trace(path: Path, header: dict, frames: list[dict], c: Chain) -> None:
    """Write a run's frames as gzipped JSON lines with their chain digests.

    Line 1 is the header ({"format": FORMAT, ...header, "segments": [...]}); then one
    line per frame: {"f": frame, "h": digest, "s": segment}.

    Args:
        path: Output file (.jsonl.gz).
        header: Run description (play name, run index, arguments, engine).
        frames: The frames.
        c: Their chain (from chain(frames)).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        head = {
            "format": FORMAT,
            **header,
            "segments": c.segments,
            "replay": c.replay_hash,
        }
        f.write(json.dumps(head) + "\n")
        for fr, h, s in zip(frames, c.digests, c.segment_of):
            f.write(json.dumps({"f": fr, "h": h, "s": s}) + "\n")


def read_trace(path: Path) -> tuple[dict, list[dict]]:
    """Read a trace file written by write_trace.

    Returns:
        (header, frames).
    """
    with gzip.open(path, "rt", encoding="utf-8") as f:
        header = json.loads(f.readline())
        frames = [json.loads(line)["f"] for line in f if line.strip()]
    return header, frames
