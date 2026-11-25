"""Choose and score the final checkpoint's physical interruption missions."""

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from coating_scene import CoatingScene, rigid_pose, rotate_z
from live_candidate import supervisor
from live_cases import Document, LiveScenario, audit_live
from live_controller import PressureSag
from offline_cases import _jaw, offline_cases
from verify_process import ProcessCheck, ProcessContext, job_with_assets

INPUTS = Path(__file__).resolve().parent / "live_inputs"


@dataclass(frozen=True)
class _LiveCase:
    """A workpiece, surveyed mounting, and ordered recovery conditions."""

    name: str
    identity: str
    job: Document
    survey: Document
    deadline_s: float
    phases: tuple[tuple[float | None, LiveScenario], ...]


def reindex(job: dict, registration: dict, angle_rad: float) -> dict:
    """Author a measured mounting revision while leaving fixture geometry fixed."""
    axis = rigid_pose(job["base_from_axis"])
    new_home = axis @ rotate_z(angle_rad) @ np.linalg.inv(axis) @ rigid_pose(registration["base_from_part_home"])
    return {
        **registration, "capture_epoch": "post-interruption-survey", "capture_ids": ["survey-after-index"],
        "base_from_part_home": {
            "translation_m": new_home[:3, 3].tolist(),
            "quaternion_xyzw": Rotation.from_matrix(new_home[:3, :3]).as_quat().tolist(),
        },
    }


def _live_cases() -> tuple[_LiveCase, ...]:
    """Return the independent live fixtures and their simulated mission durations."""
    template = json.loads((INPUTS / "job.json").read_text(encoding="utf-8"))
    survey = json.loads((INPUTS / "registration.json").read_text(encoding="utf-8"))
    coordinated = {case.name: case for case in offline_cases(3)}
    reverse = coordinated["reverse-rotary-reach-to-raised-return"]
    centered = coordinated["coat-separated-patches-across-masked-stripe"]
    split = coordinated["coat-unequal-patches-across-offset-mask"]
    stacked = coordinated["coat-two-flanges-on-stacked-carrier"]
    clamp = {"id": "deployed-service-clamp", **_jaw([.633, -.004, .254], 0.0)}
    stacked_clamp = {"id": "surveyed-service-clamp", **_jaw(
        [.626, .066, .318], 0.0, half_extents_m=(.0138, .0189, .024),
    )}
    pressure_sag = PressureSag(.15, .16, .25)
    return (
        _LiveCase("resume-offset-mask-after-stale-readback-and-remount", "service-batch-613", split.job,
                  split.registration, 15.0, (
            (None, LiveScenario(.32, stale_running=True, pressure_sag=pressure_sag)),
            (.025, LiveScenario(.45, registration_review_periods=6)),
        )),
        _LiveCase("resume-after-remount-registration-review", "service-batch-824", template, survey, 5.6,
                  ((.055, LiveScenario(.65, registration_review_periods=6)),)),
        _LiveCase("recover-reverse-return-after-pressure-loss-and-remount", "service-batch-467", reverse.job,
                  reverse.registration, 12.0, ((-.043, LiveScenario(.48, pressure_sag=pressure_sag)),)),
        _LiveCase("hold-through-expired-permission-window", "service-batch-295", template, survey, 5.2,
                  ((None, LiveScenario(.65, expect_blocked=True)),)),
        _LiveCase("recover-pressure-loss-clamp-and-remount", "service-batch-518", template, survey, 8.4, (
            (None, LiveScenario(.52, world_collision=[clamp], world_update_during_motion=True,
                                pressure_sag=pressure_sag)),
            (.025, LiveScenario(.70, registration_review_periods=6)),
        )),
        _LiveCase("repair-priming-loss-across-centered-mask", "service-batch-361", centered.job,
                  centered.registration, 11.0, ((None, LiveScenario(.51, prime_delay_periods=10)),)),
        _LiveCase("repair-priming-and-pressure-loss", "service-batch-702", template, survey, 6.4,
                  ((None, LiveScenario(.65, prime_delay_periods=10, pressure_sag=pressure_sag)),)),
        _LiveCase("reroute-stacked-carrier-after-service-clamp", "service-batch-783", stacked.job,
                  stacked.registration, 16.0, ((None, LiveScenario(.65, world_collision=[stacked_clamp])),)),
    )


def _test_live_case(context: ProcessContext, case: _LiveCase) -> ProcessCheck:
    """Replay one authored mission from a fresh supervisor state directory.

    Args:
        context: Candidate application and trusted robot assets.
        case: Fixture and ordered physical conditions to apply to this mission.

    Returns:
        The case outcome and independent measurements of the executed motions.
    """
    job = job_with_assets(case.job, context.assets)
    job["job_id"] = case.identity
    job["motion"] = {
        **job["motion"], "max_duration_ns": round(case.deadline_s * 1e9),
        "state_max_age_ns": 40_000_000, "stop_velocity_rad_s": 1e-8,
    }
    registration = {**case.survey, "job_id": case.identity}
    recipe = job["recipe"]
    target_area = CoatingScene.from_job(job).part.areas[job["target_faces"]].sum()
    minimum_completion_ml = target_area * recipe["min_covered_fraction"] * recipe["target_dose_ml_m2"][0]
    if any(phase.interrupt_after_ml >= minimum_completion_ml for _, phase in case.phases):
        raise ValueError(f"Fault threshold can be bypassed by a valid low-volume finish for {case.name}.")
    scenarios = tuple(replace(
        phase,
        remount_registration=reindex(job, registration, angle) if angle is not None else None,
        flow_gain=.94,
    ) for angle, phase in case.phases)
    with supervisor(context.app, job, registration) as runner:
        evidence = audit_live(
            job, registration, runner, urdf=context.assets / "arm.urdf", srdf=context.assets / "arm.srdf",
            scenario=scenarios[0], followups=scenarios[1:],
        )
    if evidence.status == "unresolved":
        raise RuntimeError(f"Independent live replay could not be certified for {case.name}: {evidence.explanations}")
    explanation = " ".join(evidence.explanations)
    if evidence.status == "passed":
        explanation = "Measured motion and output matched the declared mission outcome."
    return ProcessCheck(case.name, evidence.status, explanation, asdict(evidence))


def test_live_group(context: ProcessContext) -> tuple[tuple[ProcessCheck, ...], frozenset[str]]:
    """Grade physically distinct recoveries and one deadline-constrained safe hold."""
    cases = _live_cases()
    return (
        tuple(_test_live_case(context, case) for case in cases),
        frozenset(case.name for case in cases if not case.phases[-1][1].expect_blocked),
    )
