# Phase 0 spike: crime-city game task (local, 2026-11-24)

Local spike for the game task (sheet row 11), following design § 5.5 and § 6.4
(`harbor-lh/ops/swe-marathon-v2/next-tasks/game-design.md`) and the kickoff decision of 2026-11-20.
Everything ran on one Mac (Apple M5 Pro, 6 performance + 12 efficiency cores, 24 GB, macOS 26.5),
headless, with Godot **4.7.2-stable** (`4.7.2.stable.official.ed1daf0bf`, SHA-512 checked),
Jolt physics, 60 Hz, `physics_jitter_fix = 0`, the Compatibility renderer, GDScript only in the
game. Nothing ran on any platform; no network; no Docker. Free memory was checked with
`memory_pressure` before every heavy run (floor 30%; 25% between the item-5 starts); when it was
below the floor the runners waited.

## Gate

**GO for Phase 1 on everything that can be measured locally; PENDING on Linux.**

- Within budget here: items 1, 2, 3, 4, 5, 6, 8 (the import pipeline) and 9; the five scenarios
  pass (25/25 at 1.0 on the primitive build).
- Pending, Linux only: item 7 (stills under Xvfb/llvmpipe), item 3 on a Linux vCPU pinned to one
  core, the native probe core built as a `.so`, the proxy's socket audit. These should run first
  when a Linux box is allowed (no platform run before the owner says so).
- Design changes before the GDD is written: locomotion bands from the shipped clips (item 8);
  one worker thread per graded process (items 3-4); explicit texture import settings (item 1);
  ENet timeout and snapshot-size expectations in the online chapter (items 5-6).
- Item 10 is a design point (below).

## Results against the § 6.4 budgets

| # | Measurement | Budget (design) | Result | Verdict |
| --- | --- | --- | --- | --- |
| 1 | Vendor library import, headless | § 3.8 stage table: fresh import of agent files up to 8 min (cap 12); vendor cache prebuilt | 68 MB Godot-ready subset of the four CC0 packs (147 GLB, 10 glTF, 20 textures of 2048²): **6.6-16.8 s wall, 22-32 s CPU, 1.8-1.9 GB max RSS** (two fresh runs) with the default (lossless WebP) texture import; **3.9 s wall, 4.5 s CPU, 1.07 GB** with VRAM (S3TC) compression set in the `.import` files; cache 46 MB | PASS |
| 2 | Probe in an arbitrary project: bone poses under the dummy renderer, `InputEventAction`, lockstep under `--fixed-fps 60` | Works (no number) | Works in the spike game and in a foreign project (own autoloads, GodotPhysics3D): probe first in `[autoload]` under a random name; bone poses match an analytic pose to 2.1e-7 m; an injected action acts in the same tick; every frame at exactly the commanded tick, `delta` always 1/60; identical trace when the harness runs slower; forged messages stop the game. Overhead about 1.5 ms per observation (8.5x real time at 10 Hz). A C GDExtension core (no godot-cpp) keeps the key and socket out of script reach. | PASS |
| 3 | Simulation speed, downtown block, 40 cars + 60 people with animated skeletons | 2x real time on one core | **8.7x** with the real art (65-bone skeletons, UAL clips, Kenney cars), **9.3x** with the primitive rig, one worker thread (1.0 core used); 1.9 ms per tick (p95 2.1 ms) | PASS (margin 4.3x on this Mac; see caveat) |
| 4 | Spread over 50 same-seed runs (police arrival, braking, lane offsets) | Bands must hold with 15% margin in 199/200 runs (§ 3.7) | One worker: **0 spread**: 50/50 bit-identical traces in each of 3 cases (police arrival 30.317 s, lane offset q95 0.2168 m, braking 15.966 m raycast / 16.189 m `VehicleBody3D`). Default thread pool (25 threads): the same single trace in all 3 cases, identical to one worker's (150 more runs) | PASS |
| 5 | Memory of nine headless processes on the downtown map | Fits the agent (16 GB) and verifier (32 GB) | 1 server + 8 clients on the block with the real art: **2.41 GB physical footprint in total** (about 268 MB each); free memory never fell below 27% while they started one by one. The server sent 48.7 KB/s per client; P2 clients converged to 0.05 m q95. | PASS |
| 6 | Impairment proxy with ENet (UDP) and WebSocket (TCP) clients | Works per profile P0-P3 + partition (§ 3.6) | `qa/proxy.py` relays real ENet and WebSocket peers at P0-P3: measured delivery and latency follow the profiles (ENet one-way p50 17/33/67/134 ms; WebSocket loss turns into stalls); a partition stops updates to that client only. Two findings: with default ENet timeouts a 3 s partition at P1 drops the client (fixed by `set_timeout`); the § 3.6 TCP stall model makes WebSocket unusable at P3. | PASS |
| 7 | Stills with Xvfb + llvmpipe, Compatibility renderer | seconds per frame | not measured: needs Linux (Xvfb, Mesa llvmpipe) | PENDING (Linux) |
| 8 | Retargeting UAL clips onto the base bodies with the humanoid bone map at import | Works headless | **Works** with a `BoneMap` (`SkeletonProfileHumanoid`) referenced from hand-written `.import` files: the body's skeleton becomes `%GeneralSkeleton` with profile bone names (65 bones: 53 mapped + 12 leaf bones), the library's 43 clips target `%GeneralSkeleton:<Bone>`, `_Loop` clips get loop mode. Probe checks pass (height 1.70 m, 4 skinned meshes bound). The clips' own speeds do not fit the proposed GDD bands (below). | PASS, with a GDD change |
| 9 | `VehicleBody3D` on Jolt against a custom raycast car; the ferry carrying physics-body cars | Both hold the GDD bands; deck drift at most 1 m | Both tuned into the same bands (0-60 km/h 5.12 s; braking from 60: 15.97 m raycast, 16.19 m VB; wet 19.45 / 22.24 m; turning circle 11.4 / 11.8 m; top speed 165 km/h); both deterministic (item 4). Ferry deck: largest drift 0.10 m (raycast) and 0.52 m (`VehicleBody3D`) over a 60 s crossing; the raycast car needs the deck's velocity in its tyre model (without it, it slid off). | PASS |
| 10 | Can artifact transfer leave out the vendor folder | Design point | Design point only (see below) | n/a |

## What was built (repository `game-spike/`, local git, never pushed)

| Part | Where | Notes |
| --- | --- | --- |
| Plan file and generator | `tools/gen_plan.py` -> `project/design/plan/downtown_block.json` | 3 x 3 junctions 120 m apart (2 x 2 city blocks), 12 roads, 48 lanes (2 per direction, 3.5 m), 5 signalised junctions with one phase per approach, raised blocks with 3 m sidewalks, 16 parcels with zoning and heights, 5 POIs (2 police stations with exit lanes, a safehouse, a shop, a proving ground). The file carries its own conventions block. |
| World built from the plan | `project/scripts/plan.gd`, `world_builder.gd` | Lanes, junction connectors (Bezier), approaches and stop lines, anchors (`{lane, s}`, `{intersection, approach, before_m}`, `{corner_of}`, `{poi}`), A* over lane segments; road slabs, raised blocks, buildings, street lights. |
| People | `humanoid.gd` (primitive), `real_art.gd` (CC0 art), `person.gd` | Primitive: `Skeleton3D` with all 56 `SkeletonProfileHumanoid` bones built in code, a skinned box mesh bound through a `Skin`, procedural idle/walk/run/sprint/sit clips with planted stance feet. Real: Quaternius Universal Base Characters + Universal Animation Library (item 8). |
| Cars | `car_raycast.gd`, `car_vb.gd`, `car_input.gd`, `car_visual.gd` | A custom raycast car (four suspension rays, slip-angle tyres, friction circle, moving-ground aware) and Godot's `VehicleBody3D`, behind the same inputs; Kenney Car Kit models in the art build. |
| Traffic and signals | `lane_driver.gd`, `traffic.gd`, `signal_system.gd` | Pure pursuit on lane centrelines, IDM gaps from lane occupancy, stop lines, amber decision latched per approach, a forward ray for anything not on a lane; 40 cars and 60 pedestrians by default. |
| Crime, wanted, police | `wanted_system.gd` | Running a red light is the crime; witnesses are police within range with line of sight; level 1 sends one car from the nearest station that is at least 100 m away and outside the camera frustum; the unit routes over the lane graph, then closes in. |
| Automation contract | `game.gd`, `dev_console.gd`, `hud.gd`, `camera_rig.gd` | Entity registry (group `entity`; id, kind, archetype, faction), DevConsole `exec()` (`world.reset`, `player.spawn`, `vehicle.spawn`, `npc.spawn`, `prop.spawn`, `traffic.set`, `time.set`, `weather.set`, `state`), events, `hud_wanted` badges, the 30 GDD InputMap actions. |
| Probe | `probe/qa_probe.gd`; native core `probe/native/qa_core.c` | Inserted by the harness as the first autoload under a random name and folder; HMAC-SHA256-signed, length-prefixed JSON over 127.0.0.1; lockstep; census, bone poses, camera frustum, HUD, ray/height/line-of-sight queries, skinned-mesh binding check, unregistered actors; input through `InputEventAction` + `Input.parse_input_event()`. |
| QA harness | `qa/harness.py`, `prep.py`, `runner.py`, `bots.py`, `asserts.py`, `plan_geom.py`, `proxy.py` | Copies a project, inserts the probe, imports headless, runs scenario instances in the § 3.4 format, drives bots through InputMap actions only, evaluates Python-hosted assertions over the trace, scores per § 3.8. The QA side reads the plan independently of the game. |
| Scenarios | `scenarios/s1..s5*.yaml` | `wanted.red_light` (E), `traffic.intersection_watch` (C), `vehicle.handling` (B), `people.locomotion` (A), `world.plan_compliance` (H). |
| Measurement drivers | `measure/*.py` | Items 2-6 and 9; raw results under `runs/` (not committed). |

## The five scenarios (§ 3.4 format, headless through the probe)

All five pass on the build with the primitive rig: **25/25 instances at 1.0** (default thread
pool). Each instance is a fresh Godot process; setup is DevConsole commands; bots act only
through InputMap actions; assertions are Python expressions over the recorded trace; scoring
follows § 3.8 (preconditions and consistency checks gate the instance).

| Scenario | Family | Instances | Score | What the probe and the assertions saw |
| --- | --- | --- | --- | --- |
| `wanted.red_light` | E | 8 seeds (5 witnessed, 3 unwitnessed controls) | 1.0 each | Crossing on red detected from the census against the QA side's own stop lines; witness line of sight by a probe ray from the officer's `Head` bone; wanted 1 within 0 s; no escalation; HUD badges equal the state; police first seen 133 m away and outside the frustum; arrival in 30.3 s; unit speed never above 13.4 m/s between frames; unwitnessed controls kept wanted at 0. 90-132 s simulated, 8.3-13.5 s wall. |
| `traffic.intersection_watch` | C | 5 seeds (3 junctions) | 1.0 each | 150 s of traffic: median 14 moving cars within 150 m; greens exactly 10.0 s, never two approaches green; 37 entries on green, 0 on red; lane offset q95 0.24 m over 32,048 samples, 100% aligned; pedestrians 100% on walkable surfaces; 0 impacts; no pop-in in view. 22-23 s wall (6.5x). |
| `vehicle.handling` | B | 6 seeds (3 per car type) | 1.0 each | Proving ground: 0-60, dry and wet braking, turning circle, top speed, upright, continuity, for the raycast car and `VehicleBody3D`. 79 s simulated in 3.0 s wall (26x). |
| `people.locomotion` | A | 3 seeds | 1.0 each | Skeleton with all 56 profile bones and a bound skinned mesh, no unregistered actors; height 1.73 m; walk/run/sprint 1.55/4.20/6.80 m/s; cadence 2.0/2.9/3.5 Hz; feet alternate; mid-stance toe slide q95 0.18/0.01/0.04 m/s; input moves the player in the same tick. |
| `world.plan_compliance` | H | 3 seeds | 1.0 each | Ray probes at 10 m spacing: 100% of lane-centreline samples hit a road at the plan elevation, all 16 roofs at the parcel height (±0.5 m) and inside the zoning range, 100% of sidewalk samples at 0.15 m, every POI on a surface; same seed gives an identical tick-0 population (101 entities), another seed a different one; `world.reset` 25 ms. |

With the real art the locomotion template scores 0.5 (item 8): the base body passes every
skeleton check, but the UAL clips miss the proposed speed, cadence and slide bands.

## Item details

### 1. Library import (art: the four CC0 packs the owner downloaded)

- Copied into `project/assets/vendor/` (the `vendor/` originals untouched): Kenney Car Kit and
  City Kit (Roads) GLBs with their colour maps, the UBC "Godot - UE" bodies, one rigged hair set,
  and the UAL GLBs (in place and root motion). 187 files, 68 MB.
- `godot --headless --path <copy> --import` on a fresh copy (no `.godot`):

| Texture import | Wall | CPU (user+sys) | Max RSS | Peak footprint | Cache |
| --- | --- | --- | --- | --- | --- |
| Default (Lossless; "detect 3D" never fires in a one-shot headless import, so textures stay WebP lossless), two fresh runs | 16.8 s / 6.6 s | 32.3 s / 22.3 s | 1.79 / 1.93 GB | 2.59 / 2.54 GB | 46-51 MB |
| `compress/mode=2` (VRAM, S3TC) written into the 20 texture `.import` files | 3.9 s | 4.5 s | 1.07 GB | 1.19 GB | 46 MB |

- The 2048² WebP lossless encodes are almost all of the cost. CPU S3TC compression is cheap.
  The two default runs differ by 2.5x in wall time with other agents' work on the machine;
  read the wall figures as a range.
- The UBC glTFs reference two textures the pack does not contain (`T_Eye_Normal_png.png`,
  `T_Hair_1_Normal_png.png`): three non-fatal import errors on every import.
- A code-only import of the project takes 6 s and 686 MB (the editor's own footprint).
- Not measured: the larger kits the design lists (Downtown City MegaKit, nature kits) were not
  part of this download; at the measured rate (0.06-0.25 s per MB) 1 GB of source would take
  1-4 minutes, inside the 8-minute cap.

### 3. Simulation speed (bench role, no probe, 3,600 ticks after 300 warm-up ticks)

| Configuration | Wall speed | One-core speed | Cores used | ms/tick mean (p95) |
| --- | --- | --- | --- | --- |
| Primitive rig, 1 worker thread | 9.36x | 9.32x | 1.0 | 1.78 (1.99) |
| Real art, 1 worker thread | 8.67x | 8.63x | 1.0 | 1.92 (2.10) |
| Real art, default pool (25 threads) | 6.61x | 3.40x | 1.94 | 2.52 (2.75) |
| Primitive, default pool | 6.71x | 3.53x | 1.90 | 2.48 (2.94) |
| Real art, 40 cars only | 25.9x | 25.6x | 1.0 | 0.64 |
| Real art, 60 people only | 12.6x | 12.6x | 1.0 | 1.32 |
| Real art, 60 people, animation off | 19.4x | 19.2x | 1.0 | 0.86 |
| Real art, 74 cars + 120 people | 3.93x | 3.93x | 1.0 | 4.24 |

- Per entity per tick: a car about 15 µs (raycast car, lane driver, occupancy), a person about
  21 µs (8 µs of it animating a 65-bone skeleton), the empty world 0.04 ms; the full load is
  the sum of the parts (0.64 + 1.32 ms against 1.92 ms measured).
- The default worker pool makes the simulation slower in wall time and doubles the CPU, most
  likely because Jolt's job system spreads small jobs over the pool's threads (not profiled).
- With the probe observing at 10 Hz (census of 155 entities with frustum tests, state, HUD) the
  red-light runs ran at 10x and the 150 s traffic runs at 6.5x (default pool).
- Caveat: an M5 Pro performance core is roughly twice a cloud vCPU (an estimate, not measured);
  scaled down, the block stays near 4x on the verifier. The agent's game will carry more logic per
  entity than this spike.

### 4. Spread over 50 same-seed runs

Each run is a fresh Godot process on the same prepared copy; the trace hash covers every
census of every observed frame at full float precision.

| Case | Worker threads | Runs | Distinct traces | Police arrival | NPC lane offset q95 | Braking from 60 (dry / wet) | Score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `wanted.red_light` seed 1 (witnessed) | 1 | 50 | 1 | 30.317 s (sd 0) | 0.2168 m (sd 0) | - | 1.0 x50 |
| `vehicle.handling` seed 1 (raycast car) | 1 | 50 | 1 | - | - | 15.966 / 19.447 m (sd 0) | 1.0 x50 |
| `vehicle.handling` seed 5 (`VehicleBody3D`) | 1 | 50 | 1 | - | - | 16.189 / 22.240 m (sd 0) | 1.0 x50 |
| `wanted.red_light` seed 1 (witnessed) | default pool (25 threads) | 50 | 1 (the same trace as with 1 worker) | 30.317 s (sd 0) | 0.2168 m (sd 0) | - | 1.0 x50 |
| `vehicle.handling` seed 1 (raycast car) | default pool | 50 | 1 (same as 1 worker) | - | - | 15.966 / 19.447 m (sd 0) | 1.0 x50 |
| `vehicle.handling` seed 5 (`VehicleBody3D`) | default pool | 50 | 1 (same as 1 worker) | - | - | 16.189 / 22.240 m (sd 0) | 1.0 x50 |

- Jolt here is deterministic across fresh processes with the same binary and inputs, and the
  harness's pace does not matter (item 2). The design's worry (§ 6.1) about threaded Jolt
  (broad-phase and contact order under multithreading) did not show up: 25 pool threads gave
  the same bit-identical traces as one worker, only slower (mean wall per instance 11.4 s
  against 8.9 s for the red light, 2.6 s against 1.1 s for handling).
- What this does not cover: agent games that read wall-clock time, use threads of their own,
  or run their physics on a separate thread; and other CPUs (x86_64 floating point can differ
  from arm64, so a Mac-made replay is not evidence for the Linux verifier).

### 8. Retargeting and the clips against the proposed GDD bands

- The import works headless from text alone: `project/assets/vendor/humanoid_bone_map.tres`
  (UE-style names -> profile names, 53 bones) referenced from the `.import` files of the bodies,
  the hair and both UAL files (`importer="animation_library"` for the clips). No editor UI step.
- Root-motion speeds from the `_RM` library (scaled by the skeleton's `motion_scale`, 0.95):
  Walk 1.01 m/s, Jog_Fwd 5.55 m/s, Sprint 8.54 m/s. The proposed GDD bands are walk 1.3-1.8,
  run 3.5-5.0, sprint 6.0-7.5 m/s.
- Locomotion with the real rig (probe-measured, toe contact, middle 60% of each stance):

| Player speeds | Walk slide q95 | Run slide q95 | Sprint slide q95 | Cadence walk/run/sprint |
| --- | --- | --- | --- | --- |
| GDD bands (clips time-scaled x1.46 / x0.72 / x0.76) | 0.06 m/s | 0.36 m/s | 0.50 m/s | 2.2 / 1.5 / 2.6 Hz |
| The clips' own speeds | 0.04 m/s | 0.24 m/s | 0.49 m/s | 1.3 / 2.2 / 2.9 Hz |
| Primitive rig at GDD speeds (reference) | 0.18 m/s | 0.01 m/s | 0.04 m/s | 2.0 / 2.9 / 3.5 Hz |

- So a legitimate game built on these clips cannot meet "slide at most 0.25 m/s" at sprint even at
  the clip's own speed, and at the GDD speeds the slowed jog has a lower cadence than the walk.

### 9. Cars and the ferry

- Both implementations reach the same bands (table above) and are deterministic with one worker.
- Things the spike tripped over, all now handled in the spike:
  - Godot's default body damping (`default_linear_damp` 0.1/s, combined) acts as about 2 kN of
    drag at 65 km/h on a 1.3 t car: the raycast car topped out at 64 km/h until both car types
    replaced it with their own drag.
  - `VehicleBody3D.brake` is an impulse per wheel per physics step (tick-rate dependent).
  - `VehicleBody3D` only scales the forward impulse by `wheel_friction_slip` when a wheel also has
    a side impulse, so straight-line braking ignores the wet friction: the rain rule (wet braking
    at least 1.15x dry) has to be scripted.
  - A raycast car must use the ground's velocity at the contact point, or it brakes against the
    world instead of the deck it stands on.
- Ferry: the deck (an `AnimatableBody3D` moved in `_physics_process`, 0 -> 5 m/s at 0.5 m/s², 30 s
  cruise with a 0.02 rad/s turn, then slowing down) carried a parked car of each type. Largest
  drift in deck coordinates over 60 s: **raycast car 0.10 m, `VehicleBody3D` 0.52 m** (limit
  1 m); both stayed upright. Without the moving-ground fix the raycast car slid off the deck
  (198 m).

### 2. Probe details

Two projects: the spike game, and a small foreign project (`measure/foreign_project`) with its own
autoloads, GodotPhysics3D instead of Jolt, a different node layout and a hand-posed four-bone
arm whose pose is known analytically. The harness inserted the same probe into both.

- **Loads into an arbitrary project.** In both projects the harness inserted the probe as the
  first autoload under a random name and folder (`autoload_first: true`) and the project's own
  autoloads ran after it. The foreign project runs GodotPhysics3D, so the probe does not depend
  on Jolt either.
- **Skeleton poses under the dummy renderer.** In the foreign project the probe's
  `get_bone_global_pose()` readings matched the analytic arm pose to **2.1e-7 m** over 180 samples
  (3 bones, 60 ticks). In the spike game it read the primitive rig and the imported 65-bone
  base body (item 8). Skinned-mesh binding and mesh triangle counts are readable headless too.
- **InputEventAction injection.** `move_forward` injected at tick t moved the body by exactly
  -0.050 m (3 m/s for 1/60 s) in tick t; the release stopped it in the next tick. The probe calls
  `Input.flush_buffered_events()` after injecting, so the input lands in the same tick.
- **Lockstep under `--fixed-fps 60`.** Every frame of every run arrived at exactly the commanded
  tick (the harness checks this on each step); the game saw only `delta = 1/60` (64 of 64 ticks);
  physics frames minus process frames stayed at 1 (one physics step per frame); holding the reply
  for one second advanced the game by exactly the one commanded tick.
- **Pace independence.** The same 900-tick drive with the harness 4 ms slower per step produced
  the identical trace hash.
- **Signatures.** A command with a wrong HMAC made the probe stop the game (exit code 3), both
  in GDScript and with the native core.
- **Overhead** (spike game, 154 entities in the census with frustum tests and the state report,
  one worker): observing every tick 3.31 ms/tick (5.0x real time), every 6 ticks 1.96 ms/tick
  (8.5x), every 60 ticks 1.71 ms/tick (9.8x), against 1.78 ms/tick for the bench without a probe.
  An observation costs about 1.5 ms, mostly census and JSON; 10 Hz observation keeps 8.5x.
- **Native core (C, no godot-cpp).** `probe/native/qa_core.c` (269 lines, built against the
  `gdextension_interface.h` dumped from the pinned binary) registers a class under a random name
  given per run, reads the port and key, wipes the key from the environment, and owns the socket,
  framing and HMAC. Loaded by a `.gdextension` file next to the probe in the foreign project:
  `native_core: true`, `key_in_environment: false`, `key_in_script: false`; 600 ticks observed
  every tick in 0.14 s; forged command -> exit 3. The GDScript-only probe reports the key in both
  places, which is the in-process risk the design rates YELLOW.
- Notes for the build: GDScript sees JSON ids as floats (`[1.0].has(1)` is false), and
  `Performance.TIME_PHYSICS_PROCESS` includes the probe's blocking wait, so the probe keeps its
  own timers.


### 5. Nine processes

- One server and eight clients, all headless at 60 frames per second, real art (UBC bodies with
  UAL clips, Kenney cars). The server simulates the block (40 cars, 60 people, one avatar per
  client) and broadcasts 20 Hz snapshots over ENet (22 bytes per entity); each client builds the
  static world from the plan and shows interpolated replicas (100 ms buffer) with animated
  skeletons and sends wander input at 30 Hz. Clients 1 and 2 connect through the proxy at P2.
- Processes started one at a time; free memory had to be at least 25% before each start.

| Process | Connects | Footprint after start (MB) | Footprint after 40 s with all nine up (MB) | Free memory before -> after its start |
| --- | --- | --- | --- | --- |
| server | - | 267.9 | 269.4 | 33% -> 28% |
| c1 | proxy (P2) | 285.6 | 267.1 | 28% -> 33% |
| c2 | proxy (P2) | 274.8 | 266.4 | 33% -> 34% |
| c3 | direct | 296.1 | 271.3 | 34% -> 30% |
| c4 | direct | 315.8 | 267.7 | 30% -> 27% |
| c5 | direct | 314.7 | 267.2 | 27% -> 30% |
| c6 | direct | 314.7 | 267.3 | 30% -> 30% |
| c7 | direct | 303.3 | 266.9 | 30% -> 29% |
| c8 | direct | 315.4 | 267.2 | 29% -> 27% |
| **Total** | | | **2,410 MB** | never below 27% |

- All nine started and synced; none was left running afterwards. RSS is not a usable number on
  macOS under memory pressure (it fell to about 91 MB per process while the footprint stayed at
  267 MB); the footprint is what the processes cost.
- With eight clients the server sent **48.7 KB/s to each client** (full 20 Hz snapshots of 162
  entities, 22 bytes each, no delta compression): at the GDD's proposed median budget of 48 KB/s
  already. A real city will need interest management or delta snapshots to stay in budget.
- Its physics ticks arrived every 16.5 ms (p50) and 19.6 ms (p95) in real time with nine
  processes and other work on the machine; the tick itself costs about 2 ms (item 3).
- Time-shifted convergence (§ 3.6, D = 2 RTT + 250 ms) of the logged entities: q95 **0.05 m**
  for the two P2 clients and **0.02 m** for the direct ones (budget 1.5 m on foot, 3 m in
  vehicles), max 0.62 m. Same machine, same clock: this validates the check, not a hard case.


### 6. Proxy

- `qa/proxy.py` (Python asyncio, seeded): one listening port per client; UDP datagrams are
  dropped, delayed, jittered, duplicated and reordered (P3 uses Gilbert-Elliott bursts with a
  mean of 4 and 8% loss up, 2% down); TCP keeps order and turns a lost segment into a stall of
  200 ms x 2^k; a partition drops (UDP) or holds (TCP) everything for one client.
- Self-test without Godot (stamped UDP echo, about 1,900 round trips per profile): round-trip
  delivery 100% / 98.5% / 90.5% / 89.2% for P0-P3 (expected 100 / 98.0 / 90.3 / 90.2), RTT p50
  0.2 / 51 / 122 / 251 ms (profiles 0 / 50 / 120 / 250 ms), p5-p95 44-58 / 100-147 / 210-294 ms,
  1.7% duplicates per round trip at P2 (1% per direction).
  TCP: RTT p50 0.3 / 127 / 248 ms for P0 / P2 / P3, P2 p95 535 ms from loss stalls, a 2 s
  partition shows as a 2.0 s stall.
- With Godot peers (one process hosting the server peer and two client peers, each client on
  its own proxy port, 600-byte packets down and 60-byte packets up at 30 Hz, stamped with the
  shared clock, client 0 partitioned for 3 s at t = 12 s):

| Transport | Profile | Client | Delivered (down) | Dup / reordered | One-way latency p50 / p95 / max (ms) | Packets during partition | First packet after it |
| --- | --- | --- | --- | --- | --- | --- | --- |
| enet | P0 | 0 (partitioned) | 0.879 (658/749) | 0 / 0 | 16.6 / 19.9 / 20.8 | 0 | 0.022 s |
| enet | P0 | 1 | 0.999 (748/749) | 0 / 0 | 16.6 / 19.9 / 20.8 | 72 | 0.022 s |
| enet | P1 | 0 (partitioned) | 0.563 (421/748) | 0 / 0 | 33.3 / 35.9 / 37.3 | 0 | 0.061 s |
| enet | P1 | 1 | 0.991 (740/747) | 0 / 0 | 33.3 / 35.8 / 37.2 | 72 | 0.028 s |
| enet | P2 | 0 (partitioned) | 0.832 (618/743) | 0 / 7 | 66.9 / 84.7 / 117.3 | 0 | 0.072 s |
| enet | P2 | 1 | 0.953 (708/743) | 0 / 12 | 66.9 / 84.5 / 118.6 | 71 | 0.022 s |
| enet | P3 | 0 (partitioned) | 0.852 (629/738) | 0 / 59 | 133.9 / 166.6 / 169.8 | 0 | 0.134 s |
| enet | P3 | 1 | 0.969 (715/738) | 0 / 66 | 133.1 / 166.5 / 170.5 | 67 | 0.067 s |
| ws | P0 | 0 (partitioned) | 0.999 (748/749) | 0 / 0 | 16.7 / 1769.7 / 3004.0 | 0 | 0.018 s |
| ws | P0 | 1 | 0.999 (747/748) | 0 / 0 | 16.6 / 20.0 / 20.8 | 72 | 0.033 s |
| ws | P1 | 0 (partitioned) | 0.999 (747/748) | 0 / 0 | 33.6 / 1766.9 / 3002.8 | 0 | 0.018 s |
| ws | P1 | 1 | 0.999 (746/747) | 0 / 0 | 33.4 / 116.8 / 235.7 | 72 | 0.018 s |
| ws | P2 | 0 (partitioned) | 0.993 (740/745) | 0 / 0 | 83.4 / 1830.6 / 3030.6 | 0 | 0.016 s |
| ws | P2 | 1 | 0.997 (742/744) | 0 / 0 | 81.5 / 265.7 / 464.7 | 75 | 0.016 s |
| ws | P3 | 0 (partitioned) | 0.103 (76/737) | 0 / 0 | 149.5 / 1719.2 / 12946.8 | 0 | 1.109 s |
| ws | P3 | 1 | 0.993 (735/740) | 0 / 0 | 149.8 / 2748.9 / 3349.0 | 72 | 0.008 s |

  Latency floors at about one frame (16.7 ms) because sender and receiver share one 60 fps
  loop; the profile adds the rest (half the RTT one way).
- **The partition stops updates** for the partitioned client in every case (0 packets in the
  window, the other client unaffected) and traffic resumes within 0.02-0.13 s, except below.
- **Finding 1 (ENet timeouts):** at P1 (50 ms RTT) the partitioned ENet client stopped receiving
  about 5 s after the partition began and never recovered (56% delivered; reproduced twice, and
  the proxy saw both directions go silent). With `ENetPacketPeer.set_timeout(32, 10000, 30000)`
  it survived (86.5%, only the partition lost). So Godot's default ENet peer timeouts can drop a
  low-latency client after a 3 s partition; this fits ENet's rule (a peer is dropped once a
  resend has backed off past 32 x its round-trip timeout, short at low RTT, and at least 5 s have
  passed), but the rule itself was not traced in the code. At P2 and P3 the client survived.
  ENet's packet throttle was not the cause (turning it off changed nothing).
- **Finding 2 (WebSocket under P3):** the TCP model of § 3.6 (every lost segment stalls the stream
  200 ms x 2^k, bursts of mean 4) makes WebSocket state unusable at P3: p95 latency 1.7-2.7 s, and
  the partitioned client fell up to 13 s behind (10% delivered within the run). The model has no
  fast retransmit, so it is harsher than real TCP; recalibrate it before grading WebSocket games
  at P3.
- ENet shows no duplicates at the application (it filters them) and some reordering for
  `TRANSFER_MODE_UNRELIABLE` (7-66 per run at P2/P3).


### 10. Leaving the vendor folder out of the artifact (design point)

- The game needs the vendor sources only through the import cache. The sources are
  byte-identical to the image copy, so the grader can restore them from the verifier image
  after a hash check.
- What must stay in the artifact are the small text files the agent may change: each asset's
  `.import` file (texture compression, the bone map reference) and resources such as
  `humanoid_bone_map.tres`. A changed `.import` invalidates the prebuilt cache entry for that
  file, so the grader re-imports it (measured cost: seconds per asset).
- Proposal: exclude `assets/vendor/**/*.{glb,gltf,bin,png}` and `.godot/` from the artifact, keep
  `*.import` and `*.tres`, restore sources and the prebuilt cache in the verifier, then run
  `--import` (which only re-imports what changed).

## What passed and what did not

- Passed: items 1, 2, 3, 4, 5, 6, 8 (the pipeline) and 9 (both car types and the ferry); the
  five scenarios on the primitive build (25/25 at 1.0).
- Did not pass as designed:
  - The proposed locomotion bands (speed, cadence, foot slide at 0.25 m/s) against the free UAL
    clips (item 8): a GDD change, not an engine problem.
  - The default worker pool: slower (6.6x instead of 8.7x) for twice the CPU. Its traces were
    identical to one worker's, so this is a cost, not a correctness problem.
  - Two network findings (item 6): default ENet timeouts can drop a low-latency client during a
    3 s partition; the § 3.6 TCP stall model makes WebSocket unusable at P3.
  - Not a failure but at the limit: naive full snapshots already use the proposed 48 KB/s per
    client (item 5).

## What still needs Linux (or more art)

- **Item 7, stills:** Xvfb + Mesa llvmpipe with the Compatibility renderer; Linux only.
- **Item 3 on the verifier's CPU:** re-run the bench on a Linux x86_64 vCPU with `taskset -c 0`;
  the Mac's performance core is likely about twice as fast.
- **The probe's native core on Linux:** the C file has no macOS dependency; build it as
  `libqacore.so` against the same dumped header and repeat the check.
- **Socket audit for the proxy** (`/proc/<pid>/net`, file descriptors): Linux only.
- **Art:** nothing measurable is blocked on art any more: items 1 and 8 and the real-skeleton
  re-run of item 3 used the four packs. The bigger kits in § 1.2 (Downtown City MegaKit, nature
  kits, watercraft) were not downloaded, so their import time is extrapolated, not measured.
  Kenney road pieces were imported but the spike's roads stay plain slabs (headless runs do not
  look at them). Outfits stay palette-based (owner decision).

## What each result changes in the design

1. **Grading runs with one worker thread per game process.** The grader already edits the copy
   it grades (probe insertion); it should also write `override.cfg` with
   `threading/worker_pool/max_threads=1` and pin each worker to one core. Determinism does not
   need it (the default pool gave the same traces), but it is 1.3-2.5x faster in the lockstep
   scenarios, halves the CPU and keeps parallel workers from competing. GDD chapter 16 should
   say the game must hold its budgets with one worker thread.
2. **Calibration can lean on exact replays.** The reference replays exactly from a seed (Jolt
   deterministic here with 1 or 25 threads), so "199 of 200 runs" reduces to one run per
   instance plus deliberate perturbations (seed sweeps, handling sweeps); retries stay for agent
   games that read wall-clock time or race their own threads. The bands must still carry the
   15% margin for legitimate alternatives.
3. **Locomotion bands come from the shipped clips.** Set the GDD walk, run and sprint bands around
   the UAL speeds (walk about 1.0-1.2 m/s, run/jog about 5.0-6.0, sprint about 8.0-9.0) or accept
   time-scaled clips and relax the checks: measure slide at mid-stance on the toe, per gait
   (walk 0.25 m/s, run 0.4, sprint 0.6), and drop "cadence follows speed" across gaits (keep it
   within one gait).
4. **Ship explicit import settings.** In the starter, the vendor `.import` files should set
   texture compression explicitly (headless one-shot imports never apply "detect 3D"), and the
   prebuilt cache should match them. Shipping the humanoid `BoneMap` and the retargeted import
   is a choice for the panel: it removes an editor-only step, but finding it is also part of
   the job; either way a headless agent can do it from text, as the spike did.
5. **Contract text:** inputs injected at tick t act in tick t (the probe flushes Godot's input
   buffer after injecting); entity ids should never be reused within a process (here they
   restart at `world.reset`, so traces must restart there too); JSON numbers reach GDScript as
   floats, so the DevConsole must accept `1.0` where it expects an id.
6. **Grader budget:** trace handling in Python is cheap: for a 130 s red-light instance (2,033
   frames, 106 entities) loading, all ten assertions and the trace hash took 1.3 s, and a game
   process starts in about 0.3 s. Simulation dominates: about 170 instances of 45 s at 4x
   (the Mac's 8.7x halved for a cloud vCPU) on 5 workers is about 6-7 minutes, inside the 20
   minutes of § 3.8.
7. **Probe:** the GDScript prototype proved the engine-side bets, but in it the per-run key sits in
   the environment and in script memory (its hello frame says so), and a game could find and
   hook a script autoload. A 269-line C core built without godot-cpp already keeps the key and
   the socket native: the key leaves the environment and never enters script memory. Phase 1
   moves the census, bone reads and input injection into the native core (method binds against
   the dumped `extension_api.json`), adds the per-tick heartbeat for real-time mode, and builds
   it for Linux.
8. **Vehicles:** both a raycast car and `VehicleBody3D` are viable and both carry a parked car
   on the ferry within 1 m; the GDD states the wet-braking rule as behaviour (it is), and the
   bots must not assume a car's axis conventions (ours infer the heading from the spawn
   direction; `VehicleBody3D` faces +Z). The traps the spike hit (default body damping, the
   ground's velocity under a raycast car, straight-line wet braking in `VehicleBody3D`) are the
   agent's to find; none needs a contract change.
9. **Verifier sizing:** nine processes on the block need about 2.4 GB (268 MB each, real art), and a
   fresh import peaks at 1.9 GB; with the agent's game larger than the spike, budget about
   0.5-1 GB per process: 5 solo workers plus a 9-process online session fit the 32 GB verifier
   with room, and the 8 GB fallback only with fewer processes at once. The 16 GB agent image is
   fine.
10. **The vendor folder** can stay out of the artifact; keep the `.import` and `.tres` files
    (item 10).
11. **Online chapter (GDD 15) and session design:** say that a client must survive or rejoin
    after a short partition (default ENet timeouts can drop it at low RTT); set the bandwidth
    budget knowing that naive full snapshots of about 160 entities already use 48 KB/s per
    client; recalibrate the TCP impairment (fast retransmit for isolated losses) before
    grading WebSocket games at P3, or grade online play at P3 with ENet only.

## Caveats

- One machine, macOS on arm64. The verifier is Linux on x86_64: speeds, memory and even exact
  float replays can differ there (item 4 says nothing about cross-CPU replay).
- The spike game is small: one plan block, one crime, one police unit, no combat or missions.
  Per-entity costs here are lower bounds for an agent's full game.
- All bands are proposals written for the spike (no GDD exists yet).
- macOS reports RSS that shrinks under memory pressure (compression); the physical footprint
  (`vmmap --summary`) is the better number for "how much RAM does it need".
- The machine was shared with other agents' work; free memory moved between 27% and 47%, and
  runs waited whenever it was under 30%.

## Reproduce

```
cd game-spike
python3 tools/gen_plan.py --seed 7 --out project/design/plan/downtown_block.json
tools/copy_art.sh                                   # CC0 packs -> project/assets/vendor
python3 qa/prep.py project runs/game_art --seed 21  # copy, insert probe, import headless
python3 qa/runner.py scenarios/s1_wanted_red_light.yaml --seed 1 --game runs/game_art --out runs/s1
python3 measure/bench.py runs/game_art_1t runs/bench/item3.jsonl label --cars=40 --peds=60 --art=ubc
python3 measure/spread.py runs/game_art_1t runs/spread/one_worker scenarios/s1_wanted_red_light.yaml 1 50
python3 measure/item2_probe.py runs/foreign runs/game_art_1t runs/item2.json
python3 measure/net_item6.py runs/game_art_1t runs/item6
python3 measure/net_item5.py runs/game_art_1t runs/item5 ubc
python3 measure/ferry.py runs/game_art_1t runs/ferry.json
```
`runs/game_art_1t` is `qa/prep.py ... --override "threading.worker_pool/max_threads=1"`.
