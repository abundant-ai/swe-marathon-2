"""Reopen the repair window with uncertain, persistent camera attachments."""

from collections.abc import Iterator
import json
from pathlib import Path
from typing import TextIO
import zlib

import gtsam as gt
from gtsam.symbol_shorthand import C, X
import numpy as np

from .mount_math import mount_projection_factor, mount_survey_factor
from .rewind import Rewind, diagonal, json_bytes, ordered_joint, run_stream
from .vision import output_pose, pose, vector


CHECKPOINT_BYTES = 128 * 1024


class MountRewind(Rewind):
    """Estimate mounts with the archived poses and retain them through elimination."""

    edit_kinds = Rewind.edit_kinds | {"mount_survey"}

    def __init__(self, manifest: dict) -> None:
        """Initialize one prior per uncertain camera described by the manifest."""
        super().__init__(manifest)
        uncertain = manifest["uncertain_cameras"]
        if type(uncertain) is not dict or not 1 <= len(uncertain) <= 3:
            raise ValueError("Select one to three uncertain cameras")
        self.mounts = {
            name: (C(index), self.cameras[name][0], diagonal(uncertain[name]))
            for index, name in enumerate(sorted(uncertain))
        }
        self.default_mount = next(iter(self.mounts))

    def initialize_values(self) -> None:
        """Seed the uncertain mounts once, alongside the first pose and landmarks."""
        super().initialize_values()
        for key, nominal, _ in self.mounts.values():
            self.estimate.insert(key, nominal)

    def factors(self) -> Iterator[tuple[tuple[str, object], gt.NonlinearFactor]]:
        """Extend the live graph with persistent, independent mount priors."""
        yield from super().factors()
        for name, (key, nominal, noise) in self.mounts.items():
            yield ("mount_prior", name), gt.PriorFactorPose3(key, nominal, noise)

    def measurement_factor(self, row: dict) -> gt.NonlinearFactor:
        """Build a variable-mount camera factor or reuse the fixed-mount model.

        Args:
            row: Validated active record with active body-pose endpoints.

        Returns:
            A nonlinear factor rebuilt from durable measurement data.
        """
        if row["kind"] == "mount_survey":
            key, _, _ = self.mounts[row["camera"]]
            return mount_survey_factor(X(row["i"]), key, pose(row["measurement"]), row["sigmas"])
        if row["kind"] == "pixel" and row["camera"] in self.mounts:
            landmark, _, _ = self.landmarks[row["landmark"]]
            key, _, _ = self.mounts[row["camera"]]
            _, optical = self.cameras[row["camera"]]
            return mount_projection_factor(X(row["i"]), key, landmark, optical,
                                           np.asarray(row["pixel"]), row["sigma_px"])
        return super().measurement_factor(row)

    def anchor_value(self, key: int) -> gt.Pose3 | np.ndarray:
        """Preserve a correlated mount's SE(3) chart when sealing body poses."""
        if gt.Symbol(key).chr() == ord("c"):
            return self.estimate.atPose3(key)
        return super().anchor_value(key)

    def validate_measurement(self, row: dict, old: dict | None) -> None:
        """Validate survey provenance, preserving the camera on retraction."""
        if row["kind"] != "mount_survey":
            super().validate_measurement(row, old)
            return
        if row["action"] == "put":
            camera = row["camera"]
            if camera not in self.mounts:
                raise ValueError("Survey must refer to an uncertain camera")
            pose(row["measurement"])
            vector(row["sigmas"], 6, positive=True)
        else:
            camera = row.get("camera", old["camera"])
        if old is not None and camera != old["camera"]:
            raise ValueError("Survey revision changed its camera")
        row["camera"] = camera

    def revise(self, updates: list[dict]) -> dict[str, str]:
        """Apply the usual edit rules and reject multiple survey IDs on one capture.

        The driver commits only after all stream processing succeeds. A raised
        error leaves the previous durable state, including its response, intact.
        """
        dispositions = super().revise(updates)
        surveys = [(row["camera"], row["i"]) for row in self.edits.values() if row["kind"] == "mount_survey"]
        if len(surveys) != len(set(surveys)):
            raise ValueError("Survey ID reused the same camera capture")
        return dispositions

    def report_covariance(self, graph: gt.NonlinearFactorGraph, keys: list[int], packet: dict) -> dict:
        """Read the pose and mount blocks from the same native joint marginal.

        Args:
            graph: Current retained nonlinear graph and its correlated boundary.
            keys: Distinct queried body poses in reply order.
            packet: Current accepted request, possibly with a camera override.

        Returns:
            Current mount transforms and joint covariance blocks in public order.
        """
        selected = packet.get("query_mount", self.default_mount)
        key, _, _ = self.mounts[selected]
        covariance = ordered_joint(graph, self.estimate, [*keys, key])
        return {
            "mount_poses": {name: output_pose(self.estimate.atPose3(item[0])) for name, item in self.mounts.items()},
            "joint_mount_camera": selected,
            "joint_mount_covariance": covariance.tolist(),
            "joint_covariance": covariance[:-6, :-6].tolist(),
        }

    def encode_state(self, data: dict) -> bytes:
        """Compress the dense boundary and full receipt into the checkpoint limit."""
        encoded = zlib.compress(json_bytes(data))
        if len(encoded) > CHECKPOINT_BYTES:
            raise ValueError("Camera checkpoint exceeded its size limit")
        return encoded

    def decode_state(self, data: bytes) -> dict:
        """Decode the same bounded state after a cold process restart."""
        try:
            return json.loads(zlib.decompress(data))
        except zlib.error as error:
            raise ValueError("Invalid compressed camera checkpoint") from error


def stream(manifest: dict, state: Path, source: TextIO, destination: TextIO) -> None:
    """Serve one mount recalibration stream with the existing durable reply protocol."""
    run_stream(MountRewind(manifest), state, source, destination)
