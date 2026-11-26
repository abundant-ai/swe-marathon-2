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

Next: the starter project and the reference game's first module (the contract) against the kit,
the rest of the plans, and the remaining WS3 pieces (proxy, online sessions, report page).

The art (Kenney and Quaternius CC0 packs) and the Godot binary are not committed; `.gitignore` and
`spike/.gitignore` list them. The reference game and the hidden material live outside this public
repository (`notes/PHASE1-PLAN.md`, section 4).

## Development log

### 2026-11-26

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
