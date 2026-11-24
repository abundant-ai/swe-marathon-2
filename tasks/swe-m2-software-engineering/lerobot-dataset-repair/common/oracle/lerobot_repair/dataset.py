"""Read native v3.0 recording files and audit their relational invariants."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any

import av
import pyarrow as pa
import pyarrow.parquet as pq


Json = dict[str, Any]
Shard = tuple[int, int]
Clip = tuple[int, int, int, int]
TRACKED = ("data", "meta", "videos")
TIMESTAMP_TOLERANCE = 1e-4


def read_json(path: Path) -> Json:
    """Require one JSON object from a local recording sidecar."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def canonical(value: object) -> bytes:
    """Encode a deterministic compact JSON value for content fingerprints."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_report(path: Path, value: Json) -> None:
    """Atomically replace a report only after complete serialization."""
    with NamedTemporaryFile(dir=path.parent, prefix=".report-", delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(canonical(value) + b"\n")
            stream.close()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def natural(value: object) -> bool:
    """Check a nonnegative JSON integer without accepting Boolean values."""
    return type(value) is int and value >= 0


def number(value: object) -> bool:
    """Check for a finite JSON scalar in physical or timing units."""
    return type(value) in (int, float) and math.isfinite(value)


def shard_name(pair: Shard, suffix: str) -> Path:
    """Format the standard v3.0 native chunk and file path."""
    chunk, file = pair
    return Path(f"chunk-{chunk:03d}", f"file-{file:03d}.{suffix}")


def shards(folder: Path, suffix: str) -> list[tuple[Shard, Path]]:
    """Enumerate native shards in numeric file order."""
    found: dict[Shard, Path] = {}
    for path in folder.glob(f"chunk-*/file-*.{suffix}"):
        chunk = re.fullmatch(r"chunk-(\d{3,})", path.parent.name)
        name = re.fullmatch(rf"file-(\d{{3,}})\.{suffix}", path.name)
        if chunk and name and path.is_file():
            key = int(chunk[1]), int(name[1])
            if key in found:
                raise ValueError(f"Multiple files represent the same shard in {folder}")
            found[key] = path
    return sorted(found.items())


def file_index(root: Path) -> dict[str, Path]:
    """Find regular native files, rejecting links and nonportable paths."""
    result = {}
    for name in TRACKED:
        directory = root / name
        if directory.is_symlink():
            raise ValueError(f"Symbolic link in dataset at {name}")
        for path in directory.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or "\n" in relative or "\t" in relative:
                raise ValueError(f"Unsupported dataset file {relative}")
            if path.is_file():
                result[relative] = path
            elif not path.is_dir():
                raise ValueError(f"Unsupported dataset file {relative}")
    return result


def fingerprint(root: Path) -> str:
    """Hash sorted native path and byte-digest records without buffering large files."""
    result = sha256()
    for name, path in sorted(file_index(root).items()):
        with path.open("rb") as stream:
            digest = sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result.update(f"{name}\t{digest.hexdigest()}\n".encode())
    return result.hexdigest()


def decode(path: Path, fps: int, *, hashes: bool) -> tuple[int, tuple[str, ...]] | None:
    """Read one native MP4 and optionally identify every decoded RGB frame."""
    digests = []
    count = 0
    try:
        with av.open(str(path), mode="r") as container:
            if len(container.streams.video) != 1:
                return None
            for frame in container.decode(video=0):
                if frame.time is None or abs(frame.time - count / fps) > TIMESTAMP_TOLERANCE:
                    return None
                if hashes:
                    digests.append(sha256(frame.to_ndarray(format="rgb24").tobytes()).hexdigest())
                count += 1
    except (OSError, ValueError, av.FFmpegError):
        return None
    return (count, tuple(digests)) if count else None


@dataclass(frozen=True)
class Episode:
    """Frame rows for one recorded episode and the physical shards they occupy."""

    rows: list[Json]
    shards: list[Shard]

    def valid(self, fps: int, duplicates: set[int]) -> bool:
        """Check episode geometry using its native order, independent of metadata."""
        if not self.rows or len(set(self.shards)) != 1:
            return False
        first = self.rows[0]["index"]
        return natural(first) and all(
            natural(row["index"]) and row["index"] == first + frame and row["index"] not in duplicates
            and natural(row["frame_index"]) and row["frame_index"] == frame
            and number(row["timestamp"]) and abs(row["timestamp"] - frame / fps) <= TIMESTAMP_TOLERANCE
            for frame, row in enumerate(self.rows)
        )


@dataclass
class Dataset:
    """Native dataset observations, divided between frame truth and claims."""

    root: Path
    info: Json
    frames: dict[int, Episode]
    metadata: dict[int, list[Json]]
    videos: dict[str, dict[Shard, Path]]
    indices: list[object]
    duplicates: set[int]
    frame_schema: pa.Schema | None

    @property
    def fps(self) -> int:
        """Return the declared positive integer frame rate."""
        return self.info["fps"]

    @property
    def ids(self) -> set[int]:
        """Return every episode ID seen in either of the native tables."""
        return set(self.frames) | set(self.metadata)

    def usable(self, episode: int) -> bool:
        """Check whether one episode has unique and internally consistent frame rows."""
        return episode in self.frames and self.frames[episode].valid(self.fps, self.duplicates)


def episode_id(row: Json) -> int:
    """Read the identity common to both native Parquet tables."""
    value = row.get("episode_index")
    if not natural(value):
        raise ValueError("Missing or invalid episode_index")
    return value


def read_dataset(root: Path) -> Dataset:
    """Read and index native files from a local v3.0 directory."""
    file_index(root)
    info = read_json(root / "meta/info.json")
    if (info.get("codebase_version") != "v3.0" or not natural(info.get("fps")) or info["fps"] == 0
            or not isinstance(info.get("features"), dict)):
        raise ValueError("Expected fixed-rate LeRobotDataset v3.0")
    cameras = []
    for key, feature in info["features"].items():
        if not isinstance(feature, dict):
            raise ValueError("Invalid feature declaration")
        if feature.get("dtype") == "video":
            if key in (".", "..") or "/" in key or "\\" in key or not key:
                raise ValueError("Invalid camera key")
            cameras.append(key)
    videos = {key: dict(shards(root / "videos" / key, "mp4")) for key in sorted(cameras)}
    frames: dict[int, Episode] = {}
    metadata: dict[int, list[Json]] = defaultdict(list)
    indices = []
    schema = None
    for pair, path in shards(root / "data", "parquet"):
        table = pq.ParquetFile(path).read()
        if schema is None:
            schema = table.schema
        if not {"episode_index", "frame_index", "index", "timestamp", "task_index"} <= set(table.column_names):
            raise ValueError(f"Incomplete frame table {path.name}")
        for row in table.to_pylist():
            episode = frames.setdefault(episode_id(row), Episode([], []))
            episode.rows.append(row)
            episode.shards.append(pair)
            indices.append(row["index"])
    metadata_columns = {"episode_index", "length", "data/chunk_index", "data/file_index",
                        "dataset_from_index", "dataset_to_index"}
    metadata_columns.update(f"videos/{camera}/{key}" for camera in cameras
                            for key in ("chunk_index", "file_index", "from_timestamp", "to_timestamp"))
    for _, path in shards(root / "meta/episodes", "parquet"):
        table = pq.ParquetFile(path).read()
        if not metadata_columns <= set(table.column_names):
            raise ValueError(f"Incomplete episode table {path.name}")
        for row in table.to_pylist():
            metadata[episode_id(row)].append(row)
    duplicates = {index for index, count in Counter(index for index in indices if natural(index)).items() if count > 1}
    return Dataset(root, info, frames, metadata, videos, indices, duplicates, schema)


def has_data_range(episode: Episode, metadata: Json) -> bool:
    """Compare a claimed native frame interval with independent data rows."""
    first = episode.rows[0]["index"]
    values = {"length": len(episode.rows), "data/chunk_index": episode.shards[0][0],
              "data/file_index": episode.shards[0][1], "dataset_from_index": first,
              "dataset_to_index": first + len(episode.rows)}
    return all(natural(metadata.get(key)) and metadata[key] == value for key, value in values.items())


def video_index(value: object, fps: int) -> int | None:
    """Read a timestamp on the declared nonnegative frame grid."""
    if not number(value) or value < 0 or not math.isfinite(value * fps):
        return None
    index = round(value * fps)
    return index if abs(index / fps - value) <= TIMESTAMP_TOLERANCE else None


def video_range(metadata: Json, camera: str, fps: int, length: int) -> Clip | None:
    """Normalize one episode's video metadata into a candidate absolute frame interval."""
    prefix = f"videos/{camera}/"
    chunk, file = (metadata.get(prefix + key) for key in ("chunk_index", "file_index"))
    first, last = (video_index(metadata.get(prefix + key), fps) for key in ("from_timestamp", "to_timestamp"))
    if not natural(chunk) or not natural(file) or first is None or last is None or last - first != length:
        return None
    return chunk, file, first, last


def overlaps(claims: list[tuple[int, Clip]]) -> set[int]:
    """Return every episode involved in overlapping claims on one camera stream."""
    bad = set()
    furthest: tuple[int, Clip] | None = None
    for episode, clip in sorted(claims, key=lambda record: record[1]):
        if furthest is None or furthest[1][:2] != clip[:2]:
            furthest = episode, clip
            continue
        previous, old = furthest
        if clip[2] < old[3]:
            bad.update((episode, previous))
        if clip[3] > old[3]:
            furthest = episode, clip
    return bad


def audit(dataset: Path, output: Path) -> None:
    """Write an independent inventory of data, episode, and video range issues."""
    if output.resolve().is_relative_to(dataset.resolve()):
        raise ValueError("The report must be separate from the recording")
    data = read_dataset(dataset)
    problems = []
    count = len(data.indices)
    if any(not natural(value) or value != index for index, value in enumerate(data.indices)):
        problems.append("INDEX_LAYOUT")
    if (not natural(data.info.get("total_frames")) or data.info["total_frames"] != count
            or not natural(data.info.get("total_episodes")) or data.info["total_episodes"] != len(data.frames)):
        problems.append("TOTALS")
    issues: dict[int, set[str]] = {episode: set() for episode in data.ids}
    claimed: dict[str, list[tuple[int, Clip]]] = defaultdict(list)
    counts: dict[Path, int] = {}
    for episode, codes in sorted(issues.items()):
        if episode not in data.frames:
            codes.add("NO_FRAME_ROWS")
        elif not data.usable(episode):
            codes.add("INVALID_FRAME_ROWS")
        rows = data.metadata.get(episode, [])
        if not rows:
            codes.add("NO_METADATA")
        elif len(rows) > 1:
            codes.add("DUPLICATE_METADATA")
        elif data.usable(episode):
            if not has_data_range(data.frames[episode], rows[0]):
                codes.add("DATA_RANGE")
            for camera, paths in data.videos.items():
                clip = video_range(rows[0], camera, data.fps, len(data.frames[episode].rows))
                path = paths.get(clip[:2]) if clip else None
                if path is not None and path not in counts:
                    decoded = decode(path, data.fps, hashes=False)
                    counts[path] = decoded[0] if decoded else 0
                if path is None or clip[3] > counts[path]:
                    codes.add(f"VIDEO_RANGE/{camera}")
                else:
                    claimed[camera].append((episode, clip))
    for camera, clips in claimed.items():
        for episode in overlaps(clips):
            issues[episode].add(f"VIDEO_OVERLAP/{camera}")
    write_report(output, {"schema_version": 1, "frame_rows": count,
                          "metadata_rows": sum(map(len, data.metadata.values())), "dataset_issues": sorted(problems),
                          "episodes": [{"episode_index": episode, "issues": sorted(codes)}
                                       for episode, codes in sorted(issues.items())]})
