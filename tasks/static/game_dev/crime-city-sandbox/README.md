# Crime-city sandbox (game dev): work in progress

An original open-world crime-city game built from scratch in Godot 4.7.2, with our own world and cast (sheet row 11).
This is the largest task we plan. The agent builds the game; it is graded headless through a QA hook (the probe) by
hidden scripted scenarios, plus multiplayer checks under packet loss and checks that characters are really rigged and
animated.

## Status

Phase 0 spike: done locally. Every item we can measure on a Mac is within budget. See `spike/PHASE0.md`.
- **Probe:** works in our project and in an unrelated one; bone positions within 2.1e-7 m; input lands in the same
  tick; exact lockstep.
- **Simulation speed:** 40 cars and 60 people with 65-bone skeletons at 8.7x real time on one core (budget 2x).
- **Determinism:** 300 same-seed runs, zero spread.
- **Nine headless processes:** 2.41 GB.
- **Network proxy:** ENet and WebSocket work.
- **Scenarios:** five scenarios at 1.0, 25 of 25 runs.

Pending, all needing Linux:
- headless stills;
- the speed check on a cloud vCPU;
- the probe's Linux build.

Phase 1a: done (writing only). The design document the developer builds against
(`common/design/GDD.md`, 177 numbered rules), the plan format (`common/design/plan/FORMAT.md`), the
Downtown core block (`common/design/plan/downtown.json`), and the Phase 1 plan with a rule-by-rule
coverage map (`notes/PHASE1-PLAN.md`). Report: `notes/PHASE1A-REPORT.md`.

Phase 1b: the grading kit core (WS3) on macOS. The QA telemetry node's native core in C (no
godot-cpp; the per-run key and the socket never reach a script), the kit (signed link, process
control with limits and whole-tree kills, lockstep and real-time sessions, preparation, hashed
traces restarting at each `world.reset`, the `qa-play/1` format, expectations, plan anchors), the
grader (self-test first, three gates, scoring with fixed denominators, its own deadline, reward
always written after the self-test), a self-test project of ours, the instance maker and a private
instance set, 16 hostile projects, and the development checks. Report: `notes/PHASE1B-REPORT.md`.
Linux halves (the `.so`, cgroups, the unprivileged user, x86_64 replays) wait for a Linux machine.

Phase 1c: the starter project (WS5), the reference game's contract layer (WS6 module 1, kept in a
private repository), the first 13 playtests (WS4) and `qa run`. The starter (`environment/game`) has
the engine settings, the 28 actions, a DevConsole stub, an empty scene and 177 vendor `.import`
files with every option explicit, the bodies, hair and clips retargeted through the shipped bone map
(panel decision, unanimous). The reference holds all 13 playtests and grades 1.000000 through the
real grader; the starter fails every playtest cleanly and grades 0. Report: `notes/PHASE1C-REPORT.md`.

Phase 1d: the reference's world builder (WS6 module 2, private), the full Downtown plan (WS2) and
the first people playtests (WS4). The builder makes the static world from the plan (roads split at
crosswalks, junction boxes, kerbed blocks with sidewalks, parcels, solid buildings with their
interiors cut out, signals running their programs), every collider tagged with its surface.
`world.plan_compliance/downtown` checks it with 10,866 rays. Downtown is now about 0.86 x 0.87 km
(7 x 7 blocks, 160 parcels, 260 lanes) with both highway portals; `check_plan.py` reports 0
problems and catches all 17 mutations of its set. Five people playtests: paces, camera and the
leads' lineup hold on the reference; feet and crouch wait for module 3. Report:
`notes/PHASE1D-REPORT.md`.

Phase 1e: the reference's people module, first part (WS6 module 3, private), three new playtests,
the telemetry reading bones after skeleton modifiers, and the private alternative Downtown (WD-8).
Every person plays the shipped clips time-scaled to its speed, with planted toes held still by leg
IK; the player crouches, jumps, climbs ledges up to 2.45 m with its hands on the edge, vaults
obstacles up to 1.05 m while running, is hurt by falls, and its camera stays out of walls. The feet
and crouch playtests now hold and join the reference's required set, as do
`people.jump_climb_vault/plaza`, `people.fall_ragdoll/falls` and
`traffic.intersection_watch/signals`. `scripts/gen_plan.py --layout random` draws other Downtowns;
the private one shares no node, edge or parcel with the shipped plan and keeps its 27 points of
interest, and the reference builds it with every compliance ray as planned. Report:
`notes/PHASE1E-REPORT.md`.

Phase 1f: the reference's vehicles (WS6 module 4) and the rest of its people module (getting in
and out, the ragdoll), four new playtests, the telemetry's seat read, and hidden instances for the
people and signal playtests. Every one of the 11 models sits in the middle of its handling bands
(0-60 km/h, dry braking, the wet ratio, the turning circle, the handbrake; top speed at a rev limit
reached within about 1.2 km); impacts damage vehicles, parts come off, damaged engines fail, burning
vehicles explode. A three-judge panel chose how QA sees a person go limp: the `limp` metadata (A,
by majority), with the physical clauses checked on the bones while it is true. The reference holds
all 26 playtests; the private set has 31 instances, none repeating its playtest. Report:
`notes/PHASE1F-REPORT.md`.

Phase 1g: the reference's traffic and people on foot (WS6 module 5, private), six new playtests,
the telemetry's collision-shape read, and hidden instances for the vehicle, entry and crash
playtests. NPC drivers drive the module 4 vehicles through their own controls along the plan's
lanes and junction movements: they keep to the limit, stop on red and at amber when it takes
4 m/s^2 or less, take turns at all-way stops by arrival, wait for people on crosswalks and hold
behind anything in their path; out of the one-lane streets' tight corners a right turn swings over
the centre line, so the turn and the cars beside it make room for each other. People on foot walk
the sidewalk rings, cross only on crosswalk bands and step out of the way of the horn and of a
vehicle on the sidewalk. The city keeps chapter 7's densities of moving vehicles and people on
foot around the player and adds or removes them only out of sight. A three-judge panel settled
how QA observes traffic: people's `vehicle` and `seat` metadata, setup commands placing the
population at once, collisions as collision shapes touching, arrivals within 1.0 s together,
`vehicle.spawn` with a driving archetype driving in traffic, and the gunshot reaction waiting for
combat. The reference holds all 32 playtests and grades 1.000000 on them and on the private set
(39 instances, none repeating its playtest), the starter 0; a replay with a car and a ragdoll gives
one hash over ten runs. Report: `notes/PHASE1G-REPORT.md`.

Next: combat (WS6 module 6), with the gunshot reaction it opens; then police and missions.

The art (Kenney and Quaternius CC0 packs) and the Godot binary are not committed; `.gitignore` and
`spike/.gitignore` list them. The reference game and the hidden material live outside this public
repository (`notes/PHASE1-PLAN.md`, section 4).

## Development log

### 2026-11-26

Phase 1g: traffic and people on foot (WS6 module 5), the collision-shape read, the traffic and
replay playtests, and the vehicle hidden instances, on macOS. There were no downloads, no Docker,
no Linux VM and no platform runs. Every Godot run went through `scripts/heavy.py`; free memory sat
at 26-46% and runs waited below 30%.
- **Traffic (WS6 module 5, private).** A road graph from the plan (lanes, junction movements by
  FORMAT.md's turn rules and which of them cross, crosswalk bands); NPC drivers steering the module
  4 vehicles by pure pursuit and the intelligent driver model, obeying signals, amber and all-way
  stops, yielding to crosswalks and holding behind anything in their path; people on foot on the
  sidewalk rings, crossing on bands at walk or with no vehicle coming, stepping aside for the horn
  and for a vehicle on the sidewalk; chapter 7's densities kept around the player, new arrivals
  only out of sight.
- **What the playtests found in the reference, all fixed:** jams where movements crossed within a
  car's width (now 2.8 m, 4.2 m when one turns); the car kit's wide toy bodies colliding at right
  turns (collision boxes now at most 2.0 m wide); right turns out of the one-lane streets' square
  corners swinging up to 1.5 m into the street they turn into, into cars waiting there (now each
  turn waits for its own vehicle's swing to be clear, those cars stay back while one may come, and
  turns straighten out at 2.5 m/s); people starting across as a car began to move up (they step
  back now); and too few moving vehicles while many stood at the plan's long signal cycles (now
  kept by the moving count chapter 7 uses, each new one to the side round the player with the
  fewest on their way in); and at start-up every variation drew the same traffic, and the
  population settled a tick differently from `world.reset`'s (both fixed).
- **Telemetry (WS3).** The census can carry each listed kind's collision shapes as world-space
  boxes; a Godot check compares 80 points with exact positions (worst 4.6e-6 m). Census selectors
  for bone and seat reads, and values a playtest gives once (`shared`).
- **Kit and playtests (WS4).** `qakit/streets.py`: 18 street checks (drivers, density, red-light
  entries, green flow, lane keeping, speeds, crosswalk use and hits, collisions, stopping short,
  the horn, the sidewalk dodge, pop-in, the all-way stop's full stops, order, box and waits), each
  over hand-made frames from a good street and a broken one. Six playtests:
  `traffic.intersection_watch/day-flow`, `traffic.stop_junction/four-way`,
  `traffic.obstacle/lane-blocked`, `traffic.speed/arterials`,
  `traffic.panic_horn/sidewalk-and-horn` and `world.replay/car-and-ragdoll`. Two faults of the
  new all-way stop checks, found on the way, are fixed: each pass through the junction now counts
  on its own, and a car already moving off its line when the watch begins is left out.
- **Hidden instances (WS8).** Private templates for the vehicle handling, getting-in and crash
  playtests (39 instances in all); `scripts/check_disjoint.py` gains rules for models, speeds,
  stand-offs and damage.
- **Panel and clarifications.** A three-judge panel (opus, sonnet, haiku) settled six questions
  on how QA observes traffic; chapter 7's introduction, TR-6 to TR-16, FT-10, AC-5, AC-6 and
  chapter 17's `vehicle.spawn` and behaviours now say what the checks measure. An independent read
  found no evaluation wording; its fairness findings are fixed.
- **Not done:** a 1.5 km straight in Downtown (the layout has none without moving its portals).

Phase 1f: vehicles (WS6 module 4), getting in and out, the ragdoll's limp flag, and hidden
instances, on macOS. There were no downloads, no Docker, no Linux VM and no platform runs. Every
Godot run went through `scripts/heavy.py`; free memory sat at 26-39% and runs waited below 30%.
- **Vehicles (WS6 module 4, private).** Raycast vehicles on `RigidBody3D` for all 11 models: car
  kit models at 1.72 times their size, all-wheel drive under force, power and rev limits, brakes
  at the grip limit (rain's 0.78 grip lengthens stops 1.28 times), the handbrake on the rear
  wheels, the motorbike leaning into turns. A small Python model sized each model for the middle
  of its bands; measured 0-60 times match it to 0.01 s. Damage from impacts, parts as debris
  bodies, engines failing at 0.75, burning and exploding at 0.80, people run into at 20 km/h or
  more going limp.
- **Getting in and out (FT-10).** The nearest door's seat, a 1.4 m/s walk and a 1.4 s slide in;
  seated, the person rides as the vehicle's child with the hips on the seat point and the driver's
  hands on the wheel point; a 2.0 s slide out to the door.
- **The ragdoll (FT-9).** A panel (opus A, haiku A, sonnet A plus a cross-check) chose a documented
  flag: people carry `limp` and the state report `player.limp`; QA checks the rule's physical
  clauses on the bones while it is true. The reference's ragdoll is position-based physics on 17
  joints with a rigid torso fitted every tick; free fall measures 9.81 m/s^2.
- **Telemetry (WS3).** A seat read in the style of the bone reads (each vehicle's seat, door and
  wheel points in world space, every tick), a `body` query (class, mass, layers) and a census of
  some kinds; a Godot check compares 252 points with exact positions (worst 2.35e-6 m).
- **Kit and playtests (WS4).** `wait_for` an entity's speed or height, and `cruise` (QA's bot
  holding a speed). Twenty checks, each over hand-made frames from a good game and a broken
  one. `vehicle.handling/cars`, `vehicle.handling/service`, `people.vehicle_entry/sedan`,
  `vehicle.crash/barrier`; the falls playtest checks the ragdoll, getting up and free fall.
- **Hidden instances (WS8).** Private templates for the eight people and signal playtests, 31
  instances in all, and `scripts/check_disjoint.py`: no instance repeats its playtest. The new
  instances found a real defect: the reference measured falls from where its capsule had slid
  over the edge.
- **Clarifications.** FT-9 and FT-10 (what limp and seated mean and when they end), AC-5, AC-6,
  AC-12, chapter 6 (where handling is measured; the turning circle at the vehicle's position),
  IN-2, VH-3 (dv across the 0.2 s), VH-6 (the push), `player.give` (health 0 kills). An
  independent read found no evaluation wording; its fairness findings are fixed.


Phase 1e: people (WS6 module 3, first part), the signals playtest and the alternative Downtown, on
macOS. There were no downloads, no Docker, no Linux VM and no platform runs. Every Godot run went
through `scripts/heavy.py`; free memory sat at 27-47% and runs waited below 30%.
- **People (WS6 module 3, private).** Every person plays the shipped clips on an AnimationPlayer
  stepped in physics ticks, the clip chosen by gait and time-scaled by its speed over the clip's
  toe speed (measured on both library bodies). After the animation, a pose node holds a planted
  toe still with two-bone leg IK, keeps toes above the ground and puts the hands on a ledge while
  climbing. The player crouches, jumps, climbs ledges up to 2.45 m, vaults obstacles up to 1.05 m
  while running, takes fall damage, and its camera pulls in front of walls and, looking up, keeps
  above the ground. The shipped sprint clip's left toe dips mid-stance, so no time scale alone
  holds FT-2 at a sprint as QA measures it (the kit's own check, simulated over 26 scales and 12
  phases: at best 4 of 12); holding the planted toe brings the slide to 0.
- **Telemetry (WS3).** It read bones with `get_bone_global_pose` at the start of a tick, after the
  engine had put back the pose a `SkeletonModifier3D` (the engine's IK, look-at or ragdoll) set: a
  game using TwoBoneIK3D for climbing hands would have been measured on the wrong pose. It now keeps
  each skeleton's bones at `skeleton_updated` and reads those; a Godot check proves it (2.6e-7 m;
  the old library misses by 0.25-1.10 m).
- **Playtests (WS4).** `people.jump_climb_vault/plaza` (FT-3, FT-4, FT-5, CM-4),
  `people.fall_ragdoll/falls` (FT-8) and `traffic.intersection_watch/signals` (TR-4, AC-7), with
  the checks `jump`, `climb`, `vault`, `camera_clear`, `fall_damage`, `signal_entities`,
  `signal_program`, `signal_greens` and `signal_walks`, and `wait_for` with `near` (to press jump
  at a set distance). The feet and crouch playtests join the required set.
- **WD-8.** `scripts/gen_plan.py --layout random` draws other Downtowns (the default output is
  unchanged). The private one (9 x 8 lines, 74 nodes, 129 edges, 308 lanes, 33 signalised
  junctions, 180 parcels) shares no node, edge, block or parcel with the shipped plan and keeps its
  27 points of interest; `check_plan.py` reports 0 problems. A manifest entry can name its own plan
  folder, and the plan-swap instance (12,503 rays) holds on the reference.
- **Results.** The reference holds all 22 playtests and grades 1.000000 with them as instances
  and 1.000000 on the private set (15 instances); the starter fails every playtest cleanly and
  grades 0.000000; ten replays give one hash; each game process peaks at about 134 MB.
- **Clarifications.** FT-3 (off the ground), FT-4 (on top; the edge on the player's side), FT-5
  (jump pressed 1.0-1.5 m before; over: past the far side), FT-8 (a fall from the ground left to the
  ground landed on), CM-1 (nearer where a wall pulls the camera in), `prop.spawn`'s box, and the
  plan program's start tick. An independent read found no evaluation wording; its other findings
  (the falls mark, tolerances at phase changes, notes without numbers) are fixed.

Phase 1d: the world builder on Downtown, the full Downtown plan and the first people playtests, on
macOS. There were no downloads, no Docker, no Linux VM and no platform runs. Every Godot run went
through `scripts/heavy.py`; free memory stayed at 34-47%.
- **World builder (WS6 module 2, private).** The reference builds the static world from the plan
  when a map loads:
  - roads along each centreline, split at the crosswalk bands (tagged `crosswalk`);
  - junction boxes;
  - blocks raised to their elevation, with a sidewalk band and its kerb;
  - parcels as open ground (plaza, park, parking) or a forecourt round a solid building;
  - interiors cut out of their buildings (room floors tagged `interior`, doorways, openings);
  - painted lane markings;
  - signal entities running their plan programs every tick, traffic lights and stop signs.

  Each surface is one trimesh collider on layer 1 with its `surface` tag.
- **Plan compliance (WS4).** `world.plan_compliance/downtown` casts 10,866 rays in one query step:
  - lanes, sidewalk rings and crosswalk bands (WD-1, WD-2);
  - roofs over every footprint and the sidewalk beside every parcel, and the open parcels (WD-3);
  - doors, room floors, empty rooms and the opening between connected rooms (WD-4);
  - points of interest (WD-5);
  - every hit's surface tag (AC-8).

  New kit checks back it: `rays`, `clear_run`, `surface_tags`, `none_listed` and `skeleton`. The
  module 1 placeholder and three builder mutants (interiors left solid, crosswalks tagged `road`,
  roofs a metre low) each fail the expectations aimed at them.
- **Full Downtown (WS2).** About 0.86 x 0.87 km: 7 x 7 blocks, 160 parcels, 260 lanes, 15
  signalised and 45 all-way-stop junctions. The highways leave through portals to Ashby Port (east)
  and to Sable Hills (north, through an S-curve). The core keeps its parcels and points of interest.
  `check_plan.py` now follows curves and checks portals, bounds and the GDD's point-of-interest ids.
  It reports 0 problems, and `checks/test_plan_check.py` holds its mutation set: 17 mutations, all
  caught.
- **People playtests (WS4).**
  - **Paces** (FT-1, IN-2) and **camera** (CM-1 to CM-3) hold on the reference.
  - **The leads' lineup** (CA-1, CA-2, AC-5, AC-11) holds too.
  - **Feet** (FT-2) and **crouch** (FT-6) need module 3's animation and crouch, so they are out of
    the reference's required set until it lands.
  - New kit checks: `pace`, `feet`, `hips_ratio`, `camera_frame`, `look_rate`, `camera_tilt`,
    `moves_along_camera`, `look` and `looks_distinct`.
- **Results.**
  - Reference: 17 of the 19 playtests hold (the other two are feet and crouch). The real grader
    gives 1.000000 with the 17 as instances, and 1.000000 on the private set (14 of 14).
  - Starter: every playtest lists what did not hold, and it grades 0.000000.
  - Ten replays give one hash.
  - On the full map, imports take 2.8-3.6 s with a 64 MB cache, boots 0.22-0.55 s, and each game
    process peaks at about 130 MB.
- **Clarifications.** An independent read of every new developer-facing file found no evaluation
  wording. Its findings led to seven clarifications, none adding a feature:
  - which body point CM-1 frames, and on which window;
  - CM-2's pitch sign;
  - FT-2's planted toe and step;
  - FT-6's hip height measured above the ground;
  - the crosswalk height (WD-2);
  - where door and opening heights are measured (WD-4, FORMAT.md);
  - `player.spawn` with `lead`.

  It also made the checks fairer and their notes clearer. Three private templates that spawned
  inside the new world were repaired and the set redrawn.

Phase 1c: the starter, the contract module, the first playtests and `qa run`, on macOS; no
downloads, no Docker, no Linux VM, no platform runs. Every Godot run went through `scripts/heavy.py`
and the kit's memory gate; free memory sat at 26-29% for long stretches and runs waited.
- **Starter (WS5).** `environment/game`: chapter 16's settings, the 28 actions with keyboard or mouse
  and gamepad bindings, a DevConsole stub ("not implemented"), an empty main scene, a README, and
  the vendor library's 177 `.import` files written by `scripts/make_vendor_imports.py` (textures
  VRAM-compressed with mipmaps and "detect 3D" off; bodies, hair and the animation library
  retargeted through `humanoid_bone_map.tres`). The art stays out of Git
  (`scripts/stage_project.py` copies it from the packs on this machine). Imports: engine defaults
  7.87 s and 2.30 GB peak; explicit settings 3.25 s and 1.53 GB fresh, 1.26 s with the cache, no
  `.import` file changing on that pass.
- **Bone map.** A three-judge panel (opus, sonnet, haiku) voted unanimously to ship it wired into
  the imports; the GDD's AC-5 marker is settled. The reference's player has one `Skeleton3D` with
  the profile's names (Root, Hips, Spine, Chest, Head, ...) and no unregistered skeleton.
- **Reference contract layer (WS6 module 1).** GDScript in a private repository (bundle in
  harbor-lh): command line and roles, the DevConsole with every command and argument checks, the
  registry, the plan reader with every anchor, a placeholder static world, people from the variation
  on library bodies, vehicles on their library models with seats, the clock, weather, missions as
  states, hashed atomic saves, the state report, events with ticks and teleport events.
- **Playtests (WS4).** 13 in `common/kit/playtests`, written by `scripts/make_playtests.py` with
  every expected point resolved through the kit's plan reader: DevConsole bad input, every command,
  the state report's fields, the new game, the server role, same start per variation, replay at two
  paces, input in its tick, the clock rate, weather held, a kill after a save, a damaged slot, the
  real-time heartbeat. Each expectation cites its rule and says what it means; no weights.
- **`qa run` and `qa list`.** Prepare a copy, play the playtests, print per playtest "every
  expectation holds" or the expectations that did not hold with what was measured; never a total.
- **Results.** Reference: 13 of 13 playtests hold; the real grader with the playtests as instances
  gives 1.000000 (self-test 12.9 s; import 3.86 s, 64 MB; boot 0.2 s solo and server; 25.5 s in
  all), and with Phase 1b's private set 1.000000 (14 of 14). Starter: every playtest lists what
  did not hold, no run stopped on a kit error; graded 0.000000 (the boot gate: nothing playable
  within 60 s).
- **GDD clarifications the playtests rely on:** placement within 0.5 m, `--role=solo` starts a new
  game, the default plan folder, any whole variation, `time.set`'s "hh:mm", what `player.give` gives
  or sets, spawn answers carry the id, the damaged-slot answer. An independent read of everything
  new the developer sees found tampering-flavoured phrasing and three inconsistencies; all fixed.

Phase 1b, the grading kit core (WS3) on macOS; no downloads, no Docker, no Linux VM, no platform
runs. Every Godot run went through `scripts/heavy.py` (one heavy job at a time, at least 30% free
memory before every game process).
- **Telemetry native core** (`common/probe/native/`): C against the dumped interface, method binds
  by hash from the binary's `extension_api.json` (`scripts/gen_telemetry_binds.py`). The library
  reads and wipes the link settings before any script runs, registers its class (named after its
  random file name) only in processes the kit starts, and does the census, bones, input injection
  (an input injected at tick t acts in tick t), commands, events, queries and a real-time
  heartbeat. Signed messages with sequence numbers; exit 3 on a forged message. One exported
  symbol; its strings pass the wording check. Finding: in 4.7.2 an exposed extension class that a
  scene references crashes the editor during a headless import (bisected).
- **Kit** (`common/kit/qakit/`, agent-facing, 0 wording hits): process control (launcher with
  rlimits, capped output, a watchdog for lifetime-peak memory, wall time and disk, tree tracking
  with start stamps), sessions, preparation (one worker thread through `override.cfg`), traces
  (SHA-256 chain per `world.reset` segment), plays (`qa-play/1`), expectations, plan anchors.
- **Grader** (`tests/`): self-test on Tiny Town (`tests/selftest/`, ours) first, the static,
  import and boot gates, instances with fixed family denominators and the 15% retry rule, the
  grader's own deadline. `scripts/make_instances.py` draws instances from templates and a private
  draw; the private set lives in the Git-ignored `tests/private/` (backed up as a bundle in
  harbor-lh).
- **Results on macOS.** Item-2 checks in the spike game and the foreign project: bones within
  2.07e-7 m, input in its tick, 1/60 deltas, a 1 s hold advancing one tick, forged command exit 3,
  pace-independent traces. Self-test passed in 11.8 s; Tiny Town graded as a submission scored
  1.000000 in 18.7 s. The hostile set (failed and hung imports, an oversized cache, hung boots, a
  game without the contract, stalls, crashes, a removed or paused telemetry node, a memory hog, a
  corrupt save, a wall-clock game, giant logs, a process spawner, the grader's deadline) always
  produced a written reward and zeroed what each case breaks. Two holes found and fixed on the
  way: children started with `OS.create_process` escaped the process group, and processes shorter
  than one memory sample escaped the memory cap. Development checks: 82 without Godot, 3 with.
- **Still needs Linux:** the `.so`, the cgroup sandbox and unprivileged user, a real fork bomb,
  `/proc` readings, the verifier image paths, replays on x86_64.

Phase 1a, writing only (no downloads, no Docker, no Godot runs, no platform runs).
- **Plan format and the Downtown core.** `common/design/plan/FORMAT.md` (`city-plan/1`) covers
  roads, lanes, intersections and signal programs, blocks, parcels and interiors, water, terrain,
  districts, turfs, points of interest, spawning, map links and anchors. `scripts/gen_plan.py`
  writes `downtown.json`: a 4 x 4 junction core with uneven spacing, arterials, streets and a
  one-way street, 7 signalised and 5 all-way-stop junctions, 60 lanes, 33 parcels and 25 points
  of interest. `scripts/check_plan.py` reports 0 problems on it and caught all 9 deliberate
  mutations (dropped phase, point off the ground, reversed one-way, door off its wall, height out
  of range, stop line in the box, dead-end lanes, checkpoint gap, missing field).
- **GDD v1.** `common/design/GDD.md`: 17 chapters and 177 numbered rules written as a studio brief,
  with the numbers QA's playtests will read. The mechanic is called the police alert level, our own
  name for it. It folds in Phase 0's design changes. Paces come from
  the library's clips; the free swim clip moves at 2.2 m/s, so the swim band is 1.50-3.00 m/s. Each
  QA process runs one worker thread. Import settings are explicit. Input acts in the tick it
  arrives. Ids are never reused and float ids are accepted. Online play is ENet only, must survive
  a 3 s drop-out and must keep snapshots small. `scripts/check_agent_text.py` finds 0
  evaluation-sounding words in the design folder; 9 TODO(owner)/TODO(panel) markers remain open.
- **Phase 1 plan.** `notes/PHASE1-PLAN.md` covers:
  - the reward and families;
  - a catalog of 79 checks;
  - a coverage map with one row per GDD rule: 149 with a shipped playtest, 14 release-only, 7
    gates and 7 invariants;
  - ten workstreams;
  - the public and private layout;
  - Linux needs, downloads and the first platform probe;
  - a RAM-aware schedule;
  - 20 risks;
  - the one-sentence failure mode.

  `scripts/check_coverage.py` reports 0 problems and caught 7 deliberate mutations.
- **Independent review.** An independent agent read the GDD and the format in full. Its findings,
  all fixed, were evaluation-sounding phrases, wording no observer could measure, contradictions
  between rules, and GTA's own term for the alert mechanic. Among the contradictions:
  - a 400 m search zone that made the bank heist's escape impossible inside Downtown;
  - interiors the scope excluded;
  - a miscounted action list.

  `notes/PHASE1A-REPORT.md` lists them all.
- **Not done yet:** the rest of Downtown, Ashby Port, Sable Hills, `links.json`, the private
  alternative plan, the kit, the starter and the reference game.

### 2026-11-25

Moved the Phase 0 spike to `tasks/static/game_dev/crime-city-sandbox/` with its measurement scripts and results.
