"""Independent clock-recovery fixtures and native publication checks."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

import pyarrow as pa
import pyarrow.parquet as pq

from fixtures import CAMERAS, FPS, Fixture, dump, encode, fixture, parquet, path_for
from probes import fingerprint, load, native_valid


PERIOD = 1_000_000_000 // FPS


@dataclass(frozen=True)
class Clock:
    """Physical clock chosen privately before generating corrupted observations."""

    sensor_origin: int
    master_origin: int
    ppm: int

    def ticks(self, master: int) -> int:
        """Invert the planted capture clock at one authored master time."""
        return self.sensor_origin + round(Fraction((master - self.master_origin) * 1_000_000,
                                                   1_000_000 + self.ppm))

    def pulses(self) -> list[dict]:
        """Emit five useful calibration pairs and one plausible bad pulse."""
        pulse_ns = (0, 1_000_000_000, 2_000_000_000, 4_000_000_000, 6_000_000_000, 3_000_000_000)
        noise_ns = (0, -32, 40, -18, 12, 2_500_000)
        return [{"sensor_ns": self.sensor_origin + delta,
                 "reference_ns": self.master_origin + round(Fraction(delta * (1_000_000 + self.ppm), 1_000_000)) + noise}
                for delta, noise in zip(pulse_ns, noise_ns, strict=True)]


def tied_pulses(origin: int) -> list[dict]:
    """Plant equally supported competing offsets for the same device boot."""
    return [{"sensor_ns": -760_000_000 + (number * 2 + branch) * 10_000_000,
             "reference_ns": origin + (number * 2 + branch) * 10_000_000 + branch * 70_000_000}
            for branch in (0, 1) for number in range(3)]


def clocks_fixture(work: Path, asset: Path, variant: int) -> Fixture:
    """Create physical clock resets and ambiguous assignments with analytically planted labels."""
    root = work / "timed-recording"
    (root / "meta").mkdir(parents=True)
    orig = work / "clock-journal.json"
    with TemporaryDirectory(prefix="table-template-") as temporary:
        template = fixture(Path(temporary), asset)
        info = load(template.root / "meta/info.json")
        shutil.copyfile(template.root / "meta/tasks.parquet", root / "meta/tasks.parquet")
        schema = template.schema
    info.update(total_episodes=500, total_frames=12000)
    dump(root / "meta/info.json", info)
    dump(root / "meta/stats.json", {"action": {"count": [12000]}, CAMERAS[0]: {"count": [12000]}})
    base = 1_781_234_567_928_190_019 + variant * 500_000_000_000
    ids = [variant * 100 + number for number in (1, 4, 6, 9, 12, 19, 27, 35, 41, 49, 55, 63)]
    fixed_before, forced, fixed_after, choice_one, choice_two, dropped, conflict, tied, copies, terminal, aborted, absent = ids
    records = {}
    real = pq.ParquetFile(asset).read().to_pylist()
    for i, episode in enumerate(ids[:-1]):
        rows = [dict(real[(i * 3 + j + variant) % len(real)], episode_index=episode, index=i * 3 + j,
                     frame_index=j, timestamp=j / FPS, task_index=(i + j // 2) % 2, motor_temperature_c=27 + i / 2)
                for j in range(3)]
        records[episode] = pa.Table.from_pylist(rows, schema=schema).to_pylist()
    parquet(path_for(root, "data", 0, 0, "parquet"), [row for group in records.values() for row in group],
            schema=schema)
    # Deliberately leave a stale episode claim behind. It points all camera reads
    # at non-existent files, so a manifest-based matcher cannot pass these cases.
    stale_video_fields = {
        f"videos/{camera}/{key}": value
        for camera in CAMERAS
        for key, value in (("chunk_index", 91), ("file_index", 47), ("from_timestamp", 0.0), ("to_timestamp", 0.4))
    }
    parquet(path_for(root, "meta/episodes", 0, 0, "parquet"),
            [{"episode_index": episode, "tasks": ["Pick"], "length": 4, "data/chunk_index": 0,
              "data/file_index": 0, "dataset_from_index": 0, "dataset_to_index": 4, **stale_video_fields}
             for episode in (fixed_before, forced, absent)])

    slot_clips = {}
    cameras = {}
    for position, camera in enumerate(CAMERAS):
        offsets = (1250, -650, 345) if position == 0 else (-1000, 875, -260)
        master = [base - 17_000_000, base + 1_512_000_000, base + 2_404_000_000]
        sensor = [907_112_233_333_333_319, -772_000_003, 5_817_000_019_123_877]
        clocks = [Clock(sensor[index] + position * 4999, master[index] + position * 511, offsets[index])
                  for index in range(3)]
        boots = [{"id": f"cam-{position}-boot-{index}", "pulses": clock.pulses()[::-1], "shards": []}
                 for index, clock in enumerate(clocks)]
        boots.append({"id": f"cam-{position}-two-clock-tie", "pulses": tied_pulses(base), "shards": []})
        family = "videos/" + camera
        counter = 0

        def shard(start: int, ticks: list[int], boot: int, *, drop_manifest: bool = False,
                  record: bool = True) -> None:
            """Write one saturated MP4 and matching capture-clock sidecar."""
            nonlocal counter
            number = position * 10 + boot + variant
            file = 31 + 2 * counter
            counter += 1
            video = path_for(root, family, number, file, "mp4")
            seeds = list(range(80_000 + variant * 400 + position * 200 + counter * 13,
                               80_000 + variant * 400 + position * 200 + counter * 13 + len(ticks)))
            encode(video, seeds)
            stamp_clock = clocks[boot] if boot < len(clocks) else clocks[0]
            stamps = [stamp_clock.ticks(base + time) for time in ticks]
            if drop_manifest:
                stamps.pop()
            boots[boot]["shards"].append({"chunk_index": number, "file_index": file, "sensor_ns": stamps})
            if record:
                slot_clips[camera, start] = [number, file, 0, 3]

        # All first nine frames share a shard. Interior valid windows exist and
        # only global order can force the first and last released alternatives.
        extra_jitter = (300, -120, 1900, -1700, 2200, -2500, 7300, -1000, 1250)
        shard(0, [index * PERIOD + noise + position * 800 for index, noise in enumerate(extra_jitter)], 0)
        first_shard = slot_clips[camera, 0]
        for start in (3, 6):
            slot_clips[camera, start] = [first_shard[0], first_shard[1], start, start + 3]
        shard(9, [index * PERIOD for index in (9, 10, 11)], 0)
        shard(13, [13 * PERIOD, 14 * PERIOD + PERIOD // 3, 15 * PERIOD], 1)
        shift = -16_500 if position == 0 else 16_500
        shard(17, [index * PERIOD + shift for index in (17, 18, 19)], 1)
        shard(21, [index * PERIOD for index in (21, 22, 23)], 3 if position == 0 else 1)
        shard(25, [index * PERIOD for index in (25, 26, 27)], 2)
        if position == 0 and not variant:
            shard(25, [index * PERIOD for index in (25, 26, 27)], 2, record=False)
        shard(31, [index * PERIOD for index in (31, 32, 33)], 2)
        shard(31, [index * PERIOD for index in (31, 32, 33, 34)], 2, drop_manifest=True, record=False)
        cameras[camera] = [dict(boot, shards=boot["shards"][::-1]) for boot in reversed(boots)]

    windows = ((0, 6), (3, 3), (3, 6), (9, 9), (9, 9), (13, 13), (17, 17), (21, 21),
               (25, 25), (31, 31), (37, 37), (43, 43))
    ledger = []
    for episode, (start, end) in zip(ids, windows, strict=True):
        slack = 25_000 if episode == conflict else 0
        committed = episode != aborted and (not variant or episode != choice_two)
        ledger.append({"episode_index": episode, "committed": committed,
                       "earliest_ns": base + start * PERIOD - slack, "latest_ns": base + end * PERIOD + slack})
    dump(orig, {"schema_version": 1, "sync_tolerance_ns": 120, "frame_tolerance_ns": 10_000,
                "max_drift_ppm": 3000, "cameras": cameras, "episodes": ledger[::-1]})
    keep = {fixed_before: 0, forced: 3, fixed_after: 6, terminal: 31}
    reasons = {choice_one: ["UNRESOLVED_ASSIGNMENT"], choice_two: ["UNRESOLVED_ASSIGNMENT"],
               dropped: ["NO_TIMED_CLIP"], conflict: ["NO_TIMED_CLIP"], tied: ["NO_TIMED_CLIP"],
               copies: ["UNRESOLVED_ASSIGNMENT"], aborted: ["UNCOMMITTED"], absent: ["INVALID_FRAME_ROWS"]}
    if variant:
        keep.update({choice_one: 9, copies: 25})
        reasons.pop(choice_one)
        reasons.pop(copies)
        reasons[choice_two] = ["UNCOMMITTED"]
    clips = {episode: {camera: slot_clips[camera, tick] for camera in CAMERAS} for episode, tick in keep.items()}
    return Fixture(root, orig, records, clips, {}, reasons | dict.fromkeys(keep, []), sorted(keep), schema)


def expected(data: Fixture) -> dict:
    """Account for the resolvable assignments and the two unavoidable equivalence classes."""
    rows = [
        {"episode_index": episode, "status": "quarantine" if reasons else "keep", "reasons": reasons,
         "videos": {} if reasons else data.clips[episode]}
        for episode, reasons in sorted(data.reasons.items())
    ]
    return {"schema_version": 1, "source_sha256": fingerprint(data.root),
            "ledger_sha256": sha256(data.journal.read_bytes()).hexdigest(), "matched_count": 6, "episodes": rows}


def time_mission(run, work: Path, asset: Path, variant: int) -> dict[str, bool]:
    """Check fallback ignorance, inferred global recovery, and verified publication."""
    data = clocks_fixture(work, asset, variant)
    plan, published = work / "time-plan.json", work / "time-release"
    base = ("--dataset", data.root, "--ledger", data.journal)
    checks = dict(global_recovery=False, distinguishing_time_failures=False,
                  native_publication=False, transactional_recovery=False)
    if run("time-plan", *base, "--output", plan) != 0:
        return checks
    measured, wanted = load(plan), expected(data)
    if not measured or not isinstance(measured.get("episodes"), list):
        return checks
    try:
        resolved = {row["episode_index"]: row for row in measured["episodes"]}
    except (KeyError, TypeError):
        return checks
    checks["global_recovery"] = (type(measured.get("matched_count")) is int and measured["matched_count"] == 6
                                 and all(resolved.get(row["episode_index"]) == row for row in wanted["episodes"]
                                         if row["status"] == "keep"))
    checks["distinguishing_time_failures"] = all(
        resolved.get(row["episode_index"]) == row for row in wanted["episodes"] if row["status"] == "quarantine")
    if measured != wanted:
        return checks
    args = ("time-apply", *base, "--plan", plan, "--output", published)
    with ThreadPoolExecutor(max_workers=2) as pool:
        scores = list(pool.map(lambda _: run(*args), range(2)))
    checks["native_publication"] = 0 in scores and native_valid(data, published, wanted)
    if not checks["native_publication"]:
        return checks
    altered = dump(work / "altered.json", dict(wanted, matched_count=5))
    failed_target = work / "failed-release"
    wrong_plan = run("time-apply", *base, "--plan", altered, "--output", failed_target)
    recovered = run(*args)
    journal = data.journal.read_bytes()
    malformed = json.loads(journal)
    next(iter(malformed["cameras"].values()))[0]["pulses"] = [
        {"sensor_ns": 1, "reference_ns": 5}, {"sensor_ns": 1, "reference_ns": 6},
    ]
    original_plan = plan.read_bytes()
    try:
        dump(data.journal, malformed)
        wrong_pulse = run("time-plan", *base, "--output", plan)
    finally:
        data.journal.write_bytes(journal)
    clean_report = work / "audit-new.json"
    checks["transactional_recovery"] = (
        recovered == 0 and wrong_plan not in (0, 124) and wrong_pulse not in (0, 124) and not failed_target.exists()
        and plan.read_bytes() == original_plan and native_valid(data, published, wanted)
        and fingerprint(data.root) == wanted["source_sha256"]
        and run("audit", "--dataset", published, "--output", clean_report) == 0
        and load(clean_report) == {"schema_version": 1, "frame_rows": len(data.ordered) * 3,
                                    "metadata_rows": len(data.ordered), "dataset_issues": [],
                                    "episodes": [{"episode_index": number, "issues": []}
                                                 for number in range(len(data.ordered))]}
    )
    return checks
