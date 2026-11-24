"""Publish a validated, compacted v3.0 recording atomically."""

import fcntl
from hashlib import sha256
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Callable

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .dataset import Dataset, Json, canonical, fingerprint, has_data_range, natural, read_dataset, read_json
from .dataset import shard_name, video_range
from .planning import make_plan


def tasks_for(root: Path) -> dict[int, str]:
    """Load the original task registry without changing its numeric identities."""
    table = pq.ParquetFile(root / "meta/tasks.parquet").read()
    tasks = {}
    for row in table.to_pylist():
        index = row.get("task_index")
        task = row.get("task", row.get("__index_level_0__"))
        if not natural(index) or index in tasks or not isinstance(task, str):
            raise ValueError("Invalid native task registry")
        tasks[index] = task
    return tasks


def read_vector(rows: list[Json], key: str) -> np.ndarray:
    """Read one numerical training feature without changing source frame values."""
    data = np.asarray([row[key] for row in rows])
    if data.ndim != 2 or data.dtype.kind not in "iuf" or not np.isfinite(data).all():
        raise ValueError(f"Expected a finite fixed-length vector for {key}")
    return data.astype(np.float64)


def output_stats(data: Dataset, kept: list[Json], rows: list[Json]) -> Json:
    """Refresh numeric normalization stats and retain others only for identical logical data."""
    unchanged = len(rows) == len(data.indices) and all(
        selection["episode_index"] == index and len(data.metadata.get(index, ())) == 1
        and has_data_range(data.frames[index], data.metadata[index][0])
        and all(video_range(data.metadata[index][0], camera, data.fps, len(data.frames[index].rows)) == tuple(clip)
                for camera, clip in selection["videos"].items())
        for index, selection in enumerate(kept)
    )
    source = data.root / "meta/stats.json"
    result = read_json(source) if unchanged and source.is_file() else {}
    for key in ("action", "observation.state"):
        values = read_vector(rows, key)
        result[key] = {name: function(values, axis=0).tolist() for name, function in
                       (("min", np.min), ("max", np.max), ("mean", np.mean), ("std", np.std))}
        result[key]["count"] = [len(rows)]
    return result


def assemble(data: Dataset, kept: list[Json], output: Path) -> None:
    """Materialize one repaired dataset using native paths and frame-table schema."""
    tasks = tasks_for(data.root)
    rows, episodes = [], []
    copied = set()
    for new, evidence in enumerate(kept):
        old = evidence["episode_index"]
        frame_rows = data.frames[old].rows
        start = len(rows)
        names = list(dict.fromkeys(tasks[row["task_index"]] for row in frame_rows if natural(row["task_index"])))
        if any(not natural(row["task_index"]) for row in frame_rows):
            raise ValueError("Invalid task index in kept frame")
        rows.extend(dict(row, episode_index=new, index=start + offset) for offset, row in enumerate(frame_rows))
        metadata = {"episode_index": new, "tasks": names, "length": len(frame_rows),
                    "data/chunk_index": 0, "data/file_index": 0, "dataset_from_index": start,
                    "dataset_to_index": len(rows), "meta/episodes/chunk_index": 0, "meta/episodes/file_index": 0}
        for camera, (chunk, file, first, last) in evidence["videos"].items():
            key = f"videos/{camera}/"
            metadata.update({key + "chunk_index": chunk, key + "file_index": file,
                             key + "from_timestamp": first / data.fps, key + "to_timestamp": last / data.fps})
            source = data.videos[camera][chunk, file]
            target = output / "videos" / camera / shard_name((chunk, file), "mp4")
            if target not in copied:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                copied.add(target)
        episodes.append(metadata)
    tables = {
        output / "data" / shard_name((0, 0), "parquet"): pa.Table.from_pylist(rows, schema=data.frame_schema),
        output / "meta/episodes" / shard_name((0, 0), "parquet"): pa.Table.from_pylist(episodes),
    }
    for path, table in tables.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path)
    shutil.copyfile(data.root / "meta/tasks.parquet", output / "meta/tasks.parquet")
    info = dict(data.info, total_frames=len(rows), total_episodes=len(kept), total_tasks=len(tasks),
                splits={"train": f"0:{len(kept)}"})
    (output / "meta/info.json").write_bytes(canonical(info) + b"\n")
    (output / "meta/stats.json").write_bytes(canonical(output_stats(data, kept, rows)) + b"\n")


def identical_publication(output: Path, receipt: Json) -> bool:
    """Verify that an existing directory is the complete publication expected here."""
    return (not output.is_symlink() and output.is_dir() and not (output / "repair-receipt.json").is_symlink()
            and read_json(output / "repair-receipt.json") == receipt
            and fingerprint(output) == receipt["output_sha256"])


def publish_reviewed(
    dataset: Path, ledger: Path, proposal: Path, output: Path, plan_for: Callable[[Dataset, bytes], Json],
) -> None:
    """Verify and publish a reviewed repair through the same native transactional writer."""
    source, ledger_path, destination = dataset.resolve(), ledger.resolve(), output.resolve()
    if (output.is_symlink() or destination.is_relative_to(source) or source.is_relative_to(destination)
            or ledger_path.is_relative_to(destination)):
        raise ValueError("Destination overlaps the source or journal")
    input_hash = fingerprint(source)
    journal = ledger_path.read_bytes()
    data = read_dataset(source)
    plan = plan_for(data, journal)
    if input_hash != plan["source_sha256"] or canonical(read_json(proposal)) != canonical(plan):
        raise ValueError("Stale or changed repair plan")
    kept = [episode for episode in plan["episodes"] if episode["status"] == "keep"]
    if not kept:
        raise ValueError("There are no publishable episodes")
    with TemporaryDirectory(dir=destination.parent, prefix=".recording-") as location:
        staged = Path(location) / "dataset"
        assemble(data, kept, staged)
        if fingerprint(source) != input_hash or ledger_path.read_bytes() != journal:
            raise ValueError("The recording changed during publication")
        receipt = {"schema_version": 1, "source_sha256": input_hash, "ledger_sha256": plan["ledger_sha256"],
                   "plan_sha256": sha256(canonical(plan)).hexdigest(), "output_sha256": fingerprint(staged),
                   "episode_map": [[episode["episode_index"], new] for new, episode in enumerate(kept)],
                   "quarantined": [episode["episode_index"] for episode in plan["episodes"]
                                   if episode["status"] == "quarantine"]}
        (staged / "repair-receipt.json").write_bytes(canonical(receipt) + b"\n")
        # A stable lock serializes the existence test and rename, including empty destinations.
        # Removing that lock while another writer waits could create two separate locks.
        with destination.with_name("." + destination.name + ".lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if os.path.lexists(destination):
                if not identical_publication(destination, receipt):
                    raise ValueError("Destination already exists with different contents")
            else:
                staged.rename(destination)


def apply(dataset: Path, ledger: Path, proposal: Path, output: Path) -> None:
    """Publish a repair reviewed against the original exact-anchor journal."""
    publish_reviewed(dataset, ledger, proposal, output, make_plan)
