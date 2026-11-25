"""Surveyed paths and planted laboratory incidents for executable checks."""

import csv
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from math import atan2, cos, sin
from pathlib import Path

import numpy as np
from reference import Json, matches, near, posterior

Run = Callable[..., Json]
CONFIG = {
    "start_tick": 20,
    "lag_ticks": 3,
    "prior_mean": [0.43, -0.11],
    "prior_covariance": [[0.26, 0.06], [0.06, 0.31]],
    "process_covariance": [[0.23, -0.07], [-0.07, 0.41]],
}
POSE_NOISE = [[0.041, -0.006], [-0.006, 0.095]]
ANCHORS = {"a": [-1.3, 1.25], "b": [2.8, 3.75], "c": [0.1, -2.55]}
BIASES = {"a": 0.31, "b": -0.17, "c": 0.095}


def advance(tick: int) -> Json:
    """Create a replay watermark event."""
    return {"op": "advance", "tick": tick}


def sample(op: str, tick: int, value: list[float]) -> Json:
    """Make a correlated two-dimensional measurement."""
    return {"op": op, "tick": tick, "value": value, "covariance": POSE_NOISE}


def statuses(report: Json) -> list:
    """Extract event outcomes when the response follows their declared shape."""
    entries = report.get("outcomes")
    if not isinstance(entries, list) or not all(
        isinstance(row, dict) for row in entries
    ):
        return []
    return [row.get("status") for row in entries]


def smoother_cases(run: Run) -> dict[str, bool]:
    """Distinguish marginalization, delayed arrivals, and malformed batch handling."""
    config = CONFIG | {"start_tick": 10**16 + 31, "lag_ticks": 2}
    t = config["start_tick"]
    move = sample("delta", t + 1, [0.63, -0.42])
    early_fix = sample("position", t, [-0.18, 0.91])
    projection = {
        "op": "projection",
        "tick": t + 2,
        "axis": [0.35, -2.5],
        "value": 2.1,
        "variance": 0.045,
    }
    future = projection | {"tick": t + 4, "value": -23.0}
    late_fix = sample("position", t + 4, [1.63, -0.22])
    events = [
        advance(t + 1),
        move,
        early_fix,
        {"op": "snapshot", "label": "before eviction"},
        advance(t + 3),
        move,
        future,
        projection,
        advance(t + 4),
        late_fix,
        {"op": "snapshot", "label": "live marginals"},
    ]
    observed = run("smooth", {"config": config, "events": events})
    final = posterior(config, t + 4, [move, early_fix, projection, late_fix])
    first = posterior(config, t + 1, [move, early_fix])
    snapshots = observed.get("snapshots", [])
    snapshots_pass = (
        isinstance(snapshots, list)
        and len(snapshots) == 2
        and matches(snapshots[0], first)
        and matches(snapshots[1], final)
        and [row.get("label") for row in snapshots]
        == ["before eviction", "live marginals"]
    )
    plain = run("smooth", {"config": CONFIG, "events": [advance(31)]})
    return {
        "async_support_and_no_retroactive_future": statuses(observed)
        == [
            "advanced",
            "accepted",
            "accepted",
            "snapshot",
            "advanced",
            "expired",
            "future",
            "accepted",
            "advanced",
            "accepted",
            "snapshot",
        ],
        "correlated_exact_marginal_after_eviction": matches(
            observed.get("final"), final
        ),
        "immutable_snapshot_and_integer_time": snapshots_pass,
        "multi_tick_prediction_without_observations": matches(
            plain.get("final"), posterior(CONFIG, 31, [])
        ),
        "malformed_covariance_and_backward_clock_atomic": all(
            run("smooth", {"config": config, "events": bad}, invalid=True).get("atomic")
            for bad in (
                [advance(t + 1), move | {"covariance": [[1, 2], [2, 1]]}],
                [advance(t + 2), advance(t + 1)],
            )
        ),
    }


def calibration_case(seed: int, offset: int, transform: complex) -> tuple[Json, Json]:
    """Generate asynchronous wheel and surveyed ranging with independently planted faults."""
    random = np.random.default_rng(seed)
    acquire = [31 + i * 2 + i // 3 for i in range(17)]
    true = [complex(*pair) for pair in random.uniform(-0.95, 0.95, size=(17, 2))]
    wheel = [
        {"tick": tick, "delta": [value.real, value.imag]}
        for tick, value in zip(acquire, true, strict=True)
    ]
    targets = [transform * item for item in true]
    noisy_survey = [
        {"tick": capture + offset, "delta": [value.real, value.imag]}
        for capture, value in zip(acquire, targets, strict=True)
    ]
    for i, contamination in ((1, [1.8, -2.6]), (7, [-3, -1.2]), (14, [2.0, 4.1])):
        noisy_survey[i]["delta"] = contamination
    bias_rows = []
    for key, location in ANCHORS.items():
        for i, position in enumerate(random.uniform(-1.1, 1.1, size=(11, 2))):
            true_distance = np.linalg.norm(position - np.asarray(location))
            bias_rows.append(
                {
                    "anchor": key,
                    "position": position.tolist(),
                    "distance_m": float(
                        true_distance + BIASES[key] + (2.1 if i in (1, 4) else 0)
                    ),
                }
            )
    inputs = {
        "wheel": wheel[::-1],
        "survey": noisy_survey[::2] + noisy_survey[1::2],
        "offset_candidates": list(range(-5, 6)),
        "min_pairs": 5,
        "motion_floor_m": 0.025,
        "ambiguity_m": 0.002,
        "anchors": ANCHORS,
        "ranges": bias_rows,
    }
    wanted = {
        "status": "ok",
        "offset_ticks": offset,
        "wheel_scale": abs(transform),
        "wheel_yaw_rad": atan2(transform.imag, transform.real),
        "wheel_pairs": 17,
        "wheel_median_m": 0.0,
        "range_bias_m": BIASES,
    }
    return inputs, wanted


def calibration_valid(report: Json, expected: Json) -> bool:
    """Check the signed offset, proper wheel transformation and outcome statistics."""
    return (
        report.get("status") == "ok"
        and type(report.get("offset_ticks")) is int
        and report["offset_ticks"] == expected["offset_ticks"]
        and type(report.get("wheel_pairs")) is int
        and report["wheel_pairs"] == expected["wheel_pairs"]
        and near(report.get("wheel_scale"), expected["wheel_scale"])
        and near(report.get("wheel_yaw_rad"), expected["wheel_yaw_rad"])
        and near(report.get("wheel_median_m"), expected["wheel_median_m"])
    )


def calibration_cases(run: Run) -> dict[str, bool]:
    """Calibrate both clock signs and distinguish ambiguity from low excitation."""
    built = [
        calibration_case(1157, -3, -0.67 + 1.15j),
        calibration_case(2348, 4, 0.61 - 0.2j),
    ]
    reports = [run("calibrate", spec) for spec, _ in built]
    spec = built[0][0]
    constant = [{"tick": 31 + i, "delta": [0.2, -0.17]} for i in range(12)]
    ambiguous = run(
        "calibrate",
        spec | {"offset_candidates": [0, 1], "wheel": constant, "survey": constant},
    )
    still = [row | {"delta": [0.0, 0.0]} for row in constant]
    unexcited = run("calibrate", spec | {"wheel": still, "survey": still})
    unsupported = run(
        "calibrate",
        spec | {"ranges": [row for row in spec["ranges"] if row["anchor"] != "b"]},
    )
    null_fields = [
        "offset_ticks",
        "wheel_scale",
        "wheel_yaw_rad",
        "wheel_pairs",
        "wheel_median_m",
        "range_bias_m",
    ]
    return {
        "robust_wheel_calibration_signed_grid_offsets": all(
            calibration_valid(actual, wanted)
            for actual, (_, wanted) in zip(reports, built, strict=True)
        ),
        "surveyed_range_bias_resists_outliers": all(
            isinstance(report.get("range_bias_m"), dict)
            and set(report["range_bias_m"]) == set(BIASES)
            and all(
                near(report["range_bias_m"][anchor], value)
                for anchor, value in BIASES.items()
            )
            for report in reports
        ),
        "same_motion_different_clocks_is_ambiguous": ambiguous.get("status")
        == "ambiguous"
        and all(key in ambiguous and ambiguous[key] is None for key in null_fields),
        "low_excitation_or_anchor_support_is_explicit": all(
            report.get("status") == "insufficient_support"
            and all(key in report and report[key] is None for key in null_fields)
            for report in (unexcited, unsupported)
        ),
        "calibration_duplicate_tick_is_atomic": run(
            "calibrate",
            spec | {"wheel": spec["wheel"] + [spec["wheel"][0]]},
            invalid=True,
        ).get("atomic", False),
    }


def surveyed_path(data: Path) -> list[np.ndarray]:
    """Read and recenter the attributed real TUM VI room1 mocap excerpt."""
    with data.open(newline="", encoding="utf-8") as stream:
        values = [
            np.array([float(row["x_m"]), float(row["y_m"])])
            for row in csv.DictReader(stream)
        ]
    if len(values) != 80:
        raise RuntimeError("incomplete TUM VI excerpt")
    return [point - values[0] for point in values]


def room_case(
    poses: list[np.ndarray], begin: int, seed: int, calibration: Json
) -> tuple[Json, list[Json], list[str]]:
    """Construct raw noisy cart sensors over a held-out measured planar path."""
    rng = np.random.default_rng(seed)
    angle = calibration["wheel_yaw_rad"]
    A = calibration["wheel_scale"] * np.array(
        [[cos(angle), -sin(angle)], [sin(angle), cos(angle)]]
    )
    undo = np.linalg.inv(A)
    observed = poses[begin : begin + 23]
    config = CONFIG | {
        "lag_ticks": 4,
        "prior_mean": observed[0].tolist(),
        "prior_covariance": [[0.002, 0.0], [0.0, 0.002]],
    }
    events = []
    normalized = []
    outcomes = []
    for index in range(1, len(observed)):
        tick = config["start_tick"] + index
        events.append(advance(tick))
        outcomes.append("advanced")
        corrected = observed[index] - observed[index - 1] + rng.normal(0, 0.0018, 2)
        raw_noise = np.array([[0.0041, 0.0014], [0.0014, 0.0078]]) * (1 + index / 19)
        events.append(
            {
                "op": "wheel",
                "device_tick": tick - calibration["offset_ticks"],
                "value": (undo @ corrected).tolist(),
                "covariance": raw_noise.tolist(),
            }
        )
        normalized.append(
            {
                "op": "delta",
                "tick": tick,
                "value": corrected.tolist(),
                "covariance": (A @ raw_noise @ A.T).tolist(),
            }
        )
        outcomes.append("accepted")
        if index % 3 == 0:
            acquired = index - 2
            true = observed[acquired]
            first, second = ("a", "b") if index % 2 else ("a", "c")
            a, b = np.asarray(ANCHORS[first]), np.asarray(ANCHORS[second])
            variance = 0.010 + 0.0013 * index
            events.append(
                {
                    "op": "range_pair",
                    "tick": tick - 2,
                    "anchor_a": first,
                    "anchor_b": second,
                    "range_a_m": float(np.linalg.norm(true - a) + BIASES[first]),
                    "range_b_m": float(np.linalg.norm(true - b) + BIASES[second]),
                    "variance_m4": variance,
                }
            )
            normalized.append(
                {
                    "op": "projection",
                    "tick": tick - 2,
                    "value": float((b - a) @ true),
                    "axis": (b - a).tolist(),
                    "variance": variance,
                }
            )
            outcomes.append("accepted")
        if index % 5 == 0:
            delta = (
                observed[index - 1] - observed[index - 2] + rng.normal(0, 0.005, 2)
            ).tolist()
            events.append(sample("imu", tick - 1, delta))
            normalized.append(sample("delta", tick - 1, delta))
            outcomes.append("accepted")
    final_tick = config["start_tick"] + len(observed) - 1
    events.extend(
        [
            {
                "op": "wheel",
                "device_tick": final_tick - calibration["offset_ticks"] + 1,
                "value": [2, 5],
                "covariance": POSE_NOISE,
            },
            {
                "op": "range_pair",
                "tick": final_tick,
                "anchor_a": "a",
                "anchor_b": "c",
                "range_a_m": 0.02,
                "range_b_m": 2.1,
                "variance_m4": 0.01,
            },
            {
                "op": "wheel",
                "device_tick": 0,
                "value": [8, -3],
                "covariance": POSE_NOISE,
            },
        ]
    )
    outcomes.extend(("future", "invalid", "expired"))
    return (
        {
            "config": config,
            "events": events,
            "calibration": calibration,
            "anchors": ANCHORS,
        },
        normalized,
        outcomes,
    )


def fusion_cases(run: Run, dataset: Path) -> dict[str, bool]:
    """Verify the ordered sensor pipeline with authored observations over real mocap."""
    real = surveyed_path(dataset)
    fit_spec, wanted = calibration_case(99713, -4, 0.18 - 1.1j)
    estimated = run("calibrate", fit_spec)
    independent = [room_case(real, begin, 531 + begin, wanted) for begin in (9, 48)]
    reports = [run("smooth", spec) for spec, _, _ in independent]
    expected = [
        posterior(spec["config"], spec["config"]["start_tick"] + 22, factors)
        for spec, factors, _ in independent
    ]
    calibrated = (
        run("smooth", independent[0][0] | {"calibration": estimated})
        if estimated.get("status") == "ok"
        else {}
    )
    malformed = independent[0][0] | {
        "events": independent[0][0]["events"]
        + [
            {
                "op": "range_pair",
                "tick": 22,
                "anchor_a": "a",
                "anchor_b": "a",
                "range_a_m": 2,
                "range_b_m": 1,
                "variance_m4": 0.06,
            },
        ]
    }
    return {
        "commissioned_sensor_units_and_covariance_on_mocap": all(
            matches(report.get("final"), known)
            for report, known in zip(reports, expected, strict=True)
        ),
        "calibrated_acquisition_support_and_negative_range": all(
            statuses(report) == case[2]
            for report, case in zip(reports, independent, strict=True)
        ),
        "independent_fit_flows_into_heldout_replay": matches(
            calibrated.get("final"), expected[0]
        ),
        "invalid_anchor_pair_is_atomic": run("smooth", malformed, invalid=True).get(
            "atomic", False
        ),
    }


def upsert(factor: Json, identity: str, revision: int) -> Json:
    """Wrap a known normalized factor in the ingestion revision envelope."""
    return {
        "op": "upsert",
        "id": identity,
        "revision": revision,
        "factor": factor,
        "first_tick": factor["tick"] - (factor["op"] == "delta"),
        "last_tick": factor["tick"],
    }


def packet(stream: str, sequence: int, events: list[Json], **fields: object) -> Json:
    """Create a stream packet whose model is frozen during the mission."""
    return {
        "stream_id": stream,
        "sequence": sequence,
        "events": events,
        "config": CONFIG,
        **fields,
    }


def result_of(reply: Json) -> Json:
    """Return the result object, with invalid application data treated as missing."""
    result = reply.get("result")
    return result if isinstance(result, dict) else {}


def durable_cases(run: Run, root: Path) -> dict[str, bool]:
    """Exercise exact revisions, crash-safe retries, parallel streams, and bounded history."""
    state = root / "journal.json"
    early = sample("position", 20, [0.18, 0.71])
    first = sample("delta", 22, [0.53, -0.19])
    replacement = sample("delta", 22, [-0.26, 0.06])
    latest = sample("delta", 22, [0.12, 0.48])
    initial_id = upsert(early, "radio-fix", 1)
    received = upsert(first, "wheel", 1)
    pkt1 = packet("west", 1, [initial_id, advance(22), received])
    a = run("ingest", pkt1, state=state)
    retry = run("ingest", dict(reversed(list(pkt1.items()))), state=state)
    removal = {key: value for key, value in received.items() if key != "factor"} | {
        "op": "retract",
        "revision": 3,
    }
    pkt2 = packet(
        "west",
        2,
        [
            received,
            received | {"factor": replacement},
            upsert(replacement, "wheel", 3),
            upsert(replacement, "wheel", 2),
            removal,
            removal,
            {"op": "snapshot", "label": "without revised wheel"},
            upsert(latest, "wheel", 4),
            upsert(replacement, "wheel", 2),
            advance(26),
            upsert(latest, "wheel", 5),
        ],
    )
    b = run("ingest", pkt2, state=state)
    b_result = result_of(b)
    b_snapshots = b_result.get("snapshots", [])
    snapshot_matches = (
        isinstance(b_snapshots, list)
        and len(b_snapshots) == 1
        and matches(b_snapshots[0], posterior(CONFIG, 22, [early]))
    )
    physical = posterior(CONFIG, 26, [early, latest])
    rejected = [
        run("ingest", invalid, state=state)
        for invalid in (
            pkt1,
            packet("west", 4, []),
            pkt2 | {"events": []},
            packet("west", 3, []) | {"config": CONFIG | {"lag_ticks": 4}},
        )
    ]
    pkt3 = packet("west", 3, [advance(27)])
    lost = run("ingest", pkt3, state=state, lost_reply=True)
    saved_retry = run("ingest", pkt3, state=state)
    irrecoverable = run(
        "ingest",
        packet("west", 4, [advance(28), advance(27)]),
        state=state,
        invalid=True,
    )
    a_result = result_of(a)
    new_streams = [packet("east", 1, [advance(21)]), packet("north", 1, [advance(22)])]
    with ThreadPoolExecutor(max_workers=2) as workers:
        parallel = list(
            workers.map(lambda item: run("ingest", item, state=state), new_streams)
        )
    parallel_retries = [run("ingest", item, state=state) for item in new_streams]
    fresh = root / "bounded.json"
    burst = []
    for tick in range(21, 471):
        burst.extend((advance(tick), sample("delta", tick, [0.008, -0.01])))
    burst_report = run("ingest", packet("bounded", 1, burst), state=fresh)
    after_burst = run(
        "ingest",
        packet("bounded", 2, [{"op": "snapshot", "label": "after restart"}]),
        state=fresh,
    )
    try:
        bounded = (
            fresh.is_file() and not fresh.is_symlink() and fresh.stat().st_size < 32_000
        )
    except OSError:
        bounded = False
    return {
        "accept_and_restart_exact_latest_reply": (
            a.get("status") == "accepted"
            and retry == a
            and matches(a_result.get("final"), posterior(CONFIG, 22, [early, first]))
        ),
        "revision_conflicts_retractions_and_restoration": statuses(b_result)
        == [
            "duplicate",
            "conflict",
            "conflict",
            "accepted",
            "retracted",
            "duplicate",
            "snapshot",
            "accepted",
            "stale",
            "advanced",
            "expired",
        ],
        "revision_downdate_and_expired_information_conservation": snapshot_matches
        and matches(b_result.get("final"), physical),
        "wrong_sequences_and_changed_model_do_not_advance": all(
            row.get("status") == "rejected"
            and "result" in row
            and row["result"] is None
            for row in rejected
        ),
        "loss_of_reply_persists_decision": lost.get("nonzero") is True
        and saved_retry.get("status") == "accepted"
        and matches(
            result_of(saved_retry).get("final"), posterior(CONFIG, 27, [early, latest])
        ),
        "malformed_packet_is_atomic_across_state_and_reply": irrecoverable.get("atomic")
        is True,
        "independent_streams_survive_concurrent_updates": all(
            item.get("status") == "accepted" and replay == item
            for item, replay in zip(parallel, parallel_retries, strict=True)
        ),
        "state_contains_only_current_window_and_last_exchange": burst_report.get(
            "status"
        )
        == "accepted"
        and bounded
        and after_burst.get("status") == "accepted"
        and isinstance(result_of(after_burst).get("final"), dict)
        and result_of(after_burst)["final"].get("watermark") == 470,
    }
