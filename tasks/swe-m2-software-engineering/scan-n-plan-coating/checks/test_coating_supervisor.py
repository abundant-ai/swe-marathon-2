"""Test durable public protocol decisions independently of a trajectory planner."""

from pathlib import Path

import pytest

ORACLE = Path(__file__).resolve().parents[1] / "common/oracle"


def test_coating_supervisor_gates_replacement_on_fresh_complete_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replay a lost response, request one stop, and wait for the gap to close."""
    monkeypatch.syspath_prepend(str(ORACLE))
    from coating_supervisor import MeasuredDose, start_state, transact

    period = 20_000_000
    job = {
        "job_id": "qualification",
        "scene_revision": 4,
        "world_collision": [],
        "final_positioner_rad": 0.2,
        "motion": {
            "control_period_ns": period, "max_duration_ns": 20 * period,
            "state_max_age_ns": period, "stop_velocity_rad_s": 0.001,
        },
        "recipe": {"max_flow_ml_s": 2.0},
    }
    initial = {"job_id": job["job_id"], "status": "registered"}
    state = start_state(job, initial)

    def measure(history: dict) -> MeasuredDose:
        """Expose closure of late measured intervals to the planner probe."""
        return MeasuredDose(len(history["receipts"]), False)

    def plan(adjusted: dict, pose: dict, speeds: list[float], prior: MeasuredDose, state: dict) -> dict:
        """Return an observable command shape carrying the receipt count."""
        return {"status": "ready", "trajectory": [prior.data]}

    def packet(seq: int, step: int, mode: str, motion_id: str | None, *,
               permit: bool = True, delivered: list | None = None, through: int | None = None,
               age: int = 0) -> dict:
        """Construct one valid 7-axis observation and request."""
        return {
            "seq": seq, "now_ns": step * period, "spray_permitted": permit,
            "controller": {
                "mode": mode, "command_id": motion_id, "measured_ns": (step - age) * period,
                "trace_through_ns": through * period if through is not None else None,
                "q_rad": [0.0] * 7, "qd_rad_s": [0.0] * 7,
            },
            "scene": None, "receipts": delivered or [],
        }

    def receipt(name: str, start: int, end: int) -> dict:
        """Make a measured interval tied to the original authority."""
        return {
            "receipt_id": name, "command_id": "coating-1", "scene_revision": 4,
            "samples": [
                {"t_ns": step * period, "q_rad": [0.0] * 7, "qd_rad_s": [0.0] * 7, "flow_ml_s": 0.5}
                for step in range(start, end + 1)
            ],
        }

    first = packet(0, 0, "idle", None)
    state, response = transact(job, state, first, measure=measure, plan=plan)
    assert response["command"]["command_id"] == "coating-1"
    same, replay = transact(job, state, first, measure=measure, plan=plan)
    assert same is state and replay == response
    stop = packet(1, 2, "running", "coating-1", permit=False, through=2)
    state, response = transact(job, state, stop, measure=measure, plan=plan)
    assert response["command"] == {"kind": "stop", "command_id": "coating-2", "motion_id": "coating-1"}
    partial = packet(2, 4, "stopped", "coating-1", through=3, delivered=[receipt("late", 2, 3)])
    state, response = transact(job, state, partial, measure=measure, plan=plan)
    assert response["status"] == "waiting" and response["command"] is None
    changed = receipt("late", 1, 3)
    rejected = packet(3, 6, "stopped", "coating-1", through=3, delivered=[changed])
    same, response = transact(job, state, rejected, measure=measure, plan=plan)
    assert same is state and response["status"] == "rejected"
    full = packet(3, 7, "stopped", "coating-1", through=3, delivered=[receipt("early", 0, 2)], age=2)
    state, response = transact(job, state, full, measure=measure, plan=plan)
    assert response["status"] == "waiting" and response["command"] is None
    fresh = packet(4, 8, "stopped", "coating-1", through=3)
    _, response = transact(job, state, fresh, measure=measure, plan=plan)
    assert response["command"] == {"kind": "execute", "command_id": "coating-3", "scene_revision": 4, "trajectory": [2]}
