# Phase 1g report: traffic and people on foot (WS6 module 5), hidden vehicle instances, a replay with a car and a ragdoll (2026-11-26)

Author notes, never packaged. Brief: `harbor-lh/ops/swe-marathon-v2/next-tasks/game-phase1g-BRIEF.md`.
Branch `neel/game-phase1` (worktree `swe-m2-pr-game-phase1`). macOS only (Apple M5 Pro, 24 GB,
shared). No downloads, no Docker, no Linux VM, no Oddish.

Every Godot run went through `scripts/heavy.py` (one exclusive lock, then at least 30% free memory
per `memory_pressure`), and every game process re-checked through the kit's gate
(`QA_MEM_FLOOR=30`). Free memory sat at 26-46% (other work on this Mac, a virtual machine among
it, held several GB); runs waited whenever it dipped under 30%, once for a quarter of an hour. Four
runs made obsolete by a fix (two traffic reruns and the first two acceptance attempts) were
stopped by killing their process groups (the lock holder, the runner and Godot); none was left
behind. A helper (opus) built the vehicle and entry hidden
instances on files of its own and queued its Godot runs through the same lock; three judges (opus,
sonnet, haiku) settled how QA observes traffic; an independent read (sonnet) read the
developer-facing changes as the developer would.

## What was built

| Piece | Where (task folder unless noted) | What it is |
| --- | --- | --- |
| Traffic and people on foot (WS6 module 5) | private: `crime-city-reference/overlay/game/roads.gd`, `traffic.gd`; `person.gd`, `pose.gd`, `signals.gd`, `tables.gd`, `vehicle.gd`, `world.gd` | The road graph, NPC drivers through the vehicles' own controls, signals and all-way stops, crosswalks, reactions, densities, spawning out of sight (below) |
| Collision-shape read, census selectors, `shared` values (WS3) | `common/probe/native/telemetry.c`, `common/kit/qakit/play.py`, `expect.py`, `checks/test_godot_shapes.py`, `checks/fixtures/shapes/` | A census can carry the listed kinds' own collision shapes as world-space boxes; bone and seat reads can name "the n entities of a kind nearest the player"; a play can give a value once and use it in many expectations |
| Street checks (WS4) | `common/kit/qakit/streets.py`, `common/kit/README.md`, `checks/test_streets.py` | 18 checks for chapter 7: `drivers`, `density`, `red_entries`, `green_flow`, `lane_keeping`, `lane_speeds`, `walkable`, `crosswalk_use`, `crosswalk_hits`, `vehicle_contacts`, `stop_short`, `horn_clear`, `sidewalk_dodge`, `no_pop_in`, `stop_full`, `stop_order`, `box_clear`, `stop_wait` |
| Playtests (WS4) | `common/kit/playtests/`, `scripts/make_playtests.py` | `traffic.intersection_watch/day-flow`, `traffic.stop_junction/four-way`, `traffic.obstacle/lane-blocked`, `traffic.speed/arterials`, `traffic.panic_horn/sidewalk-and-horn`, `world.replay/car-and-ragdoll` |
| Hidden instances (WS8) | private: `tests/private/templates/`, `tools/build_templates.py`; public: `scripts/check_disjoint.py`, `checks/test_disjoint.py` | Templates for `vehicle.handling/cars`, `vehicle.handling/service`, `people.vehicle_entry/sedan` and `vehicle.crash/barrier`; 8 new instances (39 in all); four new disjointness rules |
| Panel | `harbor-lh/ops/swe-marathon-v2/decisions/2026-11-26-game-traffic-observables-*.md` | Six questions on how QA observes traffic |
| Clarifications | `common/design/GDD.md`, `notes/PHASE1-PLAN.md` | Chapter 7's introduction, TR-6 to TR-16, FT-10, AC-5, AC-6, chapter 17's `vehicle.spawn` and behaviours; the coverage map |
| Acceptance tool | `scripts/phase1g_acceptance.py` | `qa`, `grade`, `private`, `replay10` (any replay playtest) |

### Traffic and people on foot (private)

- **The road graph** (`roads.gd`, built with the static world). Lanes are polylines of the plan's
  own lane points; each junction gets FORMAT.md's movements (right: rightmost to rightmost; left:
  lane 0 to lane 0; straight on lane by lane; a bend continues) as cubic Beziers from the stop line
  to the exit lane, with the movements each crosses or merges with: centre lines within 2.8 m, or
  4.2 m when one of the two turns, or the same exit lane. Crosswalk bands carry their kerb ends,
  where people wait and the sidewalk ring points they meet, and each lane's and movement's stretch
  inside each band, clipped exactly.
- **NPC drivers** drive the module 4 vehicles through the same controls the player uses (throttle,
  brake, steer): pure pursuit of the way ahead, the intelligent driver model towards 95% of the
  limit, slowed for curves (2 m/s^2 lateral), held behind anything in the path (vehicles, people,
  props, debris, each by its extent along and across the path). Red stops; amber stops when it
  takes 4 m/s^2 or less; entering a box needs no vehicle on a crossing movement in it, nobody on
  the crosswalks on the way and room on the exit lane. All-way stops: stop within 4 m, queue by
  arrival (the vehicle on the right first within 1.0 s), go when first and clear. `reckless`
  drives at 1.25 times the limit and ignores signals and stops.
- **Right turns out of tight corners.** Downtown's one-lane streets are 6.5 m wide with square
  kerbs, so the shortest arc from the stop line into the exit lane is about 1.6 m, while chapter
  6's cars turn on 5.3-6.9 m. Their bodies swing over the centre line of the street they turn
  into, by about 0.5 m (hatchback), 0.8 m (sedan) and 1.5 m (SUV), measured at j_45 over the first
  6-10 m. A turn now waits until no car stands where its own vehicle's swing reaches; at all-way
  stops the car standing there goes first while later cars whose ways cross the turn keep their
  places behind it, and turns waiting on each other all round (or 15 s for a car that stays put)
  go in order. A car stopping on the approach beside such a turn stays back out of its reach while
  one may come, if it can stop gently, then moves up and stops within 4 m. Through the turn and
  over the first 11 m after it, a car more than 8 degrees off its way keeps to 2.5 m/s.
- **People on foot** walk the sidewalk rings at their pace and cross only on crosswalk bands: at
  signals while walk shows and enough walk time is left, and everywhere only when no vehicle within
  22 m moves towards the band or has its line of travel entering it, and none in or just out of the
  box still crosses it; they step back if a vehicle starts towards the band while they are still
  stepping off the kerb. The horn moves people in the lane ahead out of it; a vehicle on a block at
  16 km/h or more moves people ahead in its path aside; `panic(origin)` is ready for combat's
  gunshots.
- **Density.** Chapter 7 counts moving vehicles, so the reference does too: a setup command places
  1.5 times the table's middle within 150 m; then new vehicles are added while fewer than the
  middle move (up to 2.2 times the middle in all, those on their way in from beyond 150 m
  counted), each to the quarter round the player with the fewest vehicles on their way in, on a
  lane leading inwards; the farthest unseen ones on their way out go first when over. New people
  and vehicles appear at least 95 m away and outside a frustum 20% wider than the camera's; the
  camera's side is fed from just beyond 212 m, in view. Every random choice comes from a
  generator seeded by the variation, and the start-up population is placed at the start of the
  first tick, as a `world.reset` command's is.
- **The panel's observables:** people carry `vehicle` and `seat` metadata; drivers are seated with
  `vehicle_entered`; `vehicle.spawn` with a driving archetype drives in traffic at once; setup
  commands place and remove the population at once; `vehicle.spawn` and `prop.spawn` clear the
  city's vehicles from their spot.
- **Smaller changes:** a vehicle's collision box is at most 2.0 m wide (the car kit's models are
  wide toys; doors and seats still follow the model); people beyond 45 m skip feet and hand IK;
  `load` refills the streets.

What the playtests found in the reference on the way (all fixed, each in the playtest that caught
it): jams where movements crossed within a car's width; wide toy bodies colliding at right turns;
the swing of right turns into cars waiting beside them (two contacts and a 4 minute deadlock at
j_45 in the day flow); people starting across as a held car began to move up; moving vehicles too
few while many stood at the plan's long signal cycles (one approach green at a time and a walk
phase, about 69 s at j_44); one approach of j_34 starved because nothing appeared on the
camera's side, then another when the camera's side was fed; every variation drawing the same
traffic (the generator's state was reset after seeding) and the start-up population settling a
tick differently from `world.reset`'s (`world.same_start`). Two faults of the new checks
themselves were fixed too: the all-way stop checks took a vehicle's first and last time in the
box as one stay (a car that went round the block was "in the box" for minutes), and `stop_full`
judged a car already moving off its line when the watch began. An attempt to give turns
circular arcs instead was dropped: tangent to both lanes, the arcs cut over the kerb corners
where people wait to cross, and cars and people then waited on each other.

### Hidden instances (WS8)

The helper's templates draw models in an order of their own, lanes, lots, locks, weathers,
speeds, stand-off sides and ends, damage levels, doors and seats, never the playtests' values;
`scripts/check_disjoint.py` gains rules 7-10 (models in order, driven speeds within 0.5 km/h, the
stand-offs, damage within 0.005), each with a must-fail and a must-pass case. Private set: 8 new
instances (2 handling cars, 2 handling service, 2 getting in, 2 crash), 39 in all (A 18, B 6,
C 2, H 5, K 4, M 2, T 2).

### The replay with a car and a ragdoll

`world.replay/car-and-ragdoll` (AC-17, FT-9) plays one input timeline twice, the second time with
a 4 ms pause between ticks, with traffic and people set to none: the player drives a sedan at
30 km/h into a person standing in the lane, who goes limp and is thrown. Both runs must give the
same trace hash, the car and the ragdoll's bones included. Ten fresh processes of it are part of
the acceptance runs below.

## The panel

Three judges (opus, sonnet, haiku), each given the same facts and options, voted independently
(record: `decisions/2026-11-26-game-traffic-observables-DECISION.md`, the brief and the three
votes):

| Question | opus | sonnet | haiku | Decision |
| --- | --- | --- | --- | --- |
| Q1 who sits in a vehicle | A | A | A | **A**: people carry `vehicle` and `seat` metadata |
| Q2 the gunshot part of TR-13 | A | A | A | **A**: waits for combat (module 6); the reference has the reaction ready |
| Q3 TR-15 and setup commands | C | A | A | **A**: in a setup command's tick the game may place or remove the population anywhere |
| Q4 NPC vehicles colliding (TR-12) | D | A | B | **their collision shapes start touching, at any speed** (B and D agree on it), counted as opus proposed |
| Q5 arriving together at all-way stops | B | D | B | **B, 1.0 s** (QA allows 0.8-1.2 s either way) |
| Q6 `vehicle.spawn` with an archetype driver | A | A | A | **A**: it drives in traffic at once |

## Clarifications (no new features: 177 rules, the coverage map 0 problems)

- **Chapter 7's introduction:** which vehicles and people are counted (no player aboard; on foot
  is `vehicle` null), the table is for `traffic.set` 1, counts start a minute after the last setup
  command; a vehicle's place is its position (crossing a line, being on a lane); its body is its
  collision shapes, each taken as the box it fills.
- **TR-6:** what arriving is, 1.0 s together, which pairs the order binds. **TR-7:** the heading
  clauses leave out each lane's first 10 m. **TR-8:** speeds over 0.1 s on the lane the vehicle is
  on. **TR-10:** "approaching" as a line of travel entering the band. **TR-11, TR-12:** a hit is
  within 0.3 m; a collision is bodies starting to touch, counted per pair. **TR-13:** the dodge
  does not hit them. **TR-14:** whatever the behaviour. **TR-15:** "in the camera's view" and the
  setup-command exemption. **TR-16:** the driving archetypes listed.
- **FT-10, AC-5, AC-6:** city people seated hold the pose; `vehicle` and `seat` metadata; seat 0
  is a car's front left seat (traffic drives on the right) and the motorbike's front seat.
- **Chapter 17:** `vehicle.spawn` with an archetype seats it with `wander`; seat 0 `wander` drives,
  `reckless` drives that way, `idle` holds the vehicle.

## Independent read

An independent read (sonnet) of the GDD diff, the README diff, the six playtests and the new
checks found **no evaluation wording**. Its fairness findings, all fixed before the acceptance
runs:
- `stop_order` enforced the right-hand rule in groups of three or four; it now applies only to
  groups of exactly two arriving together.
- The replay's "survives" and "thrown 2 m" expectations cited rules that do not say so; they were
  replaced by the car moving and the person going limp (FT-9).
- "A vehicle's body" was described two ways; the GDD and the README now both say each shape is
  taken as the box it fills.
- The sidewalk dodge watched 60 m ahead without saying so; its note now gives the numbers.
- The crosswalk check's "approaching" now matches TR-10's line of travel; `stop_short`'s 40 m bound
  is in its note and TR-12's text; the vehicle's origin is its middle (chapter 6); TR-16 lists the
  driving archetypes; the obstacle cars' "at least 20 m" cites AC-3; the horn's band is in its note;
  `vehicle.spawn` clears its spot of the city's vehicles; TR-15's settle allowance is stated.

The two later fixes to the all-way stop checks (`e5de73c`, `37195ac`) came after the read; the
wording check covers them, and each comes with a check over hand-made frames.

## Acceptance results (macOS)

All on the final reference (`crime-city-reference` `f9a89c7`, staged with
`scripts/stage_project.py`) and the starter, with the kit at `37195ac`.

| Run | Result |
| --- | --- |
| Reference, every playtest (32) as the instance set | **1.000000**: self-test passed (12.1 s); static gate (25 own files); import 3.0 s with a 64.27 MB cache; boot 0.574 s solo, 0.512 s server; 32 of 32 instances at 1.0, every family 1.0 (A, B, C, H, I, K, M, T); 424.3 s in all |
| Starter, same set | **0.000000**: static (6 files) and import (3.63 s, 64.27 MB) gates pass; the boot gate fails ("solo not playable within 60 s", "server not playable within 60 s"); 124.0 s |
| Reference, the private set (39 instances: the 8 new vehicle and entry instances among them) | **1.000000**: 39 of 39 at 1.0, every family 1.0 (A, B, C, H, K, M, T); import 4.28 s; boot 0.63 s solo, 0.55 s server; 1752.6 s in all, most of it waiting for memory |
| Starter, the private set | **0.000000**: static and import gates pass, the boot gate fails; 367.1 s |
| Ten replays of `world.replay/car-and-ragdoll` in fresh processes | **1** distinct hash over 10 runs (535 frames each, 0 errors, 18.9 s): `d615d2ee...`; in the playtest the paced run gives the same hash |
| Ten replays of `world.replay/two-paces`, now with the city's traffic and people about | **1** distinct hash over 10 runs (78 frames each, 0 errors, 27.9 s): `7d4a07a1...` |
| `qa run`, all 32 playtests | Reference: **32 of 32 hold**. Starter: all 32 list what did not hold, 0 runs stopped (81.2 s) |
| Memory | Each game process peaks at 87-169 MB (Phase 1f: 120.7-125.5 MB; the traffic playtests 145-160 MB) |
| Wording | `check_agent_text.py` over `common/` and `environment/`: 0 hits (8 open markers, all from before); both `qa run` outputs: 0 hits once this Mac's scratch paths are swapped for the sandbox's; the library's strings: 0 hits (556 strings) |
| Development checks | **260 pass**, 6 Godot-only skipped (215 at the start of the phase); with Godot, the new shape check passes (80 points in 10 frames, worst 4.6e-6 m) |
| Coverage | `check_coverage.py`: 177 rules, 177 rows, 0 problems; `make_playtests.py --check`: up to date |

### Traffic on the reference (measured by the playtests, final `qa run`)

| Check | Band | Reference |
| --- | --- | --- |
| TR-1 densities at j_34, 08:00, clear (three minutes) | 10-30 moving vehicles, 20-60 people on foot | vehicles 16.5, 10.0, 16.0; people 41, 40, 40 (minute medians) |
| TR-5 red entries | none after 0.5 s of red | 0 of 30 line crossings; none that could have stopped at amber |
| TR-5 green flow | at least 3 per approach in 3 minutes | 6, 9, 4 and 11 |
| TR-7 lane keeping | offset 1.0 m (p95); heading within 15 degrees on 98% | 0.31 m (cars waiting at lines keep 0.4 m right); 100%; none against |
| TR-8 speed | at most 1.1 times the limit | at most 0.95 times it (47,351 samples) |
| TR-9 walkable ground | 95% of samples | 100% (9,144 samples) |
| TR-10 crossings | on bands; not into an approaching vehicle | 8 crossings at j_34, all on bands; 8 at j_45, none with a vehicle coming |
| TR-11 hits on crosswalks | none within 0.3 m | none (515 samples on bands against 6,318 vehicle boxes) |
| TR-12 collisions; the obstacle | at most 0.02 per vehicle-minute; never touches | 0 over 66.4 moving vehicle-minutes; the three cars stood 2.21-2.27 m short of the barrier, the tourist and the parked van |
| TR-6 at j_45 with QA's waves | full stops, order, box, waits up to 30 s | 26 crossings all after a stop; 119 crossing pairs in order; 27 through the box, none together; longest wait 15.6 s |
| TR-13 sidewalk dodge; TR-14 horn | no touch; out of the lane within 3 s | both people ahead untouched; out after 0.38 s |
| TR-15 pop-in | none in view nearer than 200 m | 133 appeared, 135 left, none too near |
| TR-16 drivers | a seated driver of a driving archetype | every moving NPC vehicle (19,925 samples), hips 0.000 m from the seat |
| FT-9 in the replay | limp within 12 ticks of the hit | 1 tick; limp 2.87 s; no bone under the ground |

## The playtests and their status

| Playtest | Rules | Reference | Starter | In the reference's required set |
| --- | --- | --- | --- | --- |
| `traffic.intersection_watch/day-flow` (new) | TR-1, TR-5, TR-7, TR-9, TR-10, TR-11, TR-12, TR-15, TR-16 | holds (10 expectations) | does not hold | yes |
| `traffic.stop_junction/four-way` (new) | TR-6, TR-10, TR-16 | holds (6) | does not hold | yes |
| `traffic.obstacle/lane-blocked` (new) | TR-12, TR-16 (and chapter 17's `vehicle.spawn`) | holds (4) | does not hold | yes |
| `traffic.speed/arterials` (new) | TR-8 | holds (1) | does not hold | yes |
| `traffic.panic_horn/sidewalk-and-horn` (new) | TR-13, TR-14 | holds (3; the gunshot flee waits for combat) | does not hold | yes |
| `world.replay/car-and-ragdoll` (new) | AC-15, AC-17, FT-9 | holds (3) | does not hold | yes |
| the 26 playtests of Phases 1c to 1f | 62 rules | all hold, now with the city's traffic and people about | all report failures | yes |

The 32 playtests cite 75 rules: Phase 1f's 62 and 13 new (TR-1, TR-5 to TR-16). Each new rule has
at least one expectation citing it. TR-2 and TR-3 are kept by the reference but not yet checked.

## What still needs Linux

Everything on Phase 1b's to 1f's lists still applies:
- the `.so`, the cgroup sandbox and the unprivileged user, a real fork bomb, `/proc` readings;
- the starter in the agent image, `qa run` with Python 3.12, the ENet server in a container;
- the verifier image's paths, the world builder and replays on x86_64, import and boot on a cloud
  vCPU;
- the bone cache and the seat read in the `.so`, replays with animation, IK and vehicles on x86_64,
  the people and vehicle bands' calibration, the plan-swap instance in the verifier image.

This phase adds:
- **The shape read in the `.so`.** The C compiles clean with the Linux flags; there is no Linux
  sysroot here, so the `.so` was not linked or run. The Godot check of the read passes on macOS.
- **Traffic on x86_64.** The street checks rest on positions, the collision boxes and many
  vehicles' physics every tick: replays with traffic, ten runs of the car-and-ragdoll replay, and
  the day-flow and stop-junction playtests' bands (density, green flow, waits, collisions) need a
  run on the verifier's CPU.
- **Calibration of the traffic bands (WS9).** The reference's margins on this Mac: moving
  vehicles 10.0-16.5 against 10-30 (one minute sat on the band's edge: the reference aims at the
  table's middle, 20, but the plan's long signal cycles hold many at lights), green flow 4-11
  against 3 per approach, the all-way stop's longest wait 15.6 s against 30 s (other runs 14-26
  s). The density margin needs widening before it meets a slower CPU.
- **Grading time.** The day-flow and stop-junction playtests' game processes take 109 s and 87 s
  here, and `traffic.speed` 57 s: 62% of the 408 s all 32 playtests take (Phase 1f's 26 took
  42 s). Measure on a cloud vCPU before setting the verifier's timeout.

## Not done in this phase

- **A 1.5 km straight in Downtown.** The plan is 860 by 869 m: its longest straight is 820 m
  (z = 50), its diagonal 1.22 km, and the two highway portals sit on the edges a straight would
  need. Top speed keeps waiting for the highways and the Sable Hills drag strip (WS2).
- **TR-13's gunshot flee** waits for combat (the panel's Q2); the reference's `panic` is ready.
- **TR-2 (rain), TR-3 (steady density over time)** have no shipped expectation yet; the
  reference keeps them (people at 60% in rain; densities by the moving count).
- From earlier phases: top speed's check, VH-7 to VH-12, WD-9, WD-10, FT-7, AC-11's look
  parameters, `inv.damage_honest`.

## Next workstream

**WS6 module 6, combat**: weapons, aiming, damage and death on the people module's bodies, which
opens TR-13's gunshot flee (timed by the shot, `idle` people included) in
`traffic.panic_horn`, then police (module 7) and missions. Alongside it: the Linux items above on
an x86_64 machine (the owner's call), and hidden instances for the traffic playtests (other
junctions, hours and weathers).

## Commits

| Commit | What |
| --- | --- |
| `c8f2413` | WS3/WS4/WS8: the telemetry reads collision shapes; census selectors and `shared` values; the 18 street checks with their hand-made-frame checks and the shape read's Godot check; `check_disjoint.py` rules 7-10; the acceptance tool |
| `77fe670` | WS1/WS4: the six playtests, the GDD's clarifications (the panel), the coverage map |
| `e5de73c` | WS4: the all-way stop checks count each pass through the junction on its own |
| `37195ac` | WS4: `stop_full` leaves out a vehicle already at its line when the watch begins |
| (next) | this report and the README |

Private, with both bundles refreshed in `harbor-lh/ops/swe-marathon-v2/next-tasks/game-private/`
(and its README's table):
- `crime-city-reference` `5eab05a` (module 5, traffic and people on foot), `f9a89c7` (traffic
  seeded by the variation; the start-up population placed in the first tick);
- `tests/private` `c265d13` (the helper: vehicle and getting-in templates, 8 instances, 39 in all),
  `b4d3fa3` (the helper: their results on `2bc0c5f`), `28488b0` (the results on `f9a89c7`).

The panel's record (`decisions/2026-11-26-game-traffic-observables-*.md`) and the bundles are in
harbor-lh's ops folder, which this phase does not push (the ops folder has its own channel).
