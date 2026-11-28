# Phase 1h report: the traffic-density margin and a sweep of every band, combat (WS6 module 6), traffic hidden instances (2026-11-26)

Author notes, never packaged. Brief: `harbor-lh/ops/swe-marathon-v2/next-tasks/game-phase1h-BRIEF.md`.
Branch `neel/game-phase1` (worktree `swe-m2-pr-game-phase1`). macOS only (Apple M5 Pro, 24 GB,
shared). No downloads, no Docker, no Linux VM, no Oddish.

Every Godot run went through `scripts/heavy.py` (one exclusive lock, then at least 30% free memory
per `memory_pressure`), and every game process re-checked through the kit's gate
(`QA_MEM_FLOOR=30`); from 2026-11-27 every run also took the shared heavy lock that every campaign
on this Mac uses (`scratchpad/heavy-docker.lock`, taken only at 30% free). Free memory sat at 24-40%
(other work on this Mac held several GB: two virtual machines, Docker's backend, editors; swap
nearly full), and runs waited whenever it dipped under 30%. The author stopped at a usage limit
around 2026-11-27 01:30 UTC with the final runs on `943dec9` done (the coordinator committed this
report as checkpoint `5df5542`) and resumed at 14:50 UTC. A helper (opus) built the traffic hidden
instances on files of its own and queued its Godot runs through the same lock; its instances found
four reference defects and a gap in the GDD, all fixed (section 8). Three judges (opus,
sonnet, haiku) settled how QA observes combat; an independent read (sonnet) read the
developer-facing changes as the developer would. Every child process was stopped by its task or
process group; a debug run made obsolete by a fix was stopped before it started Godot.

## 1. The traffic-density margin

### What was wrong

Phase 1g's day-flow playtest (j_34, 08:00, clear, variation 12) measured 16.5, 10.0 and 16.0 moving
vehicles per minute against 10-30. The design asks the reference to sit at least 15% of the band's
width inside each edge (13-27 here). A six-minute run of the same start, with the reference's
density controller printing its counts every second, showed why:

- the controller kept every vehicle within 150 m, moving or not, under 2.2 times the table's middle
  (44 cars), and added cars only while fewer than the middle (20) moved. The cap was full nearly all
  the time (40-44 cars within 150 m);
- j_34 and its four neighbours run the plan's long programs (four approaches green one at a time for
  12 s, then a 7 s walk phase: a 75 s cycle), so about 26 cars stood at any moment: 21 at the four
  neighbouring signals 95-150 m out (j_33, j_24, j_44, j_35), only 4 at j_34. New cars come in on
  lanes leading inwards, out of sight at 95-150 m, and meet a red light there;
- moving cars therefore swung between 6 and 27 with the cycles: minute medians 16.5, 10.0, 16.0,
  16.0, 15.5 and 16.0.

### The fix (reference `6e76f2f`)

While fewer than the table's middle move and the cap is reached, the controller removes one car
standing out of sight 95-150 m away (waiting at a line or in a queue; TR-15 lets cars go beyond
80 m out of view), and the room goes to a new car that moves. Nothing else changed: the same cap,
spawn rules, removal distances and route choice. A first variant also kept new cars off spots
shortly before a red light; it fed j_34's arms harder, their queues spilled back over the
neighbouring junctions (stops of 90-178 s at j_44's east approach), and it was dropped. The band and
what the playtest measures are unchanged, so no panel was needed.

### Re-measured

FILL-DENSITY

## 2. The sweep of every band

`scripts/margin_sweep.py` (new) reads what `qa run --json` found, or a grader report with the
instances' play files, and works out every banded value's margin: min(value - lo, hi - value) /
(hi - lo) for a band; for a one-sided limit the room at its one edge (at most hi on a quantity whose
floor is no limit: (hi - value) / hi; at least lo on a share: (value - lo) / (1 - lo); at least lo
on an open-ended quantity: (value - lo) / lo); a value given per person by its worst; a one-sided
pace measured over a banded pace's window (IN-2's sprint over FT-1's) in that band. The camera's
tilt stops (clamped, so exact on any machine), shares that must be 1.0 and a clock read in whole
minutes are listed, not given margins.

| Run | Banded values | Under 15% |
| --- | --- | --- |
| Reference `53192d5`, all 37 playtests | 252 in 167 expectations | **3**: CM-1's camera came 2.914 m from the head at +30 degrees of pitch (band 2.5-6.0: 11.8%) with a running player's hips 0.341 of the way out of the view's middle (at most 0.4: 14.7%); city drivers at 0.95 of the limit (TR-8's at most 1.1: 13.6%) |
| Reference `943dec9`, all 37 playtests | 252 in 167 expectations | **0**; worst 18.2% |
| Reference `943dec9`, the private set (the 40 instances the deadline let run) | 259 in 133 expectations | **1**: the collision at j_73 in day-flow instance `03eaca08` (TR-12: 0.0357 per vehicle-minute against at most 0.02, margin -78.5%), fixed in `8e959f0` (section 8); that instance's third density minute sat at exactly 15.0% (13.0 vehicles), its cause the same |
| Reference `8e959f0` (final), all 37 playtests | 252 in 167 expectations | **0**; worst 18.2% (TR-8 and VH-5) |
| Reference `8e959f0` (final), the private set (all 49 instances) | 391 in 265 expectations | **0**; worst 18.0% (VH-5 in a crash instance: 8.2 km/h against at most 10), then TR-8 in the two arterial instances (0.899 and 0.898 of the limit: 18.3%, 18.4%) |

The fixes (reference `943dec9`), each inside what the rule allows; no band or measurement changed:
- **CM-1:** the camera's pitch now stops at +25 degrees, inside CM-2's -60 to +30 (the reference had
  stopped at +30, and the worst frames were at that stop with the player running): the head stays
  3.446-4.025 m from the camera (27.0%) and the hips 0.291 of the way out (27.3%);
- **TR-8:** the city's drivers aim at 90% of the limit instead of 95%: worst 0.90 of it over 48,008
  samples (18.2%);
- **TR-6** (an order fault rather than a margin, found by the helper's instances): section 8.

The smallest margins on `943dec9`'s playtests: TR-8 18.2%; VH-5's damaged sedan at 8.18 km/h against
at most 10, 18.2%; FT-9's largest hips step in the replay's ragdoll 22.6%; FT-12's 0.45 m from the
obstacle 25.0%; CB-9's turn 0.517 s into the 2 s window, 25.9%; CM-1 27.0%. The sweep's own gaps,
closed on the way (`234caa5`, `877424f`, `0a68e7c`): one-sided limits had been read as bands from 0,
a whole-minute clock as a margin of 0, and a per-person value, the blast's push and a moved check's
zero floor as having no band; IN-2's one-sided sprint (8.50 m/s against "at least 7.40", over the
same window as FT-1's 7.40-9.60) came out at 14.9% on the open-ended measure, where FT-1's band puts
the same value at 50%, its middle; and the distance at which QA presses `jump` before a vault, which
QA's own `wait_for` sets (the player within the drawn 1.0-1.5 m), had been read as the game's margin
(one private instance's 1.397 m against at most 1.5 showed as 6.8%).

## 3. What was built

| Piece | Where (task folder unless noted) | What it is |
| --- | --- | --- |
| Combat (WS6 module 6) | private: `crime-city-reference/overlay/game/combat.gd` (new), `tables.gd`, `person.gd`, `pose.gd`, `world.gd`, `traffic.gd` | Weapons, aiming and lock-on, cover, health and armour, crews' hostility and tactics, the gunshot flight (below) |
| Combat checks (WS4) | `common/kit/qakit/combat.py` (new), `expect.py`, `common/kit/README.md`, `checks/test_combat.py` | 21 checks: `hits`, `fire_rate`, `reload`, `ammo_flow`, `dry_fire`, `aim_pose`, `lock_on`, `hit_rate`, `untouched`, `cover_enter`, `cover_hold`, `cover_leave`, `lean_out`, `cover_cuts`, `armour_split`, `turn_hostile`, `flee_away`, `reach_cover`, `retreat`, `fires_at`, `gunshot_flee`, each with hand-made frames it holds on and one it fails on |
| QA's aiming bot (WS4) | `common/kit/qakit/play.py`, README | A step, `aim_at`, that holds `aim` and turns the camera with the look actions until the state report's aim point lies on a person's bone (the panel's Q4): the long guns' ranges need aiming beyond lock-on's 30 m |
| Playtests (WS4) | `common/kit/playtests/`, `scripts/make_playtests.py` | `combat.weapons/range`, `combat.lock_on/targets`, `combat.armour/hits`, `combat.cover_firefight/low-wall`, `combat.crew_hostility/turf`; `traffic.panic_horn/sidewalk-and-horn` gains the gunshot flight (TR-13) |
| Clarifications | `common/design/GDD.md`, `notes/PHASE1-PLAN.md` | Chapter 8 and the rules around it, from the panel and the independent read (section 6); TR-5's portal approaches; the coverage map's combat rows |
| The band sweep | `scripts/margin_sweep.py` | Every measured value with a band, from `qa run --json` or a grader report, and its margin |
| Hidden instances (WS8, the helper) | private: `tests/private/templates/`, `tools/build_templates.py`; public: `scripts/check_disjoint.py`, `checks/test_disjoint.py`, `scripts/make_instances.py` | Templates for the five traffic playtests, 10 instances (49 in all), disjointness rules 11-13 (section 8) |
| Acceptance tool | `scripts/phase1h_acceptance.py` | `qa` (keeping what qa run found, for the sweep), `grade`, `private`, `replay10`; family D for combat |
| Panel | `harbor-lh/ops/swe-marathon-v2/decisions/2026-11-26-game-combat-observables-*.md` | Seven questions on how QA observes combat |

## 4. Combat in the reference (private, `53192d5` and the fixes after it)

- **Weapons (CB-1 to CB-3).** The table in `tables.gd`. `attack` held fires in the tick it goes
  down and every 60 / rate ticks after: 20, 5, 50 and 10 ticks for the pistol, SMG, shotgun and
  rifle, 30 and 48 for the fists and the bat, so the rates are exact. A shot is a ray from the gun
  hand (`RightHand`) towards the aim point; the first thing it meets takes it, and a person met
  within the weapon's range (position to position, as the GDD now says) takes the table's damage.
  The shotgun fires eight pellet rays of 10 in a 3 degree cone. A melee blow strikes the nearest
  person within reach and 60 degrees of the attacker's facing. An empty magazine reloads by itself,
  `reload` reloads a part-used one, in one go after the table's time. `weapon_next` and
  `weapon_prev` cycle the owned weapons in table order, wrapping round, 0.25 s a switch.
- **Aiming (FT-11, CM-5, AC-12).** Holding `aim` with a gun raises the right arm by two-bone IK
  along the line from the shoulder (`RightUpperArm`) to the aim point, at 0.99 of the arm's reach:
  the hand 0.01-0.11 m from shoulder height, the forearm 8 degrees off the line to the aim point. The
  aim point is the first thing the camera's centre ray meets (300 m out when nothing). Pressing
  `lock_target` locks the nearest standing person within 30 m and 45 degrees of the camera's
  forward, hostile people first, while it is held: the camera looks past the player at the target's
  `Chest`, which is the aim point, and the player faces it.
- **Cover (FT-12, CB-8).** `cover` looks for an obstacle 0.8-1.4 m high within 1.5 m (rays out at
  0.5 m in 24 directions, a ray down for the height), moves the player crouching to 0.45 m from its
  face over 0.5 s and holds the player there; a move away from it leaves cover. Holding `aim` in
  cover stands up to lean out (the head rises about 0.68 m).
- **People (CB-5, CB-7, AC-13).** 100 health each. The player's armour takes 60% of each hit
  (rounded) until it runs out. Every hit is a `damaged` event with the hit's damage, the values
  after it and the attacker's id. Health 0 is `died` and the ragdoll.
- **Fights (CB-9).** A hit on a crew member, or the player aiming a gun inside the crew's turf for
  more than 5 s, turns every member of that crew within 100 m hostile half a second later (inside the
  GDD's 2.0 s, and clear of the 5 s mark). `guard` and police people the player hits turn hostile;
  others run, but `idle` ones stand still (chapter 17). Hostile enforcers make for the far side of
  an obstacle 0.8-1.4 m high within 15 m, crouch there and stand up to fire at a player within
  40 m and in sight, from a raised gun, every 0.75 s, hitting more often the nearer the player is
  (0.62 less 0.012 per metre, kept to 0.2-0.6). Below 30 health an enforcer falls back until it is
  15 m farther from the player. Hostile lookouts run 30 m away from the player; unarmed hostile
  people close in and punch.
- **Gunshots (TR-13).** Every round sends the people on foot within 30 m (crews and police aside)
  running for 13 s, along the sidewalk they stand on, whichever way keeps taking them farther from
  the shot over the whole run (looked ahead every quarter second), else straight away.

What the playtests found on the way, all fixed: a reload with `attack` held fires in the very tick
the magazine refills, which the reload and ammo checks first read as a broken reload (the checks now
allow one round in that tick, and the GDD says a reload refills in one go); the hits check first
followed a target's health through the player's hits only (another attacker's stray round would
have broken it; it now follows every hit); in the first firefight the player kept leaning out (aim
held) through the ten seconds after the wounding and was shot dead, so the kill then locked onto
the wounded attacker; enforcers firing from their hanging hand behind their own wall never saw the
player (shots now come from a raised gun, an arm's length from the shoulder towards the target);
three rounds through the van needed a reload first; and the lock-on playtest's ten pistol rounds
began on a part-used magazine (7 fired before the reload) while a person from its first part, running
from the earlier shots, crossed the cone 14.8 m out, nearer than the 15.0 m target, and took the
lock (the playtest now reloads before each gun's rounds and resets the world before them).

## 5. The panel

Three judges (opus, sonnet, haiku), each given the same facts and options, voted independently
(record: `decisions/2026-11-26-game-combat-observables-DECISION.md`, the brief and the three votes;
sonnet answered in its reply and the author copied it into its file):

| Question | opus | sonnet | haiku | Decision |
| --- | --- | --- | --- | --- |
| Q1 what a `damaged` event says | A | A | A | **A**: the hit's damage before armour, the values after it, the attacker's id as `source`; one event per hit on anyone |
| Q2 the shotgun's pellets | A | A | A | **A**: each pellet that hits is a hit of 10; rate, magazine and reload count rounds |
| Q3 FT-11's hand and bones | A | A | A | **A**: guns in the right hand; `RightHand`, `RightLowerArm`, `RightUpperArm` |
| Q4 aiming beyond lock-on's 30 m | A | A | A | **A**: QA's bot turns the camera until the reported aim point is on the target; a hit just inside the range first |
| Q5 CB-9's times and moves | A | A | A | **A**: hostile within 2.0 s of a hit, not before 5.0 s and by 7.0 s of aiming; flight and retreat measured from the player |
| Q6 CB-8's "same attackers, same time" | B | B | B | **B**: two runs from one start (a restart), the same span from the moment `cover` is true |
| Q7 TR-13's gunshot flight | B | B | A | **B**: from 2 s to 12 s after the shot: 3 m/s on average, 20 m farther, farther on 90% of the half seconds |

## 6. Clarifications (no new features: 177 rules; the coverage map 0 problems)

From the panel's decisions and the judges' OTHER lines, the independent read, and the helper's
instances:
- **Chapter 8's introduction:** health and armour are whole numbers; guns are held in the right hand.
- **CB-1:** a weapon's range is from the attacker's position to the position of the person hit; a
  round or blow that reaches a person beyond it is no hit and no `damaged` event; the shotgun's round
  is eight pellets of 10, each a hit; the rate counts rounds (guns) or blows that land (melee); a
  reload refills in one go, timed from the `reload` press or the empty magazine to the refill.
- **CB-5:** 60% is rounded; with less armour left, the armour takes what it has and health the
  rest; armour takes weapon hits only.
- **CB-8:** the two runs from one start; the open run stands a step behind the obstacle, not in
  cover; the damage is the sum of the hits' amounts, so cover works by keeping hits off.
- **CB-9:** attacking is hitting; hostile within 2.0 s of a hit, and after aiming more than 5 s in
  one go inside the turf (not before), whatever the behaviour; a fight starts with the first member
  turning hostile; an enforcer in sight within 40 m lands a hit within 15 s; cover counts at any
  moment of the 10 s; lookouts keep `hostile` while fleeing and end 20 m farther from the player
  within 10 s; a retreat ends 10 m farther within 10 s.
- **FT-11:** the bones of the right arm, every gun, from 0.5 s after `aim` is pressed.
  **FT-12:** distances horizontal to the obstacle's nearest point; leaning out is still cover (the
  hips clause holds without `aim`); a move away leaves cover within 0.5 s.
- **CM-2:** the look actions turn the camera in proportion to their strength. **CM-5:** the target's
  `Chest` is what the view's middle holds; distances horizontal; the lock holds from 0.5 s after the
  press.
- **TR-13:** a gunshot is a round leaving a magazine; those who run are people on foot other than
  crews, police and anyone fighting; the measure (2-12 s, 3 m/s, 20 m, 90%); TR-9 and TR-10 do not
  bind people while they run.
- **TR-5 (the helper's finding):** the green flow leaves out an approach whose lanes start at a
  highway portal (WD-9): with no next map yet, nothing could feed it without appearing within 80 m.
- **AC-5:** a crew member that turned hostile keeps `hostile`. **AC-12:** `aim` while `aim` or a
  lock-on is held is the first thing the line of aim meets, at any distance; locked on, the point
  aimed at on the target. **AC-13:** the `damaged` event's fields as the panel set them.
  **`player.give`:** a gun the player did not own comes with a full magazine, in hand.

## 7. Independent read

An independent read (sonnet) of the GDD diff, the README diff, the five combat playtests, the panic
playtest's gunshot part and the new checks found **no evaluation wording**. Its fairness findings,
all fixed before the final runs (`ba262bb`): a given gun's full magazine and a reload before the
long guns' range shots; no `damaged` event beyond the range; lock-on judged from 0.5 s after the
press (it had been 0.17 s; the hit-rate rounds now fire 0.5 s after it too); CB-8's damage as the
hits' amounts and its open run described as the playtest stages it; the hit landed within 15 s
for "fires at"; the aim point when locked on (the hit point on a body would sit a capsule's radius
from the `Chest`); `hostile` for fleeing lookouts; the last armour hit; the one-go reload; ten
single rounds per gun for the hit rate (six left a 70% shooter failing a quarter of the time); the
wound and the kill from cover aimed by QA's bot rather than by whom lock-on picks; `"kind": "pre"`
explained in the README; notes that give their numbers. Its deadzone point needed no change: the
kit presses actions at a strength, and CM-2 now says the look turns in proportion to it.

## 8. Hidden instances for the traffic playtests (WS8, the helper)

Templates (`tests/private/templates/`, built by `tools/build_templates.py --only intersection_flow
stop_junction obstacle speed_limits panic_horn`); each draws its variation from 18-9999, and never
the playtest's junction, corner, clock band, lane or sidewalk:
- **day flow:** a corner of any approach of the 14 other signalised junctions (52 corners, both
  districts); a day, evening or night clock with the whole watch inside one period (three counted
  minutes, two in the evening); clear or overcast; chapter 7's bands for that district and period.
  Green flow is checked by day only, through a new `when` key on an expectation
  (`scripts/make_instances.py`), and leaves out approaches fed from a highway portal;
- **four-way:** any of the 44 other all-way stops, T-junctions and two-lane one-way approaches
  among them: the playtest's four waves of 12 cars with drawn models and chapter 3's drivers,
  25-40 m out, drawn gaps, any clock and weather;
- **lane blocked:** 120 layouts round a junction: a prop (5 kinds, drawn size), a person or a parked
  vehicle 40-80 m ahead of a car on its own lane;
- **arterials:** another signalised junction's 130 m street map, four cars sent through;
- **sidewalk, horn and gunshot:** another sidewalk side, either way, at 22-29 or 31-36 km/h past
  two people; the horn's person 5-19 m ahead; the gunshot flight from the ring's opposite side with
  six people 6-24 m away (the 28 m reach and the 2-12 s, 3 m/s, 20 m and 90% measure kept).

300 self-check expansions per template found no problem and no repeat, and all five rebuild
byte-identical from public `453249f`. `scripts/check_disjoint.py` gains rules 11 (the same
stop-line junction watched, or a street map centred within 1 m), 12 (a density watch whose clock
lies within 30 game minutes) and 13 (with a lane or sidewalk check in both, a person, vehicle or
prop placed on a lane or sidewalk the playtest uses), each with must-fail and must-pass cases
(`checks/test_disjoint.py`). Private set: 10 new instances, 49 in all (A 18, B 6, C 12, H 5, K 4,
M 2, T 2; the 39 earlier plays byte-identical); 48 compared with their playtests, 0 repeat one
(the plan swap has no playtest).

What the instances found, all fixed: a vehicle that `vehicle.spawn` gave a paramedic, police or
tactical driver never drove (reference `53192d5`, TR-16's driving archetypes); a person could step onto a
crosswalk on don't walk with too little of the walk phase left (`53192d5`); a car that reached an
all-way stop alone was given its turn at once, so a car arriving on its right within 1.0 s lost
the tie (`943dec9`, TR-6); an approach fed only from a highway portal cannot be fed out of sight
without the next map, so TR-5's green flow now leaves such approaches out (GDD); and, in the final
acceptance on `943dec9` (section 9), day-flow instance `03eaca08` (j_74 by day) caught a collision at
the all-way stop j_73, 98 m north (reference `8e959f0`, below).

**The collision at j_73 (TR-12, TR-7).** Right turns out of the tight corners of the one-lane
streets swing over the centre line of the street they turn into, so a car stopping on the approach
beside such a turn stays back out of the swing while one may come. A sports car had stopped back for
a smaller car's swing (its front 6.75 m along the exit lane, just past a hatchback's 6.5 m), its
middle 4.4 m short of its line, so it never
counted as arrived (TR-6 counts a vehicle's position within 4 m) and never queued. An SUV then came
to the one-way feeder's line to turn right; its swing (10 m) took in the sports car. The SUV waited
for its swing to clear, the sports car stayed back for the SUV, and after 15 s the SUV was forced:
it swung 1.5 m wide and hit the sports car (1 collision, 0.0357 per vehicle-minute against at most
0.02; 2 lane-keeping samples against the traffic; the third minute's density fell to 13.0). The
fix: at an all-way stop, a car held back for a narrower swing that finds itself inside a wider one,
whose turn has not yet been given its way, goes on to its line and takes its turn there (the
turn waits for it, as it already did for a car standing in its swing at the line); a turn that
waited 15 s is no longer forced into a car on its way into the junction that is still getting out
of its way (moving up to its line, or queued there less than 5 s); and a turn that waited 25 s goes
in any case (TR-6's limit is 30 s). Two other designs were tried on the way and dropped: holding
cars back only for turns already given their way gridlocked the all-way stops (four right turns
each in another's swing, waits of 107-159 s in all three four-way plays); and counting a car as
arrived by its front broke TR-6's full stop (the kit, like the GDD, counts the vehicle's position).

On `53192d5`, one by one, 8 of the 10 new instances held every expectation; the two four-way
instances failed TR-6's order (the tie above). Their margins there: density 43.75-50% (20-21
moving vehicles and 40 people at j_74 by day; 16-17 and 30 at j_36 in the evening), speeds at most
0.948 of the limit, waits at most 17.0 s, the flight at 5.42-5.48 m/s gaining 40.7-56.4 m, the
horn's person out of the lane in 0.28-0.33 s, cars stopped 2.22-2.47 m short. The grade of the
private set on `53192d5`: 0.994681 (C 0.972222, every other family 1.0; self-test passed, import
5.21 s, boot 1.475 s solo and 1.177 s server, 2878.5 s in all, game processes 151.0-171.1 MB).
Private commits `f42efc8` (templates, 10 plays, 49 instances) and `202f796` (those results); the
bundle is refreshed. The helper's own grade on `943dec9` was void (its import gate timed out at
600 s: 410 s of CPU and 1.18 GB on one 12 KB texture with 25-28% free, where the same files had
imported in about 5 s), so the private set's result on `943dec9` is the one in section 9.

## 9. Acceptance results (macOS)

### On `943dec9` (2026-11-26 20:38 to 2026-11-27 03:39 UTC)

The first full set of acceptance runs, on reference `943dec9` and the starter, with the kit at
`453249f`, ran through the task's heavy lock with free memory at 24-30% almost throughout: every
game process waited for 30% free before it started.

| Run | Result |
| --- | --- |
| `qa run`, all 37 playtests | Reference: **37 of 37 hold** (9,136 s, almost all of it waiting for memory; the import with QA's telemetry took 788.7 s against about 5 s normally). Starter: all 37 list what did not hold, 0 runs stopped (93.4 s) |
| Reference, every playtest as the instance set | **0.757062**, but only because the grader's 80-minute deadline came first: 30 of 37 instances run, all at 1.0; the 7 not run (vehicle service handling, the clock, the plan, both replays, the same start, the weather) scored 0. Self-test passed (133.5 s), import 4.99 s |
| Starter, same set | **0.000000**: static and import gates pass (import 126.8 s), the boot gate fails as before |
| Reference, the private set (49) | **0.706028**, the deadline again: 40 of 49 run, 39 at 1.0 and `traffic.intersection_watch/day-flow/03eaca08` at 0.8 (the collision at j_73, section 8); import 4.17 s |
| Starter, the private set | **0.000000**: its import gate failed for the host (2,046 s against 600 s) |
| Ten replays of each replay playtest | `world.replay/car-and-ragdoll`: **1** hash over 10 runs (535 frames, 0 errors); `world.replay/two-paces`: **1** hash over 10 runs (78 frames, 0 errors) |
| Density, six minutes at j_34 by day (variations 12, 31, 57) | every minute 18.0-21.0 moving vehicles (band 10-30) and 40-43 people (band 20-60) |

The deadline cut is the Mac's memory, not the game: the release grader runs on its own machine.
For the final runs the acceptance tool passes the grader a longer deadline (`--deadline-s`, `1603ec7`),
so every instance runs here.

### On `8e959f0` (final, from 2026-11-28 03:37 UTC)

Each part a heavy job of its own (the shared lock and the task's lock, 30% free), the reference
staged from `git archive 8e959f0`, the kit at `1603ec7`.

| Run | Result |
| --- | --- |
| `qa run`, all 37 playtests | Reference: **37 of 37 hold** (595.3 s; the import with QA's telemetry 6.3 s). Starter: all 37 list what did not hold, 0 runs stopped (85.2 s) |
| Reference, the private set (49 instances: the 10 new traffic instances among them) | **1.000000**: 49 of 49 at 1.0, every family 1.0 (A, B, C, H, K, M, T); static gate (26 own files), import 3.78 s with a 64.27 MB cache, boot passed; 7,985.5 s in all, most of it waiting for memory |
| Starter, the private set | **0.000000**: static (6 files) and import (6.63 s) gates pass, the boot gate fails ("solo not playable within 60 s", "server not playable within 60 s"); 247.2 s |
FILL-ACCEPTANCE

## 10. The playtests and their status

| Playtest | Rules | Reference (`943dec9`) | Starter | In the reference's required set |
| --- | --- | --- | --- | --- |
| `combat.weapons/range` (new) | CB-1, CB-2, CB-3, CB-7, FT-11 | holds (46 expectations) | does not hold | yes |
| `combat.lock_on/targets` (new) | CM-5, CB-4, CB-7 | holds (6) | does not hold | yes |
| `combat.armour/hits` (new) | CB-5, CB-9 | holds (2) | does not hold | yes |
| `combat.cover_firefight/low-wall` (new) | FT-12, CB-6, CB-7, CB-8, CB-9 | holds (11) | does not hold | yes |
| `combat.crew_hostility/turf` (new) | CB-9, AC-5 | holds (6) | does not hold | yes |
| `traffic.panic_horn/sidewalk-and-horn` (the gunshot flight added) | TR-13, TR-14 | holds (4) | does not hold | yes |
| the 31 other playtests of Phases 1c to 1g | as before | all hold | all report failures | yes |

The 37 playtests cite 83 rules, 11 of them new (CB-1 to CB-6, CB-8, CB-9, CM-5, FT-11, FT-12;
CB-7 and AC-5 were cited before), each by at least one expectation. CB-10 waits for the police
(module 7). The counts leave out the four standing expectations every playtest carries (the
process, telemetry, registry and events).

## 11. What still needs Linux

Everything on Phase 1b's to 1g's lists still applies:
- the `.so` (with the seat and shape reads), the cgroup sandbox and the unprivileged user, a real
  fork bomb, `/proc` readings;
- the starter in the agent image, `qa run` with Python 3.12, the ENet server in a container;
- the verifier image's paths, the world builder and replays on x86_64 (animation, IK, vehicles,
  traffic), import and boot on a cloud vCPU, the plan-swap instance in the verifier image;
- calibration of the people, vehicle and traffic bands (WS9) and the grading time of the traffic
  playtests.

This phase adds:
- **Combat on x86_64.** Hits are ray casts against the people's capsules, the shotgun's pellets
  and the hostile people's misses come from the seeded generator, and QA's aiming bot closes its loop
  on floats: the weapon, lock-on, armour, cover and crew playtests need a run on the verifier's CPU,
  and the deterministic replay (AC-17) should gain a firefight once it does.
- **The band sweep on x86_64.** `scripts/margin_sweep.py` over a `qa run --json` and a grader report
  made there: every band's margin on the verifier's CPU (the macOS sweep is in section 2).
- **Density on a slower CPU.** The controller now works on the moving count each half second;
  measure the day-flow minutes and the traffic instances' bands on a cloud vCPU.

## 12. Not done in this phase

- **CB-10** (police force by alert level) and the crimes combat commits (`shots_fired`, `assault`,
  `murder`, AL-1) wait for module 7 (crime and police); the coverage row stays on its R template.
- **Combat's hidden instances** (family D): the five playtests' templates (other weapons, distances,
  places, crews, obstacles) are the next WS8 step.
- **A replay with a firefight** in `world.replay` (AC-17) with the combat generator in it.
- From earlier phases: top speed's check (a 1.5 km straight comes with the highways and Sable Hills),
  VH-7 to VH-12, WD-9, WD-10, FT-7, AC-11's look parameters, `inv.damage_honest`, TR-2 and TR-3's
  expectations.

## 13. Next workstream

**WS6 module 7, crime and police:** the crime table (AL-1) on top of combat's events, witnesses and
sight ranges (AL-2 to AL-5), the response (AL-6, AL-7), roadblocks, arrest, death and escape (AL-8 to
AL-12) and CB-10's police force by level, with the alert playtests and `inv.alert_honest`.
Alongside it: combat's hidden instances (family D), a firefight replay, and the Linux items above
on an x86_64 machine (the owner's call).

FILL-COMMITS
