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

Next: Phase 1. Write the design document (GDD), the map plans and the grading kit, then build the reference game.

The art (Kenney and Quaternius CC0 packs) and the Godot binary are not committed; `spike/.gitignore` lists them.

## Development log

### 2026-11-25

Moved the Phase 0 spike to `tasks/static/game_dev/crime-city-sandbox/` with its measurement scripts and results.
