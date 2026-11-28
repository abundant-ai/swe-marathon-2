# Phase 1a report: the build plan and GDD v1 (2026-11-26)

Author notes, never packaged. Brief: `harbor-lh/ops/swe-marathon-v2/next-tasks/game-phase1a-BRIEF.md`.
Branch `neel/game-phase1` (worktree `swe-m2-pr-game-phase1`, from `origin/main` at `ff9359f`).
Writing only: no downloads, no Docker, no Godot run, no Oddish.

## What was written

| Deliverable | Path (under `tasks/static/game_dev/crime-city-sandbox/`) | Commit |
| --- | --- | --- |
| Plan format `city-plan/1` (agent-facing) | `common/design/plan/FORMAT.md` | `a4cc385`, revised in `29f23da` |
| Downtown core block | `common/design/plan/downtown.json` (16 nodes, 24 edges, 60 lanes, 7 signalised and 5 all-way-stop junctions, 9 blocks, 33 parcels, 25 points of interest) | `a4cc385`, revised in `29f23da` |
| Plan generator and checker | `scripts/gen_plan.py`, `scripts/check_plan.py` (0 problems; 9 mutations caught) | `a4cc385` |
| GDD v1 (agent-facing) | `common/design/GDD.md`: 17 chapters, 177 numbered rules, about 11,100 words | `90e6ad9`, revised in `29f23da` |
| Wording check | `scripts/check_agent_text.py` (0 hits on the design folder; 9 open TODO markers) | `90e6ad9` |
| Phase 1 plan | `notes/PHASE1-PLAN.md`: reward, 79-check catalog, 177-row coverage map, 10 workstreams, layout, Linux and downloads, schedule, 20 risks, failure mode | `9f5d05b`, revised in `29f23da` |
| Coverage check | `scripts/check_coverage.py` (0 problems; 7 mutations caught) | `9f5d05b` |
| Review fixes, this report, the README log | all of the above | `29f23da` (this table's hashes: the next commit) |

## Decisions taken

1. **Paces from the shipped clips** (Phase 0 item 8, re-measured from the root-motion file): walk
   0.80-1.50, run 4.60-6.40, sprint 7.40-9.60, crouch 0.50-1.10, swim 1.50-3.00 m/s. The free swim
   clip moves at 2.2 m/s, outside the design's 0.8-1.8 band. Foot slide per gait 0.25/0.40/0.60 m/s;
   cadence across gaits dropped. Both readings of the clips (raw and Phase 0's in-engine) sit at
   least 15% of the band width inside every band.
2. **No evaluation vocabulary:** `--seed` became `--variation`, cheats `--dev-commands`, mission
   rewards payouts, scenarios playtests, the harness the QA kit. The wording check runs on every
   agent-facing file.
3. **Our own mechanic names** (the design's IP mitigation): the "wanted level", GTA's own term for
   its core loop, is the **police alert level** (`hud_alert`, `alert_changed`, rules AL-1 to AL-12);
   heists pay a "haul" and a "crew share"; a lead whose working name echoed a film character was
   renamed.
4. **Checkable by construction:**
   - looks are exposed as metadata plus per-instance shader parameters (AC-11);
   - people expose `weapon` and `hostile`, and the state report gives `aim` and `cover`;
   - minimap icons name what they stand for;
   - static colliders carry a `surface` tag (AC-8);
   - money moves only through `money_changed` events (EC-4).

   Every rule names its numbers and how they are measured.
5. **Restrictions verified, not just stated:**
   - "No wall clock" and "randomness from the variation" are verified by replaying one input
     timeline at two paces (AC-17, `world.replay`).
   - GDScript only and the project settings are verified by the static gate.
   - OR-1 now covers only names and text, which the denylist can check.
   - The README deliverable was dropped from the planned instruction, because nothing would check
     it.
6. **Scope trimmed where a feature could not be checked:** no automatic weather cycle; online
   sessions stay on one map with the ferry docked (NT-15); sound not required; interiors only for
   shops, safehouses and the bank (the plan no longer gives the police station and hospital one).
7. **Online play on ENet only** (Phase 0 item 6: the TCP stall model makes WebSocket unusable at
   the worst profile). A 3 s drop-out must not disconnect, and the online chapter carries the
   bandwidth note on full snapshots.
8. **Free-tier art** (owner):
   - two bodies and six hair meshes make six leads and 35 archetypes through palettes and props;
   - cars must use their Kenney models;
   - the motorbike is built from primitives;
   - boats wait for the watercraft kit.
9. **City rules:**
   - an exclusive walk phase at signals;
   - all-way stops on minor junctions;
   - search-zone radii of 100-320 m, so an escape is possible inside Downtown;
   - the D1 limit set to 120 s after measuring its route on the plan: 746 m, a crawl still fails;
   - R1's two laps at 180 s need a 57 km/h average.
10. **Family M** now covers free play, the DevConsole contract and performance; weights unchanged.
11. **Layout:**
    - agent-facing design inputs in `common/design/` (both images need the plans);
    - author notes in `notes/`;
    - author tools in `scripts/`;
    - private material outside this public repository (plan, section 4).

## Independent review

One independent read of the GDD and the plan format, by an opus agent that had not seen my
reasoning. It reported cues, unmeasurable rules, contradictions, restrictions, originality and time
budget. Everything below was fixed in `29f23da` and is covered by the coverage map.
- **Evaluation cues:**
  - "Every value is the game's real state" was reworded;
  - the telemetry rule is now a plain "leave other nodes alone";
  - QA's hardware no longer sets the player count;
  - "alternative layouts" was dropped from the format.
- **Unmeasurable wording:**
  - idling and "by water" were removed or quantified;
  - weapon, hostility, aim, cover and icon identity are now exposed;
  - "on purpose" and "route" were replaced by measurable rules;
  - `handbrake` and `map` got rules (IN-2, UI-11), and the `npc.spawn` behaviours were defined.
- **Contradictions:**
  - the action count is 28, not 30;
  - AC-16 no longer promises reused ids;
  - H1 could not escape a 400 m zone in Downtown;
  - the police station and hospital interiors were outside the scope;
  - some stages had no place yet the GDD demanded a marker;
  - H2's stage order and missing failure;
  - chase targets were not exempt from signals;
  - police "fights" at levels 1-2;
  - unarmed lookouts were told to attack;
  - the autosave fired during an alert;
  - money and teleports on load and rejoin;
  - patrols and work districts during an alert;
  - the factions that witness crimes;
  - the H2 vehicle and the ferry model;
  - the Join menu's lead;
  - the format's examples did not match `downtown.json`;
  - the portal anchor's id type;
  - the ferry could arrive with no time docked.
- **Kept as they are:**
  - The TODO(panel) and TODO(owner) markers. The brief asks for them, and `check_agent_text.py
    --release` fails until each is settled, so none ships. Their wording no longer mentions QA
    machines or "the starter".
  - Features that need the Ashby Port and Sable Hills plans. These are the ferry, boats, swimming,
    terrain, highways, and C1, C2, D2, R2 and H2. They cannot be exercised until WS2 delivers those
    plans; the coverage map already names their checks.

## The failure mode (proposal)

The agent gets the city's parts working on their own but not together: people, cars and the map
pass their checks while police response, missions, online play and free play, where the systems
meet, fail. The per-family results show it as the integration gap, the mean of families A, B, H
and I minus the mean of E, F, L and M (plan, section 8).

## Open questions for the owner

1. **Names:** the game, the three maps, the six leads, the three crews and the task name are
   placeholders. The reviewer notes that "Merrow Bay" and "Sable Hills" sound like the names of
   another franchise's places; worth replacing.
2. **A private repo** for the reference game, hidden instances, draws, the alternative plan and the
   denylist (proposed `abundant-ai/swe-m2-crime-city-private`). The interim is a `git bundle` in
   `harbor-lh/ops/swe-marathon-v2/game-private/`.
3. **Downloads** (plan, section 5): Godot 4.7.2 for Linux, the Kenney watercraft and city kits,
   Quaternius guns, Downtown City and nature kits, Poly Haven textures, Blender for the agent image.
   Which ones, and when?
4. **An x86_64 Linux machine** (a cloud VM) for the probe's `.so`, the images and calibration, or
   wait for the first platform probe.
5. **Eight players or six:** this depends on the verifier resources the first platform probe finds.

For the panel: the starter shipping the humanoid bone map; exact replay or a tolerance (AC-17);
the tick-time limits once a cloud core is measured (PF-6).

## What remains of the world plans

The format is complete for the whole world. Plans still to build are listed below. The mission
points they must add are `giver_chase`, `c1_start`, `c2_start`, `d2_pickup`, `d2_dropoff`,
`r2_start`, `r2_cp1`-`r2_cp12`, `h2_van` and `h2_stash`, along with the Port and Hills garages,
shops, police stations, hospitals and ferry terminals, and turfs B and C.
- the rest of Downtown around the core, with both highway portals;
- Ashby Port;
- Sable Hills with its heightmap;
- `links.json`;
- the private alternative Downtown.

## Next workstream

**WS3, the grading kit core**, starting with the probe's native core on macOS, the lockstep runner,
the instance format and trace hashing. Everything else is checked through it: playtests, the
reference's modules and calibration. Its macOS half needs no download. Run WS5 (the starter, two
days) and the full Downtown plan (WS2) beside it as light work. Module 1 of the reference (the
contract) can start once the kit's runner answers.
