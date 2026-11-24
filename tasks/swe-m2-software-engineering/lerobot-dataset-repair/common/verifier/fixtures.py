"""Create native v3.0 recordings from an attributed table excerpt and authored video."""

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path

import av
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


CAMERAS = ("observation.images.front", "observation.images.wrist")
FEATURES = {"action": {"dtype": "float32", "shape": [6], "names": None},
            "observation.state": {"dtype": "float32", "shape": [6], "names": None}}
FPS = 10


@dataclass
class Fixture:
    """Capture files and independent file/episode expectations."""

    root: Path
    journal: Path
    frames: dict
    clips: dict
    audit: dict
    reasons: dict
    ordered: list[int]
    schema: pa.Schema


def dump(path: Path, document: object) -> Path:
    """Write a fixture sidecar in readable UTF-8."""
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def parquet(path: Path, data: list[dict], *, schema: pa.Schema | None = None) -> None:
    """Write a native Parquet table with its requested physical schema."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(data, schema=schema), path)


def path_for(root: Path, family: str, chunk: int, file: int, extension: str) -> Path:
    """Form one native locator from its chunk and file IDs."""
    return root / family / f"chunk-{chunk:03d}" / f"file-{file:03d}.{extension}"


def encode(path: Path, images: list[int]) -> list[str]:
    """Write independently identifiable lossless RGB video and read actual decoded bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("libx264rgb", rate=FPS)
        stream.width = 32
        stream.height = 32
        stream.pix_fmt = "rgb24"
        stream.options = {"crf": "0", "preset": "ultrafast"}
        for index, code in enumerate(images):
            rng = np.random.default_rng(code)
            image = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(image, format="rgb24")
            frame.pts = index
            frame.time_base = Fraction(1, FPS)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    with av.open(str(path)) as container:
        return [sha256(frame.to_ndarray(format="rgb24").tobytes()).hexdigest() for frame in container.decode(video=0)]


def fixture(parent: Path, asset: Path, variant: int = 0) -> Fixture:
    """Plant coupled corruption with independently known committed footage and table rows."""
    root = parent / "recording"
    (root / "meta").mkdir(parents=True)
    source = pq.ParquetFile(asset).read()
    samples = source.to_pylist()
    schema = source.schema.remove_metadata().append(pa.field("motor_temperature_c", pa.float32()))
    ids = [17, 24, 31, 41, 55, 67, 89, 97, 112, 133, 244]
    ids = [value + variant * 1000 for value in ids]
    clean, stale, aborted, ambiguous, missing, conflict_a, conflict_b, bad_rows, no_evidence, no_clip, orphan = ids
    lengths = dict(zip(ids, (4, 5, 4, 4, 3, 4, 4, 4, 4, 4, 0), strict=True))
    aborted_ids = {aborted}
    if variant:
        lengths[missing] = 1
        aborted_ids.update((clean, conflict_b))
    frames = {}
    positions = {}
    first = 0
    shard_keys = [(0, 4 + variant), (2, 1 + variant)]
    shards = [[], []]
    for index, episode in enumerate(ids[:-1]):
        if episode == bad_rows:
            first += 3
        length = lengths[episode]
        positions[episode] = first
        rows = []
        for frame in range(length):
            sample = samples[(first + frame) % len(samples)]
            rows.append(dict(sample, index=first + frame, episode_index=episode,
                             frame_index=frame if episode != bad_rows or frame != 3 else 2,
                             timestamp=frame / FPS, task_index=(index + frame // 3) % 2,
                             motor_temperature_c=24.5 + index + frame / 4))
        first += length
        shard = 0 if index < 4 else 1
        frames[episode] = pa.Table.from_pylist(rows, schema=schema).to_pylist()
        shards[shard].extend(frames[episode])
    for (chunk, file), rows in zip(shard_keys, shards, strict=True):
        parquet(path_for(root, "data", chunk, file, "parquet"), rows, schema=schema)

    clips = {episode: {} for episode in ids}
    witnesses = {}
    for camera_id, camera in enumerate(CAMERAS):
        shared_chunks = [(camera_id * 2, 3 + variant), (camera_id * 2 + 1, 8 + variant)]
        images = [[], []]
        for index, episode in enumerate(ids[:-1]):
            if episode == conflict_b:
                chunk, file, lower, upper = clips[conflict_a][camera]
                clips[episode][camera] = [chunk, file, lower + 1, upper + 1]
                continue
            slot = index % 2
            chunk, file = shared_chunks[slot]
            stream = images[slot]
            lower = len(stream)
            length = lengths[episode]
            color_seed = 10_000 + variant * 1_000 + camera_id * 300 + index * 10
            stream.extend(range(color_seed, color_seed + length + (episode == conflict_a)))
            clips[episode][camera] = [chunk, file, lower, lower + length]
        if camera_id == 0:
            # Duplicate a whole semantic clip in another file, with byte-identical decoded frames.
            _, _, start, end = clips[ambiguous][camera]
            images[0].extend(images[1][start:end])
        for (chunk, file), stream in zip(shared_chunks, images, strict=True):
            witnesses[camera, chunk, file] = encode(path_for(root, "videos/" + camera, chunk, file, "mp4"), stream)

    metadata = []
    for index, episode in enumerate(ids):
        if episode in (aborted, missing):
            continue
        if episode == orphan:
            metadata.append(dict(metadata[0], episode_index=orphan))
            continue
        chunk, file = shard_keys[index >= 4]
        start = positions[episode]
        row = {"episode_index": episode, "tasks": ["Pick", "Place"], "length": lengths[episode],
               "dataset_from_index": start, "dataset_to_index": start + lengths[episode],
               "data/chunk_index": chunk, "data/file_index": file}
        for camera, bounds in clips[episode].items():
            a, b, c, d = bounds
            if episode == stale and camera == CAMERAS[0]:
                a, b, c, _ = clips[clean][camera]
                d = c + lengths[episode]
            prefix = "videos/" + camera + "/"
            row.update({prefix + "chunk_index": a, prefix + "file_index": b, prefix + "from_timestamp": c / FPS,
                        prefix + "to_timestamp": d / FPS + (0.04 if episode == stale and camera == CAMERAS[1] else 0)})
        if episode == stale:
            row["dataset_to_index"] += 1
        metadata.append(row)
        if episode == no_clip:
            metadata.append(dict(row))
    parquet(path_for(root, "meta/episodes", 0, 1 + variant, "parquet"), metadata[:-1])
    # A native metadata shard can contain a complete row with a missing recording.
    parquet(path_for(root, "meta/episodes", 4, 0, "parquet"), [metadata[-1]])
    # Native LeRobot stores the task text as the named pandas index.
    task_schema = pa.schema([("task_index", pa.int64()), ("task", pa.string())])
    pandas_index = {
        "index_columns": ["task"],
        "column_indexes": [{"name": None, "field_name": None, "pandas_type": "unicode", "numpy_type": "object",
                            "metadata": {"encoding": "UTF-8"}}],
        "columns": [{"name": "task_index", "field_name": "task_index", "pandas_type": "int64",
                     "numpy_type": "int64", "metadata": None},
                    {"name": "task", "field_name": "task", "pandas_type": "unicode", "numpy_type": "object",
                     "metadata": None}],
        "creator": {"library": "pyarrow", "version": pa.__version__}, "pandas_version": "2.2.3",
    }
    parquet(root / "meta/tasks.parquet", [{"task": "Pick", "task_index": 0}, {"task": "Place", "task_index": 1}],
            schema=task_schema.with_metadata({b"pandas": json.dumps(pandas_index).encode()}))
    features = dict(FEATURES)
    features.update({camera: {"dtype": "video", "shape": [32, 32, 3], "names": ["height","width","channels"],
                            "info": {"video.height": 32, "video.width": 32, "video.codec": "h264",
                                     "video.pix_fmt": "gbrp", "video.fps": FPS, "video.channels": 3,
                                     "video.is_depth_map": False, "has_audio": False}} for camera in CAMERAS})
    features["motor_temperature_c"] = {"dtype": "float32", "shape": [1], "names": None}
    for field, dtype in (("index", "int64"), ("episode_index", "int64"), ("frame_index", "int64"),
                         ("timestamp", "float32"), ("task_index", "int64")):
        features[field] = {"dtype": dtype, "shape": [1], "names": None}
    dump(root / "meta/info.json", {"codebase_version": "v3.0", "robot_type": "so_follower",
         "total_episodes": 42, "total_frames": 299, "total_tasks": 2, "fps": FPS, "features": features,
         "chunks_size": 1000, "data_files_size_in_mb": 100, "video_files_size_in_mb": 200,
         "splits": {"train": "0:42"}, "data_path": "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet",
         "video_path": "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"})
    dump(root / "meta/stats.json", {"action": {"count": [299]}, CAMERAS[0]: {"count": [299]}})
    records = []
    for episode in ids:
        camera_evidence = {}
        for camera, (chunk, file, start, stop) in clips[episode].items():
            if episode == no_evidence and camera == CAMERAS[1] and not variant:
                continue
            decoded = witnesses[camera, chunk, file]
            camera_evidence[camera] = [
                {"frame": offset, "sha256": "a" * 64 if episode == no_clip and camera == CAMERAS[0]
                 else decoded[start + offset]}
                for offset in sorted({0, stop - start - 1})]
        records.append({"episode_index": episode, "committed": episode not in aborted_ids, "cameras": camera_evidence})
    journal = dump(parent / "journal.json", {"schema_version": 1, "episodes": records[::-1]})
    audits = {
        clean: ["VIDEO_OVERLAP/" + CAMERAS[0]], stale: ["DATA_RANGE", "VIDEO_OVERLAP/" + CAMERAS[0],
                                                      "VIDEO_RANGE/" + CAMERAS[1]],
        aborted: ["NO_METADATA"], ambiguous: [], missing: ["NO_METADATA"],
        conflict_a: ["VIDEO_OVERLAP/" + camera for camera in CAMERAS],
        conflict_b: ["VIDEO_OVERLAP/" + camera for camera in CAMERAS], bad_rows: ["INVALID_FRAME_ROWS"],
        no_evidence: [], no_clip: ["DUPLICATE_METADATA"], orphan: ["NO_FRAME_ROWS"],
    }
    reasons = {
        clean: [], stale: [], aborted: ["UNCOMMITTED"], ambiguous: ["AMBIGUOUS_CLIP/" + CAMERAS[0]],
        missing: [], conflict_a: ["CLIP_CONFLICT/" + camera for camera in CAMERAS],
        conflict_b: ["CLIP_CONFLICT/" + camera for camera in CAMERAS], bad_rows: ["INVALID_FRAME_ROWS"],
        no_evidence: ["NO_EVIDENCE/" + CAMERAS[1]], no_clip: ["NO_CLIP/" + CAMERAS[0]],
        orphan: ["INVALID_FRAME_ROWS"],
    }
    if variant:
        # A second recording has one uncommitted conflicting claimant and an
        # independently witnessed camera. Its recoverable episode set is different.
        reasons[clean] = reasons[conflict_b] = ["UNCOMMITTED"]
        reasons[conflict_a] = reasons[no_evidence] = []
    audit = {"schema_version": 1, "frame_rows": sum(lengths.values()), "metadata_rows": len(metadata),
             "dataset_issues": ["INDEX_LAYOUT", "TOTALS"],
             "episodes": [{"episode_index": episode, "issues": sorted(audits[episode])} for episode in ids]}
    return Fixture(root, journal, frames, clips, audit, reasons,
                   [episode for episode in ids if not reasons[episode]], schema)
