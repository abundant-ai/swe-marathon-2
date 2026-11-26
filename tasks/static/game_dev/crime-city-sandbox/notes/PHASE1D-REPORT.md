# Phase 1d report: the world builder on Downtown, the full Downtown plan, the first people playtests (2026-11-26)

Author notes, never packaged. Brief: `harbor-lh/ops/swe-marathon-v2/next-tasks/game-phase1d-BRIEF.md`.
Branch `neel/game-phase1` (worktree `swe-m2-pr-game-phase1`). macOS only (Apple M5 Pro, 24 GB,
shared). No downloads, no Docker, no Linux VM, no Oddish. Godot 4.7.2 for macOS and the CC0 packs
came from `game-spike/vendor/`, already on this machine.

Every Godot run went through `scripts/heavy.py` (one exclusive lock for heavy jobs, then at least
30% free memory per `memory_pressure`), and every game process re-checked through the kit's gate
(`QA_MEM_FLOOR=30`). Free memory stayed between 34% and 47% this phase, so no run had to wait.

## What was built

| Piece | Where (task folder unless noted) | What it is |
| --- | --- | --- |
| World builder (WS6 module 2) | private: `crime-city-reference/overlay/game/builder.gd`, `signals.gd`, `world.gd` | The static world from the plan when a map loads (below) |
| Plan-compliance playtest (WS4) | `common/kit/playtests/world.plan_compliance.downtown.json`, `scripts/plan_probes.py` | 10,866 rays over the whole of Downtown in one query step; expected heights and tags from the plan |
| Kit ray checks | `common/kit/qakit/expect.py`, `common/kit/README.md` | `rays`, `clear_run`, `surface_tags`, `none_listed`, `skeleton`; the README documents the `query` step for the first time |
| Full Downtown (WS2) | `common/design/plan/downtown.json`, `scripts/gen_plan.py` | About 0.86 x 0.87 km, both highway portals (below) |
| Plan checker | `scripts/check_plan.py`, `checks/test_plan_check.py` | Curves, portals, bounds, classes, legs on their first straight, unique district ids, connectivity through portals, the GDD cross-check; the mutation set as a development check |
| Format examples | `common/design/plan/FORMAT.md` | The examples quote the new plan; a development check keeps them true |
| People playtests (WS4) | `common/kit/playtests/people.*.json`, `scripts/make_playtests.py` | Five new: paces, camera, lineup (held by the reference), feet and crouch (not yet held) |
| Kit people checks | `common/kit/qakit/expect.py` | `pace`, `feet`, `hips_ratio`, `camera_frame`, `look_rate`, `camera_tilt`, `moves_along_camera`, `look`, `looks_distinct`; query steps can name an entity by an earlier answer |
| Private set repair | private: `tests/private/templates/` (3 templates), redrawn | Spawns on open ground at the surface's height (below) |
| Acceptance tool | `scripts/phase1d_acceptance.py` | `qa`, `grade` and `replay10` on both projects |
| Development checks | `checks/test_rays_and_people.py`, `checks/test_plan_check.py` | 13 checks of the new kit checks, 20 of the plan checker |

### The world builder (private)

`builder.gd` builds, from the plan alone:
- the ground (tagged `terrain`) 1 cm under the plan's `ground_m`, out to 200 m past the bounds;
- roads along every edge's centreline (mitred where it bends), split at the crosswalk bands, which
  are their own strips tagged `crosswalk`; junction boxes as the hull of every leg's carriageway out
  to its `box_m`; centre lines, lane lines, stop lines and zebra bars as paint;
- every block raised to its elevation: a sidewalk band round its edge (whose outer face is the
  kerb) and a fill 2 cm under it;
- every parcel: plazas, parks and parking lots as open ground with their tag; built parcels as a
  forecourt (tagged `sidewalk`) round a solid building on the footprint (tagged `building`, with
  metadata `parcel`), roof at `base_m + height_m`;
- interiors cut out of the building in the door's frame. The footprint is split into cells along the
  edges of the footprint, the rooms and the doorway. Room cells get a floor tagged `interior` and
  the building above their ceiling. Doorway cells are open to the door's height, with 0.1 m spare on
  each side and above. Every other cell is solid. Connected rooms meet across their shared edge.

Every collider is on layer 1. There is one `StaticBody3D` per surface, and one per building and per
interior, each with one two-sided `ConcavePolygonShape3D`. The look is built from the same faces as
a few vertex-coloured meshes.

`signals.gd` registers a `signal` entity per signalised approach (`intersection`, `approach`,
`state`) and per crosswalk with walk signals (`intersection`, `crosswalk`, `state`), and sets their
states every tick from the plan's program in whole ticks since the last `world.reset`. It places a
Kenney traffic light at each signalised approach and a stop sign at each all-way stop. Neither has a
collider, so no ray meets them. `world.gd` builds both when a map loads (replacing module 1's ground
and raised blocks) and steps the signals.

### The full Downtown

| | Core block (Phase 1a) | Full Downtown (this phase) |
| --- | --- | --- |
| Size (bounds) | 450 x 430 m | 860 x 869 m |
| Junctions | 16 (7 signalised, 5 all-way stops) | 64 + 2 portal nodes (15 signalised, 45 all-way stops) |
| Edges / lanes | 24 / 60 | 114 / 260 |
| Blocks / parcels | 9 / 33 | 49 / 160 (65 residential, 31 commercial, 22 parking, 17 park, 14 industrial, 10 civic, 1 plaza) |
| Points of interest | 25 | 27 (the two highway portals added) |

The highways leave the map at portal nodes on its edge: `pt_east` (east of the arterial row, 70 m,
to Ashby Port, point of interest `highway_downtown_port`, link `hw_downtown_port`) and `pt_north`
(north of the arterial column through an S-curve of two 35-degree arcs of radius 60 m, to Sable
Hills, `highway_downtown_hills`, `hw_downtown_hills`). Highways are 2 x 2 lanes of 3.75 m at
90 km/h. The north highway is the plan's first curved edge.

## Decisions

1. **The core keeps its places.** The generator draws the core's signal offsets and parcels first,
   in the same order as when the core was the whole map. Everything else draws from a generator keyed
   by its own id, so editing one block changes nothing else. The core's 33 parcels, its 5 interiors
   and every point of interest are unchanged. The exceptions are four R1 checkpoints, which moved
   2.25 m because the corner bends became junctions. Node, edge, block and sidewalk ids follow the
   full grid (the core's `j_00` is now `j_22`). Core parcels keep `p_00` to `p_32`.
2. **Column 7 is a street, not an arterial.** At a bend lanes only continue (FORMAT.md). An arterial
   meeting a one-lane street at the map's corners left its second lane unreachable. The checker
   found it (lane network not strongly connected), and it is now one of the mutations.
3. **No highway district on Downtown.** Two corridors would have needed two district records
   with the same id. Downtown's highway stubs are 70 to 100 m, with no sidewalks, so they belong to
   the districts around them. The highway district starts on the other maps.
4. **Collision as one trimesh per surface.** A ray down meets the highest face, so the ground sits
   1 cm under `ground_m` and each block's fill 2 cm under its sidewalk. Roads and crosswalks never
   share a face. Forecourts are tagged `sidewalk` (paved and walkable, TR-9). The parcel's own ground
   covers only the setback ring, so an interior floor never shares its height with another tag.
5. **What the plan-compliance playtest probes.** Every number comes from chapter 12. Where a rule
   gives no share (WD-2's sidewalks and crosswalks, WD-3's open parcels, WD-4), every ray must hold.
   Where the rays start matters:
   - rays from 100 m up for roads, sidewalks, crosswalks, roofs and open ground;
   - rays from just under each ceiling for room floors, and up from each floor for emptiness;
   - horizontal rays through each doorway and from it across its room;
   - rays across the edge two rooms share for the 1.2 m opening;
   - a ray from 0.6 m above each point of interest.

   WD-3's "no building surface outside its parcel" is probed on the sidewalk side of each built
   parcel. Between two parcels a building may fill its own setback without breaking the rule, so
   those sides are not probed. WD-6 (water) and WD-7 (terrain) have nothing to probe on Downtown, so
   they wait for Ashby Port and Sable Hills.
6. **Clarifications so each playtest relies only on what the documents state.** None adds a
   feature. There are still 177 rules, and the coverage map reports 0 problems.
   - **CM-1:** the rule said "the player stays inside the middle 40% of the view". A position is a
     node's origin (the GDD's convention), which is at the feet, and a camera that frames the head
     puts the feet about 0.46 of the half-height from the centre. The rule now names the `Hips` bone,
     on the project's 1280 x 720 window with the camera's `fov` vertical (Godot's default).
   - **CM-2:** the tilt is the pitch of the view, positive looking up.
   - **FT-2:** a foot is planted while its toe bone is within 0.04 m of its lowest height in the
     gait (Phase 0's rule), and a step is a foot coming down to plant.
   - **FT-6:** the crouched hip height is measured above the ground.
   - **WD-2:** crosswalks are at the road's height, within 0.10 m as in WD-1.
   - **WD-4 and FORMAT.md:** openings between rooms are measured 1.0 m above the floor, and a door's
     height from the floor of the room it opens into.
   - **`player.spawn` with `lead`:** the player becomes that lead.
   - **FORMAT.md:** which examples come from `downtown.json` (water, terrain and links do not).
7. **Measurement choices in the kit:**
   - an opening of k clear rays at spacing s counts as k x s wide, so a measured width is within one
     spacing (0.05 m) of the true one;
   - the tilt is checked from both extremes: look_down after look_up has been held, then look_up
     after look_down, so a camera that rests at a limit still shows both directions;
   - the rays beside a parcel accept a hit of anything but a building, or no hit;
   - the feet windows are 4 s at a walk and 3 s running and sprinting, so a slow cadence still shows
     at least 3 steps.
8. **Playtests the reference does not hold yet ship anyway.** These are `people.locomotion/feet`
   (FT-2) and `people.locomotion/crouch` (FT-6 and the crouched pace). They need animation and
   crouching (module 3). Both are in the kit for the developer, but out of the reference's required
   set (`NOT_YET` in `scripts/phase1d_acceptance.py`) until module 3 lands.
9. **No panel this phase.** The GDD leaves two choices to the panel: PF-6's tick limits (they need
   the target hardware) and AC-17's exact replay. Neither came up.
10. **The private set had spawn points that a real world breaks.** The world builder exposed them:
    - Phase 1b's `people.locomotion/same-tick` template spawned 2-12 m past the safehouse's save
      point, inside what is now the safehouse building;
    - the `world.replay` and `contract.devconsole/bad-input` templates spawned at y = 0.0 on the
      plaza, whose surface is 0.15 m up.

    The unchanged set still graded 1.000000 on the full-map reference (14 of 14). The templates now
    spawn at `plaza_central` plus 2-12 m and at the plaza's height, and the set was redrawn with the
    same private draw. Four files were rewritten in place, the two same-tick files have new names,
    and the other eight are unchanged.
11. **The ground runs 200 m past the bounds** so nothing falls off the map's edge. FORMAT.md says
    nothing the game builds from the plan lies outside the bounds, and no rule probes beyond them. A
    stricter reading wants the ground to stop at the bounds, with walls along the edge and gaps at
    the portals. That belongs with the map links (WD-9), when crossing a portal has somewhere to go.

## Independent read

An independent solver's-eye read (sonnet) of every new or changed developer-facing file found no
evaluation vocabulary. Its findings, all fixed before the final acceptance runs:
- **Wording:**
  - "could not be judged" became "could not be measured";
  - `judge_ray` became `ray_problem`;
  - the measured keys became `groups_below_share` and `first_off_plan`;
  - in `session.py`, "judges them" became "checks them".
- **Where a playtest asked more than its rule said:**
  - door height had no stated base, and FORMAT.md now gives one;
  - the crosswalk height is now in WD-2;
  - the stance and step definitions are now in FT-2;
  - FT-6's "height" is now measured above the ground;
  - the opening is now measured 1.0 m above the floor;
  - CM-1's window and field-of-view convention is now stated;
  - CM-2's pitch sign is now stated.
- **Fairness:**
  - `clear_run` undercounted by one spacing (now k x s, at 0.05 m);
  - `within_parcels` failed rays that hit nothing;
  - the feet windows could show fewer than 3 steps at a slow cadence;
  - the tilt check could not see a camera resting at its upper limit.
- **Notes a developer could not act on:**
  - `rays` now names the first ray off the plan, with its place and what it hit;
  - `camera_frame` gives the tick, the bone and the amount;
  - `camera_tilt` gives the change and the direction expected;
  - `feet` explains a step and no longer prints "None m/s";
  - `skeleton` tells an unknown id from a missing `Skeleton3D`;
  - `looks_distinct` says whether body and hair or the top colours are too alike;
  - `player.spawn` with `lead` is now stated to change the look.
- **README:**
  - the shapes of `observe`;
  - the fields of a ray's answer;
  - `$answer` in any query value;
  - the exact rules of `rays`, `clear_run`, `camera_frame` and `camera_tilt`.

Kept as it is: "expectation", the kit's word since Phase 1b, which the reader would leave as it is
unless the whole kit were swept.

## Acceptance results (macOS)

### WS6 module 2, the world builder

| Check | Result |
| --- | --- |
| Plan compliance on the Downtown core block (module 2's first target) | Every expectation holds: 2,746 rays (664 lanes, 393 sidewalk points, 220 crosswalk points, 540 roof points, 327 beside parcels, 212 open-ground points, 45 door rays, 63 floor and 63 ceiling rays, 114 from doors, 80 across the vault opening, 25 points of interest; 2,444 hits, all tagged) |
| Plan compliance on the full Downtown | Every expectation holds: 10,866 rays (2,490 lanes, 1,897 sidewalk points, 1,024 crosswalk points, 2,400 roof points, 1,268 beside parcels, 1,316 open-ground points, 45 door rays, 63 floor and 63 ceiling rays, 114 from doors, 159 across the vault opening, 27 points of interest) |
| Another plan through `--plan-dir` (WD-8's first try) | The reference given the earlier core-only plan builds that world instead, and its 2,746-ray compliance play holds |
| Fails when the world is wrong | See the mutant table below |
| The 14 earlier playtests on the full map | All hold; 0 errors or warnings in every game log |
| Boot on the full map (grader's boot gate) | Solo 0.23 s and server 0.22-0.23 s in the final grades (0.515 s and 0.552 s in one earlier grade); Phase 1c gave 0.19-0.21 s on the core's placeholder world. Imports take 2.75-4.25 s with a 64.27 MB cache (qa's own copy 2.8-3.9 s) |
| Memory | A game process peaks at 129-132 MB on the full map (117 MB in Phase 1c) |

| Mutant (compliance on the full map) | Expectations that no longer hold |
| --- | --- |
| Module 1's placeholder world (flat ground, raised blocks) | 11: `crosswalk_tags`, `roofs`, `open_plaza`, `open_park`, `open_parking`, the six room floors |
| Interiors left solid | 7: `doors` and the six room floors |
| Crosswalks tagged `road` | 1: `crosswalk_tags` |
| Roofs 1 m low | 1: `roofs`, whose note names the first ray off the plan ("hit 'building' at height 24.85, expected 25.85 within 0.5 m") |
| The bare starter (no world) | 15 of 20: every probe that needs a surface; the five that only need nothing in the way (doors, empty rooms, rooms seen from the door, the opening between rooms, beside the parcels) hold, there being nothing in the way |

### WS2, the full Downtown

| Check | Result |
| --- | --- |
| `check_plan.py` | **0 problems** on the full Downtown (260 lanes, 160 parcels), and on the earlier core plan |
| Mutation set (`checks/test_plan_check.py`) | **17 of 17 caught**: Phase 1a's nine (dropped phase, point off the ground, reversed one-way, door off its wall, height out of range, stop line in the box, dead-end lanes, checkpoint gap, missing field) and eight new (portal off the edge, portal point of interest naming a junction, curve point outside the bounds, crosswalk past a leg's first straight, district gap, unknown class, duplicate district, a bend joining lane counts) |
| The GDD cross-check (`--gdd`) | **0 problems**: all 19 points of interest the GDD names for Downtown are in the plan; 24 for Ashby Port and Sable Hills listed as still to come |
| The plan is the generator's output; FORMAT.md's examples quote ids the plan has | Both are development checks and pass |
| The core keeps its places | 33 of 33 core parcels identical (polygons, heights, interiors); every point of interest unchanged except R1's checkpoints 1, 3, 5 and 7, 2.25 m along their lanes |

### The reference and the starter through the real grader

| Run | Result |
| --- | --- |
| Reference, the 17 playtests it holds as the instance set | **1.000000**: self-test passed (11.29 s); static gate passed (20 own files, the denylist on); import 2.98 s, cache 64.27 MB; boot 0.231 s solo, 0.219 s server; 17 of 17 instances at 1.0; 26.2 s in all |
| Starter, same set | **0.000000**: static (6 files) and import (3.14 s, 64.27 MB) gates pass, the boot gate fails ("solo not playable within 60 s", "server not playable within 60 s"); the reward written, exit 0, 123.5 s |
| Reference, the private set as redrawn (14 instances) | **1.000000**, 14 of 14 (import 4.25 s; boot 0.231 s solo, 0.226 s server; 19.5 s) |
| Reference, Phase 1b's private set unchanged (before the redraw) | **1.000000**, 14 of 14 (import 3.44 s; boot 0.515 s solo, 0.552 s server) |
| Ten replays of `world.replay/two-paces` in fresh processes | **1** distinct replay hash over 10 runs (78 frames each, 0 errors, 6.7 s), the same hash in two separate acceptance runs (`0547c471...`) |
| `qa run`, all 19 playtests | Reference: 17 of 19 hold (feet and crouch wait for module 3), 15.6 s with the import (2.8 s). Starter: all 19 list what did not hold, 0 runs stopped, 10.2 s |

### WS4, the playtests and the kit

| Acceptance (plan, WS4) | Result |
| --- | --- |
| Wording check over the kit, the starter and the design folder | **0 hits** (8 open markers, all from before this phase); `qa list` 0 hits; both sample outputs 0 hits once this Mac's paths are swapped for the sandbox's (the raw files only hit the scratch folder's path) |
| The reference passes every playtest | 17 of 19; the two others are the module 3 playtests (below) |
| The starter fails them cleanly | 19 of 19 list what did not hold; 0 runs stopped on a kit error |
| Development checks | **146 pass** without Godot (108 at the start of the phase), and Phase 1b's three Godot checks pass with the changed kit (166.7 s) |
| No totals | `qa`'s notes give shares of rays and counts of steps; no "N of M", "total" or "passed" |

## The playtests and their status

| Playtest | Rules | Reference | Starter | In the reference's required set |
| --- | --- | --- | --- | --- |
| `world.plan_compliance/downtown` (new) | WD-1 to WD-5, AC-8 | holds (10,866 rays) | 15 do not hold | yes |
| `people.locomotion/paces` (new) | FT-1, IN-2 | holds: walk 1.15, run 5.5, sprint 8.5 m/s; strength 0.5 walks, 0.6 runs | 6 do not hold | yes |
| `people.locomotion/camera` (new) | CM-1, CM-2, CM-3 | holds: 3.98-4.05 m from the head, hips at most 0.22 from the middle, 180 degrees per second, pitch -60 to +30, moves 0.0 degrees off the camera's forward | 6 do not hold | yes |
| `people.lineup/leads` (new) | CA-1, CA-2, AC-5, AC-11, AR-3 | holds: six leads as in chapter 2, every look field, scale 1.0, one 65-bone skeleton with 4 bound meshes each, nothing unregistered | 15 do not hold | yes |
| `people.locomotion/feet` (new) | FT-2 | **not yet**: 0 steps, toes slide at the body's speed (no animation) | 3 do not hold | no, until module 3 |
| `people.locomotion/crouch` (new) | FT-6, FT-1 | **not yet**: hips at 100% of standing, 1.15 m/s (no crouch) | 2 do not hold | no, until module 3 |
| the 13 playtests of Phase 1c | 25 rules | all hold on the full map | all report failures | yes |

Together the 19 playtests list 43 rules: Phase 1c's 25 and 18 new (WD-1 to WD-5, AC-5, AC-8,
AC-11, AR-3, CA-1, CA-2, CM-1 to CM-3, FT-1, FT-2, FT-6 and IN-2). Each new rule has at least one
expectation citing it. The coverage map still reports 0 problems.

## What still needs Linux

Everything on Phase 1b's and Phase 1c's lists still applies:
- the `.so`;
- the cgroup sandbox and the unprivileged user;
- a real fork bomb;
- `/proc` readings;
- the starter in the agent image, with the prebuilt vendor cache and S3TC on Linux;
- `qa run` with Python 3.12 and `/opt/godot`;
- the ENet server inside a container;
- the verifier image's plan and playtest paths.

This phase adds:
- **the world builder on x86_64.** This means Jolt's ray hits on the trimesh colliders, and the
  10,866-ray compliance playtest, on the verifier's CPU. The rays hit flat faces, so the heights here
  are exact to float precision. That should carry over to x86_64, but it has not been seen there;
- **replays on x86_64 with the full map.** Signals now run every tick and appear in the census, so
  the replay hash covers them;
- **import and boot time on a cloud vCPU with the full map.** On this Mac the import takes 3 to 4 s
  and the boot 0.2 to 0.6 s.

## Not done in this phase

- **Module 3 (people).** This is animation from the shipped clips (walk, jog and sprint matched to
  speed; crouch walk), crouching, jumping, climbing and vaulting. `people.locomotion/feet` and
  `people.locomotion/crouch` wait for it, and stay out of the reference's required set until then.
- **The rest of the people playtests.** These are `people.jump_climb_vault`, `people.swim`,
  `people.fall_ragdoll`, `people.vehicle_entry`, `people.census` and `people.switch_lead`, the
  lineup's heights (AR-3) and look parameters (AC-11's shader parameters, which the telemetry node
  cannot read yet), and CM-4.
- **Module 2's remaining pieces, which come with the plans that need them:**
  - street lights (WD-12; the telemetry node needs a way to read a group's lights first);
  - water and shores, terrain and terrain-following roads, bridges and tunnels (Ashby Port, Sable
    Hills);
  - the links and map changes (WD-9, WD-10);
  - walls at the map's edge.
- **WS2's other plans:** Ashby Port, Sable Hills with its heightmap, `links.json`, and the private
  alternative Downtown with the generator's randomised layout mode. The plan swap was tried only
  with the earlier core plan, which the reference builds and checks clean through `--plan-dir`.
- **Signals' own playtest.** This is `traffic.intersection_watch` with TR-4 (the program) and AC-7
  (the entities). The reference runs the programs now, but no playtest reads them yet.
- **Hidden instances for the new templates (WS8).** These are plan compliance on the alternative
  plan, the people templates and the WD-8 swap.
- **`push_ops.sh` was not run.** The ops folder rides the ops draft PR, and the brief says not to
  touch PRs. The refreshed bundles are in `harbor-lh/ops/swe-marathon-v2/next-tasks/game-private/`.

## Next workstream

**WS6 module 3, people, with its playtests.** The work is:
- the shipped clips (`UAL1_Standard_RM` and `UAL1_Standard` through the shipped bone map) on every
  person, gaits chosen by speed;
- playback time-scaled so a planted toe stays put, within FT-2's limits (Phase 0 measured 0.06,
  0.36 and 0.50 m/s with the clips time-scaled to the GDD's paces);
- crouching and the crouched walk, the jump, climbing and vaulting with IK, swimming, the ragdoll
  and getting up, and getting in and out of vehicles.

That turns `people.locomotion/feet` and `crouch` green and opens `people.jump_climb_vault`,
`people.fall_ragdoll` and `people.vehicle_entry`. Every later module (traffic's pedestrians,
combat, police) moves people.

Light work in parallel:
- `traffic.intersection_watch/signals` for TR-4 and AC-7 on the signals the builder now runs;
- the generator's randomised layout mode and the private alternative Downtown (WD-8), now that
  the builder has shown it takes another plan.

For the Linux items above, ask the owner for an x86_64 Linux machine.

## Commits

| Commit | What |
| --- | --- |
| `1d3cfd3` | WS4/WS6: the plan-compliance playtest (core block, 2,746 rays), the kit's ray and people checks, the README's `query` step; playtest files keep short lists on one line |
| `1679499` | WS2/WS4: the full Downtown, the checker's curves, portals, bounds and GDD cross-check, the mutation set as a development check, FORMAT.md's examples; the five people playtests; CM-1's `Hips` |
| `269fe89` | The independent read's findings (wording, fairness, notes, README, seven clarifications), the lineup's own AC-11 and AR-3 expectations, the acceptance tool, this report and the README |
| (next) | this table's hashes |

Private, with both bundles refreshed in `harbor-lh/ops/swe-marathon-v2/next-tasks/game-private/`:
- `crime-city-reference` `1fa13bf`: module 2, the world builder;
- `tests/private` `bec33e5`: the three templates repaired and the set redrawn.
