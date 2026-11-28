# Phase 1e report: people (WS6 module 3, first part), the signals playtest and the alternative Downtown (2026-11-26)

Author notes, never packaged. Brief: `harbor-lh/ops/swe-marathon-v2/next-tasks/game-phase1e-BRIEF.md`.
Branch `neel/game-phase1` (worktree `swe-m2-pr-game-phase1`). macOS only (Apple M5 Pro, 24 GB,
shared). No downloads, no Docker, no Linux VM, no Oddish. Godot 4.7.2 for macOS and the CC0 packs
came from `game-spike/vendor/`, already on this machine.

Every Godot run went through `scripts/heavy.py` (one exclusive lock, then at least 30% free memory
per `memory_pressure`), and every game process re-checked through the kit's gate
(`QA_MEM_FLOOR=30`). Free memory sat at 27-47%; runs waited whenever it dipped under 30%. Two
helpers worked in parallel on files of their own and queued their Godot runs through the same
lock: one fixed the telemetry defect below, the other built the alternative Downtown. A third read
the new developer-facing material as the developer would.

## What was built

| Piece | Where (task folder unless noted) | What it is |
| --- | --- | --- |
| People, first part (WS6 module 3) | private: `crime-city-reference/overlay/game/motion.gd`, `pose.gd`, `person.gd`, `world.gd` | Animation from the shipped clips with planted feet, crouch, jump, climbing, vaulting, fall damage, the camera kept out of walls (below) |
| Bones as shown (WS3) | `common/probe/native/telemetry.c`, `checks/test_godot_bones.py`, `checks/fixtures/bone_modifiers/` | The telemetry node reads bones after the game's skeleton modifiers (below) |
| Jump, climb, vault, camera (WS4) | `common/kit/playtests/people.jump_climb_vault.plaza.json` | FT-3, FT-4, FT-5, CM-4 on the plaza with props |
| Falls (WS4) | `common/kit/playtests/people.fall_ragdoll.falls.json` | FT-8: towers 2.4, 6, 10 and 16 m |
| Signals (WS4) | `common/kit/playtests/traffic.intersection_watch.signals.json` | TR-4 and AC-7 on all 15 signalised junctions for 77 s |
| Kit checks | `common/kit/qakit/expect.py`, `common/kit/README.md` | `jump`, `climb`, `vault`, `camera_clear`, `fall_damage`, `signal_entities`, `signal_program`, `signal_greens`, `signal_walks` |
| Kit step | `common/kit/qakit/play.py` | `wait_for` with `near`: advance tick by tick until an entity stands within a distance of a point, so an action is pressed at a set spot |
| Randomised layout (WS2) | `scripts/gen_plan.py --layout random --draw N` | Other Downtowns with the same 27 points of interest; the default output is byte-identical |
| Per-instance plans (WS3) | `tests/verifier/grade.py` | A manifest entry may name `"plans"`; its game processes get a fresh copy of that folder as `--plan-dir` |
| Plan swap (WS8) | `scripts/make_plan_swap.py`; private: `tests/private/plans/`, `plan_draw.json`, `plays/world.plan_swap.downtown-be26369a.json` | The alternative Downtown and its compliance instance (WD-8) |
| Acceptance tool | `scripts/phase1e_acceptance.py` | `qa`, `grade`, `replay10` and `leads` (feet with each lead) |
| Development checks | `checks/test_jump_climb_signals.py`, `checks/test_plan_swap.py`, `checks/test_godot_bones.py` | Each new check against a well-behaved and a broken game; the plan swap tooling; bones read after modifiers (Godot) |

### People (private)

- **Animation.** Every person (player and city people) has an AnimationPlayer with the shipped
  library (`UAL1_Standard` through the bone map), stepped in physics ticks. The clip follows the
  state and speed: idle, walk (`Walk`), run (`Jog_Fwd`), sprint (`Sprint`), crouched idle and walk,
  in the air (`Jump`), driving and sitting. Each moving clip is time-scaled by speed over the clip's
  toe speed while the toe is down, times the person's scale. Those speeds were measured on both
  library bodies at 240 samples per second: the mean over the time the toe is down (coming down to
  0.07 m, rising past 0.08 m), on the slower foot, less 3%. With that margin the clip's foot never
  falls behind the body, so a planted leg bends rather than overreaches.
- **Planted feet.** A pose node runs after the animation every tick (physics priority 10). It does
  three things:
  - when a toe's animation comes down to 0.07 m it is planted: held at 0.03 m above the ground
    where it came down, the leg solved with two-bone IK and the foot keeping its animated angle;
  - when the animation lifts past 0.08 m (or strays 0.35 m) the toe rises at once and slides back
    under the animation over three ticks;
  - it keeps every toe above the ground the person stands on, because blends between clips can dip
    one.

  Poses are written straight to the bones (not by a skeleton modifier).
- **Crouch** toggles (FT-6): the capsule goes from 1.7 to 1.15 m, standing up needs headroom, and
  the crouched walk is 0.80 m/s.
- **Jump** (FT-3): 3.4 m/s up.
- **Climbing** (FT-4): `jump` with a wall or ledge 0.3-2.45 m high within 0.9 m ahead. The player
  reaches (0.2 s, hands to the edge with two-bone IK, elbows out), rises at 1.6 m/s 0.40 m out from
  the face, then mantles on top crouched (0.35 s).
- **Vaulting** (FT-5): running at 3 m/s or more, `jump` with an obstacle up to 1.05 m high and
  1.2 m deep within 1.6 m ahead. The player rises crouched before the near face, crosses 0.10 m
  above the top and comes down 0.6 m past the far side.
- **Falls** (FT-8): a fall of 3 m or more, measured from the ground left to the ground landed on,
  costs `round(100 * (h - 3) / 12)` health (all of it from 15 m), with `damaged` and `died`
  events. A dead player has no control.
- **Camera** (CM-1, CM-2, CM-4):
  - it turns around a point at chest height (1.5 m; 1.0 m crouched);
  - looking up, its arm shortens (to 2.6 m at most) so it stays 0.05 m above the player's ground;
  - a ray from the Head bone to where it would be (world and props) pulls it in 0.3 m in front of
    anything in between.

### The telemetry defect, and the fix

The telemetry node read bones with `Skeleton3D.get_bone_global_pose()` at the start of a tick. In
Godot 4.3 and later, a `SkeletonModifier3D` poses the bones only inside the skeleton's update. The
engine runs the modifiers, emits `skeleton_updated`, updates the skins, and then puts the
unmodified pose back. The modifiers this covers are the engine's TwoBoneIK3D, FABRIK3D,
LookAtModifier3D and PhysicalBoneSimulator3D ragdolls, and a script's
`_process_modification_with_delta`.

An experiment on 4.7.2 showed the gap. A modifier moved LeftHand to (0.391, 1.456, -0.526) inside
`skeleton_updated`, but the next tick's read still gave the rest position. A game that places
climbing hands with the engine's own IK, or ragdolls with physical bones, would have been measured
on the animation pose. That would have been unfair for FT-4, FT-9, FT-10, FT-11 and FT-12.

The node now follows each skeleton it reads:
- at every `skeleton_updated` it keeps each bone's skeleton-space origin;
- a read uses those when the skeleton updated during the last tick, and otherwise reads directly
  as before;
- it follows up to 80 skeletons, by instance id, replacing the least recently read first;
- a mutex guards the kept poses;
- the wire format is unchanged.

`checks/test_godot_bones.py` runs a project whose player and NPC carry script modifiers in IDLE and
PHYSICS modes. The bones the modifiers move read where the modifiers left them (worst 2.6e-7 m), and
the bones they do not move read as before. The previous library misses by 0.25-1.10 m. Phase 1b's
three Godot checks still pass. The reference does not depend on the fix, since it writes its poses
to the bones.

### The alternative Downtown (private)

`gen_plan.py --layout random` draws every one of these:
- the grid (7-9 lines each way, none within 6 m of a shipped line);
- road classes, with one or two arterials and up to two one-way streets each way;
- lane widths, speed limits and signal timings;
- the highways' lengths and S-curve, ending at the same portal nodes and links;
- sidewalks, parcel splits, zonings, heights and setbacks;
- a core that holds the plaza, the turf, the givers and the twelve parcel points of interest;
- R1's lap direction and start.

A drawn plan must pass `check_plan.py`, with the GDD cross-check, before it is written. A sweep of
400 public draws gave 0 problems and the same ids.

| | Shipped | Alternative (private) |
| --- | --- | --- |
| Grid, bounds | 8 x 8, 860 x 869 m | 9 x 8, 893 x 954 m |
| Nodes, edges, lanes | 66, 114, 260 | 74, 129, 308 |
| Junctions | 15 signalised, 45 all-way stops | 33 signalised, 35 all-way stops |
| Blocks, parcels | 49, 160 | 56, 180 |
| Shared with the shipped plan | | 27 point-of-interest ids and kinds, portal nodes and links; no node, edge, block, sidewalk, parcel or signal program |

The draw is only in `tests/private/plan_draw.json`. The plan-swap instance is family H, with
`"plans": "plans"`, which makes the private set 15 instances.

## Decisions

1. **Planted feet need IK with these clips.** The kit's own `feet` check was simulated over the
   dumped clips at 26 time scales and 12 phases, sampled every 2 ticks as the playtest does.
   - Walk and run each pass at some scales.
   - The sprint passes at best 4 of 12 phases. Its left toe dips to 0.014 m mid-stance between
     samples at 0.04-0.066 m, so stances break up and the alternation falls to 0.60-0.89.
   - Phase 0's earlier measure (0.50 m/s) used every tick.

   The reference therefore holds planted toes with leg IK; the slide is 0 at every gait. Hips
   stride and cadence follow the time scale. FT-2 is unchanged: holding a toe is how games meet it.
2. **Bones are measured as shown** (above). This is a fairness fix in QA's tooling, not a new rule.
3. **Clarifications, so each playtest relies only on what the documents state.** None adds a
   feature, and the 177 rules and the coverage map (0 problems) are unchanged.
   - **FT-3:** airborne means off the ground, its position more than 0.02 m above it.
   - **FT-4:** on top means the position over the top, within 0.10 m of its height; the edge is the
     one on the player's side.
   - **FT-5:** `jump` is pressed 1.0-1.5 m before the obstacle (from the position to its near side),
     and "over it" means past its far side. QA has to press at a defined distance: a game that
     accelerates differently would otherwise be at another distance at a fixed tick, hence
     `wait_for` `near`.
   - **FT-8:** the fall is measured from the ground left to the ground landed on. The independent
     read found the earlier "drop of the hips" could read a person still getting up after a
     ragdoll (FT-9 allows 6 s) as a longer fall. QA reads health 12 s after the walk starts.
   - **CM-1:** the camera may be nearer than 2.5 m only where a wall pulls it in (CM-4).
   - **`prop.spawn`:** the object stands on `at` (the middle of its base); `size` is width, height
     and depth, the depth along `heading`.
   - **FORMAT.md:** a signal program's ticks count from the tick a `world.reset` command runs in.
     AC-3 lets a reset take up to 3 s, which would otherwise leave the start of program time open.
4. **The camera playtest found a real conflict in the first camera.** Pulling the camera in front
   of the ground at +30 degrees of pitch put it 2.7 m from the head and the hips 0.47 of the way to
   the view's edge.
   - The reference now turns the camera around chest height (1.5 m).
   - Looking up, it shortens the arm instead: head 2.91-4.03 m, hips at most 0.341 of the way out.
   - CM-1, CM-2 and CM-4 all hold together. A developer can meet them the same way, and the GDD
     says so through CM-1's new note.
5. **What `world.plan_swap` checks now.** The compliance rays on the other plan: rebuilt, WD-1 to
   WD-5. WD-8's "missions hold on it" waits for the missions module.
6. **No panel this phase.** The GDD's two panel markers (PF-6's tick limits, AC-17's exact replay)
   did not come up. One open question surfaced, and it is not marked for the panel, so it goes to
   the next phase (below): how QA tells that a person has gone limp (FT-9).

## Independent read

An independent solver's-eye read (sonnet) of every new or changed developer-facing file found no
evaluation wording. Its other findings, all fixed before the final acceptance runs:
- **FT-8's mark.** The playtest read a "drop of the hips" 4.5 s after the walk-off, inside FT-9's
  getting-up time, so a correct ragdoll could read as a longer fall. Fixed as decision 3 above.
- **Tolerance.** `signal_greens` and `signal_walks` allowed no tick at phase changes, while
  `signal_program` allowed one. Both now let off the tick on either side of a change.
- **`jump`.** It took a fixed ground height. It now takes the player's own height at the first mark
  unless the playtest gives one.
- **Notes without numbers.** The notes for climb, vault, camera, signals and falls now say how
  high, how far short, how near, at which junction and program tick, and the expected loss with
  its tolerance.
- **README rows.** The vault's hips must pass over the top; a signal may show its program's state
  one tick either side; no approach may be amber while its crosswalk shows walk; a fall's tolerance
  is a share of the expected loss.

Kept as it is:
- **FT-4's low end.** For a 1.0 m ledge, the "hips below the top" window is short, because standing
  hips are about 0.9 m up. It is still met (the reference reaches the edge before rising), and the
  playtest uses 1.2 and 2.2 m.

## Acceptance results (macOS)

### The reference and the starter

| Run | Result |
| --- | --- |
| Reference, every playtest (22) as the instance set | **1.000000**: self-test passed (12.0 s); static gate (22 own files); import 3.78 s with a 64.27 MB cache; boot 0.289 s solo, 0.281 s server; 22 of 22 instances at 1.0; 40.5 s in all |
| Starter, same set | **0.000000**: static (6 files) and import (4.0 s, 64.27 MB) gates pass; the boot gate fails ("solo not playable within 60 s", "server not playable within 60 s"); 124.5 s |
| Reference, the private set (15 instances, with the plan swap) | **1.000000**, 15 of 15 (import 3.76 s; boot 0.264 s solo, 0.257 s server; 19.6 s) |
| Ten replays of `world.replay/two-paces` in fresh processes | **1** distinct hash over 10 runs (78 frames each, 0 errors, 8.3 s): `1ad7f82f...` |
| `qa run`, all 22 playtests | Reference: **22 of 22 hold** (87.4 s with the import, 4.5 s). Starter: all 22 list what did not hold, 0 runs stopped (13.2 s) |
| Memory | Each game process peaks at 134.0-135.0 MB on Downtown (Phase 1d: 129-132 MB); 142.1 MB on the alternative plan |
| Wording | `check_agent_text.py` over `common/` and `environment/`: 0 hits (8 open markers, all from before); `qa list`: 0 hits; both `qa run` outputs: 0 hits once this Mac's scratch paths are swapped for the sandbox's |
| Development checks | **169 pass**, 4 Godot-only skipped (146 at the start of the phase); with Godot, the new bone check and Phase 1b's three pass (53.4 s) |

### Locomotion and the other people rules against their bands

| Rule | Band | Reference |
| --- | --- | --- |
| FT-1 walk, half strength | 0.80-1.50 m/s | 1.15, 1.15 |
| FT-1 run, strength 0.6 | 4.60-6.40 m/s | 5.50, 5.50 |
| FT-1 sprint | 7.40-9.60 m/s | 8.50 |
| FT-1 crouched | 0.50-1.10 m/s | 0.80 |
| FT-2 walk | steps alternate at least 90%, slide p95 at most 0.25 m/s | 8 steps, 1.00, 0.000 |
| FT-2 run | at most 0.40 m/s | 7 steps, 1.00, 0.000 |
| FT-2 sprint | at most 0.60 m/s | 10 steps, 1.00, 0.000 |
| FT-2, each lead (both bodies) | as above | all six leads hold at every gait: 8 / 6-7 / 10 steps, 1.00, 0.000 |
| FT-6 | hips at most 75% | 0.544 (0.483 of 0.889 m) |
| FT-3 | hips up 0.40-0.80 m, off the ground 0.50-0.90 s | 0.618 m, 0.700 s |
| FT-4, 1.2 m ledge | on top within 3.5 s; a hand within 0.35 m of the edge, hips below; no bone over 0.05 m in | 1.167 s; 0.022 m; 0.000 m |
| FT-4, 2.2 m ledge | as above | 1.783 s; 0.021 m; 0.000 m |
| FT-5, 0.8 m barrier, jump at 1.108 m | over within 1.2 s; hips 0.10 m clear; no bone over 0.05 m in | 0.300 s; 0.578 m; 0.000 m |
| CM-1 | 2.5-6.0 m from the head; hips within the middle 40% | 2.91-4.03 m; 0.341 |
| CM-2 | 120-240 degrees per second; pitch -60 to +30 | 180; -60.0 to 30.0 |
| CM-3 | within 15 degrees of the camera | 0.0 |
| CM-4 | head-to-camera segment clear in 99% of ticks | 241 of 241 clear; nearest 0.31 m from the head |
| FT-8 | 2.4 m: 0; 6 m: 25.0; 10 m: 58.3 (within 10%); 16 m: all | 0; 24; 58; 100 and `died` |

### Signals (TR-4, AC-7) and the alternative Downtown (WD-8)

| Check | Result |
| --- | --- |
| AC-7 signal entities | 114: 56 signalised approaches and 58 crosswalks with walk signals, each exactly once with a valid state |
| TR-4 program | 661 frames over 77 s (every 7 ticks, all 15 junctions): 0 signals off their program by more than a tick; 0 conflicting greens; 0 walks out of phase |
| `check_plan.py --gdd` | 0 problems on both plans; the GDD cross-check lists 9 Ashby Port and 15 Sable Hills points of interest still to come |
| Shipped plan's checks | the generator's default output is byte-identical; 17 of 17 mutations caught |
| Plan swap on the reference (`qa run --plans`) | every expectation holds: 12,503 rays, 12,101 hits all tagged, the vault opening 7.3 m clear; 142.1 MB |
| Plan swap through the grader | reference 1.000000 (import 3.18 s, boot 0.257 s solo, 0.253 s server, 17.0 s); starter 0.000000 (boot gate, 244 s) |
| Shipped compliance on the same reference | holds (10,866 rays, 136.3 MB) |

## The playtests and their status

| Playtest | Rules | Reference | Starter | In the reference's required set |
| --- | --- | --- | --- | --- |
| `people.locomotion/feet` | FT-2 | holds (slide 0 at every gait, every lead) | 3 do not hold | **yes** (was out until module 3) |
| `people.locomotion/crouch` | FT-6, FT-1 | holds (0.544; 0.80 m/s) | 2 do not hold | **yes** (was out) |
| `people.jump_climb_vault/plaza` (new) | FT-3, FT-4, FT-5, CM-4 | holds | 6 do not hold | yes |
| `people.fall_ragdoll/falls` (new) | FT-8 | holds | 5 do not hold | yes |
| `traffic.intersection_watch/signals` (new) | TR-4, AC-7 | holds | 4 do not hold | yes |
| the 17 playtests of Phases 1c and 1d | 43 rules | all hold | all report failures | yes |

The 22 playtests cite 50 rules: Phase 1d's 43 and 7 new (FT-3, FT-4, FT-5, FT-8, CM-4, TR-4 and
AC-7), and FT-2 and FT-6 are now held. Each new rule has at least one expectation citing it.

## What still needs Linux

Everything on Phase 1b's to 1d's lists still applies:
- the `.so`;
- the cgroup sandbox and the unprivileged user;
- a real fork bomb;
- `/proc` readings;
- the starter in the agent image;
- `qa run` with Python 3.12;
- the ENet server in a container;
- the verifier image's paths;
- the world builder and replays on x86_64;
- import and boot on a cloud vCPU.

This phase adds:
- **The telemetry's bone cache on Linux.** The C compiles clean with the Linux flags here, but the
  `.so` and its Godot check have not run on Linux.
- **Replays with animation and IK on x86_64.** Leg and arm IK and time-scaled clips now move bones
  every tick, so bone observations in traces depend on float behaviour. The census hash in
  `world.replay` does not include bones, but the feet, climb and vault playtests read them.
- **Calibration of the people bands.** The reference's margins should be measured on the verifier's
  CPU (WS9): FT-2's slide is 0 by construction, and CM-1's framing is 0.341 against 0.40.
- **The plan-swap instance in the verifier image.** The private `plans/` folder must sit next to the
  manifest. The grader copies it for the game user; packaging must keep instance work folders
  readable by that user.

## Not done in this phase

- **Module 3's rest:**
  - **FT-9, ragdoll and getting up.** The GDD gives QA no way to see that a person "goes limp": no
    metadata or state names it. A check could only infer it from bone motion. The next phase needs
    a decision (a person metadata such as `limp`, or a definition from bone motion) before the
    playtest and the reference's ragdoll.
  - **FT-10, getting in and out of vehicles.** The telemetry has no query for a vehicle's seat
    markers (`Marker3D` children with `door` and `wheel` metadata; they are not entities), so QA
    cannot read the seat and door points yet. It lands with module 4.
  - **FT-7, swimming.** Needs water, which arrives with Ashby Port.
  - **AC-11's look shader parameters.** The telemetry cannot read instance shader parameters yet.
  - **City people's behaviours** (AR-4: wander, stroll, jog, stand). City people play their
    animation but stand still. Their walking belongs with traffic and pedestrians (module 5) and will
    reuse this module's gaits and planted feet.
- **Hidden instances for the new templates (WS8).** These are feet and crouch with other leads and
  spots, ledges and barriers of drawn sizes, other towers, and other signalised watches. Only the
  plan swap was added.
- **`make_instances.py` and the plan swap.** It rewrites `instances.json` from the templates alone,
  so `make_plan_swap.py --manifest` must be re-run after it (noted in the private README).
- **`push_ops.sh` was not run.** The ops folder rides the ops draft PR, and the brief says not to
  touch PRs. The refreshed bundles are in `harbor-lh/ops/swe-marathon-v2/next-tasks/game-private/`.

## Next workstream

**WS6 module 4, vehicles, with getting in and out (FT-10).** The work is:
- driving and the handling bands (VH-1, VH-2);
- damage, parts, fire and explosions;
- the motorbike;
- the telemetry's seat query, so QA can read seats, doors and the wheel point;
- the people side of FT-10: walking to the door and the seated pose, with the hands on the wheel
  through this module's IK.

That opens `vehicle.handling`, `vehicle.crash` and `people.vehicle_entry`.

Alongside it:
- settle how QA sees a person go limp, then add the ragdoll and getting up (FT-9);
- draw the people and signal hidden instances (WS8).

For the Linux items above, ask the owner for an x86_64 Linux machine.

## Commits

| Commit | What |
| --- | --- |
| `b40c313` | WS4: jump, climbing, vaulting, the camera kept out of walls (playtest and checks), the signals playtest, `wait_for near`, the clarifications of FT-3, FT-4, FT-5, CM-1, `prop.spawn` and the program's start |
| `43af12c` | WS3: the telemetry node reads bones as the game shows them, after its skeleton modifiers |
| `9333af0` | WS4: the falls playtest (FT-8) and `fall_damage` |
| `2cf1644` | WS2/WS3: the generator's randomised layout, per-instance plan folders in the grader, the plan-swap tool |
| `0289e78` | WS4: the independent read's fixes (FT-8's fall, one tick at phase changes, notes with numbers, README rows) |
| `f4286b2` | the acceptance tool, the README and this report |
| (next) | this table's hashes |

Private, with both bundles refreshed in `harbor-lh/ops/swe-marathon-v2/next-tasks/game-private/`:
- `crime-city-reference` `8f48ecf`, `08db084`, `6d7e9db`, `05b1e36`: module 3's first part (people,
  falls, the camera);
- `tests/private` `073aaec`: the alternative Downtown, its draw and the plan-swap instance.
