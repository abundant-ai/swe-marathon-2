"""Choose and score the final checkpoint's physical interruption missions."""

from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from coating_scene import CoatingScene, rigid_pose, rotate_z
from live_candidate import supervisor
from live_cases import LiveScenario, audit_live
from offline_cases import offline_cases
from verify_process import ProcessCheck, ProcessContext, job_with_assets

INPUTS = Path(__file__).resolve().parent / "live_inputs"


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


def test_live_group(context: ProcessContext) -> tuple[tuple[ProcessCheck, ...], frozenset[str]]:
    """Grade physically distinct recoveries and one deadline-constrained safe hold."""
    template = json.loads((INPUTS / "job.json").read_text(encoding="utf-8"))
    survey = json.loads((INPUTS / "registration.json").read_text(encoding="utf-8"))
    reverse = next(case for case in offline_cases(3) if case.name == "reverse-rotary-reach-to-raised-return")
    specifications = (
        ("resume-after-measured-valve-revocation", "service-batch-613", template, survey, None, False, .65, 5.2),
        ("resume-measured-dose-after-part-remount", "service-batch-824", template, survey, .055, False, .65, 5.6),
        ("resume-reverse-return-after-part-remount", "service-batch-467", reverse.job, reverse.registration, -.043, False,
         .48, 12.0),
        ("hold-through-expired-permission-window", "service-batch-295", template, survey, None, True, .65, 5.2),
    )
    checks = []
    positive = set()
    for name, identity, input_job, input_survey, remount, blocked, trigger, deadline in specifications:
        job = job_with_assets(input_job, context.assets)
        job["job_id"] = identity
        job["motion"] = {
            **job["motion"], "max_duration_ns": round(deadline * 1e9),
            "state_max_age_ns": 40_000_000, "stop_velocity_rad_s": 1e-8,
        }
        registration = {**input_survey, "job_id": identity}
        revision = reindex(job, registration, remount) if remount is not None else None
        recipe = job["recipe"]
        target_area = CoatingScene.from_job(job).part.areas[job["target_faces"]].sum()
        minimum_completion_ml = target_area * recipe["min_covered_fraction"] * recipe["target_dose_ml_m2"][0]
        if trigger >= minimum_completion_ml:
            raise ValueError(f"Fault threshold can be bypassed by a valid low-volume finish for {name}.")
        scenario = LiveScenario(trigger, remount_registration=revision, expect_blocked=blocked, flow_gain=.94)
        with supervisor(context.app, job, registration) as runner:
            evidence = audit_live(
                job, registration, runner, urdf=context.assets / "arm.urdf", srdf=context.assets / "arm.srdf",
                scenario=scenario,
            )
        if evidence.status == "unresolved":
            raise RuntimeError(f"Independent live replay could not be certified for {name}: {evidence.explanations}")
        explanation = "Measured motion and output matched the declared mission outcome." if evidence.status == "passed" else (
            " ".join(evidence.explanations)
        )
        checks.append(ProcessCheck(name, evidence.status, explanation, asdict(evidence)))
        if not blocked:
            positive.add(name)
    return tuple(checks), frozenset(positive)
