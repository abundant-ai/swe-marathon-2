# Robotics software benchmark shortlist

The shortlist follows the ranking from the last completed GPT-6.2 Sol xhigh
attempt on each task. Lower reward ranks first. The engineering ordering
from the benchmark catalogue breaks ties at 1.0. Provider quota failures
left newer MuJoCo and Nav2 stages untested by that model, so the table
uses the previous completed versions for selection.

| Rank | Task | Selection score | Earlier version |
| ---: | --- | ---: | --- |
| 1 | [Go2 policy deployment and raw-scan navigation](../tasks/swe-m2-software-engineering/policy-sim-bridge/README.md) | 0.200000 | v6 |
| 2 | [GTSAM fixed-lag fusion](../tasks/swe-m2-software-engineering/fixed-lag-fusion/README.md) | 0.306667 | v5 |
| 3 | [PX4 estimator and landing recovery](../tasks/swe-m2-software-engineering/px4-estimator-recovery/README.md) | 0.343997 | v6 |
| 4 | [Dual-arm payload handoff](../tasks/swe-m2-software-engineering/dual-arm-handoff/README.md) | 0.408000 | v3 |
| 5 | [LeRobot dataset and action repair](../tasks/swe-m2-software-engineering/lerobot-dataset-repair/README.md) | 0.840000 | v4 |
| 6 | [ros2_control coupled lift handover](../tasks/swe-m2-software-engineering/ros2-control-recovery/README.md) | 0.999808 | v6 |
| 7 | [Open-RMF contingent fleet recovery](../tasks/swe-m2-software-engineering/fleet-recovery/README.md) | 0.999986 | v7 |
| 8 | [Nav2 docking and powered departure](../tasks/swe-m2-software-engineering/nav2-docking-recovery/README.md) | 1.000000 | v4 |
| 9 | [MuJoCo state migration and payload handoff](../tasks/swe-m2-software-engineering/mujoco-branch-replay/README.md) | 1.000000 | v3 |
| 10 | [Online map promotion and rollback](../tasks/swe-m2-software-engineering/versioned-mapping/README.md) | 1.000000 | v2 |

## Three-model comparison

All three models use the same fresh single-session version of each task.
Each version presents every original checkpoint brief in order at startup
and runs the original cumulative tests in a separate verifier after the
agent submits. One session is the format supported by Oddish's Proximus
runner. The earlier staged scores remain selection evidence.

Each task receives three fresh attempts from `relace/deepseek-v4.1-flash`
with Proximus, three from `relace/glm-5.3` with Proximus, and three from
`openai/gpt-6.2-sol` with Codex at xhigh. A shared reference and no-op on
each version check for rewards of 1.0 and 0.0. Report the individual
attempts and use completed model attempts for any summary. A provider
or harness failure is recorded separately from the task reward.

The adapter records the sum of the original stage budgets and the
comparison timeout in its output manifest. Where the original total
exceeds Oddish's 43,200-second attempt limit, it reserves time for image
builds, verification, and Proximus's final submission. Fixed Lag,
ros2_control, and Fleet Recovery use the resulting capped session budgets.
Proximus has an explicit authoring timer within the outer agent timeout.
Codex uses the outer timeout, which gives it up to 20 more minutes.
The three capped budgets use the full lease when both builds and the
verifier reach their limits. Agent setup and artifact collection also
consume wall time, so inspect any lease expiry before using its score.

To reproduce the task bundles from this checkout, run the authoring
packager and preflight the generated task directory.

```sh
python3 -B resources/package_robotics_comparison.py --output /tmp/robotics-top-ten
oddish preflight /tmp/robotics-top-ten/dist --json
```

The manifest identifies each generated version by its relative file
inventory digest. The generated images, trial artifacts, and scores stay
outside the source tree.
