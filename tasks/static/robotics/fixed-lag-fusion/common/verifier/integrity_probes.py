"""Independent physical drives, exact covariance controls and causal protocol checks."""

import itertools
from copy import deepcopy
from math import cos, hypot, sin
from pathlib import Path

import numpy as np
from probes import Run, surveyed_path

RADIOS = {"unit-s": "west", "unit-m": "north", "unit-k": "court"}


def config(lag=7, *, first=0):
    """Set an asymmetric installation with nonzero surveyed tag and anchor offsets."""
    return {
        "start_tick": first,
        "lag_ticks": lag,
        "prior_pose": [0.0, 0.0, 0.0],
        "prior_covariance": [
            [0.0025, 0.0002, 0.0],
            [0.0002, 0.0025, 0.0],
            [0.0, 0.0, 0.0016],
        ],
        "anchors": {"west": [-1.8, -0.4], "north": [0.5, 3.1], "court": [2.7, -1.6]},
        "radio_to_anchor": RADIOS,
        "anchor_bias_m": {"west": 0.05, "north": -0.03, "court": 0.11},
        "tag_in_body_m": [0.27, -0.11],
        "range_drop_cost": 4.0,
        "ambiguity_cost": 0.2,
    }


def packet(model, seq, events, stream="loader"):
    return {"config": model, "stream_id": stream, "sequence": seq, "events": events}


def motion(tick, value=(0.0, 0.0, 0.0), noise=(0.064, 0.064, 0.047)):
    return {
        "op": "advance",
        "tick": tick,
        "body_delta": list(value),
        "sigma": list(noise),
    }


def survey(tick, key, pose, noise=(0.045, 0.045, 0.034), version=1):
    return {
        "op": "upsert",
        "tick": tick,
        "id": key,
        "revision": version,
        "measurement": {"kind": "survey", "pose": list(pose), "sigma": list(noise)},
    }


def radio(tick, key, unit, value, noise=0.032, version=1):
    return {
        "op": "upsert",
        "tick": tick,
        "id": key,
        "revision": version,
        "measurement": {
            "kind": "range",
            "radio": unit,
            "value_m": value,
            "sigma_m": noise,
        },
    }


def retract(tick, key, rev):
    return {"op": "retract", "tick": tick, "id": key, "revision": rev}


def returned(reply, seq, stream="loader"):
    """Require a fresh accepted envelope before examining its actual evidence."""
    if (
        reply.get("status") != "accepted"
        or reply.get("sequence") != seq
        or reply.get("stream_id") != stream
    ):
        return {}
    result = reply.get("result")
    return result if isinstance(result, dict) else {}


def model_scores(result, channels):
    """Check the complete selected hypothesis set with finite nonnegative objectives."""
    profiles = result.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != len(channels) + 1:
        return None
    decoded = {}
    for profile in profiles:
        if not isinstance(profile, dict) or "excluded_radio" not in profile:
            return None
        key, score = profile["excluded_radio"], profile.get("score")
        if key not in channels and key is not None:
            return None
        if type(score) not in (int, float) or not np.isfinite(score) or score < -1e-9:
            return None
        decoded[key] = score
    return decoded if decoded.keys() == {*channels, None} else None


def pose_rows(rows, ticks):
    """Decode actual means and symmetric positive definite information reports."""
    if not isinstance(rows, list) or [row["tick"] for row in rows] != list(ticks):
        return None
    means = np.array([row["pose"] for row in rows], dtype=float)
    covariance = np.array([row["covariance"] for row in rows], dtype=float)
    if means.shape != (len(rows), 3) or covariance.shape != (len(rows), 3, 3):
        return None
    if (
        not np.isfinite(means).all()
        or not np.isfinite(covariance).all()
        or not np.allclose(covariance, covariance.transpose(0, 2, 1), atol=2e-8)
        or np.min(np.linalg.eigvalsh(covariance)) <= 0
    ):
        return None
    return means, covariance


def synthetic_range(model, pose, unit):
    """Project the surveyed tag using an independent direct coordinate formula."""
    x, y, yaw = pose
    lx, ly = model["tag_in_body_m"]
    anchor = model["radio_to_anchor"][unit]
    ax, ay = model["anchors"][anchor]
    return (
        hypot(
            x - ax + lx * cos(yaw) - ly * sin(yaw),
            y - ay + lx * sin(yaw) + ly * cos(yaw),
        )
        + model["anchor_bias_m"][anchor]
    )


def capture(model, count, seed, source=None):
    """Generate independent curves or replay the geometry of the attributed TUM track."""
    checkpoints = []
    for i in range(count):
        phase = seed / 11
        if source is None:
            xy = [
                0.65 * sin(0.27 * i + phase) + 0.025 * i,
                0.43 * cos(0.38 * i + phase) - 0.031 * i,
            ]
        else:
            xy = (source[i] - source[0]) * (1.5 + 0.04 * seed) + np.array([0.24, -0.33])
        checkpoints.append([*xy, 0.71 * sin(0.34 * i + phase) + 0.16 * i - 0.82])
    return np.asarray(checkpoints, dtype=float)


def sampled_drive(model, truth, seed, failure, wrong):
    """Sample odometry with signed slip and individual radio arrivals, including NLOS."""
    rng = np.random.default_rng(seed)
    events = []
    for i, pose in enumerate(truth):
        tick = i + model["start_tick"]
        current = []
        if i:
            px, py, heading = truth[i - 1]
            dx, dy = pose[:2] - [px, py]
            change = [
                cos(heading) * dx + sin(heading) * dy,
                -sin(heading) * dx + cos(heading) * dy,
                pose[2] - heading,
            ]
            distorted = (
                np.array(change)
                + np.array([0.016, -0.009, 0.009])
                + rng.normal(0, 0.003, 3)
            )
            current.append(motion(tick, distorted.tolist()))
        if i in (0, 6, 11, 16):
            current.append(survey(tick, "survey", pose.tolist()))
        # Healthy radios report independently, with deliberate holes. A strong range
        # fault follows receiver identity rather than changing the survey pose.
        for j, unit in enumerate(model["radio_to_anchor"]):
            if i % 4 == j + 1 and unit != wrong:
                continue
            fault = 0.63 + 0.014 * (i % 3) if wrong == unit and i >= failure else 0.0
            observation = (
                synthetic_range(model, pose, unit) + fault + rng.normal(0, 0.004)
            )
            current.append(radio(tick, "range-" + unit, unit, observation))
        events.append(current)
    return events


def physical_mission(run, state, index, source):
    """Qualify clean and isolated regimes on different target paths and radio faults."""
    first = 200 + 73 * index
    model = config(7 + index, first=first)
    truth = capture(model, 18 + index, 9 + index * 7, source)
    model["prior_pose"] = (truth[0] + [0.02, -0.02, 0.025]).tolist()
    if index == 2:
        model["tag_in_body_m"] = [-0.31, 0.22]
        model["radio_to_anchor"] = {
            "unit-s": "court",
            "unit-m": "west",
            "unit-k": "north",
        }
    wrong = ("unit-k", "unit-s", "unit-m")[index]
    evidence = sampled_drive(model, truth, 138 + 11 * index, 7, wrong)
    cuts = (0, 5, 11, len(evidence))
    for seq, (a, b) in enumerate(itertools.pairwise(cuts), start=1):
        events = [event for group in evidence[a:b] for event in group]
        spec = packet(model, seq, events)
        reply = run("track-integrity", spec, state=state)
        report = returned(reply, seq)
        start = max(0, b - model["lag_ticks"])
        rows = pose_rows(report.get("poses"), range(first + start, first + b))
        scores = model_scores(report, set(RADIOS))
        if rows is None or scores is None:
            return False
        active, _ = rows
        diff = active - truth[start:b]
        if (
            np.sqrt(np.mean(np.sum(diff[:, :2] ** 2, axis=1))) > 0.085
            or np.max(np.abs(diff[:, 2])) > 0.16
        ):
            return False
        expected = None if seq == 1 else wrong
        label = "nominal" if expected is None else "isolated"
        if report.get("integrity") != label or report.get("fault_radio") != expected:
            return False
        if scores[expected] + model["ambiguity_cost"] >= min(
            value for key, value in scores.items() if key != expected
        ):
            return False
        retired = [row.get("tick") for row in report.get("finalized", [])]
        if retired != list(
            range(first + max(0, a - model["lag_ticks"]), first + start)
        ):
            return False
        for row in report["finalized"]:
            delta = np.asarray(row["pose"]) - truth[row["tick"] - first]
            if np.linalg.norm(delta[:2]) > 0.18 or abs(delta[2]) > 0.21:
                return False
    return True


def exact_walk(last, model, surveys):
    """Solve the linear special case in one full-history array, independently of the lag."""
    count = last + 1
    means, covariances = [], []
    for axis, stdev in enumerate((0.064, 0.064, 0.047)):
        inverse = np.zeros((count, count))
        vector = np.zeros(count)
        prior = model["prior_covariance"][axis][axis]
        inverse[0, 0] = 1 / prior
        vector[0] = model["prior_pose"][axis] / prior
        for t in range(1, count):
            inverse[t - 1 : t + 1, t - 1 : t + 1] += (
                np.array([[1.0, -1.0], [-1.0, 1.0]]) / stdev**2
            )
        for t, position in surveys.items():
            sigma = (0.045, 0.045, 0.034)[axis]
            inverse[t, t] += 1 / sigma**2
            vector[t] += position[axis] / sigma**2
        means.append(np.linalg.solve(inverse, vector))
        covariances.append(np.diag(np.linalg.inv(inverse)))
    return np.asarray(means).T, np.stack(
        [np.diag(x) for x in zip(*covariances, strict=True)]
    )


def exact_window(run, state):
    """Check correlated smoothing, retention of retired information, and expired revisions."""
    cfg = config(3)
    cfg["prior_covariance"] = np.diag([0.04, 0.04, 0.031]).tolist()
    measured = [0.0, 0.0, 0.48]
    early = [survey(0, "heading", measured), motion(1), motion(2)]
    first = returned(run("track-integrity", packet(cfg, 1, early), state=state), 1)
    before = pose_rows(first.get("poses"), range(3))
    if before is None:
        return False
    exact = exact_walk(2, cfg, {0: measured})
    if not all(
        np.allclose(a, b, atol=3e-6, rtol=2e-5)
        for a, b in zip(before, exact, strict=True)
    ):
        return False
    revised = [0.0, 0.0, -0.35]
    events = [
        survey(1, "temporary", [0.0, 0.0, 0.8]),
        retract(1, "temporary", 2),
        survey(0, "heading", revised, version=2),
        motion(3),
        survey(0, "heading", measured, version=3),
        motion(4),
        motion(5),
    ]
    second = returned(run("track-integrity", packet(cfg, 2, events), state=state), 2)
    if second.get("events") != [
        "accepted",
        "retracted",
        "accepted",
        "advanced",
        "expired",
        "advanced",
        "advanced",
    ]:
        return False
    after = pose_rows(second.get("poses"), range(3, 6))
    retired = pose_rows(second.get("finalized"), range(3))
    if after is None or retired is None:
        return False
    exact = exact_walk(5, cfg, {0: revised})
    if not all(
        np.allclose(a, b[3:], atol=3e-6, rtol=2e-5)
        for a, b in zip(after, exact, strict=True)
    ):
        return False
    for tick in range(3):
        expected_pose, expected_cov = exact_walk(tick + 2, cfg, {0: revised})
        if not np.allclose(
            retired[0][tick], expected_pose[tick], atol=3e-6
        ) or not np.allclose(retired[1][tick], expected_cov[tick], atol=3e-6):
            return False
    return (
        second.get("integrity") == "nominal" and model_scores(second, set()) is not None
    )


def symmetry():
    """Generate an exact physical mirror symmetry with competing single-radio faults."""
    cfg = config(2)
    cfg.update(
        tag_in_body_m=[0.0, 0.0],
        prior_covariance=np.diag([0.0004, 0.0004, 0.001]).tolist(),
        anchors={"west": [-1.0, 0.0], "north": [0.0, 2.0], "court": [1.0, 0.0]},
        anchor_bias_m={"west": 0.0, "north": 0.0, "court": 0.0},
        ambiguity_cost=0.001,
    )
    scans = [
        radio(0, "same-left", "unit-s", 1.51),
        radio(0, "same-right", "unit-k", 1.51),
        radio(0, "on-center", "unit-m", 2.0),
    ]
    return cfg, scans


def symmetry_mission(run, state):
    """Keep a mirror-symmetric fault unclassified and retire its information conservatively."""
    cfg, scans = symmetry()
    report = returned(run("track-integrity", packet(cfg, 1, scans), state=state), 1)
    rows = pose_rows(report.get("poses"), [0])
    values = model_scores(report, set(RADIOS))
    if (
        rows is None
        or values is None
        or report.get("integrity") != "ambiguous"
        or report.get("fault_radio") is not None
    ):
        return False
    if not np.allclose(rows[0], [[0.0, 0.0, 0.0]], atol=2e-7) or not np.allclose(
        rows[1][0], cfg["prior_covariance"], atol=2e-7
    ):
        return False
    # Use the symmetric sign along x and explicitly include the best shift along y.
    # The independent two-dimensional objective is directly sampled on a fine local grid.
    X, Y = np.meshgrid(np.linspace(-0.3, 0.3, 601), np.linspace(-0.08, 0.08, 321))
    nominal = (X**2 + Y**2) / (2 * cfg["prior_covariance"][0][0])
    sensor_ranges = {
        "unit-s": np.hypot(X + 1, Y),
        "unit-k": np.hypot(X - 1, Y),
        "unit-m": np.hypot(X, Y - 2),
    }
    reading = {"unit-s": 1.51, "unit-k": 1.51, "unit-m": 2.0}
    for excluded, actual in values.items():
        expected = np.min(
            nominal
            + sum(
                0.5 * ((v - reading[key]) / 0.032) ** 2
                for key, v in sensor_ranges.items()
                if key != excluded
            )
        )
        expected += cfg["range_drop_cost"] if excluded is not None else 0.0
        if abs(actual - expected) > 0.004:
            return False
    after = packet(cfg, 2, [motion(1), motion(2), retract(0, "same-left", 2)])
    response = returned(run("track-integrity", after, state=state), 2)
    live = pose_rows(response.get("poses"), (1, 2))
    final = response.get("finalized", [])
    _, exact = exact_walk(2, cfg, {})
    return (
        live is not None
        and np.allclose(live[0], np.zeros((2, 3)), atol=2e-7)
        and np.allclose(live[1], exact[1:], atol=2e-6)
        and response.get("events") == ["advanced", "advanced", "expired"]
        and response.get("integrity") == "nominal"
        and len(final) == 1
        and final[0].get("status") == "ambiguous"
        and final[0].get("fault_radio") is None
    )


def recovery(run, state, control):
    """Use real process restart and lost output to compare the counterfactual survivor."""
    cfg, scans = symmetry()
    before = packet(cfg, 1, scans)
    original = run("track-integrity", before, state=state)
    comparator = run("track-integrity", before, state=control)
    if original != comparator or returned(original, 1).get("integrity") != "ambiguous":
        return False
    broken_retransmit = deepcopy(before)
    broken_retransmit["events"][0]["measurement"]["value_m"] = 1.52
    rejected = run("track-integrity", broken_retransmit, state=state)
    if (
        rejected.get("status") != "rejected"
        or rejected.get("result", False) is not None
    ):
        return False
    actions = [
        retract(0, "same-left", 2),
        retract(0, "same-left", 2),
        retract(0, "same-left", 1),
        retract(0, "same-left", 4),
        motion(1),
        retract(2, "missing", 1),
    ]
    next_packet = packet(cfg, 2, actions)
    if not run("track-integrity", next_packet, state=state, lost_reply=True).get(
        "nonzero"
    ):
        return False
    after = run("track-integrity", next_packet, state=state)
    if after != run("track-integrity", next_packet, state=control) or after != run(
        "track-integrity", next_packet, state=state
    ):
        return False
    active = returned(after, 2)
    if (
        active.get("integrity") != "isolated"
        or active.get("fault_radio") != "unit-k"
        or active.get("events")
        != ["retracted", "duplicate", "stale", "conflict", "advanced", "future"]
    ):
        return False
    other_stream = packet(cfg, 1, [motion(1)], stream="parts-cart")
    other = run("track-integrity", other_stream, state=state)
    if returned(other, 1, "parts-cart").get("integrity") != "nominal":
        return False
    inconsistent = packet(cfg, 3, [motion(3)])
    if not run("track-integrity", inconsistent, state=state, invalid=True).get(
        "atomic"
    ):
        return False
    final = packet(cfg, 3, [motion(2), retract(0, "same-right", 2)])
    fresh = run("track-integrity", final, state=state)
    if fresh != run("track-integrity", final, state=control):
        return False
    report = returned(fresh, 3)
    return (
        report.get("events") == ["advanced", "expired"]
        and report.get("integrity") == "nominal"
        and report.get("finalized", [{}])[0].get("fault_radio") == "unit-k"
        and run("track-integrity", other_stream, state=state) == other
    )


def numeric_jacobian(residual, point):
    """Form a finite-difference differential with no candidate math imports."""
    perturb = np.eye(point.size) * 2e-6
    return np.column_stack(
        [(residual(point + step) - residual(point - step)) / 4e-6 for step in perturb]
    )


def numeric_minimum(residual, initial):
    """Solve a small independently generated regression using square-root least squares."""
    point = np.array(initial).flatten()
    for _ in range(30):
        error = residual(point)
        jac = numeric_jacobian(residual, point)
        correction = np.linalg.lstsq(jac, -error, rcond=None)[0]
        if np.linalg.norm(correction) < 1e-10:
            break
        for factor in (1, 0.5, 0.25, 0.125, 0.0625):
            candidate = point + factor * correction
            if np.linalg.norm(residual(candidate)) < np.linalg.norm(error):
                point = candidate
                break
        else:
            break
    return point, numeric_jacobian(residual, point)


def dense_objective(values, first, config, events, first_residual):
    """Evaluate physical factors at direct coordinates independent of the implementation."""
    poses = values.reshape(-1, 3)
    errors = list(first_residual(poses[0]))
    for event in events:
        tick = event["tick"] - first
        if event["op"] == "advance":
            a, b = poses[tick - 1], poses[tick]
            dx, dy, dq = b - a
            yaw = a[2]
            predicted = np.array(
                [dx * cos(yaw) + dy * sin(yaw), dy * cos(yaw) - dx * sin(yaw), dq]
            )
            errors.extend((predicted - event["body_delta"]) / event["sigma"])
            continue
        observation = event["measurement"]
        if observation["kind"] == "survey":
            errors.extend((poses[tick] - observation["pose"]) / observation["sigma"])
        else:
            predicted = synthetic_range(config, poses[tick], observation["radio"])
            errors.append((predicted - observation["value_m"]) / observation["sigma_m"])
    return np.asarray(errors)


def nonlinear_eviction(run, state):
    """Recompute a nonlinear marginal using independent finite differences and QR."""
    cfg = config(3)
    cfg["range_drop_cost"] = 95.0
    cfg["prior_pose"] = [0.11, -0.07, 0.38]
    cfg["prior_covariance"] = [
        [0.035, 0.005, -0.002],
        [0.005, 0.024, 0.001],
        [-0.002, 0.001, 0.028],
    ]
    prior = np.linalg.cholesky(cfg["prior_covariance"])
    initial_residual = lambda pose: np.linalg.solve(prior, pose - cfg["prior_pose"])
    old_radio = radio(0, "retiring-radio", "unit-s", 2.20, 0.049)
    first_motion = motion(1, (0.36, -0.07, 0.50), (0.08, 0.066, 0.07))
    survey1 = survey(1, "survey-one", [0.49, 0.12, 0.75], (0.10, 0.09, 0.14))
    motion2 = motion(2, (0.4, -0.09, 0.63), (0.06, 0.087, 0.065))
    range2 = radio(2, "range-two", "unit-m", 2.68, 0.08)
    initial = [old_radio, first_motion, survey1, motion2, range2]
    guess = [[0.10, -0.10, 0.40], [0.46, 0.08, 0.9], [0.77, 0.35, 1.5]]
    first_fn = lambda point: dense_objective(point, 0, cfg, initial, initial_residual)
    first_fit, jac = numeric_minimum(first_fn, guess)
    first_cov = np.linalg.inv(jac.T @ jac)
    original = returned(run("track-integrity", packet(cfg, 1, initial), state=state), 1)
    observed = pose_rows(original.get("poses"), range(3))
    if observed is None or original.get("integrity") != "nominal":
        return False
    if not np.allclose(observed[0], first_fit.reshape(3, 3), atol=2e-5):
        return False
    incident = lambda point: dense_objective(
        point, 0, cfg, [old_radio, first_motion], initial_residual
    )
    around = first_fit[:6]
    qr_in = numeric_jacobian(incident, around)
    orthogonal = np.linalg.qr(qr_in[:, :3], mode="complete")[0][:, 3:].T
    root = orthogonal @ qr_in[:, 3:6]
    shift = np.linalg.lstsq(root, orthogonal @ incident(around), rcond=None)[0]
    shifted_mean = around[3:] - shift
    retained = lambda pose: root @ (pose - shifted_mean)
    new_motion = motion(3, (0.4, 0.09, 0.38), (0.088, 0.058, 0.065))
    new_survey = survey(3, "survey-three", [0.92, 0.3, 2.04], (0.039, 0.045, 0.06))
    final_events = [survey1, motion2, range2, new_motion, new_survey]
    last_fn = lambda point: dense_objective(point, 1, cfg, final_events, retained)
    final_fit, jac = numeric_minimum(last_fn, [*first_fit[3:], 0.95, 0.51, 1.88])
    final_cov = np.linalg.inv(jac.T @ jac)
    expected = [final_cov[i : i + 3, i : i + 3] for i in range(0, 9, 3)]
    # Move first, then try to revise the retired ranging sample using a conflicting value.
    second = [
        new_motion,
        new_survey,
        radio(0, "retiring-radio", "unit-s", 2.64, 0.05, version=2),
    ]
    report = returned(run("track-integrity", packet(cfg, 2, second), state=state), 2)
    rows = pose_rows(report.get("poses"), (1, 2, 3))
    retired = pose_rows(report.get("finalized"), (0,))
    scores = model_scores(report, {"unit-m"})
    return (
        rows is not None
        and retired is not None
        and scores is not None
        and report.get("events") == ["advanced", "accepted", "expired"]
        and report.get("integrity") == "nominal"
        and np.allclose(retired[0], first_fit[:3][None, :], atol=3e-5)
        and np.allclose(retired[1][0], first_cov[:3, :3], atol=4e-6)
        and np.allclose(rows[0], final_fit.reshape(3, 3), atol=4e-5)
        and np.allclose(rows[1], expected, atol=4e-6)
        and abs(scores[None] - np.linalg.norm(last_fn(final_fit)) ** 2 / 2) < 2e-5
    )


def sustained_causal_track(run, state):
    """Detect, recover, and detect a second independent radio fault during uninterrupted motion."""
    first = 819
    cfg = config(9, first=first)
    truth = capture(cfg, 48, 48)
    cfg["prior_pose"] = (truth[0] + [0.022, -0.017, 0.016]).tolist()
    original = sampled_drive(cfg, truth, 7063, 99, "unit-k")
    delayed = []
    for i, events in enumerate(original):
        events.extend(delayed)
        delayed = []
        for event in list(events):
            if event["op"] != "upsert" or event["measurement"]["kind"] != "range":
                continue
            unit = event["measurement"]["radio"]
            stamp = event["tick"] - first
            if (
                unit == "unit-k"
                and 5 <= stamp <= 13
                or (unit == "unit-s" and stamp >= 29)
            ) and (stamp == i):
                event["measurement"]["value_m"] += 0.68 if unit == "unit-k" else 0.52
            if (
                unit == "unit-m"
                and stamp == i
                and 1 < i < len(original) - 1
                and i % 3 == 1
            ):
                events.remove(event)
                delayed.append(event)
        if i in (24, 33, 42):
            events.append(survey(first + i, "independent-marker", truth[i].tolist()))
    cuts = [0, 5, 14, 26, 39, 48]
    labels = [None, "unit-k", None, "unit-s", "unit-s"]
    for seq, (a, b, unit) in enumerate(
        zip(cuts[:-1], cuts[1:], labels, strict=True), start=1
    ):
        events = [event for group in original[a:b] for event in group]
        result = returned(
            run("track-integrity", packet(cfg, seq, events), state=state), seq
        )
        keep = max(0, b - cfg["lag_ticks"])
        decoded = pose_rows(result.get("poses"), range(first + keep, first + b))
        label = "nominal" if unit is None else "isolated"
        if (
            decoded is None
            or result.get("integrity") != label
            or result.get("fault_radio") != unit
        ):
            return False
        offsets = decoded[0] - truth[keep:b]
        if (
            np.sqrt(np.mean(np.sum(offsets[:, :2] ** 2, axis=1))) > 0.10
            or np.max(np.abs(offsets[:, 2])) > 0.19
            or any(
                code not in ("advanced", "accepted")
                for code in result.get("events", [])
            )
        ):
            return False
        if [row.get("tick") for row in result.get("finalized", [])] != list(
            range(first + max(0, a - cfg["lag_ticks"]), first + keep)
        ):
            return False
    return True


def integrity_cases(run: Run, root: Path, dataset: Path) -> dict[str, bool]:
    """Assess complete integration missions with an independent test dispatcher."""
    source = surveyed_path(dataset)
    checks = {
        "track_measured_motion_through_a_radio_fault": lambda: physical_mission(
            run, root / "surveyed", 0, source[22:]
        ),
        "track_with_asymmetric_antenna_and_radio_swap": lambda: physical_mission(
            run, root / "turns", 2, None
        ),
        "track_independent_turns_through_late_fault": lambda: physical_mission(
            run, root / "second", 1, None
        ),
        "relinearize_active_body_motion_with_frozen_nonlinear_marginal": lambda: (
            nonlinear_eviction(run, root / "evict")
        ),
        "retain_exact_conditional_information_at_retirement": lambda: exact_window(
            run, root / "linear"
        ),
        "abstain_on_mirror_fault_and_avoid_committing_false_information": lambda: (
            symmetry_mission(run, root / "mirror")
        ),
        "recover_radio_integrity_then_isolate_a_second_outage": lambda: (
            sustained_causal_track(run, root / "sustained")
        ),
        "correct_live_fault_then_replay_lost_response_across_restart": lambda: recovery(
            run, root / "crash", root / "control"
        ),
    }
    outcomes = {}
    for name, probe in checks.items():
        try:
            outcomes[name] = bool(probe())
        except (
            IndexError,
            KeyError,
            OSError,
            OverflowError,
            TypeError,
            ValueError,
            np.linalg.LinAlgError,
        ):
            outcomes[name] = False
    return outcomes
