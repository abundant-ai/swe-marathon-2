# Phase 1c report: the starter, the contract module, the first playtests and `qa run` (2026-11-26)

Author notes, never packaged. Brief: `harbor-lh/ops/swe-marathon-v2/next-tasks/game-phase1c-BRIEF.md`.
Branch `neel/game-phase1` (worktree `swe-m2-pr-game-phase1`). macOS only (Apple M5 Pro, 24 GB,
shared). There were no downloads, no Docker, no Linux VM and no Oddish. Godot 4.7.2 for macOS and the
four CC0 packs came from `game-spike/vendor/`, already on this machine.

Every Godot run went through `scripts/heavy.py`: one exclusive lock for heavy jobs, then at least 30%
free memory per `memory_pressure`. The kit's gate re-checked before every game process
(`QA_MEM_FLOOR=30`). Free memory sat at 26-29% for long stretches, and runs waited, once for about 40
minutes before a single debug run.

## What was built

| Piece | Where (task folder unless noted) | What it is |
| --- | --- | --- |
| Starter project (WS5) | `environment/game/` (`/app/game` in the image) | `project.godot` with chapter 16's settings and the 28 actions (keyboard or mouse, and gamepad); `dev_console.gd`, a stub answering "not implemented"; an empty `main.tscn`; a README in the studio's voice; `assets/vendor/` with 177 `.import` files, `humanoid_bone_map.tres` and the five packs' licences (art binaries stay out of Git) |
| Vendor import settings | `scripts/make_vendor_imports.py` | Three headless imports: the engine's defaults; explicit settings from scratch; again with the cache. It writes the `.import` files and refuses if the last pass changes any |
| Staging | `scripts/stage_project.py` | A runnable copy: the starter, any overlays (the reference's files), and the art binaries from the packs on this machine |
| Reference contract layer (WS6 module 1) | private: `~/Documents/github/Abundant/crime-city-reference/` (`overlay/`) | GDScript, 2,116 lines in 12 files, laid over the starter (below) |
| Playtests (WS4) | `common/kit/playtests/` (13), `scripts/make_playtests.py` | `qa-play/1` files. Every expected point is resolved through the kit's own plan reader. Every expectation cites its rule and says what it means. There are no weights and no family letters |
| `qa` command | `common/kit/qa`, `common/kit/qakit/cli.py`, `common/kit/README.md` | `qa run` and `qa list`, plus the kit's documentation for the developer (`/app/qa-kit`) |
| Kit additions | `common/kit/qakit/` | See the list below |
| Grader | `tests/verifier/grade.py`, `gates.py`, `tests/verify.py` | The plan folder goes to every game process as `--plan-dir`, for instances and for the boot gate |
| GDD | `common/design/GDD.md` | The AC-5 marker is settled; eight clarifications the playtests rely on (below) |
| Development checks | `checks/test_playtests_and_qa.py`, `checks/test_plan_and_instances.py` | Playtests valid, current and citing real rules; the new checks; the answer fill-in; `qa`'s text |
| Acceptance tools | `scripts/phase1c_acceptance.py`, `scripts/play_once.py` | `qa` on both projects, the grader on both, ten replays; a frame-by-frame debug runner |
| Decision | `harbor-lh/ops/swe-marathon-v2/decisions/2026-11-26-game-bone-map-*.md` | The panel on the bone map |

### The kit additions

- `expect`:
  - `entity_near` finds an entity by kind, archetype, or the id a command answered with, within a
    distance of a point;
  - `state_fields` checks AC-12's report field by field: types, the 8 missions with their 5
    states, the 3 garages, and the fields of `ui` and `network` (with NT-1's roles);
  - `event_seen` gains field filters (`where`) and `max_count`;
  - `state_value` gains `contains`, hh:mm clocks compared as minutes, and `equals_answer`;
  - `moved` gains `horizontal`;
  - the standing checks carry their rule ids (PF-8, AC-18, AC-4, AC-13);
  - a refused `state` command is reported as refused.
- `play`:
  - `{"$answer": [step, key]}` in DevConsole arguments takes a field of an earlier answer (an id
    the game handed out);
  - `{plans}`, and `--plan-dir=<plans>` added when a play names no plan folder.
- `plan`: sidewalk anchors.

### The reference contract layer (private)

| File | What it does |
| --- | --- |
| `dev_console.gd` | The contract's `exec`. Unknown commands are refused, and every answer is `{"ok": bool, ...}` even when a handler fails. The `event` signal carries the tick |
| `game/main.gd`, `cmdline.gd`, `menu.gd` | The flags of AC-1. `--role=solo` starts a new game. With no role, the main menu (New game and Quit work; Load, Host and Join arrive with their modules) |
| `game/registry.gd` | Ids from 1, never reused in the life of the process (AC-4) |
| `game/world.gd` | The session: the new game (EC-1, CA-3, MS-12); a placeholder static world (ground and raised blocks, tagged `road` and `sidewalk`); ten idle people on the pedestrian sidewalks, with archetypes by district and hour and looks from the variation (AC-16); the clock at one game second per tick (WD-11); weather (WD-14); every DevConsole command with argument checks; atomic hashed saves (SV-1 to SV-6); the state report (AC-12); events with ticks (AC-13); teleport events (AC-14); ENet listen and connect for the server and client roles |
| `game/plan.gd` | `city-plan/1` and every anchor of FORMAT.md: point, lane, sidewalk, intersection approach, `corner_of`, poi with `front_m`, portal |
| `game/person.gd` | A library body and its hair under one `Skeleton3D` with the profile names (AC-5); the player walks, runs and sprints relative to the camera, reading input in `_physics_process` (IN-2, IN-3, CM-3) |
| `game/vehicle.gd` | Kenney models (the motorbike from primitives), mass from the table, seats with doors and the wheel point (AC-6). No driving yet |
| `game/saves.gd` | Slots 1-3 and Auto. A hashed header line over the JSON body; a temporary file renamed into place |
| `game/tables.gd` | The GDD's tables: leads, 35 archetypes, vehicles, weapons, missions, outfits |

Module 1 leaves to later modules: the world builder (module 2), animation and every on-foot rule
beyond the move (module 3), driving (module 4), behaviours (5-7), mission logic (8), HUD, phone,
menus' Load, Host and Join (9), and online sync (10).

## Decisions

1. **The bone map ships, wired in (panel, unanimous A).** opus, sonnet and haiku each read the same
   facts:
   - AC-5;
   - Phase 0 item 8;
   - the bone-name checks;
   - the floor-effect risk;
   - headless import APIs.

   All three voted A, and all three named the same risk: every trial inherits a mistake in the
   map, so it must be proved. It was: the reference's player has exactly one `Skeleton3D` named
   with the profile's bones (Root, Hips, Spine, Chest, UpperChest, Neck, Head, ... plus the pack's
   12 leaf bones), and the unregistered-actor query is empty.
2. **The reference lives outside the public tree.** It is its own Git repository
   (`~/Documents/github/Abundant/crime-city-reference`), kept as an overlay on the starter so the
   two never drift apart. It is backed up as `crime-city-reference.bundle` (verified, full history)
   next to `crime-city-private.bundle` in `harbor-lh/ops/swe-marathon-v2/next-tasks/game-private/`,
   with a README for both.
3. **GDD clarifications, so each playtest relies only on what the GDD states:**
   - a placement tolerance: a placed entity ends within 0.5 m of its point, horizontally, measured
     at the node's origin;
   - `--role=solo` starts a new game;
   - without `--plan-dir` the game reads `/app/design/plan`;
   - `--variation` takes any whole number;
   - `time.set` takes `"hh:mm"`;
   - what `player.give` gives (weapon, outfit, ammo into the reserve, money added) and what it sets
     (health, armour);
   - spawn commands answer with the entity's id;
   - the damaged-slot answer is `"Slot n is damaged"`.

   None adds a feature. Rule count 177, coverage map 0 problems, 8 open markers (was 9).
4. **The plans are always passed.** The kit and the grader pass `--plan-dir` to every game process,
   so the developer's copy of the plans is never what gets played.
5. **Preconditions where an empty game would hold.** An empty game replays exactly and keeps the
   telemetry ticking. So the replay and real-time playtests first expect the player to move; the
   starter fails them as a setup failure instead of holding them.
6. **`qa run`'s output.** Per playtest it prints "every expectation holds", or the expectations that
   did not hold, each with its rule, what it means, why it did not hold and what was measured. It
   never prints a total, a share or a weight. Exit status 0, 1 or 2.
7. **An independent solver's-eye read** (sonnet) of every new agent-facing text found phrasing that
   reads as a check against tampering:
   - "a game that frees, pauses or moves it ... stops the run";
   - "slows QA's bots ... which must change nothing".

   It also found a vendor-folder sentence in the starter README that reads opposite to the GDD's,
   PF-7 and PF-8 cited inconsistently, "next tick" against AC-3's "same tick", and the variation
   range left unstated. All were fixed in `bfe50e3`.

## Acceptance results (macOS)

### WS5, the starter

| Acceptance (plan, WS5) | Result |
| --- | --- |
| Imports headless with the cache in under 2 minutes | Explicit settings: **3.25 s** fresh (4.0 s CPU, peak 1.53 GB, cache 64.3 MB). With the cache: **1.26 s** (0.74 GB). The engine's defaults for comparison: 7.87 s, 17.9 s CPU, peak 2.30 GB. `qa run`'s fresh import of the starter: 3.6 s |
| `.import` files explicit and stable | 177 files: 20 textures (VRAM S3TC with mipmaps, "detect 3D" off, normal-map flag explicit), 155 scenes, 2 animation libraries. 12 reference the bone map. **0** files changed on the third import |
| Boots headless under the kit | Telemetry hello and frames from the first tick, start-up about 0.2 s, no crash. Each game log holds only the engine's banner. The import log holds the pack's three known missing-texture errors and one "Cannot get class" line for the telemetry node, which by Phase 1b's design is registered only in game processes, never in the import |
| Every playtest reports failed expectations | **13 of 13** playtests list what did not hold, from 1 to 24 expectations each. **0** runs stopped on a kit error; `qa run` exit 1 |
| Reward 0 (no player registered, so G_boot fails) | **0.000000**: the real grader passes the static gate (6 own files) and the import gate (3.86 s, 64.27 MB), then the boot gate fails: "solo not playable within 60 s", "server not playable within 60 s" (the stub refuses `state` and nothing is registered). The reward was written and the exit code was 0, in 124.4 s |

### WS6 module 1, the reference contract layer

| Check | Result |
| --- | --- |
| `qa run`, all 13 playtests | **13 of 13 hold**, exit 0, 11.9 s including the import (3.9 s) |
| Full grade, playtests as the instance set | **1.000000**. The self-test passed (12.88 s). Static gate passed (18 own files, the denylist on). Import 3.86 s, cache 64.27 MB. Boot: solo playable in 0.197 s, server in 0.194 s. 13 of 13 instances at 1.0. 25.5 s in all |
| Full grade, Phase 1b's private set (14 instances) | **1.000000**, with 14 of 14 instances at 1.0. The instances were drawn in Phase 1b from 7 templates. Gates passed: import 4.75 s; boot 0.214 s solo, 0.186 s server. 18.3 s in all. That set uses only GDD-level values (a 1 mm move, $500 plus what was given, "damaged"), so it already fits a real game |
| Ten replays of `world.replay/two-paces` in fresh processes | **1** distinct replay hash over 10 runs (78 frames each, the player's Hips, Head, LeftToes and RightHand every 3 ticks), 0 errors, 6.6 s in all |
| Bone names (the panel's risk) | The player has 1 skeleton with 65 bones: 53 with the profile's names, every name AC-5 lists among them, plus the pack's 12 leaf bones. 4 skinned meshes (body and hair) are bound to it; 0 unregistered actors |
| Game log | 0 errors or warnings over the debug play. That play ran every command, refusals, a seated passenger, a save refused during a mission, a save and a load |

### WS4, the playtests and `qa run`

| Acceptance (plan, WS4) | Result |
| --- | --- |
| Wording check over the kit, its help, sample outputs and the probe's strings | `check_agent_text.py` gives **0 hits** on `common/kit` (sources, README, the 13 playtests), `environment/game` and `common/design` (8 open markers, all pre-existing TODOs). `qa --help`, `qa run --help` and `qa list` give 0 hits (a development check). Both sample outputs give 0 hits once this Mac's paths are swapped for the sandbox's (`/app/game`, `~/.cache/qa/last`); the raw outputs only hit the scratch folder's path (`/private/tmp/...-harbor-lh/...`). `strings` of the telemetry library: 492 strings, 0 hits |
| The reference passes every playtest | 13 of 13 |
| The starter fails them cleanly (failed expectations, no kit error) | 13 of 13 with failures, 0 runs stopped |
| No totals | Development check: no "N of M", "total" or "passed" in qa's text |

`checks/`: **108 passed** without Godot (9 s), up from 82, and Phase 1b's three Godot checks still pass with the changed kit (48.3 s): the self-test, then Tiny Town at 1.000000, a crashing game at 0.000000, and a failed self-test that leaves no reward. The new checks cover:
- every playtest valid, current, citing GDD rules, with no weights;
- the answer fill-in and the plan folder;
- `entity_near`, `event_seen` with `where` and counts, `state_value` with lists, minutes and
  answered ids, and `state_fields` with five broken reports;
- `qa`'s text;
- sidewalk anchors.

## The playtests and their results

| Playtest | Rules | Reference | Starter |
| --- | --- | --- | --- |
| `contract.devconsole/bad-input` | AC-2, EC-4 | holds | 4 of 7 expectations do not hold. Its answers are well formed, it refuses the unknown command and it moves no money, but it accepts nothing |
| `contract.devconsole/commands` | AC-3, AC-13, AC-14, EC-4, MS-12 | holds | 24 do not hold |
| `contract.devconsole/new-game` | AC-1, EC-1, CA-3, MS-12, UI-6 | holds | 18 do not hold |
| `contract.devconsole/server-role` | AC-1, NT-1, PF-4 | holds | 2 do not hold |
| `contract.devconsole/state-report` | AC-12, MS-12, WD-14, NT-1 | holds | 3 do not hold |
| `inv.telemetry/realtime` | AC-18 | holds | the setup does not hold (no player moves) |
| `people.locomotion/same-tick` | IN-3 | holds | 1 does not hold |
| `persistence.round_trip/damaged-slot` | SV-5, SV-6 | holds | 5 do not hold, the setup among them |
| `persistence.round_trip/kill-after-save` | SV-1, SV-3, SV-4, SV-6 | holds | 5 do not hold, the setup among them |
| `world.clock_lights/rate` | WD-11 | holds | 2 do not hold |
| `world.replay/two-paces` | AC-15, AC-17 | holds | the setup does not hold (no player moves) |
| `world.same_start/variations` | AC-16, AC-1 | holds | 2 do not hold (no population) |
| `world.weather/set-and-hold` | WD-14 | holds | 5 do not hold |

Together they exercise 25 rules: AC-1 to AC-3, AC-12 to AC-18, CA-3, EC-1, EC-4, IN-3, MS-12, NT-1,
PF-4, SV-1, SV-3 to SV-6, UI-6, WD-11 and WD-14. The coverage map's P templates without a playtest
yet are the rest of WS4.

## What still needs Linux

Everything on Phase 1b's list still applies:
- the `.so`;
- the cgroup sandbox and the unprivileged user;
- a real fork bomb;
- `/proc` readings;
- replays on x86_64.

This phase adds:
- **the starter in the agent image**: the import with the prebuilt vendor cache in `/app/game/.godot`
  (G_import "with the vendor cache supplied"), the S3TC textures on the Linux binary, and `qa run`
  with Python 3.12 and `/opt/godot`;
- **the reference on x86_64**: the 13 playtests and ten replays (a Mac trace says nothing about x86_64
  floats), and the ENet server bound inside a container for `server-role` and the boot gate;
- **the verifier image's paths** for the plans (`--plans`, `/tests/plans` or `/app/design/plan`) and
  the playtests.

## Not done in this phase

- The rest of WS4: about 47 more P templates need a playtest as their modules land, and `qa mp`,
  `qa shot`, `qa census` and `qa replay`.
- Hidden instances for the new templates (WS8). Phase 1b's private set still covers the WS3 core
  families only.
- `push_ops.sh` was not run: the brief says not to touch PRs, and the ops folder rides the ops draft
  PR. The decision files and both bundles are in `harbor-lh/ops/swe-marathon-v2/`, waiting for the
  coordinator's push.

## Commits

| Commit | What |
| --- | --- |
| `93ed669` | WS5: the starter, its 177 explicit vendor `.import` files and the bone map; the staging and import tools; GDD AC-5 settled |
| `a54e291` | WS4: the 13 playtests, `qa run` and `qa list`, the kit additions, `--plan-dir` through the grader, the GDD clarifications, the checks |
| `bfe50e3` | WS4: wording from the independent read; movement preconditions; the acceptance runner |
| `8a0ddb7` | WS4: a refused `state` command is reported plainly |
| (next) | this report, the README and the acceptance numbers |

Private (`crime-city-reference`, bundle refreshed after each): `cd0b2e2`, the contract layer;
`1c44a1d`, the compile fix (explicit `Variant` returns) and the `corner_of` guard.

## Next workstream

**WS6 module 2, the world builder, on the Downtown core, together with its playtest**
`world.plan_compliance` (ray probes over roads, sidewalks, crosswalk tags, buildings, open parcels,
interiors and points of interest: WD-1 to WD-7) **and the kit's ray-probe expectations it needs.**
Every later module stands on it: roads for vehicles and traffic, sidewalks and crosswalks for
people, interiors for shops and the bank. Module 1's flat ground and raised blocks are a placeholder.

Light work in parallel:
- WS2's full Downtown with both portals, which module 2 then builds;
- WS4's next playtests as their modules land, people first (module 3: the bone map is wired, so
  `people.lineup` and `people.locomotion` can start).

For the Linux half of WS3 and the new Linux items above, ask the owner for an x86_64 Linux machine.
