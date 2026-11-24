# Portable headless simulator regression

Inspect a small SDF world, translate its commissioned planar mechanics into a headless native test, and audit downstream ROS-shaped observations for missing simulation clocks, topics, QoS profiles, and transforms.

## Design dimensions

| Dimension | Evidence and limits |
| --- | --- |
| Novelty | MuJoCo Branch Replay focuses on deterministic snapshot restoration and branch behavior. This task starts with an SDF world and audits the observable boundary between the native trajectory and downstream topic consumers. Other SWE benchmark comparisons remain unverified. |
| Verifiability | An independent native MuJoCo program builds the same declared dynamics with separate geometry and transform code. It records actual pose, collision contact and native ray outcomes. The audit consumes independent reported traces with faults introduced separately. |
| Realism | Gazebo has an explicit world reset operation, and ROS 2 integrations expose simulator time, world control, transforms and topic bridging. The task retains local SDF frame resolution and sensor wiring decisions. The backend here is native MuJoCo 3.3.7 behind an authored portable planar subset. It does not run Gazebo, SDFormat plugins, ROS middleware, or DDS QoS negotiation. [Gazebo reset interface](https://gazebosim.org/api/sim/8/reset_simulation.html) · [ROS 2 integration](https://gazebosim.org/docs/latest/ros2_integration/) · [MuJoCo Python](https://mujoco.readthedocs.io/en/3.3.7/python.html) |
| Difficulty | Failures can affect native scene pose, deterministic event ordering, topic cadence across a reset, or downstream reported pose. The classifier must retain independent first failures even when other parts of the trace are still healthy. This is a compact pilot with no calibrated five-day workload or model difficulty. |
| Initial feasibility | A bounded XML parser, scoped frame graph, native MuJoCo planar world and timestamp-ordered bridge audit form an executable reference. Local pinned headless verification is available. Hosted controls are pending. |

All SDF models, electronics, motion schedules and observed fault cases are authored. No Fuel asset, third-party robot, or upstream simulation code ships as task data. MuJoCo is used as a pinned dependency under Apache 2.0. [License](https://github.com/google-deepmind/mujoco/blob/main/LICENSE)

## Verification

1. Resolve nested transforms and topic cadence under independent coordinate setups, and preserve prior evidence on a malformed frame graph.
2. Execute the submitted native regression against two independently authored native shadows. The checker compares real robot poses, contact transitions from seeded relocalization, resets and actual ray measurements. It does not trust a rendered image or self-reported pass.
3. Verify that independent downstream traces diagnose a missing bridge, an individually missing row, a wrong frame identifier and separately timestamped transform, QoS, topic and reset faults.

Checkpoint rewards equal the fraction of cumulative missions that pass. The task uses their arithmetic mean. The physical benchmark runs headless and reports independent first contact and sensor delivery counts rather than visual quality.

## Hackability assessment

A candidate can fit a small collection of static worlds. Private cases vary pose frames, update rate, reset epoch, actuator schedule, contact timing and fault order, and derive evidence from native simulation. The highest assessed risk is medium for the scope of fixture variety. A separate privileged verifier stages ordinary candidate files and executes the submitted CLI as an unprivileged account. Its evidence directory is root-only. Hosted artifact and runtime isolation remain unassessed.

## Development log

### 2026-11-24

Implemented three checkpoints with a pinned CPU-only native backend. Authored SDF models expose the intended Gazebo-like wiring, while the measured plant runs here in MuJoCo. Build with `python3 -B scripts/package_task.py`. Hosted trials and model difficulty remain pending.
