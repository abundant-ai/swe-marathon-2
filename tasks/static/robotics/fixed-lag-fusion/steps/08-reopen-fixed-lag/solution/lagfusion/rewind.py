"""Bounded nonlinear factor rewind with a durable, irreversible Schur boundary."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import gtsam as gt
import numpy as np
from gtsam.symbol_shorthand import L, X

from .vision import identifier, integer, output_pose, pose, sigma, vector


def diagonal(row):
    return gt.noiseModel.Diagonal.Sigmas(vector(row, 6, positive=True))


def json_bytes(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def ordered_joint(graph, value, keys):
    """Return joint covariance with blocks in caller key order."""
    if len(keys) == 1:
        return gt.Marginals(graph, value).marginalCovariance(keys[0])
    blocks = gt.Marginals(graph, value).jointMarginalCovariance(keys)
    return np.block([[blocks.at(i, j) for j in keys] for i in keys])


class Rewind:
    """Solve the archive and serve only the live state and a marginal of it."""

    edit_kinds = frozenset({"loop", "pixel"})

    def __init__(self, manifest):
        self.lag = integer(manifest["lag_frames"], 2)
        self.horizon = integer(manifest["rewind_frames"], 3)
        if not 2 <= self.lag < self.horizon <= 64:
            raise ValueError("Invalid window lengths")
        self.manifest = manifest
        self.base_pose = pose(manifest["initial_pose"])
        self.initial_noise = diagonal(manifest["initial_sigmas"])
        self.motion_noise = diagonal(manifest["odometry_sigmas"])
        self.landmarks = {}
        for number, (name, row) in enumerate(
            sorted(manifest.get("landmarks", {}).items())
        ):
            self.landmarks[identifier(name)] = (
                L(number),
                vector(row["point"], 3),
                gt.noiseModel.Isotropic.Sigma(3, sigma(row["sigma"])),
            )
        self.cameras = {
            identifier(name): (
                pose(row["body_from_camera"]),
                gt.Cal3_S2(*vector(row["intrinsics"], 5)),
            )
            for name, row in manifest.get("calibrations", {}).items()
        }
        self.newest = -1
        self.floor = 0
        self.odometry = {}
        self.edits = {}
        self.boundary = gt.GaussianFactorGraph()
        self.boundary_anchors = gt.Values()
        self.estimate = gt.Values()
        self.last_request = self.last_reply = None

    def factors(self):
        for index in range(self.boundary.size()):
            yield (
                ("boundary", index),
                gt.LinearContainerFactor(
                    self.boundary.at(index),
                    self.boundary_anchors,
                ),
            )
        if self.floor == 0:
            yield (
                ("origin", 0),
                gt.PriorFactorPose3(X(0), self.base_pose, self.initial_noise),
            )
        for end, value in sorted(self.odometry.items()):
            yield (
                ("odometry", end),
                gt.BetweenFactorPose3(
                    X(end - 1),
                    X(end),
                    pose(value),
                    self.motion_noise,
                ),
            )
        for name, (key, point, noise) in self.landmarks.items():
            yield ("landmark", name), gt.PriorFactorPoint3(key, point, noise)
        for name, row in self.edits.items():
            if row["action"] == "put":
                yield ("edit", name), self.measurement_factor(row)

    def measurement_factor(self, row: dict) -> gt.NonlinearFactor:
        """Build one native factor from a validated active loop or pixel record."""
        if row["kind"] == "loop":
            return gt.BetweenFactorPose3(
                X(row["i"]),
                X(row["j"]),
                pose(row["measurement"]),
                diagonal(row["sigmas"]),
            )
        landmark, _, _ = self.landmarks[row["landmark"]]
        extrinsic, optical = self.cameras[row["camera"]]
        return gt.GenericProjectionFactorCal3_S2(
            np.asarray(row["pixel"]),
            gt.noiseModel.Isotropic.Sigma(2, row["sigma_px"]),
            X(row["i"]),
            landmark,
            optical,
            extrinsic,
        )

    def graph(self):
        result = gt.NonlinearFactorGraph()
        for _, factor in self.factors():
            result.add(factor)
        return result

    def solve(self):
        graph = self.graph()
        parameters = gt.LevenbergMarquardtParams()
        parameters.setMaxIterations(40)
        parameters.setRelativeErrorTol(1e-9)
        parameters.setAbsoluteErrorTol(1e-9)
        self.estimate = gt.LevenbergMarquardtOptimizer(
            graph, self.estimate, parameters
        ).optimize()
        return graph

    def initialize_values(self) -> None:
        """Seed the first body pose and persistent world points prior to the first solve."""
        self.estimate.insert(X(0), self.base_pose)
        for key, point, _ in self.landmarks.values():
            self.estimate.insert(key, point)

    def append(self, packet):
        index = packet["frame"]
        if type(index) is not int or index != self.newest + 1:
            raise ValueError("Nonconsecutive frame")
        if index == 0:
            if packet.get("odometry") is not None:
                raise ValueError("Frame zero has no odometry")
            self.initialize_values()
        else:
            self.odometry[index] = packet["odometry"]
            self.estimate.insert(
                X(index),
                self.estimate.atPose3(X(index - 1)).compose(pose(packet["odometry"])),
            )
        self.newest = index
        self.solve()
        floor = max(0, index - self.horizon)
        if floor > self.floor:
            self.seal(floor)

    def seal(self, floor):
        outgoing = {X(index) for index in range(self.floor, floor)}
        graph = gt.NonlinearFactorGraph()
        for (kind, identity), factor in list(self.factors()):
            if kind != "boundary" and not outgoing.intersection(factor.keys()):
                continue
            graph.add(factor)
            if kind == "odometry":
                del self.odometry[identity]
        frozen = graph.linearize(self.estimate)
        _, self.boundary = frozen.eliminatePartialSequential(sorted(outgoing))
        for key in outgoing:
            self.estimate.erase(key)
        self.boundary_anchors = gt.Values()
        keys = {
            key
            for index in range(self.boundary.size())
            for key in self.boundary.at(index)
        }
        for key in sorted(keys):
            self.boundary_anchors.insert(key, self.anchor_value(key))
        self.edits = {
            name: row for name, row in self.edits.items() if row["i"] >= floor
        }
        self.floor = floor

    def anchor_value(self, key: int) -> gt.Pose3 | np.ndarray:
        """Read the linearization point in the variable's native manifold."""
        if gt.Symbol(key).chr() == ord("x"):
            return self.estimate.atPose3(key)
        return self.estimate.atPoint3(key)

    def validate_measurement(self, row: dict, old: dict | None) -> None:
        """Decode the editable content, retaining immutable pixel provenance on retraction."""
        if row["kind"] == "pixel":
            if row["action"] == "put":
                self.cameras[row["camera"]]
                self.landmarks[row["landmark"]]
                vector(row["pixel"], 2)
                sigma(row["sigma_px"])
            else:
                row.update(camera=old["camera"], landmark=old["landmark"])
            if old and any(old[k] != row[k] for k in ("camera", "landmark")):
                raise ValueError("Pixel revision changed its calibration or landmark")
        elif row["action"] == "put":
            pose(row["measurement"])
            vector(row["sigmas"], 6, positive=True)

    def revise(self, updates):
        if self.newest < 0 or not isinstance(updates, list):
            raise ValueError("An edit requires a pose and an update list")
        pending, results = {}, {}
        for entry in updates:
            name = identifier(entry["id"])
            i, j = (integer(entry[k]) for k in ("i", "j"))
            if name in results or not 0 <= i <= j <= self.newest:
                raise ValueError("Duplicate or invalid factor endpoints")
            kind = entry["kind"]
            action = entry["action"]
            version = integer(entry["version"], 1)
            if action not in ("put", "retract") or kind not in self.edit_kinds:
                raise ValueError("Unknown factor operation")
            single_frame = kind != "loop"
            if (i == j) != single_frame:
                raise ValueError("Factor arity disagrees with endpoints")
            if i < self.floor:
                results[name] = "sealed"
                continue
            old = self.edits.get(name)
            if not old and action != "put":
                raise ValueError("First update must be a measurement")
            if old and (i, j, kind) != (old["i"], old["j"], old["kind"]):
                raise ValueError("A revision cannot change its endpoints")
            if version != (old["version"] + 1 if old else 1):
                raise ValueError("Nonconsecutive factor version")
            row = dict(entry)
            self.validate_measurement(row, old)
            pending[name] = row
            results[name] = "applied"
        self.edits.update(pending)
        return results

    def apply(self, packet):
        op = packet["operation"]
        dispositions = {}
        if op == "frame":
            self.append(packet)
        elif op == "edit":
            dispositions = self.revise(packet["updates"])
        elif op != "estimate":
            raise ValueError("Unknown operation")
        if self.newest < 0:
            raise ValueError("No pose has been accepted")
        graph = self.solve()
        oldest = max(0, self.newest - self.lag)
        keys = (
            [X(self.newest)] if oldest == self.newest else [X(oldest), X(self.newest)]
        )
        marginals = self.report_covariance(graph, keys, packet)
        return {
            "request_id": packet["request_id"],
            "frame": self.newest,
            "active_frames": list(range(oldest, self.newest + 1)),
            "archive_start": self.floor,
            "archived_frames": self.newest - self.floor + 1,
            "pose": output_pose(self.estimate.atPose3(X(self.newest))),
            "joint_frame_ids": [gt.Symbol(k).index() for k in keys],
            **marginals,
            "updates": dispositions,
        }

    def report_covariance(
        self, graph: gt.NonlinearFactorGraph, keys: list[int], packet: dict
    ) -> dict:
        """Compute a pose-pair marginal in the requested output order."""
        return {"joint_covariance": ordered_joint(graph, self.estimate, keys).tolist()}

    def encode_state(self, data: dict) -> bytes:
        """Encode a complete checkpoint including the last accepted receipt."""
        return json_bytes(data)

    def decode_state(self, data: bytes) -> dict:
        """Decode a checkpoint written by this solver."""
        return json.loads(data)

    def snapshot(self, path):
        data = {
            "manifest_sha256": hashlib.sha256(json_bytes(self.manifest)).hexdigest(),
            "newest": self.newest,
            "floor": self.floor,
            "odometry": self.odometry,
            "edits": self.edits,
            "boundary": self.boundary.serialize(),
            "anchors": self.boundary_anchors.serialize(),
            "estimate": self.estimate.serialize(),
            "last_request": self.last_request,
            "last_reply": self.last_reply,
        }
        with NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            try:
                output.write(self.encode_state(data))
                output.flush()
                os.fsync(output.fileno())
                os.replace(temporary, path)
                descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            finally:
                temporary.unlink(missing_ok=True)

    def recover(self, path):
        data = self.decode_state(path.read_bytes())
        if (
            data["manifest_sha256"]
            != hashlib.sha256(json_bytes(self.manifest)).hexdigest()
        ):
            raise ValueError("Manifest changed across restart")
        self.newest, self.floor = data["newest"], data["floor"]
        self.edits = data["edits"]
        self.odometry = {int(key): value for key, value in data["odometry"].items()}
        self.boundary.deserialize(data["boundary"])
        self.boundary_anchors.deserialize(data["anchors"])
        self.estimate.deserialize(data["estimate"])
        self.last_request, self.last_reply = data["last_request"], data["last_reply"]


def stream(manifest, state: Path, source, destination):
    """Run the fixed-extrinsic repair stream under the Stage 8 contract."""
    run_stream(Rewind(manifest), state, source, destination)


def run_stream(solver, state: Path, source, destination):
    """Restore committed state and serve one writer with durable exact replies."""
    from .__main__ import invalid_constant

    if state.exists():
        solver.recover(state)
    for line in source:
        packet = json.loads(line, parse_constant=invalid_constant)
        request_id = packet["request_id"]
        if type(request_id) is not int:
            raise ValueError("Request ID must be an integer")
        if packet == solver.last_request:
            reply = solver.last_reply
        else:
            prior_id = solver.last_request["request_id"] if solver.last_request else 0
            if request_id != prior_id + 1:
                raise ValueError("Missing sequence or modified retry")
            reply = solver.apply(packet)
            solver.last_request, solver.last_reply = packet, reply
            solver.snapshot(state)
        print(json_bytes(reply).decode(), file=destination, flush=True)
