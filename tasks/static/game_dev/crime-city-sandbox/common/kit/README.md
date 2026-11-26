# QA kit

This is the kit our QA team plays Merrow Bay with. Its bots run the game headless, press the input
actions of chapter 4 of the design document, and read what the game exposes for them (chapter 17).
Use it while you build; it never changes your project.

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
- the game keeps running and answering (PF-8), within 1.5 GB of memory (PF-7);
- QA's telemetry node is left alone and runs every tick (AC-18);
- every entity carries its metadata, and ids are whole numbers, unique and never reused (AC-4);
- every event carries its fields and its tick (AC-13).

## The telemetry node

`qa run` adds one node to the copy: a small native library, listed first among the autoloads,
that steps the game tick by tick under `--fixed-fps 60`, presses actions, calls the DevConsole and
reads the entity census, bones, camera, HUD groups and the state report. The game runs with one
worker thread (`override.cfg`), as on QA's machines (PF-6). The node is part of QA's tooling and
the game has no reason to touch it (AC-18); if it goes missing or stops ticking, `qa run` says so.

## Playtests

A playtest is a JSON file (format `qa-play/1`) in `playtests/`. Every value in it is explicit:

- `args`: the game's command line after `--` (`{save_dir}` is a fresh folder per run);
- `mode`: `lockstep` (QA's bots advance the game tick by tick) or `realtime`;
- `runs`: one entry per run; `pace_ms` adds a pause between ticks, as a slower machine would
  (AC-17: the game plays the same either way);
- `limits`: what one run may use: wall and CPU seconds, memory (PF-7's 1.5 GB), disk, and the
  seconds allowed to start (PF-4) and per step;
- `steps`, in order:
  - `observe`: what each frame reports and how often: `census` (`true`, or `{"meta": [keys],
    "view": true}` to add those metadata values and whether each entity is in the camera's
    view), `bones` (`{"ids": [entity ids, or "player"], "names": [bone names]}`: world
    positions), `camera` (`true`: position, back axis and `fov`), `hud` (a list of HUD group
    names), `state` (`true`: the state report) and `every` (ticks between frames, default 6);
  - `dev`: DevConsole commands, run at the start of the next tick, so their effect shows in that
    tick (AC-3); an argument `{"$answer": [step, key]}` takes that field of an earlier step's
    answer (an id the game handed out, for example);
  - `press` and `release`: input actions and their strengths;
  - `run`: advance N ticks; `wait_s`: let a real-time run go on;
  - `mark`: name the current frame for the expectations;
  - `query`: questions the telemetry node answers at the next tick, each with an `id`:
    `ray` (`from`, `to`: what the segment hits first), `down` (rays straight down at many
    `[x, z]` points, from height `y0` to `y1`), `los` (a clear line between two entities),
    `skeleton` (an entity's `Skeleton3D`: its bone names and the skinned meshes bound to it),
    `unregistered` (nodes with a `Skeleton3D`, `CharacterBody3D` or `VehicleBody3D` outside the
    entity registry) and `meta` (an entity's metadata by key); rays use collision `mask`
    (default 1, the world layer) and answer `{"hit": false}` or `{"hit": true, "p": [x, y, z],
    "surface": ..., "entity": ...}` (the collider's `surface` metadata and the id of the
    entity it belongs to, when it has them); any value in a query can be `{"$answer": [step,
    key]}`, as in `dev` (an entity named by the id a command answered with, for example);
  - `wait_for`: advance until an event arrives, or (`near`) tick by tick until an entity of a
    kind stands within a distance of a point, horizontally (to press an action at that spot);
  - `files`: corrupt the save files written since a mark, as a failed disk write would;
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
| `rays` | the rays of a query hit surfaces with the listed tags (`tags`, not `not_tags`) at the expected heights (`y` within `tol_m`), in at least `min_share` of each group of rays (default all); with `hit_optional` a ray that hits nothing is fine, with `clear` only a ray that hits nothing is |
| `clear_run` | rays laid side by side across an opening, `spacing_m` apart, leave a run of k rays that hit nothing with k times `spacing_m` at least `min_width_m` |
| `surface_tags` | every surface the rays of a query step hit carries one of the listed `surface` tags |
| `none_listed` | a query that lists things (such as `unregistered`) lists nothing |
| `skeleton` | an entity has exactly one `Skeleton3D` with the listed bone names and skinned meshes bound to it |
| `pace` | a bone (or the entity) moved at a horizontal speed inside a range between two marks |
| `feet` | between two marks the toes take alternating steps and stay put while planted (a stance is the toe within 0.04 m of its lowest height; slide is measured over the middle 60% of each stance) |
| `hips_ratio` | the hips are at most a share of their standing height above the ground |
| `camera_frame` | the camera keeps its distance from the `Head` bone, and a bone (the `Hips`, or `frame_bone`) inside the middle of the view, the camera's `fov` read as vertical on a view of the given `aspect` |
| `look_rate` | the camera turns around the player at a rate inside a range |
| `camera_tilt` | the camera's pitch (positive looking up) stays inside a range, within half a degree, and tilts the way asked |
| `moves_along_camera` | the player moves along the camera's forward direction |
| `look` | an entity's `look` metadata has every field and the expected values |
| `looks_distinct` | the looks at several marks differ from each other enough |
| `jump` | between two marks the hips rise within a range above their height at the first, and the entity is off the ground (its position more than `off_m` above `ground_y`) for a time within a range: the longest run of samples off the ground |
| `climb` | from the mark where jump is pressed the entity stands on top of a box (over its top, within `on_top_m` of its height) in time; before that a hand comes within `hand_m` of the top edge (`edge`) while the `Hips` are below the top; no observed bone is ever more than `max_into_m` inside the box |
| `vault` | from the mark where jump is pressed the entity's position goes past the box's far side in time; while the `Hips` are over its top they are at least `clear_m` above it; no observed bone is ever more than `max_into_m` inside the box |
| `camera_clear` | in at least `min_share` of the samples, the segment from the `Head` bone to the camera passes through none of the listed boxes |
| `signal_entities` | at a mark, each listed signalised approach and each listed crosswalk with walk signals has exactly one `signal` entity with its metadata and a valid state |
| `signal_program` | every signal shows its plan program's state within one tick; program ticks count from the tick the `world.reset` of `reset_step` ran in, and a frame taken at tick t shows the game's tick t - 1 |
| `signal_greens` | the approaches of a junction that are green at the same time all belong to one phase |
| `signal_walks` | while a crosswalk shows walk, every approach of its junction is red except those green in the phase that lists it |

A box is a solid placed with `prop.spawn`: `{"p": the middle of its base, "size": [width,
height, depth], "heading": degrees}`, its depth along the heading (chapter 17). A program is a
junction's plan program in ticks: `{"offset", "cycle", "phases": [{"start", "green_end",
"amber_end", "green", "walk"}]}`, phases in order from program time 0.

You can add playtests of your own in the same format and run them with
`qa run path/to/file.json`.
