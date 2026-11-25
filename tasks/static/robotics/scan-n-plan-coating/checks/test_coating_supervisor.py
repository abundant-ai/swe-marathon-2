"""Test durable public protocol decisions independently of a trajectory planner."""

from pathlib import Path

import pytest

ORACLE = Path(__file__).resolve().parents[1] / "common/oracle"
VERIFIER = ORACLE.with_name("verifier")


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


def test_coating_supervisor_stops_when_a_moving_readback_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the same measured moving sample at the inclusive limit and one tick later."""
    monkeypatch.syspath_prepend(str(ORACLE))
    monkeypatch.syspath_prepend(str(VERIFIER))
    from coating_supervisor import MeasuredDose, start_state, transact
    from live_controller import LiveController
    from trajectory import Knot

    period = 20_000_000
    rest = (0.0,) * 7
    job = {
        "job_id": "moving-readback",
        "scene_revision": 4,
        "world_collision": [],
        "start_q_rad": list(rest),
        "final_positioner_rad": 0.0,
        "motion": {"control_period_ns": period, "max_duration_ns": 20 * period,
                   "state_max_age_ns": 2 * period, "stop_velocity_rad_s": 0.001},
        "recipe": {"max_flow_ml_s": 2.0},
    }
    plant = LiveController(job)
    state = start_state(job, {"job_id": job["job_id"], "status": "registered"})

    def deliver(controller: dict) -> dict:
        nonlocal state
        state, response = transact(
            job, state, {"seq": state["next_seq"], "now_ns": plant.now_ns,
                         "controller": controller, "spray_permitted": plant.permitted,
                         "scene": None, "receipts": []},
            measure=lambda _: MeasuredDose(None, False),
            plan=lambda *_: {"status": "ready", "trajectory": []},
        )
        return response

    motion_id = deliver(plant.observation())["command"]["command_id"]
    plant.accept(motion_id, job["scene_revision"],
                 (Knot(0, rest, rest, .5), Knot(10 * period, (.1, *rest[1:]), rest, 0.0)))
    plant.advance()
    cached = plant.observation()
    assert cached["mode"] == "running" and cached["qd_rad_s"][0] > 0
    assert deliver(cached)["status"] == "ready"
    plant.advance(2)
    assert plant.q != tuple(cached["q_rad"])
    assert deliver(cached) == {"seq": 2, "status": "ready", "command": None}
    plant.advance()
    assert plant.permitted and plant.mode == "running"
    assert deliver(cached) == {
        "seq": 3, "status": "waiting",
        "command": {"kind": "stop", "motion_id": motion_id, "command_id": "coating-2"},
    }


@pytest.mark.parametrize(("measured_gap_flow", "replacement_flow"), [(0.0, 1.0), (0.225, 0.75)])
def test_coating_repair_preserves_the_wet_lanes_between_measured_gaps(
    monkeypatch: pytest.MonkeyPatch, measured_gap_flow: float, replacement_flow: float,
) -> None:
    """Repair dry or reduced flow without recoating the spans delivered at normal gain."""
    monkeypatch.syspath_prepend(str(ORACLE))
    from coating_resume import DeliveredSweep, delivered_sweep, repair_spans

    period = 20_000_000
    issued = 17 * period
    trajectory = [
        {"t_ns": tick * period, "q_rad": [0.0] * 7, "qd_rad_s": [0.0] * 7, "flow_ml_s": flow}
        for tick, flow in ((0, 0.0), (1, 1.0), (4, 0.5), (8, 0.0))
    ]
    samples = [
        {"t_ns": issued + tick * period, "flow_ml_s": flow}
        for tick, flow in enumerate((0.0, 0.9, measured_gap_flow, 0.9, measured_gap_flow / 2, 0.45, 0.0, 0.0))
    ]
    sweep = delivered_sweep(trajectory, ({"samples": samples[3:]}, {"samples": samples[:4]}), issued)
    assert sweep is not None and sweep.gain == pytest.approx(0.9)
    assert sweep == DeliveredSweep(6 * period, sweep.gain, (
        (2 * period, 3 * period, replacement_flow), (4 * period, 5 * period, replacement_flow / 2),
    ))

    repair = repair_spans(trajectory, sweep, shift=0.0)
    assert [(row["t_ns"] // period, row["flow_ml_s"]) for row in repair] == [
        (0, replacement_flow), (1, 0.0), (2, replacement_flow / 2), (3, 0.0), (4, 0.5), (6, 0.0),
    ]
