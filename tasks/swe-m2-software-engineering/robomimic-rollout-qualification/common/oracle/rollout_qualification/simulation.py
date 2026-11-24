"""Restore MuJoCo and controller state and reproduce command traces."""

from collections import deque
from pathlib import Path

import mujoco
import numpy as np

from .dataset import Controller, Demo, SIGNATURE, joint_id, read, write


class Simulation:
    """Fresh physics plus FIFO and filtered actuator state for one rollout."""

    def __init__(self, demo: Demo, controller: Controller, delay: int | None = None):
        self.model, self.config = demo.model, controller
        self.data = mujoco.MjData(self.model)
        mujoco.mj_setState(self.model, self.data, demo.states[0], SIGNATURE)
        mujoco.mj_forward(self.model, self.data)
        self.filtered = demo.filtered.copy()
        length = controller.delay if delay is None else delay
        overlap = min(len(demo.queue), length)
        newest = demo.queue[len(demo.queue) - overlap:]
        self.queue = deque([np.zeros(self.model.nu) for _ in range(length - overlap)] + list(newest))
        self.goal_positions = [self.model.jnt_qposadr[joint_id(self.model, name)] for name in controller.joints]
        self.limit = np.asarray(controller.limits)

    def state(self) -> np.ndarray:
        """Read a fresh full-physics state vector in native MuJoCo order."""
        result = np.empty(mujoco.mj_stateSize(self.model, SIGNATURE))
        mujoco.mj_getState(self.model, self.data, result, SIGNATURE)
        return result

    def step(self, requested: np.ndarray) -> np.ndarray:
        """Saturate, delay, filter, then apply one action for the configured substeps."""
        self.queue.append(np.clip(requested, -self.limit, self.limit))
        delayed = self.queue.popleft()
        self.filtered = self.config.alpha * delayed + (1 - self.config.alpha) * self.filtered
        self.data.ctrl[:] = self.filtered
        mujoco.mj_step(self.model, self.data, nstep=self.config.substeps)
        return self.filtered.copy()

    def success(self) -> bool:
        """Measure whether the two slide joints are within the task goal."""
        delta = self.data.qpos[self.goal_positions] - self.config.target
        return float(np.linalg.norm(delta)) <= self.config.radius


def replay(dataset: Path, demo: str, output: Path) -> None:
    """Execute the recorded actions and report the first pre-action state divergence."""
    study = read(dataset)
    capture = study.demos[demo]
    sim = Simulation(capture, study.controls)
    first = None
    steps = []
    for index, (measured, requested) in enumerate(zip(capture.states, capture.actions, strict=True)):
        before = sim.state()
        applied = sim.step(requested)
        if first is None and np.max(np.abs(before - measured)) > 1e-8:
            first = index
        steps.append({"state_before": before.tolist(), "applied": applied.tolist(), "state_after": sim.state().tolist()})
    write(output, {"schema_version": 1, "demo": demo, "first_divergence": first,
                   "goal_success": sim.success(), "steps": steps, "final_state": sim.state().tolist()})
