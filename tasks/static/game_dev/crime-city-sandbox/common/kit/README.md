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
reads the entity census, bones, camera, HUD groups and the state report. Bones are read as the game
shows them, after its skeleton modifiers (IK, look-at, ragdoll) have run. The game runs with one
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
    view (the point 1 m above its position inside the camera's frustum), with `"kinds": [kinds]`
    to list only the entities of those kinds, and `"shapes": [kinds]` to give the entities of
    those kinds their collision shapes: for each `CollisionShape3D` that is a direct child of the
    entity, the box of its shape in world space, as its centre and three half-axis vectors), `bones`
    (`{"ids": [entity ids, or "player"], "names": [bone names]}`: world positions), `seats`
    (`{"ids": [entity ids, or "vehicle"]}`: each vehicle's `Marker3D` nodes in group `seat`,
    in tree order, with their `index` and, in world space, the seat point and the `door` and
    `wheel` points, `null` where a seat has none), `camera` (`true`: position, back axis and
    `fov`), `hud` (a list of HUD group names), `state` (`true`: the state report) and `every`
    (ticks between frames, default 6); an id can also be `{"$answer": [step, key]}`, as in
    `dev`, or `{"kind": k, "meta": {key: value}, "within_m": d, "max": n}`: the n entities of
    that kind nearest the player within d metres whose census metadata has those values (so a
    play can read the bones of the drivers around the player);
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
    entity registry), `body` (an entity's node class, whether it is a physics body, and its
    `mass`, `collision_layer` and `collision_mask`, `null` where it has none) and
    `meta` (an entity's metadata by key); rays use collision `mask`
    (default 1, the world layer) and answer `{"hit": false}` or `{"hit": true, "p": [x, y, z],
    "surface": ..., "entity": ...}` (the collider's `surface` metadata and the id of the
    entity it belongs to, when it has them); any value in a query can be `{"$answer": [step,
    key]}`, as in `dev` (an entity named by the id a command answered with, for example);
  - `wait_for`: advance until an event arrives, or (`near`) tick by tick until an entity of a
    kind stands within a distance of a point, horizontally, with the metadata values in `meta`
    when given (to press an action at that spot, or once a traffic light shows red),
    or (`entity`, by `id` or `kind`) tick by tick until its horizontal speed is at least
    `min_kmh` or at most `max_kmh`, or its position is below `below_y` (to brake at 60 km/h,
    or to act at a point of a fall);
  - `cruise`: QA's bot driving a vehicle at `kmh` for `ticks` ticks, one tick at a time (so it
    reads the vehicle's speed every tick, whatever `every` says): each tick it presses
    `accelerate` at 0.5 for each m/s the speed is below `kmh`, and `brake` at 0.3 for each m/s
    past 0.15 m/s above it, while holding the actions in `hold` (`steer_left` at full strength,
    for example); it lets go of them at the end unless `keep` is true;
  - `aim_at`: QA's bot aiming like a player at an entity's bone (`entity` by `id`, `bone`,
    `Chest` by default) for `ticks` ticks, one tick at a time: it holds `aim` (and the actions
    in `hold`, `attack` for example) and turns the camera with `look_left`, `look_right`,
    `look_up` and `look_down`, at a strength in proportion to the angle, seen from the camera,
    between the state report's aim point and the bone (full strength from 4 degrees); it lets go
    of them at the end unless `keep` is true (the play observes the state, the camera and that
    entity's bones);
  - `files`: corrupt the save files written since a mark, as a failed disk write would;
  - `restart`: kill the game and start it again with the same save folder;
- `expect`: what must hold, each with the rule it comes from (`rule`) and what it means (`says`);
  one marked `"kind": "pre"` describes the situation the playtest sets up (when it does not hold,
  the playtest's other expectations say little);
- `shared`: values several expectations use, given once (a map of the streets around a
  junction, for example); an argument `{"$shared": name}` stands for one.

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
| `jump` | between two marks the hips rise within a range above their height at the first, and the entity is off the ground (its position more than `off_m` above `ground_y`, by default its height at the first mark) for a time within a range: the longest run of samples off the ground |
| `climb` | from the mark where jump is pressed the entity stands on top of a box (over its top, within `on_top_m` of its height) in time; before that a hand comes within `hand_m` of the top edge (`edge`) while the `Hips` are below the top; no observed bone is ever more than `max_into_m` inside the box |
| `vault` | from the mark where jump is pressed the entity's position goes past the box's far side in time; the `Hips` pass over its top, and while they are over it they are at least `clear_m` above it; no observed bone is ever more than `max_into_m` inside the box |
| `fall_damage` | between a mark standing before a fall and one after it, the entity's position drops h metres and `player.health` falls by FT-8's amount for h: nothing under 3 m, all of it from 15 m, and in between `100 * (h - 3) / 12` within `tol` (a share of that amount, and at least half a health point) |
| `camera_clear` | in at least `min_share` of the samples, the segment from the `Head` bone to the camera passes through none of the listed boxes |
| `signal_entities` | at a mark, each listed signalised approach and each listed crosswalk with walk signals has exactly one `signal` entity with its metadata and a valid state |
| `signal_program` | every signal shows its plan program's state at that tick or one tick either side; program ticks count from the tick the `world.reset` of `reset_step` ran in, and a frame taken at tick t shows the game's tick t - 1 |
| `signal_greens` | the approaches of a junction that are green at the same time all belong to one phase (with `reset_step`, the tick on either side of a phase change is let off) |
| `signal_walks` | while a crosswalk shows walk, every approach of its junction is red except those green in the phase that lists it, and none is amber (with `reset_step`, the tick on either side of a phase change is let off) |
| `body` | a `body` query found the entity's root a physics body on collision layer `layer` (2 is vehicles), with `mass_kg` within `tol` when given |
| `accel` | from rest at the first mark, the vehicle's horizontal speed (from its position tick by tick) reaches `kmh` within `min_s`-`max_s`, interpolated between ticks |
| `brake` | from the last tick before the vehicle starts slowing (after the first mark) to where it stands still, the distance it needs, scaled from the speed it had to `kmh` (by the square of the speeds), lies in `min_m`-`max_m`; with `dry` (the marks of a dry stop of the same model) it is the ratio to that stop's distance that lies in `min_ratio`-`max_ratio` |
| `decel` | from the last tick before the vehicle starts slowing (from at least `min_kmh`), its speed falls at `min_mps2`-`max_mps2` on average over `over_s` seconds |
| `turn_circle` | between two marks, driven at `kmh` (within `kmh_tol`) with full lock, the vehicle's position traces a circle (fitted by least squares) whose diameter lies in `min_m`-`max_m`, after turning at least `min_turn_deg` around it |
| `seats` | at a mark the vehicle's seat read lists `count` seats, indices 0 to `count` - 1 once each, each with a door point, and the driver's seat with a wheel point |
| `get_in` | at the first mark `interact` is pressed with the player within `near_m` of a door; the door nearest the player picks the seat; the player's path passes within `door_m` of that door, and `player.vehicle` and `player.seat` name the vehicle and that seat `min_s`-`max_s` after the press |
| `seated` | on every frame with the player seated in the vehicle, the `Hips` bone is within `hips_m` of that seat's point and, in the driver's seat, both hands within `hands_m` of the wheel point |
| `get_out` | from the first mark (`interact` pressed in the vehicle), `player.vehicle` is `null` `min_s`-`max_s` later, with the player within `door_m` of the door of the seat it sat in, horizontally |
| `camera_vehicle` | between two marks, driving, the camera stays `min_m`-`max_m` from the vehicle's position and the player's `Hips` bone inside the middle `middle` of the view |
| `ragdoll` | between two marks the person is not limp at the first; its `limp` metadata turns true within `within_ticks` of the trigger (its `died` event, or the tick its position comes within `near_m` of `landing_y`; going limp earlier in a fall is fine) and stays true at least `min_s`; meanwhile no observed bone is more than `below_m` under the ground (`ground_y`, or the top of a listed box it is over), the `Hips` never move more than `step_m` in a tick, and the state report's `player.limp` says what the metadata says |
| `free_fall` | over the limp frames where every observed bone is at least `clear_m` above `ground_y`, a parabola fitted to the `Hips` bone's height gives a downward acceleration within `tol` of 9.81 m/s^2 |
| `impact_damage` | across one impact between two marks, the vehicle's `damage` metadata rises by `rate * (dv - free_kmh)` within `tol`, dv being the change of its velocity (from its positions) from just before the impact to 0.2 s after it, in km/h; and it never falls |
| `part_off` | an impact of at least `min_dv_kmh` that leaves the damage at `min_damage` or above is followed within `within_s` by a `part_detached` event for the vehicle, and a `debris` entity whose `vehicle` metadata is the vehicle's id |
| `max_speed` | between two marks the vehicle's horizontal speed, over every 6 ticks, stays at or below `max_kmh` |
| `meta_value` | at a mark an entity's metadata `key` equals `equals` (or lies in `min`-`max`) |
| `explosion` | the vehicle, burning from the first mark, explodes (its `vehicle_exploded` event) `min_s`-`max_s` later and is a wreck at damage 1.0 at the second |
| `blast` | when the vehicle explodes, the entity `of` (the player by default) at distance d from it: with `what` `harm`, a person loses all its health within 3 m and `100 * (6 - d) / 3` from 3 to 6 m (within `tol`), read from the state report for the player and from its `died` event for anyone else within 3 m; with `what` `push`, a vehicle within 8 m ends at least `push_m` further away a second later and, within 6 m, its damage has risen by 0.30 |
| `lean` | on the samples where the vehicle corners at `min_lat` m/s^2 or more (its speed times its turn rate, from its positions), its up axis tilts at least `min_deg` degrees on at least `share` of them |
| `get_up` | a person still alive is back on its feet within `within_s` of going limp: `limp` false and the `Hips` at least `ratio` of their standing height (at the first mark) above `ground_y`; a person that died (its `died` event) is not expected to get up |
| `drivers` | every vehicle moving faster than `min_kmh` and carrying no player has a person of one of the `archetypes` whose `vehicle` metadata names it and whose `seat` is 0; where the frame has that person's `Hips` and the vehicle's seats, the hips are within `hips_m` of seat 0's point; no two people name one seat |
| `density` | once a second, the moving NPC vehicles (faster than 1 km/h) and the NPC people on foot (alive, `vehicle` null) within `within_m` of the player are counted; each full minute's median lies within `vehicles` and `people` |
| `red_entries` | no NPC vehicle's position passes a listed stop line (`approaches`: its line, the direction towards the junction) once the approach's light has been red for `grace_s` (plus a frame); none passes at amber, or in red's first `grace_s`, when at amber's first frame it could have stopped braking at `amber_mps2` or less (with 10% to spare) |
| `green_flow` | at least `min_vehicles` NPC vehicles pass each listed stop line towards its junction |
| `lane_keeping` | on the listed lanes (`lanes`, or those of `area`), NPC vehicles' offsets from the lane centre are at most `max_offset_m` at the 95th percentile; past each lane's first `skip_start_m` (where turns out of a junction end), their forward axis is within `max_heading_deg` of the lane's on at least `min_share` of moving samples and none moves more than 90 degrees off its lane's direction |
| `lane_speeds` | on the listed lanes, NPC vehicles' speed over every `window` ticks stays at or under the lane's `limit_kmh` times `share` |
| `walkable` | at least `min_share` of the samples of NPC people on foot in `area` stand on walkable ground: a crosswalk band, a block outside every building's footprint, a room of an interior, or ground off the road network |
| `crosswalk_use` | of the road crossings of NPC people on foot in `area` (on a carriageway or junction box between samples off it), at least `min_share` start and end on a crosswalk band; one that starts on a band with walk signals starts while it shows walk (that frame or the one before); one that starts at an all-way stop starts with no NPC vehicle approaching the band (moving faster than 1 km/h with its line of travel, `gap_m` long from its position, entering the band) |
| `crosswalk_hits` | no NPC vehicle's collision boxes come within `clear_m` of a person standing on a crosswalk band of `area`, and nobody goes limp on one |
| `vehicle_contacts` | NPC vehicles' collision boxes start touching (within `touch_m`) at most `max_rate` times per vehicle per minute of moving NPC vehicles; a contact counts once for each of the two, and the same two again only after `apart_s` apart |
| `stop_short` | no NPC vehicle's collision boxes come within `touch_m` of a listed prop's box (`props`) or a listed vehicle's boxes (`vehicles`), or within `person_m` of a listed person (`people`); each listed driving vehicle (`drivers`) stands still (1 km/h or less) within `stop_within_m` of them |
| `horn_clear` | the listed people standing in `lane` within `ahead_m` ahead of `vehicle` at the first mark (where `horn` is pressed) are out of the lane's band within `within_s` |
| `sidewalk_dodge` | while `vehicle` drives on a sidewalk (on a listed block) at `min_kmh` or more, the people on foot standing in its path anywhere up to `ahead_m` ahead of it step out of it before it reaches them: its collision boxes never come within `clear_m` of them and none goes limp |
| `no_pop_in` | NPC people and vehicles that join the census are at least `near_m` from the player (less what they could have covered since the frame before) and, nearer than `view_m`, outside the camera's view; those that leave are held to the same in the last frame that shows them; frames made by DevConsole steps are let off, and so are the frames up to `settle_s` after a world.reset or a load |
| `stop_full` | at an all-way stop (`approaches`, `box`), every NPC vehicle that crosses a stop line first stood (1 km/h or less) within `zone_m` before it (one already within `zone_m` of its line at the first mark may have stood before it, and is left out); here and in the three checks below, each time a vehicle comes back to the junction more than 10 s after leaving its box counts on its own |
| `stop_order` | of two NPC vehicles on different approaches whose paths through the box cross: arrivals `late_s` or more apart go in order of arrival; when exactly two arrived within `tie_s` of each other (no third within `tie_s` of either), the one on the right (`right_of`) goes first; other pairs, and three or four arriving together, may go in any order. A vehicle arrives when it first stands within `zone_m` before its line with no vehicle ahead of it there, and goes when it crosses the line |
| `box_clear` | no two NPC vehicles on crossing paths through the box (from where each entered it to where it left, or leaving by the same lane) are in the box at once |
| `stop_wait` | no NPC vehicle waits more than `max_s` from its arrival to crossing its stop line |
| `hits` | every damaged event on the listed people dealt by the player has `amount` equal to `damage`, at least `min_hits` of them; on a hit that does not kill, the person's health falls by the amount (from `start_health`, 100 by default); the person's died event comes on the hit that takes its health to 0 and no hit after it; with `per_round`, no round lands more than that many hits |
| `fire_rate` | rounds leaving the magazine (or, with `blows`, the player's hits on the listed people) come at `rate` per second within `tol`: the count less one over the time from the first to the last |
| `reload` | from the first mark (`start` `mark`) or the first tick after it with the magazine empty (`start` `empty`), the magazine rises `reload_s` later within `tol`, to `magazine` or by the whole reserve (one less when a round leaves in that same tick), and the reserve gives exactly what the reload moved |
| `ammo_flow` | every change of the ammo in the state report is a round (the magazine down by one, the reserve unchanged) or a reload (the magazine up, the reserve down as much, or one less up when a round leaves in that same tick), with at least `min_rounds` rounds and `min_reloads` reloads |
| `dry_fire` | with the magazine and the reserve empty at the first mark, the ammo stays empty and nobody takes a hit from the player until the second |
| `aim_pose` | on every frame, the `RightHand` is within `hand_m` of the height of `RightUpperArm`, and the forearm (`RightLowerArm` to `RightHand`) points within `max_deg` of the direction from the hand to the state report's aim point |
| `lock_on` | on every frame, the aim point is within `aim_m` of the target's `Chest` bone and that bone lies inside the middle `middle` of the view (by width and height, the camera's `fov` vertical, the view's `aspect`) |
| `hit_rate` | over `bursts` (`from`, `to`, `target`), of the rounds that left the magazine while the target stood (alive, not limp), at least `min_share` landed on it (its damaged events from the player, until `grace_s` after the burst) |
| `untouched` | the player fires at least `min_rounds` rounds and none of the listed people takes a hit |
| `cover_enter` | from the mark where `cover` is pressed, within `within_s` the state report's `cover` is true with the player within `near_m` of the box and the `Hips` at most `ratio` of their standing height (at the mark) above `ground_y` |
| `cover_hold` | on every frame `cover` is true, the player within `near_m` of the box and the `Hips` at most `ratio` of their standing height (read at `standing_mark`) above `ground_y` |
| `cover_leave` | from the mark where a move away from the box is pressed, `cover` turns false within `within_s` and stays false, and at the second mark the player is more than `near_m` from the box |
| `lean_out` | from the mark where `aim` is pressed in cover, the `Head` bone rises at least `rise_m` within `within_s` with `cover` still true, and between `fire_from` and `fire_to`, in cover, a round leaves the magazine |
| `cover_cuts` | two windows of equal length in separate game processes (`open` and `cover`, each with `from`, `to` and the `attackers`): the damage those attackers deal the player in the cover window is at most `max_ratio` of the open window's, which holds at least `min_open_hits` hits |
| `armour_split` | for every damaged event on the player, armour falls by `share` of the hit's amount (within a point) until it runs out and health by the rest (within a point), from the values before the hit; at least `min_armoured` hits while armour lasted and `min_bare` after |
| `turn_hostile` | the listed people's `hostile` metadata turns true within `within_s` of the trigger: with `trigger` `hit`, the first damaged event the player deals one of them; with `aim`, `after_s` after the first mark, and none turns hostile before that |
| `flee_away` | each listed person ends at least `min_m` farther from the player (horizontally) within `within_s` of its `hostile` metadata turning true, still `hostile` |
| `reach_cover` | within `within_s` of the first of `crew` turning hostile, at least `min_share` of the hostile `enforcers` stand at some moment within `near_m` of one of the `boxes` |
| `retreat` | each listed enforcer whose health drops below `below` (alive) ends at least `min_m` farther from the player within `within_s` |
| `fires_at` | each listed attacker that comes within `max_m` of the player lands at least `min_hits` hits on the player |
| `gunshot_flee` | the first round after the first mark is the shot; each listed person on foot within `near_m` of the player at the shot (and not limp, dead or seated meanwhile), from `start_s` to `end_s` after it, moves at least `min_mps` on average, ends at least `min_gain_m` farther from where the player stood, and gets farther over at least `min_share` of the half seconds |
| `crime_event` | a `crime` event of `type` comes within `within_s` of mark `at` (default the first mark), its `witnesses` listing everyone of `seen_by` and none of `not_seen_by` (`witnessed: false`: an empty list); with `count`, that many events of the type between the marks |
| `alert_rise` | after the first `crime` event of `type`, the level rises to `level` (an `alert_changed` event, and the state report) from `min_s` to `max_s` after it |
| `alert_steady` | between the marks the level stays `level`: no `alert_changed` to another level, and the state report agrees |
| `alert_sequence` | the levels the `alert_changed` events take between the marks are `levels`, in order |
| `alert_levels` | at each mark of `at` (`{mark: level}`) the state report shows that level |
| `police_arrival` | the first police unit (a police vehicle, or an officer on foot; those in `ignore` aside) gets within `reach_m` of the player within `within_s` of the level's first rise; none is within `clear_m` when it rises |
| `police_count` | within `by_s` of the level's first rise, the police vehicles moving towards the player or within 100 m number at least `count`; after that, those within 100 m and the dispatched ones moving towards the player number at most `count` plus `over` |
| `police_origin` | every police unit new after the level's first rise first shows at least `min_m` from the player and outside the camera's view (officers in a vehicle judged by it) |
| `police_kinematics` | police units move no faster than 1.1 times their model's top speed (`top_kmh`) or, on foot, FT-1's sprint (`foot_mps`), and never stand inside a building (`buildings`) |
| `roadblock` | within `within_s` of the level reaching 3, while the player drives, at least two police vehicles stand below 1 km/h for 2 s across a road of `roads` (each within 30 degrees of square, middles within 8 m of one cross-section), covering 70% of its carriageway, within `ahead_m` ahead of the player by road (`reach`) |
| `arrest` | with the level at 1 or 2 and `officer` within `near_m` of the still player, `arrested` comes from `min_s` to `max_s` after the later of the two; with `expect: false`, no arrest between the marks |
| `came_back` | within `within_s` of the first `arrested` (or the player's `died`), a `teleport` and a `respawned` naming `poi` come, the player within 2 m of `respawn`; a second later, level 0 and the `fine` lost (or all the money), and the `weapons`, `health` and `armour` given |
| `escape` | the level stays above 0 until `cooling_s` after mark `anchor` and drops to 0, reason `escaped`, by `cooling_s` plus `slack_s` after it |
| `police_force` | below level 3 (and for 2 s after a drop below it) no police officer hits the player or is `hostile`; with `fight: true`, from level 3 with an officer within 40 m, an officer lands a hit within `within_s` |
| `left_alone` | from 10 s after the level returns to 0, no unit that responded keeps moving towards the player for more than 10 s, and no officer on foot stays within 5 m of the player for more than 5 s (`exempt` points aside) |
| `alert_honest` | every rise of the level follows a crime seen by police at most 1.0 s before it, or by others 10-11 s before it, to the level AL-4 gives; drops go to 0 only, with reason `escaped`, `arrested` or `died` |

A police unit is a police vehicle (`police`, `tactical_van`; not a wreck, nor one carrying the player) or a police officer on foot; it moves towards the player when its horizontal distance to them has fallen by 2 m or more over the last 2 s (AL-6). A road of `roads` is `{"id", "pts": its centre line [[x, z], ...] from end a to end b, between the junction boxes, "width": its carriageway}`; `reach` gives, for a road and the way the player drives it (`"road|ab"`), the metres by road from its far end to the entry end of each road the player's vehicle can reach.

A box is a solid placed with `prop.spawn`: `{"p": the middle of its base, "size": [width,
height, depth], "heading": degrees}`, its depth along the heading (chapter 17). An `area` is a
map of the streets around a place, worked out from the plan: its lanes (`id`, centre line `pts`
from the start box to the stop line, `width`, `limit_kmh`), its carriageways and junction boxes
(`roads`), its crosswalk bands (`crosswalks`: `id`, `intersection`, `control`, `walk_signals`,
`poly`), `blocks`, building footprints (`buildings`) and interior `rooms`, every polygon a list of
`[x, z]` corners. An approach's stop line is `{"intersection", "approach", "line": [[x, z], [x,
z]], "toward": [dx, dz]}`, the line across the lanes that arrive and the direction of travel
towards the junction. QA reads speeds from positions, counts people and vehicles with the
`vehicle` and `seat` metadata (AC-5), and takes each collision shape as the box the shape's own
mesh fills (exact for a box shape, a little larger for rounded ones). A program is a
junction's plan program in ticks: `{"offset", "cycle", "phases": [{"start", "green_end",
"amber_end", "green", "walk"}]}`, phases in order from program time 0. In fights, QA counts a
round each time the state report's magazine drops (by one per round), reads every hit from its
`damaged` event (AC-13: the hit's damage, the values after it, the attacker's id as `source`)
and names people by the ids the commands that placed them answered with.

You can add playtests of your own in the same format and run them with
`qa run path/to/file.json`.
