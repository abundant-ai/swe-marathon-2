# Multi-bag replay conformance

This workflow gives ROS 2 researchers a deterministic offline answer to what
each subscriber could observe when multiple recordings share replay. A single
record timeline coexists with the recorded ROS clock, which may reset. The
consumer-level check exposes transform errors after seeking or joining late.

| Milestone | Evidence |
| --- | --- |
| Index native recordings | Exact CDR digests and order from one SQLite3 and one MCAP bag, including clock authority, ties and clock reset. |
| Replay subscribers | Exact per-subscriber event trace under reliability, durability and depth, plus history restoration after a seek. |
| Qualify transforms | Known composed and inverse poses, expired dynamic transforms, conflicting parents, seek and reset behavior. A second case swaps native backends and shifts record times. |
| Reconstruct an incident | Exact bounded clock calibration, native duplicate reconciliation, causal boot and sequence ordering, and transform queries that distinguish stable, missing and ambiguous poses. Both recorders use independently calibrated pieces. |

**Novelty.** Localization Replay prepares bags and scores localization
trajectories. This tool establishes what subscribers receive during replay
and whether observations from independent recorders support a trustworthy
timeline. rosbag2 replay provides the bag playback and QoS context for the
scenario. Researchers also ask for deterministic control of callback ordering
in offline replay. A comparison with specific Deep SWE and SWE-Marathon v1
tasks remains unverified. [rosbag2](https://github.com/ros2/rosbag2) · [User replay discussion](https://discourse.openrobotics.org/t/fast-accurate-robust-replay-in-ros2/30406)

**Verifiability.** Private fixtures use real native ROS 2 bags generated through
Rosbags. The verifier derives digests directly from authored CDR messages and
uses explicit delivery IDs and analytic transform truth. The incident probes
author explicit logical intervals and poses with large integer timestamps,
fractional calibration, causal ties that conflict with lexical order, copies
with complementary delay bounds, same-nanosecond native ordinals, and a restart
first observed on a diagnostic topic. At the CLI they check isolated pulse,
timing, payload and causal contradictions along with atomic malformed-input
handling.

**Realism.** Bag record time, ROS time, publisher history, and listener state
are distinct constraints observed when developing robotics tools. The spec
supplies known offsets and effective offered QoS so the application can focus
on replay behavior. Native recordings are authored, including measured-style
time resets and multiple storage backends. The incident spec supplies sidecar
clock pulses, latency bounds and producer IDs. It models independent clocks
and conservative per-event timing bounds in an offline forensic workflow.
Native recordings are authored directly in the verifier. The workflow's TF
queries use planar poses.

**Difficulty.** Preserving all semantics across ties, reset, seek,
late subscriptions and changing TF edges requires keeping the provider and
consumer state independent. The fourth checkpoint adds exact interval
arithmetic, graph constraint propagation, explicit rejection of conflicted
evidence, and lifecycle-aware snapshot reconstruction. The initial three
90-minute checkpoints all scored 1.0 in the archived GPT-6.2 Sol xhigh trial.
Its final checkpoint passed all four verifier groups. Hosted difficulty for
the new checkpoint is unmeasured. [Archived Oddish experiment](https://www.oddish.app/experiments/57208689)

**Initial feasibility.** Rosbags supports both storage backends. Deterministic
clock/ordering, per-publisher history and planar rigid composition can be
implemented without a ROS daemon. The task authors wrote the implementation
in common/oracle. No external recording assets are redistributed.

The first three checkpoints retain their applicable averages. The final score
gives 25% to the original four verifier groups and 37.5% to each of two
private incident scenarios. Each incident scenario prioritizes exact event
reconstruction and transform outcomes, with additional credit for isolated
evidence errors. A correct native index is a prerequisite for credit. The
private verifier runs candidate code with separate credentials in the hosted
environment, bounds JSON output and stages only the package.

## Development log

### 2026-11-24

Implemented the native ingestion, replay and consumer trace workflow.
Added incident reconstruction after reviewing the completed three-checkpoint
hosted trial, including the final step's verifier report.

## Hackability assessment

The main assessed weakness is specialization to fixed event traces. Wire
digests, real messages and backend swapping exercise varied bytes and
runtime I/O. Fixture recognition remains medium risk. Credentials and
network policy are configured for separate verification, with hosted
isolation unassessed.

The reviewed package scored 1.0 in every reference checkpoint and 0.0 for
every no-op checkpoint. The final reference took 3.86 seconds locally.
The maintained package check passed, and Oddish preflight had no findings.

#### Sealed splits and replay readers

GPT‑6.2 Sol xhigh scored 1.0 at all four hosted checkpoints after adding
causal incident reconstruction. The fifth checkpoint adds a long-lived
software service for native recording splits. Readers pin a generation and
advance through durable acknowledgements while the recorder attaches fresh
shards. The service must reconstruct a valid transient-local prelude from the
last visible publisher boot and deduplicate only explicitly identified
split repeats. [Version 2 result](https://www.oddish.app/experiments/9a2d8a0f) ·
[rosbag2 split and snapshot semantics](https://github.com/ros2/rosbag2#repeating-transient-local-messages-on-split-and-snapshot)

An independent verifier writes native SQLite and MCAP files with identifiable
CDR bytes. It deletes the source files after attaching them, overlaps two
real writer processes, and replaces the replay process after both poll and
acknowledgement reply failures. It also checks actual process memory while
indexing and seeking a 272 MiB native camera recording. This service uses
file-based transactional replay and operates offline. The final score gives
20% to checkpoint four and 80% to six snapshot-service checks. The new
fraction requires the pinned-history and restart case.

All five cumulative local reference and no-op runs scored 1.0 and 0.0.
The archived v2 GPT implementation scored 0.20. A reader that eagerly
loaded native messages missed the resident-memory case. Publishing the
response before committing the journal failed the pinned reader test.
[Version 3 trial](https://www.oddish.app/experiments/3d3f9dc5)


Fresh GPT‑6.2 Sol xhigh scored 1.0 through checkpoint four and 0.20 at the
snapshot checkpoint. Hosted reference and no-op scored 1.0 and 0.0. GPT
passed concurrent attachment, conflicting-repeat rollback and the 272 MiB
memory probe. In the lost-reply case it rejected the occupied response path
before recording the poll, so the next poll used the new limits instead of
returning the original pending batch. The three dependent snapshot flags
failed. The exact archive reproduced 0.20 locally. A copy with the early
response-path rejection removed passed all six flags and scored 1.0.
[Version 3 checkpoint evidence](https://www.oddish.app/experiments/3d3f9dc5)

Oddish's automatic analysis saw only the first verifier output and labeled
the result a harness error. The saved final checkpoint lists all six
snapshot outcomes and records 0.20. The local replay confirmed where the
three dependent flags were lost.

#### Native Jazzy transport and observable acceptance

The sixth checkpoint publishes original CDR on native ROS 2 Jazzy endpoints using Cyclone DDS restricted to loopback. The author examples and sealed inputs contain authored laboratory messages. The task redistributes no external bag recordings. SQLite holds immutable original messages, pinned readers and application-level receipts. DDS offers a reliable writer per replay stream. A transient-local writer holds one retained sample for each live publisher and topic, with new publisher identities after boot changes and seeks. ROS 2 explains the middleware QoS requirements, and rosbag2 supplies the motivating split and snapshot workflow. [ROS 2 Jazzy QoS](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html) · [rosbag2 split and snapshot semantics](https://github.com/ros2/rosbag2#repeating-transient-local-messages-on-split-and-snapshot)

The recovery mechanism separates durable acceptance from physical emission. The verifier reads the committed prepare through a separate receipt process, kills the live worker before its stdout is consumed, and obtains the accepted result from a new process. It then subscribes and issues emission under the recovered batch ID. This measures a real interrupted caller and worker. A DDS publication attempt can repeat physical samples until the caller acknowledges. Restart reconstructs the acknowledged transient-local state and never implicitly emits acknowledged volatile data. The qualification is a local transport and recovery test. It omits multi-host network conditions and clock-paced playback.

The retained fifth checkpoint now discards successful accepted responses before checking a fresh reader request. That removes a particular output path failure as the precondition for all pinning flags. The public contract explicitly distinguishes accepted requests from reply write failures. The exact hosted v3 artifact, without modifications, scored 1.0 against the revised fifth checkpoint. Its official earlier result remains 0.20. The stage-six reward combines 20% of the retained fifth-checkpoint result with 80% of its native mission pass fraction. Earlier task interfaces, including the immutable archive and resource cap, remain cumulative.

The public runnable example builds a new native SQLite bag, seals it through the CLI, opens and prepares a live seek, and creates its subscription after publication. It received identical original `TFMessage` CDR and decoded the expected sensor frame. Local runtime used Jazzy `rclpy` 7.1.13, `rmw_cyclonedds_cpp` 2.2.4, and `tf2_msgs` 0.36.23 from the extracted Ubuntu Noble ROS packages. The Docker recipe uses the Jazzy release and retains the Python dependency pins.

The packed reference passed 40 of 40 checks, including all five native DDS outcomes, and scored 1.0 in 57.62 seconds with the extracted Jazzy runtime. The no-op scored 0.0. The exact hosted v3 artifact passed the retained portion and scored 0.20 on the new final checkpoint. Package pytest and Oddish preflight passed. The native verifier uses aligned CDR when comparing complete raw callback buffers. Cyclone DDS can append transport alignment padding after an unaligned serialized string, even when the worker passed the original bytes unchanged to the raw publisher.

Fresh GPT‑6.2 Sol xhigh scored 1.0 across all six checkpoints. The
reference scored 1.0 and no-op scored 0.0. The saved final report verifies
all five DDS outcomes, including recovery of accepted state after process
death. [Live transport experiment](https://www.oddish.app/experiments/16ebd21c)
