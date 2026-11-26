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

Next: the grading kit core (probe native core, lockstep runner, instance format, trace hashing),
the starter project and the rest of the plans, then the reference game module by module.

The art (Kenney and Quaternius CC0 packs) and the Godot binary are not committed; `.gitignore` and
`spike/.gitignore` list them. The reference game and the hidden material live outside this public
repository (`notes/PHASE1-PLAN.md`, section 4).

## Development log

### 2026-11-26

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
