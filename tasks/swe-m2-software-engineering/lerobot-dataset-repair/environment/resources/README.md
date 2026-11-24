# Public recording table example

so101-rows.parquet contains 48 consecutive native frame rows extracted from the
original Parquet recording described below. It is a schema and numerical-data
example. A complete LeRobotDataset also needs its metadata and synchronized
videos.

Source is the lsalomme SO-101 cube pick-and-place recording, available under
Creative Commons Attribution 4.0 International. Attribution and source details
are in [SO101-ATTRIBUTION.md](SO101-ATTRIBUTION.md).

## Drive write example

Run `python3 /app/examples/action_example.py OUTPUT_DIR` to generate a small
`source.parquet` and `write-ledger.json`. The generator records encoder samples
from a native MuJoCo rollout with separate policy and operator write records.
It includes a delayed ramp, a missing sample, and two distinct receipts that
produce the same physical command. Run `action-qualify` on the two files to
recover the identifiable writes and flag the unresolved provenance.

The generator copies `so101-headless.xml` and its license beside the ledger.
The model comes from the pinned SO101 asset in MuJoCo Menagerie under Apache
2.0. The derivative omits visual and gripper meshes and keeps the inertial
properties, actuator settings, and primitive collision geometry. [Pinned SO101 asset](https://github.com/google-deepmind/mujoco_menagerie/tree/3abca2e302625cec9429c49806121ea2855cef81/robotstudio_so101) · [Upstream license](https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/3abca2e302625cec9429c49806121ea2855cef81/robotstudio_so101/LICENSE)

LeRobot documents changes to action normalization and hardware calibration.
Its real-time chunking queue distinguishes between model-space actions,
processed actions, and request provenance. The authored drive example makes
that distinction visible in a short episode. [Backward compatibility notes](https://github.com/huggingface/lerobot/blob/main/docs/source/backwardcomp.mdx) · [Action queue](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/rtc/action_queue.py)
