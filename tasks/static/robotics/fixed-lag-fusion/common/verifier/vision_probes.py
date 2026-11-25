"""Drive a live camera graph and compare it with an all-history surveyed fit."""

import json
import os
import pwd
import signal
import subprocess
import sys
from dataclasses import dataclass
from math import cos, sin
from pathlib import Path
from selectors import EVENT_READ, DefaultSelector
from time import monotonic

import gtsam as g
import numpy as np
from gtsam.symbol_shorthand import L, X


def transform(roll, pitch, yaw, position):
    return g.Pose3(g.Rot3.Ypr(yaw, pitch, roll), np.asarray(position, dtype=float))


def packet_pose(pose):
    q = pose.rotation().toQuaternion()
    return {
        "translation": pose.translation().tolist(),
        "quaternion_wxyz": [q.w(), q.x(), q.y(), q.z()],
    }


def from_packet(pose):
    rotation = np.asarray(pose["quaternion_wxyz"], dtype=float)
    position = np.asarray(pose["translation"], dtype=float)
    if (
        rotation.shape != (4,)
        or position.shape != (3,)
        or not np.all(np.isfinite(position))
        or not np.all(np.isfinite(rotation))
        or abs(np.linalg.norm(rotation) - 1) > 1e-5
    ):
        raise ValueError("Invalid reported pose")
    return g.Pose3(g.Rot3.Quaternion(*rotation), position)


@dataclass
class Capture:
    """Hold surveyed motion and calibration separately from the public manifest."""

    manifest: dict
    poses: list
    relative: list
    features: list
    mounts: dict


def capture(seed, reverse=False):
    rng = np.random.default_rng(seed)
    direction = -1 if reverse else 1
    poses = [
        transform(
            0.025 * sin(k * 0.18),
            0.075 * cos(k * 0.14),
            0.032 * k,
            (direction * 0.07 * k, 0.37 * sin(0.14 * k), 0.13 * sin(0.24 * k)),
        )
        for k in range(42)
    ]
    mounts = {
        "forward-camera": (
            transform(0.024, -0.037, 0.043, (0.035, -0.08, 0.13)),
            [495.0, 481.0, 0.0, 320.0, 240.0],
        ),
        "alternate-camera": (
            transform(-0.1, 0.065, -0.19, (0.145, -0.06, 0.19)),
            [534.0, 513.0, 0.3, 316.0, 237.0],
        ),
    }
    points = np.array(
        [
            [
                direction * (0.12 + 0.4 * (j % 4)),
                -0.72 + 0.51 * (j // 4),
                3.1 + 0.44 * (j % 3),
            ]
            for j in range(12)
        ]
    )
    seeds = points + rng.normal(0, 0.20, points.shape)
    anchors = (0, 3, 6, 9)
    seeds[list(anchors)] = points[list(anchors)] + rng.normal(
        0, 0.015, (len(anchors), 3)
    )
    odometry_sigmas = np.array([0.026, 0.03, 0.035, 0.043, 0.044, 0.06])
    prior_pose = poses[0].retract(
        np.array([-0.004, 0.004, 0.002, 0.006, -0.005, 0.003])
    )
    relative, features = [None], [[] for _ in poses]
    for frame, body in enumerate(poses):
        name = "forward-camera" if frame < 19 else "alternate-camera"
        extrinsic, intrinsics = mounts[name]
        camera = g.PinholeCameraCal3_S2(body.compose(extrinsic), g.Cal3_S2(*intrinsics))
        if frame:
            noise = rng.normal(0, odometry_sigmas * 0.15)
            offset = np.array([0.004, -0.003, 0.008, direction * 0.018, -0.009, 0.006])
            relative.append(poses[frame - 1].between(body).retract(noise + offset))
        for j, point in enumerate(points):
            last_frame = 22 + (j % 3) if j in (5, 8, 11) else 35 + (j % 4)
            if not ((j % 4) * 2 <= frame <= last_frame) or (j + frame) % 11 == 3:
                continue
            arrival = min(len(poses) - 1, frame + (j * 5 + frame * 3) % 4)
            if frame < 19 and arrival >= 19:
                arrival = max(arrival, 20)
            pixel = camera.project(point) + rng.normal(0, 0.33, 2)
            features[arrival].append(
                {
                    "id": f"pixel-{frame}-{j}",
                    "version": 1,
                    "action": "put",
                    "frame": frame,
                    "landmark": f"track-{j:02d}",
                    "camera": name,
                    "pixel": pixel.tolist(),
                    "sigma_px": 0.75,
                }
            )
    manifest = {
        "lag_frames": 8,
        "initial_pose": packet_pose(prior_pose),
        "initial_sigmas": [0.009] * 3 + [0.012] * 3,
        "odometry_sigmas": odometry_sigmas.tolist(),
        "calibrations": {
            name: {"body_from_camera": packet_pose(extrinsic), "intrinsics": intrinsics}
            for name, (extrinsic, intrinsics) in mounts.items()
        },
        "landmarks": {
            f"track-{j:02d}": {
                "point": point.tolist(),
                "sigma": 0.085 if j in anchors else 4.0,
            }
            for j, point in enumerate(seeds)
        },
    }
    return Capture(manifest, poses, relative, features, mounts)


class CandidateStream:
    """Send one live record at a time to the staged candidate under restricted credentials."""

    def __init__(self, app, manifest):
        user = {}
        if os.geteuid() == 0:
            account = pwd.getpwnam("candidate")
            user = {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []}
        environment = {
            key: os.environ[key]
            for key in ("PATH", "PYTHONPATH", "LANG")
            if key in os.environ
        }
        environment.update(
            OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", HOME=str(manifest.parent)
        )
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "lagfusion",
                "smooth-tracks",
                "--manifest",
                manifest,
            ],
            cwd=app,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
            start_new_session=True,
            env=environment,
            **user,
        )
        self.selector = DefaultSelector()
        self.selector.register(self.process.stdout, EVENT_READ)
        self.buffer = b""

    def send(self, packet):
        data = (json.dumps(packet, allow_nan=False) + "\n").encode()
        if self.process.stdin.write(data) != len(data):
            raise ValueError("Worker did not consume the packet")
        deadline = monotonic() + 3.0
        while b"\n" not in self.buffer:
            if not self.selector.select(max(0.0, deadline - monotonic())):
                raise ValueError("Worker did not emit a response")
            chunk = os.read(self.process.stdout.fileno(), 4096)
            if not chunk:
                raise ValueError("Worker closed its response stream")
            self.buffer += chunk
            if len(self.buffer) > 262144:
                raise ValueError("Response exceeds line budget")
        response, self.buffer = self.buffer.split(b"\n", 1)
        value = json.loads(response)
        if value["request_id"] != packet["request_id"]:
            raise ValueError("Response does not match the request")
        return value

    def close(self):
        self.selector.close()
        self.process.stdin.close()
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait(timeout=3)
        self.process.stdout.close()


def offline(data, accepted, frame):
    """Estimate one full graph independently from the incremental solver interface."""
    initial = from_packet(data.manifest["initial_pose"])
    prior = g.noiseModel.Diagonal.Sigmas(np.asarray(data.manifest["initial_sigmas"]))
    odom = g.noiseModel.Diagonal.Sigmas(np.asarray(data.manifest["odometry_sigmas"]))
    graph, values = g.NonlinearFactorGraph(), g.Values()
    graph.add(g.PriorFactorPose3(X(0), initial, prior))
    values.insert(X(0), initial)
    for index in range(1, frame + 1):
        delta = data.relative[index]
        graph.add(g.BetweenFactorPose3(X(index - 1), X(index), delta, odom))
        values.insert(X(index), values.atPose3(X(index - 1)).compose(delta))
    landmark_keys = {
        name: L(index) for index, name in enumerate(sorted(data.manifest["landmarks"]))
    }
    for row in accepted.values():
        point = landmark_keys[row["landmark"]]
        if not values.exists(point):
            prior = data.manifest["landmarks"][row["landmark"]]
            seed = np.array(prior["point"])
            graph.add(
                g.PriorFactorPoint3(
                    point, seed, g.noiseModel.Isotropic.Sigma(3, prior["sigma"])
                )
            )
            values.insert(point, seed)
        extrinsic, calibration = data.mounts[row["camera"]]
        model = g.noiseModel.Isotropic.Sigma(2, row["sigma_px"])
        graph.add(
            g.GenericProjectionFactorCal3_S2(
                np.array(row["pixel"]),
                model,
                X(row["frame"]),
                point,
                g.Cal3_S2(*calibration),
                extrinsic,
            )
        )
    params = g.LevenbergMarquardtParams()
    params.setMaxIterations(30)
    answer = g.LevenbergMarquardtOptimizer(graph, values, params).optimize()
    return answer.atPose3(X(frame)), g.Marginals(graph, answer).marginalCovariance(
        X(frame)
    )


def verify_pose(state, frame, lag, last_seen):
    assert state["frames"] == list(range(max(0, frame - lag), frame + 1)), (
        "reported active frames",
        state["frames"],
    )
    expected = sorted(
        name for name, latest in last_seen.items() if latest >= frame - lag
    )
    assert state["landmarks"] == expected, (
        "active landmark retirement",
        state["landmarks"],
        expected,
    )
    p = from_packet(state["pose"])
    covariance = np.asarray(state["covariance"], dtype=float)
    assert covariance.shape == (6, 6) and np.all(np.isfinite(covariance)), (
        "invalid covariance shape or range"
    )
    assert (
        np.allclose(covariance, covariance.T, atol=1e-8)
        and np.min(np.linalg.eigvalsh(covariance)) > 0
    ), "covariance must be positive definite"
    return p, covariance


def compare_batch(estimate, cov, offline_pose, offline_cov):
    target_values = np.linalg.eigvalsh(offline_cov)
    relative = np.linalg.norm(offline_cov - cov) / np.linalg.norm(offline_cov)
    ratio = np.linalg.eigvalsh(cov) / target_values
    translation = np.linalg.norm(estimate.translation() - offline_pose.translation())
    rotation = np.linalg.norm(
        g.Rot3.Logmap(estimate.rotation().between(offline_pose.rotation()))
    )
    return {
        "covariance_relative_error": float(relative),
        "largest_eigenvalue_ratio_error": float(max(abs(ratio - 1))),
        "position_difference_m": float(translation),
        "rotation_difference_rad": float(rotation),
    }


def run_case(app, manifest_path, seed, reverse, revisions):
    data = capture(seed, reverse)
    manifest_path.write_text(json.dumps(data.manifest), encoding="utf-8")
    worker = CandidateStream(app, manifest_path)
    accepted, measures, orientation, receipt_checks = {}, [], [], []
    number = 0
    changed = None
    comparisons = {}
    last_seen = {}
    try:
        for frame in range(len(data.poses)):

            def request(operation, retry=False, *, frame=frame, **kwargs):
                nonlocal number
                number += 1
                payload = {"request_id": number, "operation": operation, **kwargs}
                reply = worker.send(payload)
                if retry:
                    receipt_checks.append(worker.send(payload) == reply)
                assert reply["frame"] == frame, ("wrong newest frame", reply["frame"])
                return reply

            body = request(
                "frame",
                **(
                    {"frame": frame, "odometry": packet_pose(data.relative[frame])}
                    if frame
                    else {"frame": frame}
                ),
            )
            incoming = data.features[frame]
            if revisions and frame == 21:
                idx = next(i for i, row in enumerate(incoming) if row["frame"] < 21)
                clean = incoming[idx]
                wrong = {
                    **clean,
                    "pixel": [clean["pixel"][0] + 45.0, clean["pixel"][1] - 26.0],
                    "sigma_px": 0.49,
                }
                incoming = [*incoming[:idx], wrong, *incoming[idx + 1 :]]
                changed = clean, wrong
            if incoming:
                body = request(
                    "tracks", updates=incoming, retry=(frame == 14 or frame == 21)
                )
                for row in incoming:
                    assert body["updates"].get(row["id"]) == "applied", (
                        "disposition",
                        row["id"],
                        body["updates"],
                    )
                    accepted[row["id"]] = row
                    last_seen[row["landmark"]] = frame
            if changed and frame in (22, 23):
                clean, wrong = changed
                item = (
                    {
                        "id": clean["id"],
                        "action": "retract",
                        "frame": clean["frame"],
                        "version": 2,
                    }
                    if frame == 22
                    else {**clean, "version": 3}
                )
                body = request("tracks", updates=[item], retry=True)
                assert body["updates"].get(clean["id"]) == "applied", (
                    "live replacement",
                    body["updates"],
                )
                if frame == 22:
                    accepted.pop(clean["id"])
                else:
                    accepted[clean["id"]] = item
                    last_seen[item["landmark"]] = frame
            if revisions and frame == 30:
                clean, _ = changed
                item = {
                    "id": clean["id"],
                    "action": "retract",
                    "frame": clean["frame"],
                    "version": 4,
                }
                expired = request("tracks", updates=[item])
                receipt_checks.append(
                    expired["updates"] == {clean["id"]: "expired"}
                    and expired["state"] == body["state"]
                )
                body = expired
            estimate, covariance = verify_pose(
                body["state"], frame, data.manifest["lag_frames"], last_seen
            )
            truth = data.poses[frame]
            measures.append(
                float(np.linalg.norm(estimate.translation() - truth.translation()))
            )
            orientation.append(
                float(
                    np.linalg.norm(
                        g.Rot3.Logmap(estimate.rotation().between(truth.rotation()))
                    )
                )
            )
            if frame in (16, 22, 23, 33, 41):
                reference, ref_cov = offline(data, accepted, frame)
                comparisons[str(frame)] = compare_batch(
                    estimate, covariance, reference, ref_cov
                )
        rms = float(np.sqrt(np.mean(np.square(measures[12:]))))
        detail = {
            "position_rmse_m": rms,
            "terminal_position_error_m": measures[-1],
            "terminal_rotation_max_rad": max(orientation[-12:]),
            "batch_comparisons": comparisons,
            "receipt_checks": receipt_checks,
            "last_active_landmarks": len(body["state"]["landmarks"]),
        }
        corrected = all(
            comparisons[str(frame)]["position_difference_m"] < 0.06
            and comparisons[str(frame)]["rotation_difference_rad"] < 0.04
            for frame in (22, 23)
        )
        return {
            "track_accuracy": rms < 0.19
            and measures[-1] < 0.25
            and max(orientation[-12:]) < 0.09,
            "full_marginal": all(
                row["covariance_relative_error"] < 0.35
                and row["largest_eigenvalue_ratio_error"] < 0.45
                and row["position_difference_m"] < 0.10
                and row["rotation_difference_rad"] < 0.05
                for row in comparisons.values()
            ),
            "revisions_and_retries": bool(receipt_checks)
            and all(receipt_checks)
            and corrected,
        }, detail
    except (
        AssertionError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        return {
            "track_accuracy": False,
            "full_marginal": False,
            "revisions_and_retries": False,
        }, {"error": str(exc)}
    finally:
        worker.close()


def vision_cases(app: Path, scratch: Path):
    """Evaluate three held-out live trajectories including active and expired revisions."""
    outcomes, evidence = {}, {}
    for name, seed, reverse, revisions in (
        ("camera_handoff", 127, False, False),
        ("reverse_baseline", 305, True, True),
        ("late_track_edit", 130, False, True),
    ):
        outcomes[name], evidence[name] = run_case(
            app, scratch / (name + ".json"), seed, reverse, revisions
        )
    return outcomes, evidence
