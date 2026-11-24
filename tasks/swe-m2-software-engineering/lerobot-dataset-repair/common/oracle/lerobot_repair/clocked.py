"""Recover common episode timelines from camera boot clocks and sequence evidence."""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

from .dataset import Clip, Dataset, Json, decode, fingerprint, natural, read_dataset, write_report
from .publication import publish_reviewed


Pulse = tuple[int, int]
Clock = tuple[int, Fraction, Fraction]
Bounds = tuple[int, int]


@dataclass(frozen=True)
class Option:
    """One jointly feasible clip tuple and its inclusive integer start interval."""

    clips: tuple[Clip, ...]
    bounds: Bounds


@dataclass
class Capture:
    """Validated calibration and capture evidence independent of native metadata."""

    sync_tolerance: int
    frame_tolerance: int
    drift: int
    cameras: dict[str, list[Json]]
    episodes: dict[int, Json]


def integer(value: object) -> bool:
    """Validate an integer clock reading without a Boolean coercion."""
    return type(value) is int


def positive_span(row: Json, first: str, last: str) -> bool:
    """Check an inclusive time interval in integer nanoseconds."""
    return integer(row.get(first)) and integer(row.get(last)) and row[first] <= row[last]


def parse_capture(data: Dataset, payload: bytes) -> Capture:
    """Validate a clock journal and its unique episode, boot and shard identities."""
    raw = json.loads(payload)
    if not isinstance(raw, dict) or not integer(raw.get("schema_version")) or raw["schema_version"] != 1:
        raise ValueError("Invalid clock journal schema")
    limits = [raw.get(key) for key in ("sync_tolerance_ns", "frame_tolerance_ns", "max_drift_ppm")]
    if not all(natural(value) for value in limits) or limits[1] * 2 * data.fps >= 10**9 or limits[2] > 50_000:
        raise ValueError("Invalid clock journal tolerances")
    cameras = raw.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(data.videos) or not 1 <= len(cameras) <= 3:
        raise ValueError("Camera journal must cover the dataset cameras")
    for epochs in cameras.values():
        if not isinstance(epochs, list) or not epochs:
            raise ValueError("Each camera needs boot epochs")
        seen_ids, seen_shards = set(), set()
        for epoch in epochs:
            if not isinstance(epoch, dict):
                raise ValueError("Invalid epoch")
            key = epoch.get("id")
            if not isinstance(key, str) or not key or key in seen_ids:
                raise ValueError("Invalid or repeated epoch ID")
            seen_ids.add(key)
            pulses, shards = epoch.get("pulses"), epoch.get("shards")
            if not isinstance(pulses, list) or not isinstance(shards, list):
                raise ValueError("Invalid epoch arrays")
            seen_pulses = set()
            for pulse in pulses:
                if (not isinstance(pulse, dict) or not integer(pulse.get("sensor_ns"))
                        or not integer(pulse.get("reference_ns")) or pulse["sensor_ns"] in seen_pulses):
                    raise ValueError("Invalid or repeated sync pulse")
                seen_pulses.add(pulse["sensor_ns"])
            for shard in shards:
                if not isinstance(shard, dict):
                    raise ValueError("Invalid camera shard")
                pair = shard.get("chunk_index"), shard.get("file_index")
                stamps = shard.get("sensor_ns")
                if (not all(natural(value) for value in pair) or pair in seen_shards
                        or not isinstance(stamps, list) or not stamps or not all(map(integer, stamps))
                        or any(a >= b for a, b in zip(stamps, stamps[1:]))):
                    raise ValueError("Repeated shard or invalid frame stamps")
                seen_shards.add(pair)
    values = raw.get("episodes")
    if not isinstance(values, list):
        raise ValueError("Expected capture episodes")
    episodes = {}
    for row in values:
        if (not isinstance(row, dict) or not natural(row.get("episode_index")) or row["episode_index"] in episodes
                or type(row.get("committed")) is not bool or not positive_span(row, "earliest_ns", "latest_ns")):
            raise ValueError("Invalid or repeated capture episode")
        episodes[row["episode_index"]] = row
    return Capture(*limits, cameras, episodes)


def slope_ok(slope: Fraction, drift: int) -> bool:
    """Check the physical drift envelope in exact parts per million."""
    return abs(slope - 1) * 1_000_000 <= drift and slope > 0


def fit_clock(pulses: list[Pulse], tolerance: int, drift: int) -> Clock | None:
    """Find one best pulse consensus and refit its affine clock without epoch cancellation."""
    best: set[frozenset[int]] = set()
    support = 2
    for (x, y), (u, v) in combinations(pulses, 2):
        slope = Fraction(v - y, u - x)
        if not slope_ok(slope, drift):
            continue
        inliers = frozenset(index for index, (a, b) in enumerate(pulses) if abs(y + slope * (a - x) - b) <= tolerance)
        if len(inliers) > support:
            best, support = {inliers}, len(inliers)
        elif len(inliers) == support and support >= 3:
            best.add(inliers)
    if len(best) != 1:
        return None
    sample = [pulses[index] for index in best.pop()]
    origin = sample[0][0]
    xx = [x - origin for x, _ in sample]
    yy = [y for _, y in sample]
    n = len(sample)
    sum_x, sum_y = sum(xx), sum(yy)
    slope = Fraction(n * sum(x * y for x, y in zip(xx, yy, strict=True)) - sum_x * sum_y,
                     n * sum(x * x for x in xx) - sum_x * sum_x)
    intercept = Fraction(sum_y, n) - slope * Fraction(sum_x, n)
    if not slope_ok(slope, drift) or any(abs(intercept + slope * x - y) > tolerance
                                         for x, y in zip(xx, yy, strict=True)):
        return None
    return origin, slope, intercept


def timed_shards(data: Dataset, capture: Capture) -> dict[str, dict[tuple[int, int], list[int]]]:
    """Index trusted master times only for physically decodable calibrated shards."""
    tracks = {}
    for camera, epochs in sorted(capture.cameras.items()):
        slots = {}
        for epoch in epochs:
            pulses = [(value["sensor_ns"], value["reference_ns"]) for value in epoch["pulses"]]
            clock = fit_clock(pulses, capture.sync_tolerance, capture.drift)
            if clock is None:
                continue
            origin, slope, intercept = clock
            for shard in epoch["shards"]:
                pair = shard["chunk_index"], shard["file_index"]
                path = data.videos[camera].get(pair)
                decoded = decode(path, data.fps, hashes=False) if path else None
                if decoded and decoded[0] == len(shard["sensor_ns"]):
                    slots[pair] = [round(intercept + slope * (stamp - origin)) for stamp in shard["sensor_ns"]]
        tracks[camera] = slots
    return tracks


def phase(index: int, fps: int) -> int:
    """Return the exact nominal master-clock spacing for a relative frame index."""
    return round(Fraction(index * 1_000_000_000, fps))


def clip_options(slots: dict, phases: list[int], limits: Bounds, tolerance: int) -> list[tuple[Clip, Bounds]]:
    """Intersect first-frame timing bounds with every aligned camera frame."""
    matches = []
    length = len(phases)
    for (chunk, file), stamps in slots.items():
        for first, stamp in enumerate(stamps[:len(stamps) - length + 1] if len(stamps) >= length else []):
            lo = max(limits[0], stamp - tolerance)
            hi = min(limits[1], stamp + tolerance)
            if lo > hi:
                continue
            for index in range(1, length):
                anchor = stamps[first + index] - phases[index]
                lo, hi = max(lo, anchor - tolerance), min(hi, anchor + tolerance)
                if lo > hi:
                    break
            if lo <= hi:
                matches.append(((chunk, file, first, first + length), (lo, hi)))
    return matches


def shared_options(tracks: dict[str, dict], phases: list[int], limits: Bounds, tolerance: int) -> list[Option]:
    """Enumerate all camera tuples with a common master-clock episode start."""
    choices = [Option((), limits)]
    for slots in tracks.values():
        camera = clip_options(slots, phases, limits, tolerance)
        choices = [
            Option(option.clips + (clip,), (max(lo, option.bounds[0]), min(hi, option.bounds[1])))
            for option in choices
            for clip, (lo, hi) in camera
            if max(lo, option.bounds[0]) <= min(hi, option.bounds[1])
        ]
    return choices


def maximum(cases: list[tuple[int, int, list[Option]]], forbidden: tuple[int, Option] | None = None) -> int:
    """Maximize assigned episodes, retaining the earliest viable end for each count."""
    earliest: list[int | None] = [None]
    for episode, duration, choices in cases:
        after = earliest + [None]
        for option in choices:
            if forbidden == (episode, option):
                continue
            lo, hi = option.bounds
            for count, current in enumerate(earliest):
                if current is None and count > 0:
                    continue
                start = lo if current is None else max(current, lo)
                if start <= hi:
                    end = start + duration
                    if after[count + 1] is None or end < after[count + 1]:
                        after[count + 1] = end
        if after[-1] is None:
            after.pop()
        earliest = after
    return len(earliest) - 1


def recover_plan(data: Dataset, evidence: bytes) -> Json:
    """Keep only mandatory native clip identities across all maximum assignments."""
    capture = parse_capture(data, evidence)
    tracks = timed_shards(data, capture)
    decisions, cases = {}, []
    for episode in sorted(data.ids | set(capture.episodes)):
        entry = capture.episodes.get(episode)
        reason = "UNCOMMITTED"
        if entry and entry["committed"]:
            reason = "INVALID_FRAME_ROWS"
            if data.usable(episode):
                length = len(data.frames[episode].rows)
                phases = [phase(index, data.fps) for index in range(length)]
                limits = (entry["earliest_ns"], entry["latest_ns"])
                options = shared_options(tracks, phases, limits, capture.frame_tolerance)
                reason = "UNRESOLVED_ASSIGNMENT" if options else "NO_TIMED_CLIP"
                if options:
                    cases.append((episode, phase(length, data.fps), options))
        decisions[episode] = {"episode_index": episode, "status": "quarantine", "reasons": [reason], "videos": {}}
    count = maximum(cases)
    for episode, _, choices in cases:
        for option in choices:
            if maximum(cases, forbidden=(episode, option)) < count:
                decisions[episode].update(status="keep", reasons=[], videos=dict(zip(tracks, option.clips, strict=True)))
                break
    return {"schema_version": 1, "source_sha256": fingerprint(data.root), "ledger_sha256": sha256(evidence).hexdigest(),
            "matched_count": count, "episodes": list(decisions.values())}


def time_plan(dataset: Path, ledger: Path, output: Path) -> None:
    """Preview a clock-driven repair without changing its recording or journal."""
    if output.resolve().is_relative_to(dataset.resolve()) or output.resolve() == ledger.resolve():
        raise ValueError("Output must be separate from capture inputs")
    write_report(output, recover_plan(read_dataset(dataset), ledger.read_bytes()))


def time_apply(dataset: Path, ledger: Path, proposal: Path, output: Path) -> None:
    """Re-derive the approved clock plan and publish it through the native writer."""
    publish_reviewed(dataset, ledger, proposal, output, recover_plan)
