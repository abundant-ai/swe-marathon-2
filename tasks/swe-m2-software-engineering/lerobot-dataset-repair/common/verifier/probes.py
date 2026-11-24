"""Verify native dataset results independently of the implementation."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import math
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from fixtures import Fixture, dump, fixture, path_for


def load(path: Path) -> dict:
    """Read one bounded candidate JSON result with no symbolic links."""
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 450_000:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def canonical(value: object) -> bytes:
    """Encode the published semantic plan digest representation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def fingerprint(dataset: Path) -> str:
    """Derive the expected dataset checksum from complete ordered native files."""
    native = [file for directory in ("data", "meta", "videos")
              for file in (dataset / directory).rglob("*") if file.is_file()]
    records = [(file.relative_to(dataset).as_posix(), sha256(file.read_bytes()).hexdigest()) for file in native]
    return sha256("".join(name + "\t" + digest + "\n" for name, digest in sorted(records)).encode()).hexdigest()


def expected_plan(data: Fixture) -> dict:
    """Return settled clip ownership from the recorder's independent fixture model."""
    episodes = []
    for episode, reasons in sorted(data.reasons.items()):
        episodes.append({"episode_index": episode, "status": "quarantine" if reasons else "keep",
                         "reasons": sorted(reasons), "videos": {} if reasons else data.clips[episode]})
    return {"schema_version": 1, "source_sha256": fingerprint(data.root),
            "ledger_sha256": sha256(data.journal.read_bytes()).hexdigest(), "episodes": episodes}


def operation(run, command: str, data: Fixture, output: Path, *extra: object) -> int:
    """Invoke a public command with this recording as the source."""
    options = () if command == "audit" else ("--ledger", data.journal)
    return run(command, "--dataset", data.root, *options, "--output", output, *extra)


def audits(run, data: Fixture, work: Path) -> dict:
    """Check categorical diagnosis, deterministic output and atomic rejection."""
    report = work / "audit.json"
    result = {
        "exact_issues": operation(run, "audit", data, report) == 0 and load(report) == data.audit,
        "deterministic": False,
        "malformed_preserves_report": False,
    }
    if not result["exact_issues"]:
        return result
    first = report.read_bytes()
    result["deterministic"] = operation(run, "audit", data, report) == 0 and report.read_bytes() == first
    info = data.root / "meta/info.json"
    original = info.read_bytes()
    try:
        info.write_text("malformed")
        result["malformed_preserves_report"] = operation(run, "audit", data, report) != 0 and report.read_bytes() == first
    finally:
        info.write_bytes(original)
    return result


def planning(run, data: Fixture, work: Path) -> dict:
    """Check unique matches, data evidence and conflict handling as separate outcomes."""
    plan = work / "reviewed.json"
    actual = load(plan) if operation(run, "plan", data, plan) == 0 else {}
    expected = expected_plan(data)
    keys = (("verified_clips", lambda row: row["status"] == "keep"),
            ("unresolved_evidence", lambda row: any("CLIP" in reason or "EVIDENCE" in reason for reason in row["reasons"])),
            ("journal_and_row_failures", lambda row: any("ROWS" in reason or "UNCOMMITTED" in reason for reason in row["reasons"])))
    checks = {key: False for key, _ in keys}
    checks.update(fingerprints_and_order=False, malformed_ledger_preserves_plan=False)
    if not isinstance(actual.get("episodes"), list):
        return checks
    try:
        by_episode = {row["episode_index"]: row for row in actual["episodes"] if type(row["episode_index"]) is int}
        checks["fingerprints_and_order"] = (
            all(actual.get(key) == value for key, value in expected.items() if key != "episodes")
            and [row["episode_index"] for row in actual["episodes"] if type(row["episode_index"]) is int]
            == list(data.reasons)
            and len(actual["episodes"]) == len(data.reasons))
        for name, relevant in keys:
            checks[name] = all(by_episode.get(row["episode_index"]) == row for row in expected["episodes"] if relevant(row))
    except (KeyError, TypeError, ValueError):
        return checks
    previous = plan.read_bytes()
    contents = data.journal.read_bytes()
    corrupt = json.loads(contents)
    corrupt["episodes"].append(corrupt["episodes"][0])
    try:
        dump(data.journal, corrupt)
        checks["malformed_ledger_preserves_plan"] = (operation(run, "plan", data, plan) != 0
                                                    and plan.read_bytes() == previous)
    finally:
        data.journal.write_bytes(contents)
    return checks


def native_tables(root: Path, family: str) -> list[tuple[tuple[int, int], object]]:
    """Read physical shards directly, without running candidate readers."""
    return [((int(file.parent.name.split("-")[1]), int(file.stem.split("-")[1])), pq.ParquetFile(file).read())
            for file in sorted((root / family).glob("chunk-*/file-*.parquet"))]


def native_valid(data: Fixture, output: Path, approval: dict) -> bool:
    """Check a submitted publication, treating malformed artifacts as failed evidence."""
    try:
        return verify_native(data, output, approval)
    except (OSError, TypeError, ValueError, KeyError, IndexError, OverflowError, pa.ArrowException):
        return False


def verify_native(data: Fixture, output: Path, approval: dict) -> bool:
    """Prove native row content, clip references, stats and receipt from source facts."""
    if output.is_symlink() or not output.is_dir():
        return False
    for item in output.rglob("*"):
        if item.is_symlink() or not (item.is_dir() or item.is_file()) or (item.is_file() and item.stat().st_size > 10_000_000):
            return False
    rows = []
    locations = defaultdict(set)
    for shard, table in native_tables(output, "data"):
        if not table.schema.equals(data.schema):
            return False
        for row in table.to_pylist():
            rows.append(row)
            locations[row["episode_index"]].add(shard)
    expected = []
    for new, old in enumerate(data.ordered):
        first = len(expected)
        expected.extend(dict(row, episode_index=new, index=first + offset)
                        for offset, row in enumerate(data.frames[old]))
    if rows != expected:
        return False
    metadata = [row for _, table in native_tables(output, "meta/episodes") for row in table.to_pylist()]
    if len(metadata) != len(data.ordered):
        return False
    camera_files = set()
    first = 0
    for new, old in enumerate(data.ordered):
        row, length = metadata[new], len(data.frames[old])
        if row.get("episode_index") != new or len(locations[new]) != 1:
            return False
        chunk, file = next(iter(locations[new]))
        names = list(dict.fromkeys(("Pick", "Place")[item["task_index"]] for item in data.frames[old]))
        fields = {"length": length, "dataset_from_index": first, "dataset_to_index": first + length,
                  "data/chunk_index": chunk, "data/file_index": file, "tasks": names}
        if any(row.get(key) != expected for key, expected in fields.items()):
            return False
        first += length
        for camera, (chunk, file, start, end) in data.clips[old].items():
            prefix = f"videos/{camera}/"
            fields = {"chunk_index": chunk, "file_index": file,
                      "from_timestamp": start / 10, "to_timestamp": end / 10}
            if any(row.get(prefix + key) != expected for key, expected in fields.items()):
                return False
            original = path_for(data.root, "videos/" + camera, chunk, file, "mp4")
            retained = path_for(output, "videos/" + camera, chunk, file, "mp4")
            if not retained.is_file() or original.read_bytes() != retained.read_bytes():
                return False
            camera_files.add(retained)
    if camera_files != set((output / "videos").rglob("*.mp4")):
        return False
    info = load(output / "meta/info.json")
    original_info = load(data.root / "meta/info.json")
    if (info.get("codebase_version") != "v3.0" or info.get("fps") != original_info["fps"]
            or info.get("features") != original_info["features"] or info.get("total_frames") != len(rows)
            or info.get("total_episodes") != len(data.ordered) or info.get("total_tasks") != 2
            or info.get("splits") != {"train": f"0:{len(data.ordered)}"}
            or (output / "meta/tasks.parquet").read_bytes() != (data.root / "meta/tasks.parquet").read_bytes()):
        return False
    stats = load(output / "meta/stats.json")
    for key in ("action", "observation.state"):
        columns = list(zip(*(row[key] for row in expected), strict=True))
        means = [math.fsum(column) / len(column) for column in columns]
        quantities = {"min": list(map(min, columns)), "max": list(map(max, columns)), "mean": means,
                      "std": [math.sqrt(math.fsum((value - mean)**2 for value in column) / len(column))
                              for column, mean in zip(columns, means, strict=True)]}
        evidence = stats.get(key, {})
        if not isinstance(evidence, dict) or evidence.get("count") != [len(expected)]:
            return False
        for name, wanted in quantities.items():
            actual = evidence.get(name)
            if (not isinstance(actual, list) or len(actual) != len(wanted)
                    or not all(type(a) in (float, int) and math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-7)
                               for a, b in zip(actual, wanted, strict=True))):
                return False
    receipt = {"schema_version": 1, "source_sha256": approval["source_sha256"],
               "ledger_sha256": approval["ledger_sha256"], "plan_sha256": sha256(canonical(approval)).hexdigest(),
               "output_sha256": fingerprint(output), "episode_map": [[old, new] for new, old in enumerate(data.ordered)],
               "quarantined": [episode for episode in sorted(data.reasons) if data.reasons[episode]]}
    return set(stats) == {"action", "observation.state"} and load(output / "repair-receipt.json") == receipt


def publication(run, data: Fixture, work: Path) -> dict:
    """Measure complete repair, unsafe publication refusal, and replay after lost feedback."""
    checks = dict(end_to_end=False, unsafe_plan_preserves_output=False, concurrent_repeat=False)
    plan_path, output = work / "approval.json", work / "repaired"
    expected = expected_plan(data)
    actual = load(plan_path) if operation(run, "plan", data, plan_path) == 0 else {}
    if actual != expected:
        return checks
    arguments = ("--plan", plan_path)
    published = operation(run, "apply", data, output, *arguments)
    if published != 0 or not native_valid(data, output, expected):
        return checks
    clean_audit = work / "post-audit.json"
    if run("audit", "--dataset", output, "--output", clean_audit) != 0:
        return checks
    audit = load(clean_audit)
    checks["end_to_end"] = (audit == {
        "schema_version": 1, "dataset_issues": [], "frame_rows": sum(len(data.frames[e]) for e in data.ordered),
        "metadata_rows": len(data.ordered),
        "episodes": [{"episode_index": index, "issues": []} for index in range(len(data.ordered))],
    } and fingerprint(data.root) == expected["source_sha256"])
    before = (output / "repair-receipt.json").read_bytes()
    altered = json.loads(plan_path.read_bytes())
    videos = next(row["videos"] for row in altered["episodes"] if row["status"] == "keep")
    first = next(iter(videos.values()))
    first[2] += 1
    first[3] += 1
    changed_plan = dump(work / "altered-plan.json", altered)
    accepts_change = operation(run, "apply", data, work / "altered-publication", "--plan", changed_plan) == 0
    source = data.root / "meta/stats.json"
    prior = source.read_bytes()
    try:
        source.write_bytes(prior + b"\n")
        stale = operation(run, "apply", data, output, *arguments)
        stale_new = operation(run, "apply", data, work / "bad-publication", *arguments)
    finally:
        source.write_bytes(prior)
    checks["unsafe_plan_preserves_output"] = (
        stale != 0 and stale_new != 0 and not accepts_change
        and not (work / "bad-publication").exists() and not (work / "altered-publication").exists()
        and (output / "repair-receipt.json").read_bytes() == before and native_valid(data, output, expected))
    race = work / "race"
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(operation, run, "apply", data, race, *arguments) for _ in range(2)]
        completed = [call.result() for call in calls]
    checks["concurrent_repeat"] = (0 in completed and native_valid(data, race, expected)
                                   and operation(run, "apply", data, race, *arguments) == 0
                                   and native_valid(data, race, expected))
    return checks


def verify(run, work: Path, asset: Path, stage: int) -> dict[str, dict[str, bool]]:
    """Run cumulative phases and a second independently seeded publication mission."""
    data = fixture(work, asset)
    groups = {"audit": audits(run, data, work)}
    if stage >= 2:
        groups["plan"] = planning(run, data, work)
    if stage >= 3:
        groups["publish"] = publication(run, data, work)
        other = work / "shift"
        other.mkdir()
        other.chmod(0o1777)
        relocated = fixture(other, asset, variant=4)
        groups["publish_shifted"] = publication(run, relocated, other)
    if stage >= 4:
        from time_probes import time_mission

        for tag, variant in (("clocked", 0), ("clocked_restart", 7)):
            target = work / tag
            target.mkdir()
            target.chmod(0o1777)
            groups[tag] = time_mission(run, target, asset, variant)
    return groups
