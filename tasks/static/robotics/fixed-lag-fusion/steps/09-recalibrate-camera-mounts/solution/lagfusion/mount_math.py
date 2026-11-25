"""Native factors for a moving robot's uncertain camera mounts."""

import gtsam as gt
import numpy as np
from numpy.typing import ArrayLike


def mount_projection_factor(
    body_key: int,
    mount_key: int,
    landmark_key: int,
    optical: gt.Cal3_S2,
    measured: ArrayLike,
    sigma_px: float,
) -> gt.CustomFactor:
    """Build a reprojection factor with separate body, mount, and point keys.

    Args:
        body_key: Key for the capture-time world-from-body Pose3.
        mount_key: Key for the camera epoch's body-from-camera Pose3.
        landmark_key: Key for the world-frame landmark coordinates in metres.
        optical: Fixed camera intrinsics, including skew.
        measured: Observed image coordinates in pixels.
        sigma_px: Positive isotropic standard deviation of the observation.

    Returns:
        A nonlinear GTSAM factor whose native Jacobians follow the three
        supplied key blocks. Behind-camera points use GTSAM's default
        projection penalty and contribute no linearized constraint.
    """
    pixel = np.array(measured, dtype=float)

    def evaluate(
        _factor: gt.CustomFactor,
        values: gt.Values,
        jacobians: gt.JacobianVector | None,
    ) -> np.ndarray:
        """Return the unwhitened pixel residual and fill requested tangent blocks."""
        world_from_body = values.atPose3(body_key)
        body_from_camera = values.atPose3(mount_key)
        point = values.atPoint3(landmark_key)
        derivative = jacobians is not None
        compose_body = np.empty((6, 6), order="F") if derivative else None
        compose_mount = np.empty((6, 6), order="F") if derivative else None
        project_camera = np.empty((2, 6), order="F") if derivative else None
        project_point = np.empty((2, 3), order="F") if derivative else None
        world_from_camera = world_from_body.compose(
            body_from_camera, compose_body, compose_mount
        )
        camera = gt.PinholeCameraCal3_S2(world_from_camera, optical)
        try:
            predicted = camera.project(point, project_camera, project_point)
        except RuntimeError as error:
            if str(error) != "CheiralityException":
                raise
            if jacobians is not None:
                jacobians[0] = np.zeros((2, 6), order="F")
                jacobians[1] = np.zeros((2, 6), order="F")
                jacobians[2] = np.zeros((2, 3), order="F")
            return np.full(2, 2.0 * optical.fx())
        if jacobians is not None:
            jacobians[0] = np.asfortranarray(project_camera @ compose_body)
            jacobians[1] = np.asfortranarray(project_camera @ compose_mount)
            jacobians[2] = project_point
        return predicted - pixel

    noise = gt.noiseModel.Isotropic.Sigma(2, sigma_px)
    return gt.CustomFactor(noise, [body_key, mount_key, landmark_key], evaluate)


def mount_survey_factor(
    body_key: int,
    mount_key: int,
    measured: gt.Pose3,
    sigmas: ArrayLike,
) -> gt.CustomFactor:
    """Constrain the combined world camera pose at an external survey timestamp.

    Args:
        body_key: Key for the surveyed frame's world-from-body Pose3.
        mount_key: Key for the camera epoch's shared body-from-camera Pose3.
        measured: Surveyed world-from-camera pose.
        sigmas: Six positive diagonal deviations for the survey in right-local
            rotation-first order, in radians and metres.

    Returns:
        A nonlinear factor over both poses using GTSAM's Pose3 prior residual
        on their composition. Neither pose is a fixed substitution.
    """

    def evaluate(
        _factor: gt.CustomFactor,
        values: gt.Values,
        jacobians: gt.JacobianVector | None,
    ) -> np.ndarray:
        """Map the composed camera pose into the survey's local coordinates."""
        world_from_body = values.atPose3(body_key)
        body_from_camera = values.atPose3(mount_key)
        derivative = jacobians is not None
        compose_body = np.empty((6, 6), order="F") if derivative else None
        compose_mount = np.empty((6, 6), order="F") if derivative else None
        survey_camera = np.empty((6, 6), order="F") if derivative else None
        world_from_camera = world_from_body.compose(
            body_from_camera, compose_body, compose_mount
        )
        residual = measured.localCoordinates(world_from_camera, None, survey_camera)
        if jacobians is not None:
            jacobians[0] = np.asfortranarray(survey_camera @ compose_body)
            jacobians[1] = np.asfortranarray(survey_camera @ compose_mount)
        return residual

    noise = gt.noiseModel.Diagonal.Sigmas(np.asarray(sigmas, dtype=float))
    return gt.CustomFactor(noise, [body_key, mount_key], evaluate)
