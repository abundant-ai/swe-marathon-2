"""Check incident reconstruction from independently authored native recorder traces."""

from copy import deepcopy
from hashlib import sha256
from math import isclose, pi
from pathlib import Path

from rosbags.rosbag2 import StoragePlugin, Writer

from probes import Run, TEXT, TF, TS, dump, report, tf


class Recorder:
    """Encode mixed native storage while keeping the authored emission truth separate."""

    def __init__(self, root: Path, name: str, index: int, base: int, plugin: StoragePlugin):
        self.writer = Writer(root / name, version=9, storage_plugin=plugin)
        self.writer.open()
        self.connections = {}
        self.records = {}
        self.name = name
        self.pieces = []
        self.spec = {"id": name, "path": name, "segments": []}
        for piece, rate in enumerate((100_003, 99_991) if index == 0 else (99_997, 100_009)):
            local = 331_111_000_001 + index * 10**10 + piece * 10**8
            master = base + 10_000_000 + index * 4_000_000 + piece * 22_000_000
            self.pieces.append((local, master, rate))
            self.spec["segments"].insert(0, {
                "local_start_ns": local,
                "local_end_ns": local + 10_000_000,
                "rate": [rate, 100_000],
                "pulses": [
                    {"local_ns": local, "earliest_ns": master - 40, "latest_ns": master + 90},
                    {"local_ns": local + 100_000, "earliest_ns": master + rate - 65,
                     "latest_ns": master + rate + 40},
                ],
            })

    def add(self, topic: str, kind: str, wire: bytes, piece: int, slot: int, emit: tuple[int, int],
            fractional: bool = False) -> dict:
        """Write one native occurrence with a designed receipt-delay envelope."""
        local, master, rate = self.pieces[piece]
        record = local + slot * 100_000
        arrival = master + slot * rate
        if fractional:
            # The extra recorder nanosecond maps to just over or just under one master nanosecond.
            record += 1
            arrival += rate // 100_000
        key = topic, record
        ordinal = self.records.get(key, 0)
        self.records[key] = ordinal + 1
        if topic not in self.connections:
            self.connections[topic] = self.writer.add_connection(topic, kind, typestore=TS)
        self.writer.write(self.connections[topic], record, wire)
        return {"capture": self.name, "topic": topic, "record_ns": record, "ordinal": ordinal,
                "latency_min_ns": arrival + 40 - emit[1],
                "latency_max_ns": arrival - 40 - emit[0] + fractional}


def incident_fixture(root: Path, variant: int) -> tuple[dict, list, list, dict]:
    """Encode hand-solved causal intervals and two genuine native bag formats."""
    base = 1_781_234_567_934_485_213 + variant * 2_789_391
    formats = (StoragePlugin.SQLITE3, StoragePlugin.MCAP)
    if variant:
        formats = formats[::-1]
    left = Recorder(root, "camera-recorder", 0, base, formats[0])
    right = Recorder(root, "operations-recorder", 1, base, formats[1])
    events, expected = [], []
    diagnostic = TS.types[TEXT]

    def add(name, producer, boot, number, topic, kind, message, measured, tightened, recorder, piece, slot,
            causes=(), duplicate=None, fractional=False):
        wire = bytes(TS.serialize_cdr(message, kind))
        copies = [recorder.add(topic, kind, wire, piece, slot, tuple(base + value for value in measured), fractional)]
        if duplicate:
            other, copy_piece, copy_slot, copy_interval = duplicate
            copies.append(other.add(topic, kind, wire, copy_piece, copy_slot,
                                    tuple(base + value for value in copy_interval)))
        events.append({"id": name, "producer": producer, "boot": boot, "sequence": number,
                       "copies": copies, "causes": list(causes)})
        expected.append({"id": name, "topic": topic, "type": kind, "sha256": sha256(wire).hexdigest(),
                         "earliest_ns": base + tightened[0], "latest_ns": base + tightened[1]})

    add("mount-open", "mount", "old", 0, "/diagnostic", TEXT, diagnostic("booted"),
        (0, 100), (0, 100), left, 0, 20)
    # A different wire message with the same topic and native record time precedes health.
    # It is not an incident event and the recorder must number it as ordinal zero.
    right.add("/diagnostic", TEXT, bytes(TS.serialize_cdr(diagnostic("unlisted"), TEXT)),
              0, 21, (base + 600, base + 800))
    narrow_overlap = (left, 0, 22, (530, 630)) if variant else None
    add("B-health", "switching", "only", 0, "/diagnostic", TEXT, diagnostic("healthy"),
        (600, 800), (600, 630 if variant else 800), right, 0, 21, duplicate=narrow_overlap)
    old_y = 1 + variant
    add("Z-base", "mount", "old", 10, "/tf_static", TF, tf("world", "/base", 0, old_y, pi / 2, 0),
        (850, 1450), (850, 1100), left, 0, 23)
    camera_x = 1 + variant
    camera = tf("base", "camera", camera_x, 0, 0, 0)
    add("A-camera", "mount", "old", 11, "/tf_static", TF, camera,
        (420, 1100), (850, 1100), left, 0, 24,
        duplicate=(right, 0, 30, (500, 1180)))
    wrong_camera = tf("base", "camera", 99, 0, 0, 0)
    incorrect = right.add("/tf_static", TF, bytes(TS.serialize_cdr(wrong_camera, TF)),
                          0, 31, (base + 500, base + 1180))
    add("ready", "switching", "only", 2, "/diagnostic", TEXT, diagnostic("switch ready"),
        (2000, 2300), (2000, 2300), right, 0, 35)
    motion_x = 3 - variant
    add("motion-1", "position", "b0", 9, "/tf", TF, tf("world", "base", motion_x, 0, 0, 9_000_000),
        (1700, 3200), (2000, 3200), left, 0, 28, causes=("ready", "A-camera"))
    add("mount-reboot", "mount", "new", 0, "/diagnostic", TEXT, diagnostic("restarted"),
        (5000, 5300), (5000, 5300), right, 1, 22, fractional=True)
    fresh_camera_x = 2 + variant
    add("new-camera", "mount", "new", 1, "/tf_static", TF, tf("base", "camera", fresh_camera_x, 0, 0, 0),
        (6100, 6400), (6100, 6400), left, 1, 26)
    fresh_base_x = 1 - variant
    add("new-base", "mount", "new", 2, "/tf_static", TF, tf("world", "base", fresh_base_x, 2, pi / 2, 0),
        (6500, 6900), (6500, 6900), right, 1, 27)

    old_pose = [0, old_y + camera_x, pi / 2]
    fresh_pose = [fresh_base_x, 2 + fresh_camera_x, pi / 2]
    samples = [
        (1050, 3000, "ambiguous", None),
        (1200, 3000, "ok", old_pose),
        (2500, 3000, "ambiguous", None),
        (3500, 1600, "ok", [motion_x + camera_x, 0, 0]),
        (4100, 1400, "ambiguous", None),
        (4850, 1200, "ok", old_pose),
        (5100, 1200, "ambiguous", None),
        (5600, 1200, "unavailable", None),
        (6300, 1200, "ambiguous", None),
        (6800, 1200, "ambiguous", None),
        (7200, 1000, "ok", fresh_pose),
    ]
    lookups = [{"at_ns": base + at, "source_frame": "/camera", "target_frame": "world", "max_age_ns": age}
               for at, age, _, _ in samples]
    expected_queries = [
        {"at_ns": base + at, "source_frame": "camera", "target_frame": "world",
         "status": status, "target_from_source": pose}
        for at, _, status, pose in samples
    ]
    lookups.append({"at_ns": base + 7200, "source_frame": "world", "target_frame": "/camera", "max_age_ns": 1000})
    expected_queries.append({"at_ns": base + 7200, "source_frame": "world", "target_frame": "camera",
                             "status": "ok", "target_from_source": [-fresh_pose[1], fresh_pose[0], -pi / 2]})
    if variant:
        # The switched-storage scenario also introduces an independent static authority.
        add("third-authority", "switching", "only", 4, "/tf_static", TF, tf("world", "base", 19, 1, 0, 0),
            (7500, 7600), (7500, 7600), right, 1, 29, causes=("new-base",))
        lookups.append({"at_ns": base + 7900, "source_frame": "camera", "target_frame": "world", "max_age_ns": 1})
        expected_queries.append({"at_ns": base + 7900, "source_frame": "camera", "target_frame": "world",
                                 "status": "ambiguous", "target_from_source": None})
    for at, age in ((3590, 1550), (5010, 1200)):
        lookups.append({"at_ns": base + at, "source_frame": "camera", "target_frame": "world", "max_age_ns": age})
        expected_queries.append({"at_ns": base + at, "source_frame": "camera", "target_frame": "world",
                                 "status": "ambiguous", "target_from_source": None})
    left.writer.close()
    right.writer.close()
    return {"captures": [right.spec, left.spec], "boots": {"mount": ["old", "new"], "switching": ["only"],
          "position": ["b0"]}, "events": list(reversed(events)), "lookups": lookups}, expected, expected_queries, incorrect


def matches(actual: object, expected: dict) -> bool:
    """Compare a candidate lookup against explicit status and rational-coordinate truth."""
    if not isinstance(actual, dict):
        return False
    if any(actual.get(key) != expected[key] for key in ("at_ns", "source_frame", "target_frame", "status")):
        return False
    pose, truth = actual.get("target_from_source"), expected["target_from_source"]
    if truth is None:
        return "target_from_source" in actual and pose is None
    return isinstance(pose, list) and len(pose) == 3 and all(
        type(a) in (int, float) and isclose(a, b, abs_tol=1e-8) for a, b in zip(pose, truth, strict=True)
    )


def incident_probe(run: Run, root: Path, variant: int) -> dict[str, bool]:
    """Grade exact causal order, consumer decisions, and isolated evidence failures."""
    root.mkdir(mode=0o777)
    root.chmod(0o1777)
    spec, expected_events, expected_queries, incorrect_copy = incident_fixture(root, variant)

    def command(name: str, data: dict, previous: bool = False) -> tuple[int, dict]:
        output = root / (name + "-report.json")
        if previous:
            # The candidate may read and replace this path. A failed command preserves its old value.
            dump(output, {"sentinel": 32971})
            output.chmod(0o666)
            root.chmod(0o777)
        code = run("incident", "--spec", dump(root / (name + ".json"), data), "--output", output)
        root.chmod(0o1777)
        return code, report(output)

    code, result = command("incident", spec)
    result_ok = code == 0 and result.get("schema_version") == 1 and result.get("status") == "ok"
    actual = result.get("lookups")
    fits = [matches(row, truth) for row, truth in zip(actual, expected_queries)] if isinstance(actual, list) else []
    if not isinstance(actual, list) or len(actual) != len(expected_queries):
        fits = [False] * len(expected_queries)
    checks = {
        "wire_reconciliation_and_tight_causal_timeline": result_ok and result.get("events") == expected_events,
        "known_poses_and_inverse_with_correct_authority": result_ok and all(fits[index] for index in (1, 3, 10, 11)),
        "time_and_dynamic_age_uncertainty": result_ok and all(fits[index] for index in (0, 2, 4, 5, -2)),
        "restart_before_first_new_transform": result_ok and all(fits[index] for index in (6, 7, 8, 9, -1)),
    }
    if variant:
        checks["overlapping_authorities_remain_ambiguous"] = result_ok and fits[12]
    for expected_status, event_id, change in (
        ("timing_conflict", "motion-1", {"causes": ["new-base"]}),
        ("causal_cycle", "Z-base", {"causes": ["A-camera"]}),
    ):
        changed = deepcopy(spec)
        next(row for row in changed["events"] if row["id"] == event_id).update(change)
        code, result = command(expected_status, changed)
        checks[expected_status] = code == 0 and result == {
            "schema_version": 1, "status": expected_status, "events": [], "lookups": []}
    changed = deepcopy(spec)
    next(row for row in changed["events"] if row["id"] == "A-camera")["copies"][1] = incorrect_copy
    code, result = command("payload_conflict", changed)
    checks["payload_conflict"] = code == 0 and result == {
        "schema_version": 1, "status": "payload_conflict", "events": [], "lookups": []}
    changed = deepcopy(spec)
    pulse = changed["captures"][0]["segments"][0]["pulses"][0]
    pulse["earliest_ns"] += 1000
    pulse["latest_ns"] += 1000
    code, result = command("bad_pulses", changed)
    checks["incompatible_sync_pulses"] = code == 0 and result == {
        "schema_version": 1, "status": "timing_conflict", "events": [], "lookups": []}
    changed = deepcopy(spec)
    changed["events"][0]["copies"][0]["ordinal"] = 1289
    code, result = command("missing_ordinal", changed, previous=True)
    checks["missing_native_message_preserves_report"] = code not in (0, 124) and result == {"sentinel": 32971}
    return checks
