# QA kit

This is the kit our QA team plays Merrow Bay with. Its bots run the game headless, press the input
actions of chapter 4 of the design document, and read what the game exposes for them (chapter 17).
Run it on your builds as often as you like; it never changes your project.

## qa run

    qa run                                  # every playtest, on /app/game
    qa run world.replay/two-paces           # one playtest, by name
    qa run --game /path/to/project          # another copy of the game
    qa list                                 # the playtests and the rules they exercise

`qa run` copies the project (without its `.godot` folder), adds QA's telemetry node, imports the
copy headless, and plays each playtest in fresh game processes, passing `--plan-dir` with the plans
in `/app/design/plan`. For each playtest it prints either "every expectation holds" or the
expectations that did not hold: the rule each one comes from, what it expects, and what was
measured. The copy, the game's output and a trace of every run stay in `~/.cache/qa/last` (or
`--work DIR`), and `--json FILE` writes the same findings as JSON. `qa run` exits with 0 when
every expectation held, 1 when one did not or the copy could not be prepared, and 2 when it could
not run at all.

Besides its own expectations, every playtest also expects that:
- the game keeps running and answering, within its memory (PF-7, PF-8);
- QA's telemetry node is left alone and runs every tick (AC-18);
- every entity carries its metadata, and ids are whole numbers, unique and never reused (AC-4);
- every event carries its fields and its tick (AC-13).

## The telemetry node

`qa run` adds one node to the copy: a small native library, listed first among the autoloads,
that steps the game tick by tick under `--fixed-fps 60`, presses actions, calls the DevConsole and
reads the entity census, bones, camera, HUD groups and the state report. The game runs with one
worker thread (`override.cfg`), as on QA's machines (PF-6). Leave the node alone (AC-18): a game
that frees, pauses or moves it, or stops its ticks, stops the run.

## Playtests

A playtest is a JSON file (format `qa-play/1`) in `playtests/`. Every value in it is explicit:

- `args`: the game's command line after `--` (`{save_dir}` is a fresh folder per run);
- `mode`: `lockstep` (QA's bots advance the game tick by tick) or `realtime`;
- `runs`: one entry per run; `pace_ms` slows QA's bots between ticks, which must change nothing;
- `steps`, in order:
  - `observe`: what each frame reports (`census`, `bones`, `camera`, `hud`, `state`) and how
    often (`every` N ticks);
  - `dev`: DevConsole commands, run at the next tick; an argument `{"$answer": [step, key]}`
    takes that field of an earlier step's answer (an id the game handed out, for example);
  - `press` and `release`: input actions and their strengths;
  - `run`: advance N ticks; `wait_s`: let a real-time run go on;
  - `mark`: name the current frame for the expectations;
  - `wait_for`: advance until an event arrives;
  - `files`: damage the save files written since a mark;
  - `restart`: kill the game and start it again with the same save folder;
- `expect`: what must hold, each with the rule it comes from (`rule`) and what it means (`says`).

The checks an expectation can use:

| Check | Holds when |
| --- | --- |
| `dev_answers` | every command of the listed steps got an answer of AC-2's form |
| `dev_result` | one command's answer has the given fields (`equals`) or text (`contains`) |
| `state_value` | a state-report value at a mark equals a value, contains an item, lies in a range, or equals an id a command answered with |
| `state_fields` | the state report has every field of AC-12 in its form |
| `event_seen` | events with that name (and field values) arrived between marks, as many as asked |
| `entity_near` | an entity of a kind, archetype or id stands within a distance of a point |
| `moved` | an entity moved at least (or at most) a distance between two marks |
| `same_start` | equal variations gave equal starting populations and different ones differed |
| `replay_equal` | every run did the same thing tick for tick |
| `heartbeat` | in real time, the telemetry node reported every tick |

Write your own playtests in the same format and run them with `qa run path/to/file.json`.
