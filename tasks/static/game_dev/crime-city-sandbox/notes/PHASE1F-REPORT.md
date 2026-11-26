# Phase 1f report: vehicles (WS6 module 4), getting in and out, the ragdoll's limp flag, hidden instances (2026-11-26)

Author notes, never packaged. Brief: `harbor-lh/ops/swe-marathon-v2/next-tasks/game-phase1f-BRIEF.md`.
Branch `neel/game-phase1` (worktree `swe-m2-pr-game-phase1`). macOS only (Apple M5 Pro, 24 GB,
shared). No downloads, no Docker, no Linux VM, no Oddish. Godot 4.7.2 for macOS and the CC0 packs
came from `game-spike/vendor/`, already on this machine.

Every Godot run went through `scripts/heavy.py` (one exclusive lock, then at least 30% free memory
per `memory_pressure`), and every game process re-checked through the kit's gate
(`QA_MEM_FLOOR=30`). Free memory sat at 26-39% (other work on this Mac held about 2 GB); runs
waited whenever it dipped under 30%. Two helpers worked in parallel on files of their own and
queued their Godot runs through the same lock: one added the seat read to the native telemetry,
the other drew the people and signal hidden instances. A three-judge panel settled how QA sees a
person go limp, and an independent read (sonnet) read the new developer-facing material as the
developer would.

## What was built

| Piece | Where (task folder unless noted) | What it is |
| --- | --- | --- |
| Vehicles (WS6 module 4) | private: `crime-city-reference/overlay/game/vehicle.gd`, `tables.gd`, `world.gd` | Raycast vehicles for all 11 models inside their handling bands, damage, parts, fire and explosions, the motorbike's lean, people run into, the driving camera (below) |
| Getting in and out (FT-10) | private: `person.gd`, `pose.gd`, `world.gd` | Walking to the nearest door, sliding in, riding as the vehicle's child with the hips on the seat point and the driver's hands on the wheel, sliding out |
| The ragdoll (FT-9) | private: `ragdoll.gd`, `person.gd`, `world.gd` | The `limp` flag (the panel's option A), a position-based ragdoll with a rigid torso, getting up |
| Seat read, `body` query, census `kinds` (WS3) | `common/probe/native/telemetry.c`, `common/kit/qakit/play.py`, `trace.py`, `checks/test_godot_seats.py`, `checks/fixtures/seats/` | Each vehicle's seat, door and wheel points in world space every tick, in the style of the bone reads; a body's class, mass and layers; a census of some kinds only |
| QA's bot steps (WS4) | `common/kit/qakit/play.py` | `wait_for` an entity's speed or height; `cruise` (holding a speed with accelerate and brake) |
| Checks (WS4) | `common/kit/qakit/expect.py`, `common/kit/README.md`, `checks/test_vehicles_and_ragdoll.py` | `accel`, `brake`, `turn_circle`, `decel`, `body`, `seats`, `get_in`, `seated`, `get_out`, `camera_vehicle`, `lean`, `ragdoll`, `free_fall`, `get_up`, `impact_damage`, `part_off`, `max_speed`, `meta_value`, `explosion`, `blast` |
| Playtests (WS4) | `common/kit/playtests/` | `vehicle.handling/cars`, `vehicle.handling/service`, `people.vehicle_entry/sedan`, `vehicle.crash/barrier`; `people.fall_ragdoll/falls` gains FT-9 |
| Hidden instances (WS8) | private: `tests/private/templates/`, `tools/build_templates.py`, `plays/`; public: `scripts/check_disjoint.py`, `checks/test_disjoint.py`, `scripts/make_instances.py` | Templates for the eight people and signal playtests, 16 new instances (31 in all), a disjointness check, `expr` parameters |
| Panel | `harbor-lh/ops/swe-marathon-v2/decisions/2026-11-26-game-ragdoll-visibility-*.md` | How QA sees a person go limp: A by majority |
| Acceptance tool | `scripts/phase1f_acceptance.py` | `qa`, `grade` (the playtests and the private set, on the reference and the starter), `private` (the private set alone), `replay10` |

### Vehicles (private)

- **A raycast vehicle on a `RigidBody3D`**, the design Phase 0 measured: a spring and damper per
  wheel along a ray down from its mount, slip-angle tyres inside a friction circle, all-wheel
  drive under a force limit and a power limit, a rev limit at the top speed, brakes that hold
  every wheel at the grip limit, the handbrake on the rear wheels, drag and rolling resistance,
  and the ground's velocity under each wheel (so a vehicle rides a moving deck). The car kit's
  models are toys, so they are shown at 1.72 times their size (a sedan 4.4 m long); the motorbike
  is ours, on four close rays with a roll controller that leans it into turns (VH-9).
- **Sizing.** A small Python model of the longitudinal dynamics set each model's force, power and
  drag for the middle of its 0-60 and top-speed bands, its grip for the middle of its dry braking
  band, and its full lock from the wheelbase for the middle of its turning-circle band. It
  predicted Godot's 0-60 times to 0.01 s. Two corrections came from measuring in Godot:
  - the cars were still accelerating at the end of a 2.08 km straight, so each now has a rev limit
    at its band's middle, with power and force re-solved so the 0-60 time stays at its middle and
    the limit is reached within about 1.2 km (the GDD measures top speed on a 1.5 km straight);
  - low-speed tyre slip made every circle about 5% wide, so each full lock was corrected from its
    measured circle.
- **Rain.** Grip falls to 0.78 of dry; braking is at the grip limit, so every stop from 60 km/h
  takes 1.28 times as far (VH-2's band is 1.15-1.60).
- **Damage (VH-3 to VH-6).** An impact is a contact of the body; its dv runs from just before the
  contact to 0.2 s later and adds `0.004 * (dv - 8)`. One of 25 km/h or more that leaves damage at
  0.25 or above throws off a part (a car kit debris model on its own `RigidBody3D`, registered as
  `debris` with `vehicle` metadata, and `part_detached`). From 0.75 the engine gives 8 km/h; from
  0.80 the vehicle burns and explodes 10 s later: `vehicle_exploded`, every physics body within 8 m
  pushed away, people within 3 m killed, `100 * (6 - d) / 3` health taken from 3 to 6 m, everyone
  within 6 m limp, 0.30 damage to vehicles within 6 m, and the wreck at 1.0.
- **People run into.** Vehicles no longer collide with people's capsules; a vehicle at 20 km/h or
  more that overlaps a person makes it go limp, thrown along at 0.8 of the vehicle's velocity.
- **Driving.** The driver's actions are read in the vehicle's `_physics_process` (IN-3); brake held
  at a standstill for 0.3 s reverses; vehicles without a driving player hold their brakes. NPC
  drivers only sit: driving in traffic is module 5's.
- **The driving camera.** 7.0 m from a point 1.6 m above the vehicle's centre, behind it, pulled in
  front of walls (CM-1, CM-4).

### Getting in and out (FT-10)

- `interact` on foot finds the seat whose door is nearest the player, horizontally, within 3.0 m
  (the nearest door picks the seat; an occupied one gives nothing). The player walks to the door at
  1.4 m/s and slides into the seat over 1.4 s, then `vehicle_entered`.
- Seated, the person is a child of the vehicle without collisions of its own, so it moves with
  the vehicle's physics step. When the seating happens inside the person's own physics step, the
  move under the vehicle waits for the end of the frame: moving a node out of the tree during its
  own callback skipped that tick's pose node, which showed as one frame with the hips 0.33 m off.
- After the animation (the shipped Driving and Sitting clips), the pose node moves the person so
  the `Hips` bone is on the seat point, and puts a driver's hands 0.17 m either side of the wheel
  point with two-bone IK. The hands follow the forearms: the Driving clip's hand bones have a
  collapsed axis, which made rewriting their own basis fail.
- `interact` in a vehicle slides out to the door over 2.0 s; the player stays in the seat in the
  state report until it stands at the door (`vehicle_exited`).

### The panel and the ragdoll (FT-9)

The GDD gave QA no way to see that a person has gone limp. Three judges (opus, sonnet, haiku),
each given the same facts and options, voted independently:

| Judge | Vote | Main point |
| --- | --- | --- |
| opus | A | a level flag read every tick is unambiguous and costs any rig one line; events would count the animated get-up as limp; an engine property fits one simulator only |
| sonnet | D (A plus a motion cross-check) | A is the fairest and fits AC-12's honesty pattern; the flag needs the bones checked against it |
| haiku | A | no engine assumptions; the physical clauses are measured on the bones, so a lying flag still needs real ragdoll motion |

**Decision: A.** People carry `limp` (and `player.limp`), true exactly while the body is under
ragdoll physics. The cross-checks all three asked for are now in the rule and the checks: free fall
measured on the bones, the ground clause on every limp tick, no hips move over 1 m in a tick, and
the state report saying what the metadata says. Record:
`decisions/2026-11-26-game-ragdoll-visibility-DECISION.md`, the brief and the three votes.

The reference's ragdoll is position-based physics on seventeen joints:
- Verlet points (no air damping, so free fall is exactly g; measured 9.81 m/s^2), links at their
  lengths, a ground pass by rays against the world, props and vehicles;
- a rigid torso: every tick its starting shape is fitted to its seven points (the best rotation,
  by Mueller et al.'s iteration, since GDScript has no SVD) and, if any of it is under the surface,
  the whole torso is lifted; then the limbs are solved again against it;
- the bones follow: the torso's turned rigidly, each joint swung to point at its child's point.

The first versions let a bone dip under the ground on a hard landing, for three reasons, each
fixed:
- the Head was 0.19-0.26 m under when the torso was posed from a frame of four points;
- a foot was 0.07 m under when the limbs were not solved again after the torso fit;
- a toe was 0.03-0.04 m under in the very first limp frame after a landing, because that frame
  still showed the jump clip's pointed toes on the landed body; the ragdoll now settles out of
  the ground and poses the body in the tick it starts.

Joints rest 0.06 m above the surface, about a limb's half thickness. On the final reference no
observed bone went under the ground in any playtest or instance.
Dying, landing from 6 m or more, an explosion within 6 m and being run into at 20 km/h or more make
a person go limp at once. A living person stays limp 1.5-3 s, until it settles, then the flag goes
false and the pose blends into standing over 1.0 s. `player.give` with health 0 kills (CB-7).

### Hidden instances (WS8)

- **Templates** (private) for the eight people and signal playtests. They draw variations (never
  the playtests' 2 to 10), places on parks and plaza strips away from `plaza_central`, headings,
  leads and lead orders, action strengths and durations, ledge and barrier sizes, tower heights
  across FT-8's bands, the press distance, and signal watches around a second `world.reset`. The
  falls template now also has FT-9: a sixth tower, 17-21 m, with a death 1-3 m into the fall.
- **`expr` parameters** in `make_instances.py`: arithmetic over drawn values that draws nothing, to
  place props at any heading and put computed numbers in the notes. Earlier instances come out
  byte-identical.
- **Disjointness, checked.** `scripts/check_disjoint.py` calls an instance a repeat of its playtest
  when it shares a variation, a place within 1 m, the lead order, a prop's height, a signal watch's
  start, or every step. On the private manifest, 30 instances compared, none repeats (the plan swap
  has no playtest).
- **31 instances:** A 16, C 2, H 5, K 4, M 2, T 2.
- The first grade of the new set was 0.997466: a drawn 3.47 m fall cost 3 health against 3.91
  within 10%. Two causes, both fixed:
  - the reference measured the fall from where the capsule had already slid over the edge, so it
    now keeps the ground found straight under the person each tick;
  - with health in whole numbers, 10% of a loss under 5 health is less than one point, so
    `fall_damage` now always allows half a point.

## Decisions

1. **Raycast vehicles, not `VehicleBody3D`.** They tune exactly, are deterministic with one
   worker, and ride a moving deck (Phase 0). The GDD does not prescribe one; both stay open to the
   developer.
2. **Top speed.** Downtown has no 1.5 km straight, so no shipped playtest checks top speed yet; the
   reference is measured on a 2.1 km test straight (an author tool, below). The check comes with
   the Sable Hills drag strip and the highways (WS2).
3. **Clarifications, so each check measures only what the GDD states** (no new features: the 177
   rules stay; the coverage map's rows for FT-9, FT-10, VH-3, VH-4 and AC-5 now name the new
   expectations, 0 problems):
   - **FT-9:** the `limp` metadata (AC-5) and `player.limp` (AC-12); the fall trigger is the
     landing; "under physics" includes no hips step over 1 m; getting up is the flag false with the
     hips back to 90%.
   - **FT-10:** what "seated" means; that the seated pose lasts until `interact` is pressed to get
     out (getting out must take 1.0-3.0 s, so the state report still names the seat meanwhile);
     the distances are horizontal.
   - **AC-6:** `wheel` is in vehicle space; a seat's position is its seat point.
   - **Chapter 6:** handling is measured on roads or parking lots; the turning circle's centre is
     the vehicle's position. **IN-2:** the handbrake's rate is from 40 km/h over its first second.
   - **VH-3:** dv runs from just before the impact to 0.2 s after it. Jolt pushed a car back out of
     a wall in one step, which reads as a 13 km/h bounce for one tick; the reference and QA now
     both read the change across the 0.2 s.
   - **VH-6:** the push moves a parked car 5 m away at least 0.3 m, and is not an impact of VH-3;
     d is between positions.
   - **`player.give`:** health 0 is death.
4. **The ferry and the boats wait for Ashby Port.** The plan lists the ferry in module 4, but VH-10
   to VH-12 and WD-10 all need water, the ferry terminals and the Port and Hills plans.
5. **Traffic-aware driving is module 5's.** The plan's module 4 covers cars, handling, damage,
   parts, fire, the motorbike, boats and the ferry; signals, lanes and spawning are module 5.

## Independent read

An independent solver's-eye read (sonnet) of the GDD diff, the README diff, the five playtests and
the new check and step docstrings found no evaluation wording. Its other findings, all fixed before
the final acceptance runs:
- **The run-into clock** started when the sedan's centre came within 3.5 m, about 0.15 s before
  contact; it now starts at 2.5 m (about where a sedan's front meets him) and allows 0.3 s.
- **Getting up after a fatal hit:** the GDD does not say whether a hit at 30 km/h kills, so
  `get_up` now holds for a person whose `died` event came.
- **The blast's push** had no stated size and could have counted as an impact: VH-6 now states both.
- **Traffic** could cross a proving run: the handling, entry and crash playtests set traffic and
  people to none.
- **The run-into speed** depended on how a game coasts: QA's bot now holds 30 km/h through the hit.
- Also: the wet stop on the dry stop's lane; `cruise`'s gains and margin in the README; "2.4 m to
  the right of its centre line" instead of "from its side"; "velocity" in VH-3's note; model names
  in notes.

## Acceptance results (macOS)

### The reference and the starter

| Run | Result |
| --- | --- |
| Reference, every playtest (26) as the instance set | **1.000000**: self-test passed (11.7 s); static gate (23 own files); import 3.61 s with a 64.27 MB cache; boot 0.282 s solo, 0.277 s server; 26 of 26 instances at 1.0, every family 1.0 (A, B, C, H, I, K, M, T); 63.0 s in all |
| Starter, same set | **0.000000**: static (6 files) and import (3.15 s, 64.27 MB) gates pass; the boot gate fails ("solo not playable within 60 s", "server not playable within 60 s"); 123.6 s |
| Reference, the private set (31 instances: the alternative Downtown and the 16 new people and signal instances among them) | **1.000000**: 31 of 31 at 1.0, every family 1.0 (A, C, H, K, M, T); import 4.06 s; boot 0.687 s solo, 0.735 s server; 300.1 s in all, most of it waiting for memory (an earlier run on the same reference but the ragdoll's start: 1.000000, the instances 47.1 s together, the longest 4.6 s) |
| Starter, the private set | **0.000000**: static and import gates pass, the boot gate fails; 244.8 s |
| Ten replays of `world.replay/two-paces` in fresh processes | **1** distinct hash over 10 runs (78 frames each, 0 errors, 11.6 s): `1ad7f82f...`, the same as Phase 1e |
| `qa run`, all 26 playtests | Reference: **26 of 26 hold** (49.9 s with the import). Starter: all 26 list what did not hold, 0 runs stopped (16.6 s) |
| Memory | Each game process peaks at 120.7-125.5 MB on the playtests (Phase 1e: 134-135 MB) |
| Wording | `check_agent_text.py` over `common/` and `environment/`: 0 hits (8 open markers, all from before); `qa list`: 0 hits; both `qa run` outputs: 0 hits once this Mac's scratch paths are swapped for the sandbox's; the library's strings: 0 hits (845 strings) |
| Development checks | **215 pass**, 5 Godot-only skipped (169 at the start of the phase); with Godot, the new seat check (252 points, worst 2.35e-6 m) and the bone check pass |
| Coverage | `check_coverage.py`: 177 rules, 177 rows, 0 problems |

### Handling against the bands (VH-1, VH-2, IN-2; measured by the playtests)

| Model | 0-60 km/h s | Dry stop from 60 m | Wet / dry | Turning circle m (at km/h) | Handbrake m/s^2 | Mass kg | Top speed km/h (author straight, 2.1 km) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sedan` | 5.50 (4.5-6.5) | 16.27 (13.5-19.5) | 1.283 | 11.54 (7.2) (10.0-13.0) | 3.36 | 1,350 | 166.6 (150-185) |
| `hatchback` | 5.00 (4.0-6.0) | 15.77 (13.0-19.0) | 1.284 | 10.54 (7.1) (9.0-12.0) | 3.37 | 1,150 | 161.6 (145-180) |
| `sports` | 3.50 (2.8-4.2) | 14.25 (12.0-17.0) | 1.283 | 12.03 (7.5) (10.5-13.5) | 3.37 | 1,300 | 221.6 (200-245) |
| `suv` | 6.25 (5.0-7.5) | 17.51 (14.5-21.0) | 1.283 | 12.52 (7.2) (11.0-14.0) | 3.37 | 1,900 | 164.1 (150-180) |
| `van` | 7.50 (6.0-9.0) | 19.30 (16.0-23.0) | 1.283 | 13.77 (7.2) (12.0-15.5) | 3.37 | 2,300 | 139.0 (125-155) |
| `pickup` | 6.75 (5.5-8.0) | 18.54 (15.5-22.0) | 1.283 | 13.53 (7.2) (12.0-15.0) | 3.37 | 2,000 | 149.0 (135-165) |
| `taxi` | 5.50 (4.5-6.5) | 16.26 (13.5-19.5) | 1.283 | 11.54 (7.1) (10.0-13.0) | 3.37 | 1,350 | 166.6 (150-185) |
| `police` | 4.70 (3.8-5.6) | 15.51 (13.0-18.5) | 1.283 | 12.04 (7.3) (10.5-13.5) | 3.37 | 1,500 | 191.6 (175-210) |
| `ambulance` | 8.00 (6.5-9.5) | 20.29 (17.0-24.0) | 1.283 | 14.03 (7.0) (12.5-16.0) | 3.37 | 2,800 | 144.0 (130-160) |
| `tactical_van` | 8.48 (7.0-10.0) | 20.30 (17.0-24.0) | 1.283 | 14.28 (7.1) (12.5-16.0) | 3.33 | 3,000 | 136.5 (125-150) |
| `motorbike` | 3.25 (2.5-4.0) | 14.37 (12.0-17.0) | 1.284 | 7.49 (7.8) (6.0-9.0) | (cars only) | 220 | 189.1 (170-210) |

The 0-60 times, the dry stops, the turning circles and the top speeds sit within 2% of their
bands' middles. The wet ratio (1.28, band 1.15-1.60) and the handbrake (3.37 m/s^2, band 2-6) sit
below their middles, yet inside the 15%-of-width margins WS1 asks for (1.22-1.53 and 2.6-5.4).
Masses are exact. The motorbike leans 31.2 degrees (the
median) cornering at 3.8 m/s^2 (VH-9: at least 10 degrees from 2 m/s^2). Top speed is measured by
an author-only scene on eleven 195 m slabs end to end (props are at most 200 m), since Downtown has
no 1.5 km straight; it is reached within about 1.1-1.2 km.

### Getting in and out, the ragdoll, damage

| Check | Band | Reference |
| --- | --- | --- |
| FT-10 getting in (both sides) | path within 1.0 m of the door; seated in 1.0-4.0 s | 0.008 m; 1.93 s (the door 0.76 m away at the press) |
| FT-10 seated | hips within 0.35 m of the seat point; hands within 0.30 m of the wheel | 0.000 m over 247 and 494 frames, driving included; hands 0.175 m |
| FT-10 getting out | 1.0-3.0 s, on foot within 2.5 m of the door | 2.02 s; 0.001 m |
| AC-6 seats | 4 seats, doors, a wheel point | 4, every door, the wheel |
| CM-1 driving | 5.0-10.0 m from the vehicle; hips in the middle 40% | 7.48-7.57 m; 0.062 |
| FT-9 landing from 10 m | limp within 12 ticks; at least 1.0 s; no bone 0.05 m under; no hips step over 1 m | 1 tick; 1.5 s; deepest 0.000 m; 0.25 m |
| FT-9 getting up | within 6.0 s, hips back to 90% | 2.3 s |
| FT-9 death (16 m), mid-air death, blast, run into | as above | 1, 1, 1 and 0 ticks; deepest 0.000 m; limp 8.3, 10.0, 1.5 and 2.5 s |
| FT-9 free fall | 9.81 m/s^2 within 20% | 9.81 (75 samples) |
| VH-3 impact | `0.004 * (dv - 8)` within 25% | dv 43.9 km/h: 0.1433 for 0.1436 |
| VH-4 part | within 0.5 s | 0.20 s, a debris entity naming the car |
| VH-5 engine at 0.78 | at most 10 km/h | 8.18 km/h |
| VH-6 explosion | 8-12 s after burning; wreck at 1.0 | 9.95 s; 1.0 |
| VH-6 blast | death within 3 m; `100 * (6 - d) / 3` from 3 to 6 m; a car 5 m away pushed 0.3 m and +0.30 damage | died at 2.0 m; 50 lost at 4.50 m (49.93); 1.25 m and +0.30 |

## Running the jobs: one slip

Stopping the first acceptance run (its playtests had to change after the independent read), the
first kill took its `qa` part and the acceptance loop started its `grade` part before the loop was
killed; that orphaned grade then ran a few minutes without the heavy lock, beside the new run,
writing into the same work folder (the new run's private grades failed on the folder it left). Its
game processes still waited for 30% free memory one by one, and memory never ran short. The
private grades were rerun alone, under the lock, in a clean folder. Next time: kill the process
group, not its members.

## The playtests and their status

| Playtest | Rules | Reference | Starter | In the reference's required set |
| --- | --- | --- | --- | --- |
| `vehicle.handling/cars` (new) | VH-1, VH-2, IN-2, AC-6 | holds (42 expectations: 6 models) | 42 do not hold | yes |
| `vehicle.handling/service` (new) | VH-1, VH-2, IN-2, AC-6, VH-9 | holds (35: 5 models, the motorbike's lean) | 35 do not hold | yes |
| `people.vehicle_entry/sedan` (new) | FT-10, AC-6, CM-1, IN-2 | holds (9) | 9 do not hold | yes |
| `vehicle.crash/barrier` (new) | VH-3, VH-4, VH-5, VH-6, FT-9, AC-10 | holds (11) | 11 do not hold | yes |
| `people.fall_ragdoll/falls` (FT-9 added) | FT-8, FT-9 | holds (11) | 11 do not hold | yes |
| the 21 other playtests of Phases 1c to 1e | 50 rules | all hold | all report failures | yes |

The 26 playtests cite 61 rules: Phase 1e's 50 and 11 new (FT-9, FT-10, VH-1 to VH-6, VH-9, IN-2,
AC-6). Each new rule has at least one expectation citing it.

## What still needs Linux

Everything on Phase 1b's to 1e's lists still applies:
- the `.so`, the cgroup sandbox and the unprivileged user, a real fork bomb, `/proc` readings;
- the starter in the agent image, `qa run` with Python 3.12, the ENet server in a container;
- the verifier image's paths, the world builder and replays on x86_64, import and boot on a cloud
  vCPU;
- the telemetry's bone cache on Linux, replays with animation and IK on x86_64, the people bands'
  calibration, the plan-swap instance in the verifier image.

This phase adds:
- **The seat read, the `body` query and census `kinds` in the `.so`.** The C compiles clean for
  x86_64 and arm64 with this Mac's clang and the Linux flags (the `LOAD` macro now casts through
  `void (*)(void)`, which those flags needed), but there is no Linux sysroot here, so the `.so` was
  not linked or run.
- **Vehicles and the ragdoll on x86_64.** Every handling check reads positions every tick, and the
  ragdoll's bones feed the ground and free-fall checks; both rest on float behaviour (Jolt's
  contacts, the raycast suspension, the Verlet points). `world.replay` has no vehicle yet: add a
  replay with a car and a ragdoll, and run ten of them on x86_64.
- **Calibration of the vehicle bands (WS9).** The reference sits at each band's middle on this
  Mac; its spread on the verifier's CPU, and across handling sweeps, is still to measure.
- **Grading time.** The two handling playtests' game processes run 9.0 s and 7.9 s here, two
  fifths of the 42.0 s all 26 playtests' processes take; measure on a cloud vCPU.

## Not done in this phase

- **Top speed's shipped check** waits for a straight of 1.5 km (the Sable Hills drag strip and
  the highways, WS2).
- **"A car's body mesh comes from its library model's file" (VH-1) and AR-3's body mesh** need a
  query that says where a mesh came from (WS3), then their checks.
- **VH-7** (repair, with the garage menu, module 9), **VH-8** (taking a car, with crimes, module 7),
  **VH-9's rider thrown off** at 40 km/h, **VH-10 to VH-12** and **WD-9, WD-10** (boats, the ferry and
  the map links, with Ashby Port and Sable Hills).
- **`inv.damage_honest`** (damage only from observed impacts) as an invariant on every instance.
- **Hidden instances for the vehicle playtests and `people.vehicle_entry`** (family B and A):
  drawn models, lanes, weathers, sides and seats.
- From module 3: FT-7 (swimming, with water), AC-11's look shader parameters, and city people's
  behaviours (module 5).

## Next workstream

**WS6 module 5, traffic and pedestrians**, on this phase's vehicles: NPC drivers seated with
FT-10's pose and driving lanes (TR-7, TR-8), obeying signals and all-way stops (TR-5, TR-6),
yielding to people on crosswalks and stopping for obstacles (TR-11, TR-12), city people walking
the sidewalks and crossing at crosswalks (TR-9, TR-10, AR-4), panic and the horn (TR-13, TR-14),
spawning without pop-in at the table's densities (TR-1 to TR-3, TR-15, TR-16). That opens
`traffic.intersection_watch`'s flow checks, `traffic.stop_junction`, `traffic.obstacle`,
`traffic.speed` and `traffic.panic_horn`.

Alongside it:
- the vehicle and entry hidden instances (WS8);
- a replay with a car and a ragdoll in `world.replay`;
- for the Linux items above, an x86_64 Linux machine (the owner's call).

## Commits

| Commit | What |
| --- | --- |
| `0bd3925` | WS3/WS4: the telemetry's seat read, `body` query and census `kinds`; `wait_for` entity and `cruise`; the vehicle, getting in and out, ragdoll and damage checks with their hand-made-frame checks; the seat read's Godot check |
| `ca4c901` | WS8: `scripts/check_disjoint.py` and its check, `expr` parameters; `fall_damage` allows half a health point |
| `60ff0ec` | WS1/WS4: the GDD's clarifications (FT-9, FT-10, AC-5, AC-6, AC-12, chapter 6, IN-2, VH-3, VH-6, `player.give`), the four new playtests and the falls playtest's FT-9, the lean check, the independent read's fixes, the acceptance tool, the coverage map |
| `8676f3e` | the acceptance tool's `private` part, this report, the README |
| (next) | this table's hashes |

Private, with both bundles refreshed in `harbor-lh/ops/swe-marathon-v2/next-tasks/game-private/`:
- `crime-city-reference` `62ab893`, `2bc0c5f`: module 4 (vehicles) and module 3's rest (getting in
  and out, the ragdoll), falls measured from the ground straight under, the ragdoll settling at
  its start;
- `tests/private` `d77977e` (the helper: templates, 16 instances, the builder), `101feca` (FT-9 in
  the falls template, its two instances redrawn), `e7ae072` (the results).
