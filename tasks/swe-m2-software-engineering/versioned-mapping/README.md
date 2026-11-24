# Versioned indoor maps

A robotics mapping engineer needs to release occupancy-map changes after multiple visits to a site. A new shelving unit can be permanent, a cart can be transient, and a wall behind either can remain unseen. The workflow builds a baseline from posed lidar, registers new visits against occupied geometry, proposes auditable changes from independent observations, and publishes snapshots that localization operators can activate, pin and roll back.

## Checkpoints

| Checkpoint | Request and carried state | Verification |
| --- | --- | --- |
| [Build a map](steps/01-build-map/instruction.md) | Integrate scans in a shared metric frame. | Compare exact occupied and traversed cells and verify clipping, boundary rules, deterministic output and malformed-input preservation. |
| [Register a visit](steps/02-register-visits/instruction.md) | Keep the map format and place visit-local observations in its frame. | Independently place an asymmetric set of endpoints and recompute support from the reported transform. Repeat a motif to test ambiguity. Keep outliers in the support denominator. |
| [Reconcile evidence](steps/03-reconcile-evidence/instruction.md) | Apply visit transforms and document every proposed state change. | Compare changes against known independent votes, including temporary obstructions, an opposing visit, a mixed visit, protected cells, order independence and duplicated visit identity. |
| [Release versions](steps/04-release-maps/instruction.md) | Publish immutable snapshots and use compare-and-swap activation. | Preserve pinned bytes and SHA-256, reject malformed patches, check idempotence, race concurrent activations and reopen snapshots after rollback. A simulated hall adds registration and immutable export after furniture moves. |

All steps use the same /app/versioned_mapping package. Site data are supplied through files at each invocation, with map JSON shared across commands. The rollout has no network dependency or GPU requirement.

## Design dimensions

**Novelty.** The existing [Localization Replay](../localization-replay/) workflow packages ROS logs, calibrates clocks and sensor geometry, and diagnoses localization estimates. Versioned Mapping changes what a robot localizes against and checks that old inputs remain reproducible after map changes. The Physical Intelligence VLA policy port in SWE-Marathon v1.1 also evaluates a robotics artifact against numerical behavior, with its concrete goal being parity and inference optimization during a framework port. This task adds incremental evidence and operator release decisions across visits. Published lifelong-mapping systems are closer in domain and motivate the changing-scene work. The immutable release and rollback interface is a separate engineering deliverable. Concrete Deep SWE, Frontier SWE and Multi-Step SWE task comparisons remain unverified. [SWE-Marathon task catalog](https://www.swe-marathon.org/) · [Lifelong localization and mapping study](https://arxiv.org/abs/2111.10946)

**Verifiability.** The verifier drives the public CLI with generated data and checks geometric outcomes, provenance, determinism and observations made by fresh processes. Fixture generation, support measurement and expected cells are independent of the reference modules. The registration test accepts a range of poses and independently counts supported points, preserving valid differences in search algorithms. Reward behavior under additional candidate implementations and more severe layouts remains unmeasured.

**Realism.** LUH's multi-visit dataset provides an observed use case. It records a hall under high partitioning, partial occlusion by furniture and poster walls, and an open arrangement with pedestrian traffic. These are reasons to preserve unknown cells and separate persistent structural changes from intermittent returns. The release documents survey-prism position and SLAM-derived orientation, with a static hall scan. Those assets do not supply cell-level truth for each arrangement. The task authors wrote the exact test fixtures and simulated the hall with first-hit box intersections and metric lidar rays. The LUH dataset license is CC BY 4.0. The runtime data are entirely authored. [LUH dataset DOI and license](https://doi.org/10.25835/gkytjesg) · [Published dataset paper](https://isprs-archives.copernicus.org/articles/XLVIII-1-W6-2025/155/2025/)

**Difficulty.** Registration must handle translated and rotated odometry frames, changing observations, outliers, and competing locations. The next step must reconcile positive and negative evidence without erasing unobserved structure, then carry that evidence into a content-addressed store with consistent promotion and pinning. These are coupled subtasks with increasingly consequential state. This CPU pilot has a 90-minute per-step budget and has yet to demonstrate the repository's five-day workload target. Candidate retries, times, scores and failure modes are needed before extrapolating difficulty.

**Initial feasibility.** Exact intersections and clipped rays can support mapping. A bounded coarse-to-fine scan matcher with a spatial index can recover the provided registration cases. Content-addressed blobs and a locked atomic active pointer cover the release workflow. The authored standard-library reference demonstrates that approach locally. The pilot assumes planar geometry, already usable scanner poses, and a bounded registration prior. Map-tile scale, drift over entire routes, extensive environmental change and power-loss recovery remain outside measured evidence.

## Reference solution

The task authors wrote the reference implementation in [common/oracle](common/oracle/). It uses parametric grid clipping, bounded coarse registration with discrete hypotheses and local refinement, independent visit sets for update evidence, and immutable snapshots with serialized pointer updates. The package includes reference modules introduced through the current checkpoint. A valid solution can use a different ray traversal, optimizer or persistence design. The correlative search is approximate on dense or weakly observable scans.

```bash
python3 -B scripts/package_task.py
python3 -B checks/calibrate.py
oddish preflight experiment/dist/swe-m2_software-engineering_versioned-mapping --json
```

## Reward and verification

Each family is the fraction of its named checks that passes. A missing or invalid family result contributes zero for that whole family. The first three checkpoints average the available build, registration and evidence families. The fourth checkpoint averages all five families, consisting of those three, release, and the hall fixture. Build geometry gates those four checkpoint scores. In the first release, Oddish reported the fourth checkpoint as the task reward and retains behavioral details for earlier checkpoints in `checkpoint.json`.

Build has three checks. Registration has four, evidence has four, release has five and the hall fixture has two. Checkpoints run on authored inputs. An absent workspace produces the defined no-op result. The hall fixture measures relocalization to approximately one map-cell width.

## Hackability assessment

| Severity | Boundary and evidence | Mitigation and remaining validation |
| --- | --- | --- |
| YELLOW / MEDIUM | Fixture recognition could reward a submission tailored to the finite authored geometries. Separate expected values and full-output checks were reviewed in source. | The hall fixture adds independent scene simulation and changed geometry to the exact cases. Rotate hall layouts and inspect live candidate rollouts for overfitting. |
| YELLOW / UNASSESSED | Private sources, logs, process environment and artifact handoff are configured for separate images. Read-only candidate staging, symlink rejection and subprocess credential dropping were reviewed in source. The local process checks do not exercise OCI boundaries. | The verifier image restricts `/tests` and logs to root and passes an explicit subprocess environment. Check actual permissions, network denial, mounts and result integrity in a hosted oracle/no-op pair. |
| YELLOW / UNASSESSED | Publicly writable outputs remain a boundary for process interference. The active pointer race and historical byte preservation were executed locally. Hostile subprocess behavior was untested. | Launch each CLI in its own process group, retain verifier-owned logs, and reject symlinked JSON results. Verify process cleanup and artifact isolation in a fresh verifier container. |

## Development log

### 2026-11-23

Designed four requests from a recurring mapping workflow and added independent geometric, evidence and release probes. Added a raycast hall with shifted sensor positions and a relocated obstacle. Local packed oracle scored 1.0 at each checkpoint, and the no-op scored 0.0 at each. Oddish preflight passed. Docker and Harbor executables were unavailable in the authoring shell. Hosted trials, container-boundary checks and Harbor's model-based review are pending.

The hosted no-op scored 0.0 and the reference scored 1.0. One Codex GPT‑6.2 Sol xhigh attempt scored 1.0 at all four checkpoints and passed all 18 final checks, including the authored hall and active-map release probes. [Oddish screen](https://www.oddish.app/experiments/9fe9d13b)

#### Closed-loop release qualification

The fifth checkpoint runs unit-cell navigation canaries against a pinned
occupancy map. The independent guard can block a cell even when that
map marks it free. The candidate must replan around observed obstructions.
The review verifies the entire movement history and survey error,
rejects stale authority, and rolls back a suspect active map while both
old and new snapshots stay available.

The current final reward combines 30% from the five earlier check
groups and 70% from the eight canary checks. A valid guarded-detour
promotion is required for credit in the canary group. Earlier milestone
scores retain their prior formulas.
[Nav2 route-tool workflow](https://docs.nav2.org/rolling/tutorials/general_tutorials/route_server_tools/navigation2_route_tool/navigation2_route_tool/)

The packaged reference passed all five retained groups and eight canary cases. The final no-op score was zero. Oddish preflight reported no findings.
