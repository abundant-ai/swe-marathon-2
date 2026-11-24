"""Native MuJoCo shadow plant with authored compound limbs."""

from math import cos, sin
from pathlib import Path

import mujoco
import numpy as np

from fixtures import JOINTS, Physical, TruthPolicy, export, manifest
from transport import Stream, require


def model(*, mass_scale: float = 1.0, damping_scale: float = 1.0) -> mujoco.MjModel:
    """Build the authored fixed-deck eight-joint MJCF from physical limb dimensions."""
    positions = [(-0.28, -0.19), (-0.28, 0.19), (0.28, -0.19), (0.28, 0.19)]
    legs = []
    for i, (x, y) in enumerate(positions):
        outer, inner = JOINTS[i * 2:i * 2 + 2]
        legs.append(f"""
        <body name="outer-{i}" pos="{x} {y} 0">
          <joint name="{outer}" axis="0 1 0" damping="{0.12 * damping_scale}"/>
          <geom type="capsule" fromto="0 0 0 0 0 -0.23" size="0.035" mass="{0.55 * mass_scale}"/>
          <body name="inner-{i}" pos="0 0 -0.23">
            <joint name="{inner}" axis="0 1 0" damping="{0.085 * damping_scale}"/>
            <geom type="capsule" fromto="0 0 0 0 0 -0.22" size="0.024" mass="{0.29 * mass_scale}"/>
          </body>
        </body>""")
    drives = "".join(f'<position name="servo-{name}" joint="{name}" kp="11"/>' for name in reversed(JOINTS))
    xml = f"""
    <mujoco model="portable-fixed-deck">
      <compiler angle="radian"/>
      <option timestep="0.005" gravity="0 0 -9.81" integrator="implicitfast"/>
      <default>
        <joint limited="true" range="-1.4 1.4"/>
        <geom contype="0" conaffinity="0"/>
      </default>
      <worldbody><body name="deck" pos="0 0 0.64">
        <geom type="box" size="0.33 0.22 0.06" mass="1.7"/>
        {''.join(legs)}
      </body></worldbody><actuator>{drives}</actuator>
    </mujoco>"""
    return mujoco.MjModel.from_xml_string(xml)


def pose(model: mujoco.MjModel, data: mujoco.MjData, tick: int) -> Physical:
    """Read articulated state and a common held-out base/command replay signal."""
    return Physical(
        {name: float(data.qpos[model.joint(name).qposadr[0]]) for name in JOINTS},
        {name: float(data.qvel[model.joint(name).dofadr[0]]) for name in JOINTS},
        [0.91, 0.13 + 0.012 * cos(tick / 6), -0.19, 0.22],
        [0.31 * cos(tick / 5), -0.36, 0.21 * sin(tick / 7)],
        [0.46 * sin(tick / 8), -0.34 * cos(tick / 13), 0.29 * sin(tick / 11)],
    )


def drive(model: mujoco.MjModel, data: mujoco.MjData, spec: dict, controls: list[float]) -> None:
    """Apply the emitted bus values through position actuators and step native physics."""
    bus = dict(zip(spec["model"]["actuator_order"], controls, strict=True))
    for name, entry in spec["actions"].items():
        joint = spec["joints"][name]
        data.ctrl[model.actuator(f"servo-{name}").id] = joint["sign"] * (bus[entry["actuator"]] - joint["zero"])
    mujoco.mj_step(model, data)


def shadow_rollout(app: Path, root: Path, check: object) -> dict:
    """Drive two independently exported native plants and compare a canonical shadow."""
    physics = model()
    left, right, canonical = (mujoco.MjData(physics) for _ in range(3))
    for data in (left, right, canonical):
        data.qpos[:] = [0.17 * cos(i * 0.57) - 0.07 for i in range(physics.nq)]
        data.qvel[:] = [0.15 * sin(i * 0.51) for i in range(physics.nv)]
        mujoco.mj_forward(physics, data)
    starting = canonical.qpos.copy()
    a = manifest(152, 0, count=8, history=4, period=3)
    b = manifest(152, 3, count=8, history=4, period=3)
    truth = TruthPolicy(a)
    peak_position_error = 0.0
    policy_ticks = 0
    with Stream(app, root / "left", a) as one, Stream(app, root / "right", b) as two:
        for tick in range(55):
            raw_a = export(a, pose(physics, left, tick), tick, sign_flip=tick % 3 == 1)
            raw_b = export(b, pose(physics, right, tick), tick, sign_flip=tick % 4 == 2)
            reference = truth.evaluate(pose(physics, canonical, tick)) if tick % 3 == 0 else truth.quiet("held")
            r1, r2 = one.push(raw_a), two.push(raw_b)
            check(r1, reference)
            if tick % 3 == 0:
                for key in ("observation", "action", "target"):
                    require(np.allclose(r1[key], r2.get(key), rtol=1e-9, atol=1e-9),
                            f"native exports disagree in {key} at tick {tick}")
                policy_ticks += 1
            else:
                require(r2.get("status") == "held", "native target stepped on a physics-only tick")
            if tick == 22:
                two.restart()
                require(two.push(raw_b) == r2, "native target lost its committed actuator step after restart")
            drive(physics, left, a, r1["control"])
            drive(physics, right, b, r2["control"])
            drive(physics, canonical, a, reference["control"])
            peak_position_error = max(peak_position_error, float(np.max(np.abs(right.qpos - canonical.qpos))))
            require(peak_position_error < 2e-8, f"native plant rolled away from the canonical trace at tick {tick}")
    displacement = float(np.linalg.norm(canonical.qpos - starting))
    require(displacement > 0.11 and policy_ticks == 19, "native test did not exercise a moving articulated plant")
    return {"policy_updates": policy_ticks, "physics_steps": 55, "joints": physics.nq,
            "articulated_displacement_rad_l2": displacement, "peak_position_error_rad": peak_position_error}
