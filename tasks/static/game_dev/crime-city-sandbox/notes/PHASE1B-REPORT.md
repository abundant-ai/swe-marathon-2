# Phase 1b report: the grading kit core, WS3 on macOS (2026-11-26)

Author notes, never packaged. Brief: `harbor-lh/ops/swe-marathon-v2/next-tasks/game-phase1b-BRIEF.md`.
Branch `neel/game-phase1` (worktree `swe-m2-pr-game-phase1`). macOS only (Apple M5 Pro, 24 GB,
shared): no downloads, no Docker, no Linux VM, no Oddish. Godot 4.7.2 macOS from
`game-spike/vendor/`.

Every Godot run went through `scripts/heavy.py` (one exclusive lock for heavy jobs, then at
least 30% free memory per `memory_pressure`), and the grader's own memory gate re-checked before
every game process (`QA_MEM_FLOOR=30`). Free memory sat at 27-29% for long stretches, so runs
waited often. One exception: the very first smoke import (2.7 s) started at 27% before the gate
existed; everything after it was gated.

## What was built

| Piece | Where (task folder) | What it does |
| --- | --- | --- |
| Telemetry native core | `common/probe/native/` | C11, no godot-cpp; method binds by hash from the pinned binary's `extension_api.json` (`scripts/gen_telemetry_binds.py` writes `gen/binds.h` and refuses a changed signature) |
| Kit core (agent-facing) | `common/kit/qakit/` | signed link, process control, lockstep and real-time sessions, preparation, traces, plays, expectations, plan anchors |
| Grader | `tests/verify.py`, `tests/test.sh` (draft), `tests/verifier/` | self-test, gates, scoring, deadline, reward and report |
| Self-test project and plays | `tests/selftest/` | Tiny Town, our own GDScript project, and 7 plays over 5 families |
| Instance maker | `scripts/make_instances.py` | template + private draw -> explicit instances, anchors resolved against the plan |
| Private set | `tests/private/` (Git-ignored, its own repository) | 7 templates, the draw, 14 instances, the originality denylist; bundle in harbor-lh |
| Hostile projects | `checks/hostile_projects.py`, `checks/fixtures/hostile/` | 16 broken or hostile cases plus a control |
| Development checks | `checks/` | 82 checks without Godot, 3 end-to-end with Godot |
| Tools | `scripts/heavy.py`, `scripts/ws3_acceptance.py` | the heavy-job lock and memory gate; the acceptance runs |

### The telemetry node (native core)

- **Loading.** The kit copies the library under a random folder and file name; the class it
  registers is the file name (`dladdr`), and a one-node scene of that class goes first in
  `[autoload]` (not a singleton, so no global name in scripts).
- **The key never reaches a script.** At scene initialisation, before any game script runs, the
  library reads `QA_TELEMETRY_PORT`, `QA_TELEMETRY_KEY` and `QA_TELEMETRY_MODE`, overwrites the
  key in place and unsets all three, then connects. There is no GDScript part: the key and the
  socket only exist in native memory. Measured: `settings_in_environment` 0 from the game's own
  `OS.get_environment`, and the self-test project's state report says it cannot see the key.
- **Registration only in kit-started processes.** In 4.7.2 an exposed extension class that a
  project scene references crashes the editor during a headless import (SIGSEGV while it loads its
  docks; bisected: also as a runtime class, not with an unexposed class), and an unexposed class
  cannot be instantiated from the autoload scene. So the class is registered only when the link
  settings are present: the import never sees it and the kit's runs instantiate it normally.
- **Every tick, before the game.** Internal physics processing at the lowest priority with
  process mode "always" (pausing the tree does not stop it). Lockstep: at an observation tick it
  sends a frame and blocks for the next command; inputs are injected as `InputEventAction` and
  flushed, so an action injected at tick t acts in tick t. Real time: it never blocks; it applies
  the commands that have arrived, sends a heartbeat (tick, monotonic microseconds) every tick and
  a frame every N ticks.
- **What it reports.** Census (id, kind, archetype, faction, position, orientation, velocity,
  in-view flag, metadata asked for), bone positions, camera, HUD groups, the state report,
  DevConsole events (a custom Callable, serialised at emission with their tick), command answers
  (a failed call is reported "unanswered", never as a refusal the game made), queries (ray, down
  rays, line of sight from the Head bone, skeleton and skinned-mesh binding, unregistered actors,
  metadata).
- **Link.** Length, HMAC-SHA256 tag, JSON with a sequence number, both directions. A bad tag,
  sequence or length stops the game with exit code 3; a lost link with 4; leaving the scene tree
  sends a final "gone". Frames, single events and pending events are capped (64, 1 and 16 MB).
- **Build.** macOS: universal dylib (233 KB), local symbols stripped, an export list so the
  entry symbol `qa_telemetry_init` is the only defined global symbol. Linux: the same script's
  other branch (x86_64, `-fno-ident`, section GC, no build id, version script, `strip
  --strip-unneeded`); not built yet. `strings` of the dylib: 0 hits of the wording check.

### The kit core (`common/kit/qakit`, agent-facing; `check_agent_text.py` 0 hits)

- `procs`: every game process starts through a small launcher (a fresh `python -I -S` with no
  threads) that sets rlimits (CPU seconds, no core files, file size, open files), joins a cgroup
  and drops to an unprivileged user on Linux, then executes the game in its own session. Output is
  drained through a pipe; the first 8 MB and last 2 MB are kept. A watchdog samples every 0.1 s:
  lifetime-peak memory (macOS `ri_lifetime_max_phys_footprint`, Linux `VmHWM`), wall time, home
  folder size, and the process tree every 0.5 s, remembering each process with its start stamp.
  The kill reaches the cgroup (Linux), the process group, and every remembered process still the
  same process, wherever it went.
- `session`: lockstep sessions check every frame's tick and tick count; real-time sessions keep
  the heartbeat record (count, skipped ticks, largest gap, gaps, ongoing silence). Failures are
  kinds: `no_link`, `closed`, `limit`, `stalled`, `out_of_step`, `gone`, `unsigned`,
  `bad_message`.
- `prepare`: copy without `.godot`, telemetry first in `[autoload]`, `override.cfg` with
  `threading/worker_pool/max_threads=1` and file logging off, a headless import under limits,
  then checks: normal exit, the engine registered exactly our library, telemetry files unchanged
  (also re-checked before every instance).
- `trace`: canonical JSON (sorted keys, shortest round-trip floats, no NaN); the hashed part of
  a frame is its tick, census, bones and event names with ticks (command answers are kept but not
  hashed: the spike game's `world.reset` answer carries milliseconds); a SHA-256 chain that
  restarts at each successful `world.reset`; the replay hash covers the segments after the first
  reset; the first divergence is located (segment, frame, tick, entity, fields).
- `play`: the `qa-play/1` format (steps: observe, dev, press, release, run, wait_s, mark, query,
  wait_for, files, restart) with runs at several paces; bones can be asked for by role
  ("player"); save files can be damaged or truncated since a mark; SIGKILL and restart in the
  same save folder. Time spent waiting for memory does not count against a play's time cap.
- `expect`: 8 checks (`dev_answers`, `dev_result`, `replay_equal`, `same_start`, `moved`,
  `state_value`, `event_seen`, `heartbeat`), each reporting what it measured, and 4 standing
  checks on every play: process (no crash, hang or limit, including limits recorded at exit),
  telemetry (no removal, no skipped or late heartbeat), registry (integer ids, kinds, never
  reused, no duplicates; restarts reset it), events (AC-13 fields and a tick).
- `plan`: reads `city-plan/1` and resolves anchors (points, points of interest with `front_m`,
  lane points, intersection approaches) to positions and headings.

### The grader (`tests/`, verifier only)

`verify.py` -> `verifier.grade.grade()`:
1. Stale `reward.txt` and `report.json` removed.
2. The self-test (below). Failure: `report.json` with `"status": "evaluation_error"`, no reward,
   exit code 1. This is the only path without a reward.
3. G_static on the submission as collected: no C# or native files (PF-1), PF-2 settings, the 28
   actions with keyboard or mouse and gamepad events (IN-1), the private denylist over the
   project's own text and file names (OR-1, vendor library excluded). G_import from the
   preparation: normal end within the cap (600 s), registration, cache under 1 GB. G_boot: solo and
   server processes playable within 60 s (state answers; a player registered, or role "server").
4. Instances in manifest order, one fresh process per run, telemetry files verified first.
   s_i = 0 on a failed standing check or precondition, else the weighted share of assertions.
   Physics-sensitive instances below 1 rerun once, at most 15% of instances. Families keep their
   fixed N_f; instances not run count 0.
5. The grader's own deadline (80 minutes): a timer kills every game process and stops new
   instances; an alarm 60 s later writes the reward from what was graded and exits.
6. `reward.txt` and `report.json` (gates, families, integration gap, every instance with its
   checks, measured values, errors and exits) written through a temporary file and a rename.

Linux-only paths written, not exercised: `verifier/sandbox.py` (a cgroup v2 per game process:
`memory.max`, `memory.swap.max` 0, `pids.max`, `cpu.max`, `cgroup.kill`; the unprivileged user
`qa`), the launcher's cgroup join and privilege drop, `/proc` process table and memory readings.

### The self-test (runs first)

On `tests/selftest/project` (Tiny Town: Jolt, the PF-2 settings, the 28 actions, a DevConsole,
a registry, a rigged player whose right arm turns 1 degree per tick, people and crates placed
from the variation, atomic saves in `--save-dir`, an optional `hostile.gd` hook used by the
hostile cases): preparation; a first start-up with a 20 s allowance (so a broken kit fails in
seconds); the 7 plays with every expectation and standing check holding and the telemetry hello
as expected; bones against the analytic arm; a forged command; a 1.5 s stall seen in real time;
a kill with no strays. It stops at the first problem.

## Acceptance results (macOS)

WS3 acceptance (plan, section 3), the macOS half:

### 1. Phase 0's item-2 checks pass in our game and a foreign project

`experiment/phase1b/item2.json` (native core only; no GDScript in the telemetry):

| Check | Foreign project (GodotPhysics3D, own autoloads) | Our game (spike game, Jolt, primitive rig) |
| --- | --- | --- |
| Telemetry first among autoloads, link settings gone from the environment | yes, 0 visible | yes, 0 visible |
| One worker thread (override.cfg) | 1 | 1 |
| Bone reads under the dummy renderer | max error 2.07e-7 m over 180 samples (analytic arm) | Head, Hips, hands, toes read; skeleton query 56 bones, 1 bound mesh, 264 triangles; 0 unregistered actors |
| Input injected at tick t acts in tick t | dz -0.050 m in the tick (3 m/s x 1/60 s); release 0.0, 0.0 | player moved 8.8 mm in the tick |
| Lockstep: every frame at the commanded tick, delta 1/60 | 64 of 64 deltas 1/60; physics minus process frames 1 | every step checked by the session |
| Holding the reply 1 s advances exactly the commanded tick | 1 | 1 |
| Forged command stops the game | exit 3, no strays | exit 3 |
| Pace independence | - | identical trace hash at 0 and 4 ms extra per step (900 ticks) |
| Overhead (154-entity census with view flags and the state report) | 600 ticks observed every tick in 0.064 s | every tick 3.42 ms/tick (4.9x real time), every 6 ticks 1.89 (8.8x), every 60 ticks 1.59 (10.5x) |

Against Phase 0's GDScript prototype (3.31, 1.96, 1.71 ms/tick for the same three rates) the
native core costs about the same when observing every tick and less when observing sparsely;
the census JSON is no longer the bottleneck.

### 2. Forged frames stop the game; a missing heartbeat fails the instance

- Forged command: exit code 3 in the foreign project, the spike game and Tiny Town (self-test).
- Missing heartbeat: the self-test's real-time run showed a steady heartbeat (63 beats in 1 s,
  0 skipped, largest gap 22 ms), then a 1.5 s stall on the game's main thread showed as a 1.515 s
  gap. In the hostile runs, `pause_telemetry` and `stall` zero their real-time instance through
  the standing telemetry check (heartbeat lost), and `remove_telemetry` zeroes every instance as
  `gone`.

### 3. Ten replays of one instance give one trace hash

`experiment/phase1b/replay10.json`: one instance replayed ten times, each in a fresh process,
lockstep, comparing the replay hash (all segments after the first `world.reset`):

| Project | Instance | Runs | Distinct hashes | Frames per run |
| --- | --- | --- | --- | --- |
| Tiny Town (Jolt crates, walking people, the player's bones every 3 ticks, about 200 ticks) | `world.replay/two-paces` | 10 | **1** | 68 |
| Spike game (traffic at density 1.0 on Jolt, the player's sedan accelerating, steering and braking, census every 6 ticks, about 600 ticks; 1.63 s per run) | `world.replay/spike-drive` | 10 | **1** | 104 |

Every `world.replay` instance in the grading runs (one run at 0 ms and one at 4 ms extra per
step) held too, and the spike game's 900-tick drive gave one hash at both paces (item 2).

### 4. Every candidate-failure class yields a written reward

Yes: all 17 cases (16 broken or hostile projects and the control) ended with `reward.txt`
written and exit code 0, and each lost exactly what it breaks (next section). The plan's list:
crash (`crash`), hang (`stall`, `hang_boot`, `import_hang`), failed import (`import_crash`),
stalled or killed telemetry (`pause_telemetry`, `remove_telemetry`), oversized cache
(`big_cache`), fork bomb (`spawner`, bounded: 40 children per process), giant logs
(`giant_logs`). Not covered yet: proxy-breaking traffic (the proxy is not ported).

### 5. `checks/` pytest suite green

`checks/`: 82 passed without Godot (8.6 s): link framing and signing, traces, the play format
and runner parts, every expectation and standing check, scoring, the static gate and its
mutations, process control with Python children (output cap, wall, CPU, memory and disk limits,
a kill that reaches grandchildren and a child in its own session), preparation, the C SHA-256,
HMAC and number formatting against Python, the built library's strings and exports, plan anchors
and instance drawing. With `CC_GODOT_CHECKS=1`: 3 passed (44.9 s): the self-test followed by
Tiny Town at 1.000000; a crashing game at 0.000000 with the reward written; a failed self-test
leaving no reward (a stale `reward.txt` removed, exit code 1, `status: evaluation_error`).

### Full grades

- Tiny Town graded as a submission with the public self-test set: self-test passed in 11.8 s,
  the three gates passed, 7 of 7 instances at 1.0, reward 1.000000, 18.7 s in all.
- Tiny Town graded with the private set (14 instances drawn from 7 templates, denylist on): self-
  test passed in 11.5 s, gates passed, 14 of 14 at 1.0, reward 1.000000 in 24.6 s.

## Hostile-project results

`experiment/phase1b/hostile.json` (and `hostile-1.json` for the final deadline run). Each case is
Tiny Town with an overlay from `checks/fixtures/hostile/` (or the spike's foreign project),
graded by the real grader (`--skip-selftest`; the self-test ran separately). Some caps were
lowered for a case so it finishes quickly; its description says which.

| Case | What the project does | Gates | Instances | Reward |
| --- | --- | --- | --- | --- |
| control | nothing wrong (Tiny Town itself) | pass | 7 of 7 at 1.0 | 1.000000 |
| foreign | the spike's unrelated project (GodotPhysics3D, Forward+, none of the 28 actions) | static fails (not Jolt, not Compatibility, actions missing); boot not run | not run | 0.000000 |
| import_crash | an editor plugin crashes the editor during the import | import fails (signal 6) | not run | 0.000000 |
| import_hang | an editor plugin spins during the import (cap 25 s here) | import fails (stopped at 25 s) | not run | 0.000000 |
| big_cache | a 2048 x 2048 noise texture (cap 4 MB here) | import fails (cache 12 MB) | not run | 0.000000 |
| hang_boot | the main scene never finishes starting (boot budget 15 s here) | boot fails (no first frame, solo and server) | not run | 0.000000 |
| no_contract | a DevConsole without `exec` | boot fails (no state report) | not run | 0.000000 |
| stall | the main thread spins from tick 10 (stall allowance 8 s here) | pass | 6 `stalled`, the real-time one loses its heartbeat | 0.000000 |
| crash | `OS.crash` at tick 10 | pass | 7 `closed` | 0.000000 |
| remove_telemetry | frees the first autoload at tick 10 | pass | 7 `gone` (seen within about 0.15 s) | 0.000000 |
| pause_telemetry | turns off the first autoload's processing at tick 10 | pass | 6 `stalled`, the real-time one loses its heartbeat | 0.000000 |
| memory_hog | +96 MB a tick from tick 8 (cap 400 MB here) | pass | 7 over the cap (peaks 432-699 MB; one caught only by the lifetime peak at exit) | 0.000000 |
| corrupt_save | crashes when loading a damaged slot | pass | the damaged-slot instance `closed`; 6 others at 1.0 | 0.875000 |
| wallclock | moves people by the wall clock | pass | replay and same-start fail their checks (family H at 0); 5 others at 1.0 | 0.700000 |
| giant_logs | prints about 1 MB a tick | pass | 7 at 1.0; up to 207.6 MB printed per run, 10.4 MB kept | 1.000000 |
| spawner | 40 child processes per game process (Godot starts them in their own session) | pass | 7 at 1.0; **0** children left (400 on the first run, before the fix) | 1.000000 |
| deadline | the stall project with the grader's deadline at 60 s (margin 5 s, stall allowance 120 s) | pass | at 60.0 s the watchdog killed the stalled game; that instance and the 6 not started are `not_run:deadline` | 0.000000 (status `deadline`) |

"Each must score 0": the 12 cases that break the gates or every instance score 0.000000; the
corrupt save and the wall clock zero exactly the instances they break (the damaged-slot instance;
replay and same start), as the reward formula intends; giant logs and spawned processes break no
rule the core instances check, and the point is that grading survives them.

## Findings and decisions

1. **The exposed-class crash** (above): the class is registered only in kit-started processes.
2. **Children that leave the process group.** Godot's `OS.create_process` starts children in
   their own session; on the first hostile run a graceful quit orphaned them and 400 `sleep`
   processes outlived their games (all killed afterwards; they were the test's own). Fixed by
   remembering every process seen in a game's tree with its start stamp (snapshots every 0.5 s and
   right before the quit) and killing those still the same process. On Linux the cgroup does this
   atomically; on macOS a child started and orphaned between two snapshots could still escape.
3. **Processes shorter than one memory sample.** Tiny Town's plays run in a fraction of a second,
   so the memory hog passed its cap unseen in 4 of 7 instances on the first run. Fixed with the
   lifetime-peak footprint, read again at the end of every process; a limit recorded at exit fails
   the standing process check.
4. **Memory waits are not play time.** The first full grade lost a play to its 120 s cap while the
   grader waited about eight minutes for free memory; the wait is now excluded.
5. **The state report's nesting.** GDD AC-12 does not say whether the report is the `exec`
   answer itself or under `"state"` (the spike nests it). The kit accepts both; GDD v2 should say.
6. **What a replay must reproduce.** The replay hash covers the physical record and event names
   and ticks, not answers or the state report, which may carry timing. GDD v2 could say that the
   state report and event data hold game state only.
7. **A DevConsole call that fails** (missing method, wrong argument types, a script error) is
   reported as unanswered, so it never counts as a well-formed refusal under AC-2.
8. **Wording.** Kit sources, the library's strings and its log lines pass `check_agent_text.py`.
   Words such as "timeout", "evaluate" and "hidden" were removed from kit code; even the build
   script's visibility flag was replaced by an export list.

## What still needs Linux

- Build `libtelemetry.so` with `build.sh` (x86_64) and repeat the strings and export checks.
- Repeat the item-2 checks, the self-test and the hostile set with the `.so`.
- Exercise the sandbox: cgroup per process (memory, pids, CPU, kill), the unprivileged user, the
  launcher's cgroup join and privilege drop; then a real fork bomb under `pids.max` (macOS ran a
  bounded spawner only: `RLIMIT_NPROC` is per user there).
- Check that the in-place overwrite clears the key from `/proc/<pid>/environ`.
- The `/proc` process table, `VmRSS` and `VmHWM` readings, and `test.sh` in the verifier image
  with the container paths (`/app/game`, `/tests`, `/logs/verifier`).
- Ten replays on x86_64 and the cross-architecture question (a Mac trace is no evidence for the
  verifier's floats), then the timing on a cloud vCPU.

## Not done in this phase (rest of WS3)

- The proxy and its socket audit, and multi-process online sessions (server plus clients, real
  time with timestamps, partitions): the real-time session and heartbeat are in place; the proxy
  from the spike is not ported.
- The HTML report (the JSON report has everything it would show).
- The assertion library's breadth (temporal, aggregate, geometry and physics helpers for the
  catalog's templates): 8 checks so far, enough for the core families.
- Restoring the vendor sources and import cache in the verifier (WS7).

## Private material

`tests/private/` is Git-ignored in the task and is its own Git repository (commit `bf66f18`):
7 templates for the core families, the private draw, the 14 drawn instances and their manifest,
and the originality denylist (38 entries). Backup: `crime-city-private.bundle` (verified, full
history) and a README in `harbor-lh/ops/swe-marathon-v2/next-tasks/game-private/`. Not pushed:
`push_ops.sh` commits the whole ops folder to the ops draft PR's branch, and this brief said not to
touch PRs; push it with `push_ops.sh` when convenient.

## Commits

| Commit | What |
| --- | --- |
| `4f5d06f` | telemetry native core; kit link, processes, sessions, prepare; heavy-job lock; binds generator |
| `f9280f0` | plays, traces, expectations; the grader with its self-test; self-test project and plays; hostile fixtures; checks |
| `5a82219` | plan anchors, instance maker; play time without memory waits; first full grade |
| `d2498ca` | children leaving the process group, lifetime memory peaks, deadline case, fail-fast self-test, Godot e2e checks |
| FINAL_COMMIT | final runs: deadline case reworked, build and grader without deletions, README, this report |

## Next workstream

**WS5 (the starter project) and WS6 module 1 (the contract: registry, DevConsole, state report,
events) against this kit**, with WS4's first playtests written as `qa-play/1` files and a thin
`qa run` command on the kit (its output: failed expectations and measured values, never a
total). The kit now answers, so the next useful evidence is a real game built to the GDD under it;
Tiny Town only stands in for one. Light work in parallel: the rest of WS3 (port the spike's proxy
into the kit with multi-process real-time sessions and partitions, the report page, assertion
helpers as the catalog's templates need them) and WS2's full Downtown.

For the Linux half of WS3, ask the owner for an x86_64 Linux machine (a cloud VM): the `.so`, the
sandbox, a real fork bomb under `pids.max`, `/proc/<pid>/environ`, replays on x86_64. Local
Docker (arm64) would cover the functional part without x86_64 numbers, but this brief ruled
Docker out.
