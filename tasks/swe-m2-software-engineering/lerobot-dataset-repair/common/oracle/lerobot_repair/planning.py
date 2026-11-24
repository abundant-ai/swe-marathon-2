"""Find admissible footage from independent recorder evidence."""

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re

from .dataset import Clip, Dataset, Json, decode, fingerprint, natural, overlaps, read_dataset, write_report


def parse_ledger(payload: bytes) -> dict[int, Json]:
    """Reject ambiguous identities and malformed journal evidence."""
    value = json.loads(payload)
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported ledger schema")
    entries = value.get("episodes")
    if not isinstance(entries, list):
        raise ValueError("Expected ledger episode array")
    ledger = {}
    for item in entries:
        if not isinstance(item, dict) or not natural(item.get("episode_index")):
            raise ValueError("Invalid ledger episode")
        episode = item["episode_index"]
        if episode in ledger or type(item.get("committed")) is not bool or not isinstance(item.get("cameras"), dict):
            raise ValueError("Invalid or duplicated ledger episode")
        for camera, anchors in item["cameras"].items():
            if not camera or not isinstance(anchors, list):
                raise ValueError("Invalid camera evidence")
            seen = set()
            for anchor in anchors:
                if not isinstance(anchor, dict) or not natural(anchor.get("frame")):
                    raise ValueError("Invalid frame anchor")
                frame, digest = anchor["frame"], anchor.get("sha256")
                if frame in seen or not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
                    raise ValueError("Repeated frame or invalid digest")
                seen.add(frame)
        ledger[episode] = item
    return ledger


def indexed_video(data: Dataset) -> dict[str, dict[str, list[tuple[int, int, int]]]]:
    """Build an inverted index of frame witnesses for every usable camera shard."""
    cameras = {}
    for camera, files in data.videos.items():
        hits = defaultdict(list)
        for (chunk, file), path in files.items():
            decoded = decode(path, data.fps, hashes=True)
            if decoded is None:
                continue
            for index, digest in enumerate(decoded[1]):
                hits[digest].append((chunk, file, index))
            # Use an impossible SHA-256 key to store each file's decoded length.
            hits[""].append((chunk, file, decoded[0]))
        cameras[camera] = hits
    return cameras


def clip_matches(length: int, anchors: list[Json], hits: dict[str, list[tuple[int, int, int]]]) -> set[Clip]:
    """Intersect candidate clip starts implied by all anchors and bound each window."""
    starts = None
    for anchor in anchors:
        offset = anchor["frame"]
        matches = {(chunk, file, frame - offset) for chunk, file, frame in hits.get(anchor["sha256"], ())
                   if frame >= offset}
        starts = matches if starts is None else starts & matches
        if not starts:
            return set()
    size = {(chunk, file): count for chunk, file, count in hits.get("", ())}
    return {(chunk, file, frame, frame + length) for chunk, file, frame in starts
            if frame + length <= size[chunk, file]}


def make_plan(data: Dataset, evidence: bytes) -> Json:
    """Compose committed episodes whose frame rows and all camera claims are uniquely supported."""
    ledger = parse_ledger(evidence)
    hits = indexed_video(data)
    claims = defaultdict(list)
    decisions = {}
    for episode in sorted(data.ids | set(ledger)):
        commit = ledger.get(episode)
        clips = {}
        reasons = []
        if commit is None or not commit["committed"]:
            reasons.append("UNCOMMITTED")
        elif not data.usable(episode):
            reasons.append("INVALID_FRAME_ROWS")
        else:
            length = len(data.frames[episode].rows)
            for camera, sources in hits.items():
                anchors = commit["cameras"].get(camera, [])
                if len(anchors) < min(length, 2) or any(anchor["frame"] >= length for anchor in anchors):
                    reasons.append(f"NO_EVIDENCE/{camera}")
                    continue
                found = clip_matches(length, anchors, sources)
                if not found:
                    reasons.append(f"NO_CLIP/{camera}")
                elif len(found) > 1:
                    reasons.append(f"AMBIGUOUS_CLIP/{camera}")
                else:
                    clips[camera] = found.pop()
        if not reasons:
            for camera, clip in clips.items():
                claims[camera].append((episode, clip))
        decisions[episode] = (reasons, clips)
    for camera, intervals in claims.items():
        for episode in overlaps(intervals):
            decisions[episode][0].append(f"CLIP_CONFLICT/{camera}")
    return {
        "schema_version": 1,
        "source_sha256": fingerprint(data.root),
        "ledger_sha256": sha256(evidence).hexdigest(),
        "episodes": [{"episode_index": episode, "status": "quarantine" if reasons else "keep",
                      "reasons": sorted(reasons), "videos": {} if reasons else clips}
                     for episode, (reasons, clips) in sorted(decisions.items())],
    }


def plan(dataset: Path, ledger: Path, output: Path) -> None:
    """Write a deterministic plan without modifying the original recording or journal."""
    if output.resolve().is_relative_to(dataset.resolve()) or output.resolve() == ledger.resolve():
        raise ValueError("The repair plan output must be separate from the input data")
    write_report(output, make_plan(read_dataset(dataset), ledger.read_bytes()))
