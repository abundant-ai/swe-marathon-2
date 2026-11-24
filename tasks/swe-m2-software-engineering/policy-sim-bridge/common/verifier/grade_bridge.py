"""Stage the declared artifact and score cumulative independent missions."""

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from probes import cadence_case, compare_case, malformed_case, native_case, observation_case, replay_case, watchdog_case
from transport import Rejected


CASES = (
    ("world_gyro_and_wxyz", 1, observation_case, {"layout": 0, "count": 4, "seed": 11}),
    ("mirrored_xyzw_sensor_conventions", 1, observation_case, {"layout": 3, "count": 7, "seed": 36}),
    ("malformed_manifest_preserves_report", 1, malformed_case, {}),
    ("exported_actor_history_and_actuator_bounds", 2, cadence_case, {"skip": False}),
    ("decimation_does_not_fill_gaps", 2, cadence_case, {"skip": True}),
    ("watchdog_latch_rearm_and_new_phase", 3, watchdog_case, {}),
    ("interrupted_actor_replay_with_history", 3, replay_case, {}),
    ("equal_physical_time_with_different_rate", 4, compare_case, {"mode": "equal"}),
    ("first_observation_divergence", 4, compare_case, {"mode": "observation"}),
    ("missing_update_physical_timestamp", 4, compare_case, {"mode": "time"}),
    ("first_actor_layer_divergence", 4, compare_case, {"mode": "action"}),
    ("first_actuator_target_divergence", 4, compare_case, {"mode": "target"}),
    ("native_mujoco_closed_loop_portability", 4, native_case, {}),
)


def stage(source: Path, app: Path) -> bool:
    """Copy a bounded regular application tree without following candidate links."""
    if not source.is_dir() or source.is_symlink():
        return False
    total = 0
    for count, child in enumerate(source.rglob("*")):
        if count >= 1024 or child.is_symlink() or not (child.is_file() or child.is_dir()):
            return False
        if child.is_file():
            total += child.stat().st_size
            if total > 12_000_000:
                return False
    shutil.copytree(source, app / "policy_bridge", ignore=shutil.ignore_patterns("__pycache__"))
    for obj in (app / "policy_bridge").rglob("*"):
        obj.chmod(0o755 if obj.is_dir() else 0o644)
    return True


def grade(artifact: Path, checkpoint: int) -> dict:
    """Run the selected missions in isolated subprocesses and assemble evidence."""
    checks, observations = {}, {}
    advanced = ()
    drive_model = ()
    physical = ()
    locomotion = ()
    courses = ()
    if checkpoint >= 5:
        from commission import calibration_case, commissioned_rollout

        advanced = (
            ("signed_axis_and_affine_clock_fit", 5, calibration_case, {"seed": 71, "count": 5, "condition": "ok"}),
            ("seven_joint_velocity_and_control_fit", 5, calibration_case, {"seed": 78, "count": 7, "condition": "ok"}),
            ("sensor_symmetry_is_unidentifiable", 5, calibration_case, {"seed": 53, "count": 4, "condition": "duplicate-sensor"}),
            ("actuator_equivalence_is_unidentifiable", 5, calibration_case, {"seed": 38, "count": 6, "condition": "duplicate-drive"}),
            ("wrong_holdout_zero_is_reported", 5, calibration_case, {"seed": 69, "count": 6, "condition": "wrong-holdout"}),
            ("clock_without_overlap_is_rejected", 5, calibration_case, {"seed": 43, "count": 4, "condition": "missing-fit"}),
            ("missing_holdout_preserves_fit", 5, calibration_case, {"seed": 68, "count": 5, "condition": "missing-holdout"}),
            ("commissioned_native_heavier_plant", 5, commissioned_rollout, {"seed": 172, "mass": 1.72, "damping": 0.78}),
            ("commissioned_native_fault_and_restart", 5, commissioned_rollout, {"seed": 183, "mass": 0.76, "damping": 1.55, "fault": True}),
        )
    if checkpoint >= 6:
        from dynamics import model_case, reject_unqualified, rollout

        drive_model = (
            ("drive_coupled_torque_and_delays", 6, model_case, {"seed":72,"size":5,"variant":"ok"}),
            ("drive_recover_eight_distinct_axes", 6, model_case, {"seed":66,"size":8,"variant":"ok"}),
            ("drive_validate_frozen_fit", 6, model_case, {"seed":107,"size":6,"variant":"changed-holdout"}),
            ("drive_no_unexcited_model", 6, model_case, {"seed":76,"size":5,"variant":"unexcited"}),
            ("drive_abstain_on_periodic_delay", 6, model_case, {"seed":39,"size":4,"variant":"ambiguous-delay"}),
            ("drive_noncontiguous_capture_is_atomic", 6, model_case, {"seed":47,"size":4,"variant":"invalid"}),
            ("drive_reject_unqualified_deployment", 6, reject_unqualified, {}),
        )
        physical = (
            ("track_asymmetric_payload", 6, rollout, {"seed":26,"size":4,"stop":False}),
            ("track_through_latch_and_persistent_restart", 6, rollout, {"seed":122,"size":7,"stop":True,"twin":True}),
            ("track_eight_delayed_drives_under_load", 6, rollout, {"seed":16,"size":8,"stop":False}),
            ("track_after_recoupling_discovered_axis_map", 6, rollout, {"seed":75,"size":6,"stop":True,"mapped":True}),
            ("track_recovery_with_low_bus_slew", 6, rollout, {"seed":31,"size":6,"stop":True,"max_step":.022}),
        )
    if checkpoint >= 7:
        from locomotion_native import CASES as MOTION_CASES, run_locomotion

        locomotion = tuple((case["name"], 7, run_locomotion, case) for case in MOTION_CASES)
    if checkpoint >= 8:
        from course_checks import COURSES, run_course

        courses = tuple((case["name"], 8, run_course, case) for case in COURSES)
    with tempfile.TemporaryDirectory(prefix="policy-checkpoint-") as location:
        root = Path(location)
        root.chmod(0o755)
        app = root / "application"
        app.mkdir()
        ready = stage(artifact, app)
        for index, (name, first, mission, kwargs) in enumerate(CASES + advanced + drive_model + physical + locomotion + courses):
            if first > checkpoint:
                continue
            checks[name] = False
            if not ready:
                observations[name] = "no usable application artifact"
                continue
            case = root / f"case-{index}"
            case.mkdir()
            try:
                observations[name] = mission(app, case, **kwargs)
                checks[name] = True
            except (Rejected, ValueError, TypeError, KeyError, OverflowError) as error:
                observations[name] = str(error)
    advanced_names = {entry[0] for entry in advanced}
    drive_names = {entry[0] for entry in drive_model}
    physical_names = {entry[0] for entry in physical}
    locomotion_names = {entry[0] for entry in locomotion}
    course_names = {entry[0] for entry in courses}
    legacy = {name: passed for name, passed in checks.items()
              if name not in (advanced_names | drive_names | physical_names | locomotion_names | course_names)}
    positive = any(passed for name, passed in legacy.items() if name != "malformed_manifest_preserves_report")
    published = sum(legacy.values()) / len(legacy) if positive else 0.0
    commissioning_positive = any(checks.get(name) for name in (
        "signed_axis_and_affine_clock_fit", "seven_joint_velocity_and_control_fit",
        "wrong_holdout_zero_is_reported", "missing_holdout_preserves_fit",
        "commissioned_native_heavier_plant", "commissioned_native_fault_and_restart",
    ))
    commissioned = sum(checks[name] for name in advanced_names) / len(advanced_names) if commissioning_positive else 0.0
    reward = 0.20 * published + 0.80 * commissioned if advanced else published
    drive_fraction = None
    physical_fraction = None
    if checkpoint >= 6:
        has_model = any(checks.get(name) for name in ("drive_coupled_torque_and_delays",
                                                        "drive_recover_eight_distinct_axes", "drive_validate_frozen_fit"))
        drive_fraction = sum(checks[name] for name in drive_names) / len(drive_names) if has_model else 0.0
        physical_fraction = sum(checks[name] for name in physical_names) / len(physical_names)
        reward = .20 * reward + .15 * drive_fraction + .65 * physical_fraction
    locomotion_fraction = None
    if locomotion:
        locomotion_fraction = sum(checks[name] for name in locomotion_names) / len(locomotion_names)
        reward = .20 * reward + .80 * locomotion_fraction
    course_fraction = None
    if courses:
        course_fraction = sum(checks[name] for name in course_names) / len(course_names)
        reward = .20 * reward + .80 * course_fraction
    return {"stage": checkpoint, "reward": reward, "checks": checks,
            "course_fraction": course_fraction,
            "drive_fraction": drive_fraction, "physical_fraction": physical_fraction,
            "locomotion_fraction": locomotion_fraction,
            "positive_mission_passed": positive or commissioning_positive,
            "legacy_fraction": published, "commissioning_fraction": commissioned if advanced else None,
            "observations": observations}


def main() -> None:
    """Publish the protected reward and checkpoint evidence for this stage."""
    cli = argparse.ArgumentParser()
    cli.add_argument("--stage", type=int, choices=range(1, 9), required=True)
    cli.add_argument("--artifact", default=Path("/app/policy_bridge"), type=Path)
    cli.add_argument("--output", default=Path("/logs/verifier"), type=Path)
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.output.chmod(0o700)
    report = grade(args.artifact, args.stage)
    (args.output / "checkpoint.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (args.output / "reward.txt").write_text(f"{report['reward']:.12g}\n")


if __name__ == "__main__":
    main()
