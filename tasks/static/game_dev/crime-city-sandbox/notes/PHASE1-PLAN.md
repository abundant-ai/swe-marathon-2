# Crime-city sandbox: Phase 1 build plan and hardening (author notes)

Written 2026-11-26 for sheet row 11. Author-only: this folder is never packaged, copied into an
image or shown to the developer. Technical names (grader, hidden instances, reward) are fine here
and nowhere in agent-facing files.

Inputs: the design (`harbor-lh/ops/swe-marathon-v2/next-tasks/game-design.md`), the kickoff
decision (`decisions/2026-11-20-game-kickoff-DECISION.md`), Phase 0 (`../spike/PHASE0.md`), the
Phase 1a brief, `CHECKLIST.md` Part 1, and these overrides of 2026-11-24 to 11-26:
- no task-side timer of any kind; the session ends at `timeout_sec`, so the game must be committed,
  importable and bootable at every moment;
- one flat single-step task;
- no evaluation vocabulary anywhere the developer reads (`scripts/check_agent_text.py`);
- every GDD rule exercised by a check that fails when the feature is missing, and every stated
  restriction verified (the coverage map below, enforced by `scripts/check_coverage.py`);
- `solution/` holds the reference as readable source;
- an original game with placeholder names.

Status after Phase 1a: GDD v1 (`common/design/GDD.md`, 177 rules), the plan format
(`common/design/plan/FORMAT.md`), the Downtown core block (`common/design/plan/downtown.json`),
its generator and checker (`scripts/gen_plan.py`, `scripts/check_plan.py`), and this plan.

## 1. Reward, families and the check catalog

### Reward

```
reward = G_static * G_import * G_boot * sum_f( w_f * S_f )        sum of w_f = 1
S_f    = (1 / N_f) * sum_i s_i                                     N_f fixed per release
s_i    = 0 if a precondition or an invariant fails on instance i, or the game crashes or hangs
       = sum_j w_ij * pass_ij / sum_j w_ij over the assertions that apply, otherwise
```

- **Gates** (multiply; a failed gate makes the reward 0): `G_static` (no C#, no native code, project
  settings, the InputMap, the originality denylist), `G_import` (a clean import within 10 minutes
  and an own cache under 1 GB), `G_boot` (solo and server reach a playable world within 60 s,
  `state` answers, a player is registered). Booting earns nothing, so the starter scores 0.
- **Invariants** run on every instance; a failure zeroes that instance.
- **Retries:** an instance tagged physics-sensitive that scores below 1 reruns once with the same
  draw and keeps the higher result; at most 15% of instances.
- **Evaluation errors** (our grader, proxy or probe failing through our fault, failed self-test)
  write no reward. Anything the game causes (crash, hang, broken import, stalled probe, proxy-breaking
  traffic, oversized cache, slow game) is a candidate failure and scores 0 for what it breaks.

| Family | Weight | Hidden instances (planned) |
| --- | --- | --- |
| A People and animation | 0.09 | 22 |
| B Vehicles | 0.10 | 22 |
| C Traffic and pedestrians | 0.09 | 16 |
| D Combat and cover | 0.08 | 16 |
| E Crime, the alert level, police | 0.12 | 24 |
| F Missions | 0.11 | 20 |
| G Economy | 0.05 | 10 |
| H World, links, replay | 0.07 | 12 (2 on the alternative plan) |
| I Time and weather | 0.04 | 8 |
| J UI | 0.05 | 12 |
| K Save and load | 0.04 | 8 |
| L Online | 0.12 | 4 sessions |
| M Free play, contract, performance | 0.04 | 3 free-play runs + 4 |

The visual judge stays QA-only (kickoff decision): no weight.

### Check catalog

Kinds: **P** a template with a shipped playtest (fixed parameters on the shipped plans) plus hidden
instances drawn from it; **R** a release-only template (tests a stated rule; no playtest ships);
**G** a gate; **I** an invariant checked on every instance.

| Template | Family | Kind | Sets up |
| --- | --- | --- | --- |
| `gate.static` | - | G | scans the project copy before import |
| `gate.import` | - | G | clean import with the vendor cache supplied |
| `gate.boot` | - | G | solo, server and client processes start with flags |
| `inv.registry` | - | I | every frame's census |
| `inv.teleport` | - | I | player and carrying-vehicle continuity |
| `inv.money` | - | I | money against `money_changed` events |
| `inv.alert_honest` | - | I | every alert change against crimes, witnesses, missions |
| `inv.damage_honest` | - | I | vehicle damage against observed impacts |
| `inv.mission_honest` | - | I | stage changes against observed arrivals |
| `inv.state_honest` | - | I | state report against census, HUD and events |
| `inv.events` | - | I | event schema and ticks |
| `inv.alive` | - | I | process alive, answering, under the memory limit |
| `inv.telemetry` | - | I | probe heartbeat every tick |
| `people.lineup` | A | P | every lead and a sample of archetypes, standing |
| `people.locomotion` | A | P | walk, run, sprint, crouch, turns, camera |
| `people.jump_climb_vault` | A | P | walls 1.0-2.4 m, barriers 0.5-1.0 m, a wall behind the camera |
| `people.swim` | A | P | water edge, swim, ladder and beach exits |
| `people.fall_ragdoll` | A | P | tower drops, get-up |
| `people.vehicle_entry` | A | P | driver and passenger seats, driving camera |
| `people.census` | A | P | district and hour sweeps around the player |
| `people.switch_lead` | A | P | safehouse menu, switch |
| `vehicle.handling` | B | P | proving runs per model, dry and wet |
| `vehicle.crash` | B | P | barrier rams, fire, explosion |
| `vehicle.carjack` | B | P | NPC-driven car, interact at the door |
| `vehicle.motorbike` | B | P | cornering and a crash |
| `vehicle.boats` | B | P | water runs and a beaching |
| `vehicle.ferry` | B | P | timetable, boarding, crossing |
| `traffic.intersection_watch` | C | P | three minutes at a signalised junction |
| `traffic.stop_junction` | C | P | three minutes at an all-way stop |
| `traffic.obstacle` | C | P | an object placed in a lane |
| `traffic.speed` | C | P | NPC speeds on long edges |
| `traffic.panic_horn` | C | P | gunfire, sidewalk driving, the horn |
| `traffic.steady` | C | R | five minutes of steady conditions |
| `traffic.density_profile` | C | R | districts x hours x clear/rain |
| `combat.weapons` | D | P | firing range per weapon |
| `combat.lock_on` | D | P | targets at 15 m |
| `combat.cover_firefight` | D | P | open phase, cover phase, fight, wall shots |
| `combat.armour` | D | P | hits with and without armour |
| `combat.crew_hostility` | D | P | aiming inside a turf, attacking a member |
| `combat.police_force` | D | R | police at levels 1-2 and 3+ |
| `alert.red_light` | E | P | witnessed red light (6 of 8 hidden draws) |
| `alert.unwitnessed` | E | R | the same crimes with no witness |
| `alert.phone_in` | E | P | civilian-only witness, witness killed |
| `alert.crime_table` | E | P | each crime type, escalation |
| `alert.sight_range` | E | R | crimes just inside and outside the range, by weather and hour |
| `alert.response_levels` | E | R | levels 2-5 reached by crimes |
| `alert.roadblock` | E | P | level 3 and a drive |
| `alert.arrest` | E | P | level 1, standing still near an officer |
| `alert.death` | E | P | death during an alert |
| `alert.escape` | E | P | breaking sight, leaving the zone |
| `alert.ignore_at_zero` | E | R | officers near a player at level 0 |
| `mission.delivery` | F | P | D1 pass and timeout; D2 and destroyed cargo hidden |
| `mission.chase` | F | P | C1; C2 hidden |
| `mission.race` | F | P | R1 pass and a skipped checkpoint; R2 hidden |
| `mission.heist` | F | P | H1; H2 hidden |
| `mission.unlocks` | F | R | the unlock chain from a new game |
| `economy.shops` | G | P | buy, refuse, notices |
| `economy.outfits` | G | P | buy and wear |
| `economy.garage` | G | P | store, retrieve, capacity, repair |
| `world.plan_compliance` | H | P | ray probes over every plan element |
| `world.plan_swap` | H | R | the alternative Downtown plan |
| `world.same_start` | H | P | resets with equal and different variations |
| `world.replay` | H | P | one input timeline at two paces |
| `world.links` | H | P | highway portals and the ferry's map change |
| `world.clock_lights` | I | P | clock rate, lamps, sun |
| `world.weather` | I | P | the four weathers |
| `ui.hud` | J | P | HUD widgets against state |
| `ui.minimap` | J | P | icons, route, search zone |
| `ui.phone` | J | P | apps through `ui_*` |
| `ui.menus` | J | P | main menu, host, join, pause |
| `persistence.round_trip` | K | P | save, SIGKILL, reload, damaged slot |
| `persistence.rules` | K | P | refusals and autosave |
| `online.session_a` | L | P | 4 clients at P2 (2 at P1 in the playtest) |
| `online.session_b` | L | R | 8 clients at P1 on Ashby Port |
| `online.session_c` | L | R | 2 clients at P3 with a partition |
| `online.session_d` | L | P | co-op H1 (2 clients in the playtest) |
| `freeplay.new_game` | M | R | the main menu, D1, then ten minutes of bot play |
| `perf.city` | M | P | busiest district by day, resets |
| `contract.devconsole` | M | P | every command, bad input, float ids |

## 2. Coverage map

Every GDD rule, the assertions that exercise it, and what a game without the feature shows.
"Fails when missing" means the assertion fails on a game that lacks the feature (a calibration
mutant per assertion proves it, workstream 9). `scripts/check_coverage.py` fails if a rule has no
row, a row names no assertion, or an assertion's template is not in the catalog.

| Rule | Requires | Exercised by | Kind | Fails when missing |
| --- | --- | --- | --- | --- |
| OR-1 | no outside IP in project text or names | `gate.static: denylist` | G | a denylisted name zeroes the reward |
| OR-2 | alert level shown as badges | `ui.hud: alert_badges` | P | badge count differs from the level |
| CA-1 | leads spawn with their table looks | `people.lineup: lead_looks` | P | missing lead, wrong body, hair or colours |
| CA-2 | leads pairwise distinct | `people.lineup: leads_distinct` | P | two leads too alike |
| CA-3 | lead unlocks | `mission.unlocks: leads_unlocked` | R | unlock list wrong after a pass |
| CA-4 | switching at a safehouse | `people.switch_lead: switch` | P | no menu entry, look unchanged, possessions changed |
| CA-5 | leads online | `online.session_a: lead_skins` | P | a remote client shows another look |
| AR-1 | archetypes present by place and hour | `people.census: presence` | P | an archetype absent or under its count |
| AR-2 | archetype signatures | `people.census: signatures` | P | wrong colours or props |
| AR-3 | library bodies, heights and scale | `people.lineup: body_mesh`, `people.lineup: heights`, `people.census: heights` | P | body not from a library file, height or scale out of band |
| AR-4 | behaviours | `people.census: behaviours` | P | a stand, work, turf or patrol rule broken |
| AR-5 | who is armed | `people.census: armed` | P | unarmed enforcer or armed civilian |
| IN-1 | the 28 actions with bindings | `gate.static: inputmap` | G | an action or binding missing |
| IN-2 | strength gaits, mode actions, handbrake | `people.locomotion: gait_select`, `people.vehicle_entry: drive_actions`, `vehicle.handling: handbrake` | P | half strength runs, vehicles ignore their actions, handbrake outside 2-6 m/s² |
| IN-3 | input acts in its tick | `people.locomotion: same_tick` | P | movement starts a tick late |
| CM-1 | camera distance and framing | `people.locomotion: camera_frame`, `people.vehicle_entry: camera_vehicle` | P | camera too near or far, player off centre |
| CM-2 | look rates and tilt | `people.locomotion: look_rates` | P | rate or tilt out of band |
| CM-3 | camera-relative movement | `people.locomotion: camera_relative` | P | movement not along the camera |
| CM-4 | camera never in walls | `people.jump_climb_vault: camera_clear` | P | head-to-camera segment hits static geometry |
| CM-5 | lock-on | `combat.lock_on: lock_nearest`, `combat.lock_on: lock_hostile` | P | no lock, the wrong person, target off centre, aim off the Chest |
| FT-1 | paces | `people.locomotion: paces` | P | a pace out of band |
| FT-2 | planted feet | `people.locomotion: alternation`, `people.locomotion: foot_slide` | P | sliding or non-alternating feet |
| FT-3 | jump | `people.jump_climb_vault: jump` | P | rise or air time out of band |
| FT-4 | climbing | `people.jump_climb_vault: climb_low`, `people.jump_climb_vault: climb_high` | P | not on top in time, hand far, penetration |
| FT-5 | vaulting | `people.jump_climb_vault: vault` | P | too slow, too low, penetration |
| FT-6 | crouch | `people.locomotion: crouch_pose` | P | hips above 75% |
| FT-7 | swimming | `people.swim: swim_pose`, `people.swim: swim_pace`, `people.swim: exits` | P | head under, pitch, pace, no exit |
| FT-8 | fall damage | `people.fall_ragdoll: fall_damage` | P | health loss off the formula |
| FT-9 | ragdoll and getting up | `people.fall_ragdoll: ragdoll`, `people.fall_ragdoll: get_up`, `people.fall_ragdoll: free_fall`, `vehicle.crash: blast_ragdoll`, `vehicle.crash: run_into` | P | no `limp` flag, scripted fall, bone below ground, no get-up |
| FT-10 | getting in and out | `people.vehicle_entry: get_in`, `people.vehicle_entry: seated`, `people.vehicle_entry: get_out`, `traffic.intersection_watch: drivers` | P | path misses the door, hips out of the seat (the player's or a city driver's) |
| FT-11 | aim pose | `combat.weapons: aim_pose_rifle`, `combat.weapons: aim_pose_pistol` | P | hand or forearm off, no aim point |
| FT-12 | cover | `combat.cover_firefight: cover_enter`, `combat.cover_firefight: cover_hold`, `combat.cover_firefight: cover_leave` | P | not in cover within 1 s, hips high, `cover` state wrong, cover kept moving away |
| VH-1 | handling, mass, library models | `vehicle.handling: accel`, `vehicle.handling: top_speed`, `vehicle.handling: brake_dry`, `vehicle.handling: turn_circle`, `vehicle.handling: mass`, `vehicle.handling: model_mesh` | P | any value out of band, body not from its library model |
| VH-2 | wet braking | `vehicle.handling: brake_wet`, `world.weather: rain_braking` | P | ratio under 1.15 or over 1.60 |
| VH-3 | damage from impacts | `vehicle.crash: impact_damage`, `inv.damage_honest: impacts_only` | P | no damage, or damage without an impact |
| VH-4 | parts come off | `vehicle.crash: part_off` | P | no debris entity |
| VH-5 | engine failure | `vehicle.crash: disabled` | P | above 10 km/h at full throttle |
| VH-6 | fire and explosion | `vehicle.crash: burning`, `vehicle.crash: explosion`, `vehicle.crash: blast` | P | no explosion, no push, no harm |
| VH-7 | repair | `economy.garage: repair` | P | damage unchanged or price wrong |
| VH-8 | taking a car | `vehicle.carjack: pull_out`, `vehicle.carjack: driver_after`, `vehicle.carjack: crime` | P | no pull-out, no crime event |
| VH-9 | motorbike | `vehicle.motorbike: lean`, `vehicle.motorbike: thrown` | P | under 10 degrees, rider stays on |
| VH-10 | boats | `vehicle.boats: float`, `vehicle.boats: speeds`, `vehicle.boats: beach` | P | sinks, out of band, drives on land |
| VH-11 | ferry timetable and capacity | `vehicle.ferry: timetable`, `vehicle.ferry: crossing_time`, `vehicle.ferry: capacity` | P | late, crossing out of band, a seventh vehicle boards |
| VH-12 | riding the ferry | `vehicle.ferry: deck_drift`, `vehicle.ferry: arrival` | P | drift over 1 m, left behind |
| TR-1 | densities | `traffic.intersection_watch: density`, `traffic.density_profile: table` | P | counts outside the table |
| TR-2 | rain thins pedestrians | `traffic.density_profile: rain_ratio` | R | ratio outside 40-80% |
| TR-3 | steady density | `traffic.steady: drift` | R | a later minute off by more than 30% |
| TR-4 | signal programs | `traffic.intersection_watch: program`, `traffic.intersection_watch: greens_compatible`, `traffic.intersection_watch: walk_in_green` | P | states off schedule, conflicting greens, walk out of its phase |
| TR-5 | obeying signals | `traffic.intersection_watch: no_red_entry`, `traffic.intersection_watch: green_flow` | P | entries on red, or no flow |
| TR-6 | all-way stops | `traffic.stop_junction: full_stop`, `traffic.stop_junction: order`, `traffic.stop_junction: box_clear`, `traffic.stop_junction: no_deadlock` | P | rolling stops, two in the box, waits over 30 s |
| TR-7 | lane keeping | `traffic.intersection_watch: lane_keeping` | P | offset p95 over 1 m, heading off, wrong way |
| TR-8 | speed limits | `traffic.speed: limit` | P | NPC over the limit plus 10% |
| TR-9 | walkable ground | `traffic.intersection_watch: walkable` | P | under 95% on walkable ground |
| TR-10 | crossing at crosswalks | `traffic.intersection_watch: crosswalks`, `traffic.stop_junction: ped_gap` | P | jaywalking, crossing on don't walk |
| TR-11 | yielding to pedestrians | `traffic.intersection_watch: no_ped_hits` | P | a person hit on a crosswalk |
| TR-12 | obstacles, crash rate | `traffic.obstacle: stop_short`, `traffic.intersection_watch: crash_rate` | P | NPC hits the object, rate over 0.02 |
| TR-13 | panic | `traffic.panic_horn: flee`, `traffic.panic_horn: dodge` | P | no flight (with module 6's firing), no dodge |
| TR-14 | horn | `traffic.panic_horn: horn_clear` | P | people stay in the lane |
| TR-15 | no pop-in | `traffic.intersection_watch: no_pop_in` | P | appearing near or in view |
| TR-16 | drivers | `traffic.intersection_watch: drivers` | P | a moving NPC car without a driver |
| CB-1 | weapon table | `combat.weapons: pistol_hits`, `combat.weapons: shotgun_hits`, `combat.weapons: fists_hits`, `combat.weapons: smg_rate`, `combat.weapons: bat_rate`, `combat.weapons: rifle_magazine`, `combat.weapons: rifle_reload`, `combat.weapons: shotgun_range`, `combat.weapons: rifle_range`, `combat.weapons: fists_range` (each for every weapon of its kind) | P | any value off the table, damage beyond the range |
| CB-2 | ammo | `combat.weapons: pistol_ammo`, `combat.weapons: pistol_reload_hand`, `combat.weapons: dry_fire` | P | ammo unchanged, no reload, firing when empty |
| CB-3 | switching weapons | `combat.weapons: switch_next_0`, `combat.weapons: switch_next_5`, `combat.weapons: switch_prev`, `combat.weapons: fists_owned` | P | wrong order, no wrap, slow, fists missing |
| CB-4 | lock-on hit rate | `combat.lock_on: hit_rate_pistol`, `combat.lock_on: hit_rate_rifle`, `combat.lock_on: hit_rate_smg` | P | rate under the floor |
| CB-5 | armour | `combat.armour: absorb` | P | split off 60/40 |
| CB-6 | no shots through walls | `combat.cover_firefight: through_wall`, `combat.cover_firefight: through_van` | P | damage through a wall or a vehicle |
| CB-7 | death | `combat.cover_firefight: kill_hits`, `combat.cover_firefight: kill_ragdoll`, `combat.weapons: pistol_kill` | P | no `died` event, death at the wrong hit, or no ragdoll |
| CB-8 | cover cuts damage, firing from cover | `combat.cover_firefight: cover_cuts`, `combat.cover_firefight: fire_from_cover` | P | ratio over 0.4, cannot fire |
| CB-9 | crew hostility and tactics | `combat.crew_hostility: turn_hostile_aim`, `combat.crew_hostility: turn_hostile_hit`, `combat.crew_hostility: lookouts_flee`, `combat.crew_hostility: enforcers_cover`, `combat.crew_hostility: enforcers_fire`, `combat.cover_firefight: retreat` | P | no hostility, hostile before 5 s, lookouts stay, under half reach cover, no fire, no retreat |
| CB-10 | police force by level | `combat.police_force: by_level` | R | police shooting at level 1 |
| AL-1 | crime events | `alert.crime_table: events` | P | a crime without its event |
| AL-2 | reporting delays | `alert.red_light: police_witness`, `alert.phone_in: delay`, `alert.phone_in: dead_witness` | P | late rise, wrong phone-in time, a dead witness still reports |
| AL-3 | unwitnessed crimes | `alert.unwitnessed: stays_zero`, `inv.alert_honest: witnessed_only` | R | the level rises without a witness |
| AL-4 | alert rule and escalation | `alert.red_light: no_escalation`, `alert.crime_table: levels`, `alert.crime_table: escalation` | P | wrong level |
| AL-5 | sight ranges | `alert.sight_range: inside`, `alert.sight_range: outside` | R | seen from outside the range, missed inside it |
| AL-6 | response time and count | `alert.red_light: arrival`, `alert.response_levels: counts` | P | late, too few or too many units |
| AL-7 | where police come from | `alert.red_light: origin`, `alert.red_light: kinematics` | P | appears near or in view, too fast, through walls |
| AL-8 | roadblocks | `alert.roadblock: ahead`, `mission.heist: roadblock` | P | no roadblock within 90 s |
| AL-9 | arrest | `alert.arrest: arrested`, `alert.arrest: consequences` | P | no arrest, wrong fine, weapons or place |
| AL-10 | death and respawn | `alert.death: respawn`, `alert.death: fee` | P | wrong place, fee or level |
| AL-11 | escape | `alert.escape: cooling_off`, `alert.escape: zone`, `inv.alert_honest: drops_only_on_escape` | P | drops early, never drops |
| AL-12 | ignored at level 0 | `alert.ignore_at_zero: no_pursuit` | R | police approach at level 0 |
| MS-1 | contacts offer missions | `mission.delivery: accepted`, `mission.unlocks: locked_not_offered` | P | no start, a locked mission offered |
| MS-2 | markers | `mission.delivery: markers` | P | marker far from its point, next shown early |
| MS-3 | stage completion | `mission.delivery: stages_in_order`, `inv.mission_honest: arrivals` | P | a stage done away from its point |
| MS-4 | timed stages | `mission.delivery: timer_fail`, `mission.delivery: timer_hud` | P | no failure, no HUD timer |
| MS-5 | failures | `mission.delivery: fail_destroyed`, `mission.chase: escaped` | P | no failure, payout on failure |
| MS-6 | payout, unlocks, autosave | `mission.delivery: payout`, `mission.unlocks: unlocks`, `persistence.rules: autosave` | P | wrong payout, no unlock, no Auto save |
| MS-7 | contact messages | `ui.phone: messages` | P | no message |
| MS-8 | checkpoint order | `mission.race: order`, `mission.race: skip_no_finish` | P | a skipped checkpoint counted |
| MS-9 | NPC racers | `mission.race: racers` | P | racers stall or skip checkpoints |
| MS-10 | chase targets | `mission.chase: target_flees`, `mission.chase: stopped`, `mission.chase: runner` | P | target static, teleporting or uncatchable |
| MS-11 | heist vault and crew cut | `mission.heist: vault_level`, `mission.heist: take_and_cut` | P | no level 3, money events wrong |
| MS-12 | mission states | `mission.delivery: states` | P | state missing or wrong |
| EC-1 | new game start | `ui.menus: new_game`, `freeplay.new_game: start_state` | P | wrong money, weapons or health |
| EC-2 | prices, effects, refusals | `economy.shops: prices`, `economy.shops: effects`, `economy.shops: refusals` | P | any price or effect off |
| EC-3 | unaffordable purchases | `economy.shops: refused_funds` | P | money taken, no notice |
| EC-4 | money only through events | `inv.money: conserved` | I | an unexplained change |
| EC-5 | outfits | `economy.outfits: buy`, `economy.outfits: wear` | P | look unchanged |
| EC-6 | garages | `economy.garage: store`, `economy.garage: retrieve`, `economy.garage: capacity`, `economy.garage: refused_kinds` | P | vehicle stays, a third accepted |
| EC-7 | storage persists | `economy.garage: persists`, `persistence.round_trip: garages` | P | lost after leaving or loading |
| WD-1 | roads | `world.plan_compliance: roads` | P | rays miss the road or wrong height |
| WD-2 | sidewalks and crosswalks | `world.plan_compliance: sidewalks`, `world.plan_compliance: crosswalk_tags` | P | wrong height or tag |
| WD-3 | buildings and open parcels | `world.plan_compliance: buildings`, `world.plan_compliance: open_parcels` | P | roof off, building outside its parcel |
| WD-4 | interiors | `world.plan_compliance: interiors` | P | door blocked, room filled |
| WD-5 | points of interest on surfaces | `world.plan_compliance: pois` | P | nothing under a point |
| WD-6 | water | `world.plan_compliance: water` | P | no water area or wrong level |
| WD-7 | terrain | `world.plan_compliance: terrain` | P | ground off the heightmap |
| WD-8 | plan changes | `world.plan_swap: rebuilt`, `world.plan_swap: missions` | R | the world ignores the other plan |
| WD-9 | highway links | `world.links: portal` | P | no transition, new vehicle id, damage lost |
| WD-10 | ferry map change | `world.links: ferry`, `vehicle.ferry: arrival` | P | the deck's load left behind |
| WD-11 | clock | `world.clock_lights: rate`, `world.clock_lights: set` | P | rate off |
| WD-12 | street lights | `world.clock_lights: spacing`, `world.clock_lights: on_off` | P | missing lamps, lamps on by day |
| WD-13 | sun | `world.clock_lights: sun` | P | elevation off |
| WD-14 | weather set and held | `world.weather: set_and_hold` | P | changes by itself, wrong report |
| WD-15 | rain effects | `world.weather: rain_fx` | P | no emitting rain node |
| WD-16 | fog | `world.weather: fog_env` | P | fog off |
| WD-17 | overcast light | `world.weather: overcast_light` | P | sun too bright |
| UI-1 | HUD | `ui.hud: health`, `ui.hud: armour`, `ui.hud: money`, `ui.hud: weapon`, `ui.hud: alert_badges` | P | a widget disagrees with state |
| UI-2 | minimap icons | `ui.minimap: icons_fit`, `ui.minimap: icon_set` | P | residual over 3 px, icons missing |
| UI-3 | route | `ui.minimap: route_on_roads`, `ui.minimap: route_length` | P | off the roads, too long |
| UI-4 | search zone | `ui.minimap: search_zone`, `alert.escape: zone_shown` | P | zone missing or off |
| UI-5 | phone | `ui.phone: open`, `ui.phone: apps`, `ui.phone: gps` | P | apps missing, not navigable with `ui_*` |
| UI-6 | main menu | `ui.menus: main_menu`, `ui.menus: new_game`, `ui.menus: load`, `ui.menus: host`, `ui.menus: join` | P | buttons missing, host or join fails |
| UI-7 | pause | `ui.menus: pause` | P | the world moves while paused |
| UI-8 | timer and notices | `mission.delivery: timer_hud`, `economy.shops: notice` | P | timer or notice missing |
| UI-9 | place menus | `economy.shops: menu`, `economy.garage: menu`, `people.switch_lead: menu` | P | entries missing |
| UI-10 | net warning | `online.session_a: net_warning` | P | warning absent or late |
| UI-11 | full-screen map | `ui.minimap: map_screen` | P | no map screen, icons off, `state.ui.map` wrong |
| SV-1 | saving and autosave | `persistence.round_trip: save`, `persistence.rules: autosave` | P | no `saved` event |
| SV-2 | refusals | `persistence.rules: refused_alert`, `persistence.rules: refused_mission` | P | saves during an alert |
| SV-3 | contents and placement | `persistence.round_trip: restored` | P | a field lost |
| SV-4 | atomic saves | `persistence.round_trip: sigkill` | P | slot unreadable after SIGKILL |
| SV-5 | damaged slot | `persistence.round_trip: corrupt` | P | crash, or another slot fails |
| SV-6 | `--save-dir` | `persistence.round_trip: save_dir` | P | saves elsewhere |
| NT-1 | roles, flags, player cap | `gate.boot: server_client`, `online.session_b: max_players` | R | flags ignored, a ninth player admitted |
| NT-2 | server authority | `online.session_a: teleport_rejected` | P | an injected move reaches the server |
| NT-3 | client dev commands refused | `online.session_a: console_refused` | P | a client changes its money |
| NT-4 | server-confirmed damage | `online.session_a: pvp_confirmed` | P | client-only damage counts |
| NT-5 | joining | `online.session_a: late_join` | P | census differs after 5 s |
| NT-6 | convergence | `online.session_a: convergence`, `online.session_c: convergence_p3` | P | q95 above the limit |
| NT-7 | local responsiveness | `online.session_a: local_response` | P | no prediction |
| NT-8 | event agreement | `online.session_a: events` | P | late or out of order |
| NT-9 | dropping and reconnecting | `online.session_b: reconnect` | R | avatar stays, state not restored |
| NT-10 | surviving a partition | `online.session_a: partition`, `online.session_c: recovery` | P | dropped, ghosts, oscillation |
| NT-11 | PvP switch | `online.session_a: pvp`, `online.session_b: pvp_off` | P | damage with PvP off, none with it on |
| NT-12 | missions online, co-op heist | `online.session_d: offered`, `online.session_d: crew`, `online.session_d: payout_each`, `online.session_d: fails_all` | P | H1 not offered in a fresh session, payout to one player only |
| NT-13 | bandwidth | `online.session_b: bandwidth` | R | over 48/96/16 KB/s |
| NT-14 | server tick | `online.session_b: tick` | R | p95 over 16.7 ms |
| NT-15 | online sessions stay on one map | `online.session_b: one_map` | R | a map change, or the ferry sailing, online |
| PF-1 | GDScript and shaders only | `gate.static: languages` | G | C# or a native library present |
| PF-2 | project settings | `gate.static: settings` | G | a setting differs |
| PF-3 | import time and cache | `gate.import: time`, `gate.import: cache_size` | G | over 10 minutes or 1 GB |
| PF-4 | boot time | `gate.boot: boot_time` | G | over 60 s |
| PF-5 | reset time | `perf.city: reset_time` | P | over 3 s |
| PF-6 | tick time | `perf.city: tick_mean`, `perf.city: tick_p95` | P | over 8 ms or 12 ms |
| PF-7 | memory | `perf.city: memory`, `inv.alive: memory` | P | over 1.5 GB |
| PF-8 | no crash | `freeplay.new_game: survives`, `inv.alive: process` | R | the process dies or hangs |
| PF-9 | headless | `inv.alive: headless` | I | anything needing a frame fails headless |
| AC-1 | command line | `gate.boot: flags`, `world.same_start: variation_flag` | G | a flag ignored |
| AC-2 | robust `exec` | `contract.devconsole: bad_input`, `contract.devconsole: float_ids` | P | crash, no error answer, floats refused |
| AC-3 | commands do what they say | `contract.devconsole: commands` | P | a command missing or without effect |
| AC-4 | entity registry | `inv.registry: ids` | I | reused id, missing metadata |
| AC-5 | people's skeletons, weapon, hostility, limp, vehicle and seat | `people.lineup: skeleton`, `inv.registry: unregistered`, `combat.crew_hostility: hostile_meta`, `people.fall_ragdoll: ragdoll`, `traffic.intersection_watch: drivers` | P | wrong bone names, unbound mesh, unregistered actor, `weapon`, `hostile`, `limp`, `vehicle` or `seat` wrong |
| AC-6 | vehicles' metadata and seats | `people.vehicle_entry: seats`, `vehicle.crash: metadata` | P | seats, doors or wheel point missing |
| AC-7 | signal entities | `traffic.intersection_watch: signal_entities` | P | an approach without its signal |
| AC-8 | layers, surface tags, water areas | `world.plan_compliance: tags`, `people.swim: water_area` | P | tags or layers wrong |
| AC-9 | groups | `world.clock_lights: groups`, `world.weather: groups` | P | group missing |
| AC-10 | marker and debris metadata | `mission.delivery: marker_meta`, `vehicle.crash: debris_meta` | P | metadata missing |
| AC-11 | looks | `people.lineup: look_params` | P | parameters disagree with `look` |
| AC-12 | honest state | `inv.state_honest: matches` | I | state disagrees with what is seen |
| AC-13 | events | `inv.events: schema` | I | an event without its fields or tick |
| AC-14 | announced teleports | `inv.teleport: announced` | I | an unannounced jump |
| AC-15 | no wall clock | `world.replay: pace` | P | the trace changes with the pace |
| AC-16 | variations | `world.same_start: same`, `world.same_start: different` | P | populations differ, or never vary |
| AC-17 | replays | `world.replay: replay_hash` | P | traces differ |
| AC-18 | telemetry left alone | `inv.telemetry: heartbeat` | I | heartbeat lost |

Rules with no shipped playtest (R rows) are still stated in the GDD as behaviour; their hidden
instances test exactly what the rule says and add no new requirement.

## 3. Workstreams, in dependency order

Sizes are working days with agents writing most of the code and a person reviewing (design § 5.2,
revised with Phase 0's head start). "Acceptance" is what must hold before the workstream counts as
done.

### WS1 GDD (v1 done)
- **Deliverables:** v1 (done, 177 rules); v2 after the first playtests and reference modules
  (numbers re-measured on the reference, TODO markers settled, the Port and Hills points of
  interest named); freeze before hidden instances are drawn.
- **Acceptance:** `check_agent_text.py --release` 0 hits and 0 open markers; `check_coverage.py`
  clean; every band holds the reference's worst value at least 15% of the band width inside each
  edge; the owner approves the names.
- **Size:** v2 3 days, freeze 1 day.

### WS2 World plans and the plan format (format v1 and the Downtown core done)
- **Deliverables:**
  - full Downtown (about 0.8 x 0.8 km around the core, both highway portals);
  - Ashby Port (about 1.0 x 0.7 km: docks, quays with ladders, a beach, the bay, the ferry terminal,
    `turf_crew_b`, `garage_port`, `giver_chase`, the C1, C2, D2 and H2 points);
  - Sable Hills (about 2 x 2 km: `hills_height.png`, the town, farms, the drag strip, the R2 course,
    `turf_crew_c`, `garage_hills`, the ferry terminal);
  - `links.json` (two highway portals, the ferry routes);
  - the generator extended to curves, terrain-following roads, bridges, water and shores, and a
    randomised layout mode for the alternative plan;
  - the alternative Downtown (private: same point-of-interest ids, different roads and parcels).
- **Acceptance:** `check_plan.py` 0 problems on every plan (and its mutation set caught); a cross
  check that every point-of-interest id the GDD names exists in the plans; the reference builds
  every plan; plan compliance passes on each.
- **Size:** 9 days.

### WS3 Grading kit core
- **Deliverables:**
  - the probe's native core (C, no godot-cpp, as in Phase 0) taking over the census, bone reads,
    input injection and queries through method binds against the dumped `extension_api.json`; HMAC
    framing and a per-tick heartbeat; built for macOS (`.dylib`, development) and Linux x86_64
    (`.so`, the images); stripped, with neutral strings;
  - the lockstep runner (solo and server roles under `--fixed-fps 60`; real-time mode with
    timestamps for clients) and process control (start, SIGKILL, restart, partition);
  - the instance format: a template plus a draw gives a fully expanded instance JSON (anchors
    resolved against the plan, every parameter explicit), so an instance replays without the
    generator;
  - the assertion library (temporal, aggregates, geometry, physics; each assertion records its
    measured values) and scoring per section 1;
  - trace format and hashing: canonical JSON per observed frame, a running SHA-256 chain, used by
    `world.replay`, calibration and regression;
  - the proxy (from the spike) with the socket audit, and the sandbox (unprivileged user, cgroup and
    rlimits below the container's limits);
  - the grader's own 80-minute deadline and a reward always written, a self-test on a tiny project
    of ours that runs first (its failure is the only path to "no reward"), and the HTML report.
- **Acceptance:**
  - Phase 0's item-2 checks pass in our game and a foreign project on macOS and Linux;
  - forged frames stop the game and a missing heartbeat fails the instance;
  - ten replays of one instance give one trace hash;
  - every candidate-failure class (crash, hang, failed import, stalled or killed probe,
    proxy-breaking traffic, oversized cache, fork bomb, giant logs) yields a written reward;
  - `checks/` pytest suite green.
- **Size:** 16 days (probe 6, runner and instances 4, assertions and scoring 3, proxy and sandbox 3).

### WS4 Playtests and `qa run`
- **Deliverables:** the developer's `qa` command (`qa run`, `qa mp`, `qa shot`, `qa census`,
  `qa replay`); about 60 playtests, at least one per P template, with fixed parameters on the
  shipped plans and `expect` lines that cite GDD rule ids and numbers; output that lists the
  expectations that failed and the measured values, never a total; documentation in the
  requester's voice.
- **Acceptance:** `check_agent_text.py` 0 hits over the kit, its `--help` output, sample runs' output
  and `strings` of the probe binary; the reference passes every playtest; the starter fails them
  cleanly (failed expectations, no kit error).
- **Size:** 9 days.

### WS5 Starter project
- **Deliverables:** `project.godot` (4.7 features, Jolt, 60 Hz, jitter fix 0, main-thread physics,
  Compatibility); the 28 actions with keyboard-and-mouse and gamepad defaults; a `DevConsole` stub
  that answers `{"ok": false, "error": "not implemented"}`; the vendor library under
  `assets/vendor/` with explicit texture import settings; the bone map if the panel says so; the
  prebuilt import cache; an empty main scene; a short README.
- **Acceptance:** imports headless with the cache in under 2 minutes; boots; every playtest reports
  failed expectations; reward 0 (no player registered, so `G_boot` fails).
- **Size:** 2 days.

### WS6 Reference game
- **Deliverables:** a GDScript project that implements every GDD rule, in this order, each module
  landing with its playtests green:
  1. contract, registry, DevConsole, state and events (3 days);
  2. world builder from plans: roads, junction boxes, blocks, parcels, interiors, water, terrain,
     links, street lights, surface tags (8);
  3. people: looks, retargeting, locomotion, IK climb and vault, swimming, ragdoll, vehicle entry
     (10);
  4. vehicles: cars and handling bands, damage, parts, fire, motorbike, boats, ferry (10);
  5. traffic and pedestrians: signals, all-way stops, lanes, crosswalks, spawning, panic (9);
  6. combat, cover and crew tactics (6);
  7. crime, witnesses, police response, roadblocks, arrest, escape (7);
  8. the eight missions (8);
  9. economy, UI, phone, minimap, menus, saving (9);
  10. online: server authority, prediction, interpolation, interest management, delta snapshots,
      reconnects, co-op H1 (14; its architecture is fixed in module 1 so nothing is retrofitted);
  11. performance and finishing (5).
- **Acceptance:** every playtest passes; every hidden instance scores 1.0; replays are exact; the
  full grade takes at most 40 minutes on 8 vCPU and 32 GB.
- **Size:** about 90 agent-days, about 50 human days of review and integration.

### WS7 Packaging
- **Deliverables:**
  - `task.toml`: flat single step; no task-side timer; agent `timeout_sec` the platform's session
    length; verifier 5,400 s with the grader's own 80-minute deadline inside it; agent 8 vCPU,
    16 GB, 40 GB disk, no GPU, no network, user `dev`; verifier 8 vCPU, 32 GB;
  - `instruction.md` (short, requester's voice, no README deliverable since nothing would check it);
  - the agent image (Ubuntu, Godot 4.7.2 Linux at `/opt/godot`, Python 3.12, the kit, Blender LTS,
    Mesa and Xvfb, the starter with the vendor library and its cache at `/app/game`, the design
    folder at `/app/design`, offline docs: `--doctool` XML and the HTML manual);
  - the verifier image: the agent image's heavy base plus copy-only layers (grader, probe `.so`,
    private instances, alternative plan, denylist), so it rebuilds offline after a full session;
  - collection: `/app/game` without `.godot/` and without the vendor sources (`.import` and `.tres`
    kept), with a size cap; the grader restores the vendor sources and cache from its image after a
    hash check;
  - `solution/solve.sh` plus the reference as readable source (staged from the private store by
    the packager; never committed here);
  - `scripts/package_single_step.py`, preflight, the README's reward formula, validation table and
    hackability table.
- **Acceptance:** in local Linux containers the reference grades 1.0 and the starter 0.0, twice each,
  on one bundle; packaging twice gives the same bundle hash; the verifier image builds with the
  network off; the bundle's agent-visible files pass `check_agent_text.py --release`.
- **Size:** 7 days.

### WS8 Hidden instances
- **Deliverables:** `scripts/make_instances.py` (public code) drawing about 170 instances and 4 session
  specs from a private draw; the R templates; disjointness from the playtests (anchors, times,
  weather, variations differ); `tests/private/` staged by the packager.
- **Acceptance:** no hidden instance repeats a playtest's parameters (checked); `N_f` fixed per
  family; every R row of the coverage map has at least one instance; the draw is recorded only in
  the private store.
- **Size:** 4 days.

### WS9 Calibration and mutants
- **Deliverables:**
  - exact-replay calibration on the verifier's CPU (Linux x86_64): every instance once, plus sweeps
    (variations, handling across the GDD bands, weather and hour) to find the reference's spread;
  - one mutant per assertion family member (police that warp in, alert levels without witnesses,
    client-authoritative movement, NPC drivers that ignore red, sliding feet, damage without
    impacts, missions passed on a timer, saves that drop garages, misplaced minimap icons,
    teleporting ragdolls, wall-clock timers, reused ids, filled interiors, unannounced teleports);
  - with the owner's OK for a platform run, a second implementation (a model rollout) to find checks
    that overfit the reference.
- **Acceptance:** the reference at 1.0 with every band's margin at least 15%; each mutant loses its
  target assertion in at least 95% of runs; overfit checks loosened or removed.
- **Size:** 9 days, most of it machine time on Linux.

### WS10 QA
- **Deliverables:** 20+ independent adversarial passes (CHECKLIST Part 1 lenses), a re-check after
  every fix round by a reviewer who did not write the fix; hostile and broken projects (fork bombs,
  giant logs, import bombs, probe hooks and detection, proxy bypass, oversized artifacts);
  `harbor check` and ratings; then, with the owner's go, the first platform probe and the Oddish
  gate (reference 1.0 x2, no-op 0 x2, audit clean) before any model trial.
- **Acceptance:** every must-fix closed and re-checked; CHECKLIST Part 1 all ticked.
- **Size:** 9 days plus fix rounds.

**Total:** about 119 days of people's time (4 + 9 + 16 + 9 + 2 + 50 + 7 + 4 + 9 + 9), above the
design's 95 because every rule now needs a failing check and the kit gains the sandbox and
self-test. The fifteen weeks of section 6 assume about 1.6 people's worth of review in parallel,
with agents writing the code; one person alone needs about 24 weeks.

## 4. Public and private layout

swe-marathon-2 is public. The developer never sees GitHub (no network in the sandbox), but anything
committed there is public for good.

**Public, in this task folder:**

| Path | Contents | Packaged into |
| --- | --- | --- |
| `README.md` | author README: dev log, design dimensions, reward formula, hackability | nothing |
| `notes/` | this plan, reports | nothing |
| `instruction.md` | the brief (later) | the bundle |
| `task.toml` | runtime settings (later) | the bundle |
| `common/design/` | GDD, plan format, shipped plans | agent image (`/app/design`); verifier reads the shipped plans |
| `common/probe/` | probe source (later; the spike's is already public) | both images, as a stripped build |
| `environment/` | agent Dockerfile, starter project (without vendor binaries), kit sources and playtests | agent image |
| `tests/` | verifier Dockerfile, `test.sh`, `verify.py`, grader code | verifier image |
| `tests/private/` | hidden instances, R templates, alternative plan, denylist | verifier image; Git-ignored |
| `solution/` | `solve.sh` (public); `solution/game/` the reference (Git-ignored, staged) | the bundle |
| `scripts/` | generator, checkers, instance maker, packager | nothing |
| `checks/` | pytest suite for the kit and grader | nothing |
| `experiment/` | runs, traces, bundles | nothing; Git-ignored |
| `spike/` | Phase 0, frozen | nothing |

**Private** (never in this repository):

| Item | Working copy | Kept and backed up in |
| --- | --- | --- |
| Reference game source | `~/Documents/github/Abundant/crime-city-reference/` (its own Git repo) | a private GitHub repo, proposed `abundant-ai/swe-m2-crime-city-private` (TODO(owner): create it); until then a `git bundle` copied into `harbor-lh/ops/swe-marathon-v2/game-private/` and pushed with `push_ops.sh` (harbor-lh is private) |
| Hidden instances and R templates | `tests/private/` (Git-ignored) | the private repo, `instances/` |
| The draw behind the instances and the alternative plan | private repo only | the private repo, `draws/` |
| Alternative Downtown plan | `tests/private/plans/` | the private repo, `plans/` |
| Originality denylist | `tests/private/denylist.txt` | the private repo, `denylist/` |
| Calibration results | `experiment/calibration/` (raw traces, large, regenerable by replay) | summaries, trace hashes and the mutant table in the private repo, `calibration/` |
| Author notes on grading internals (thresholds beyond the GDD, mutant designs) | the private repo, `notes/` | the private repo |

**Never in Git anywhere:** the vendor art and its import cache (kept in `game-spike/vendor/` and the
owner's downloads; the zips' SHA-256 recorded in the private repo so they can be fetched again),
every `.godot/` folder, built probe libraries, Godot binaries. This folder's `.gitignore` lists
them. Nothing durable goes in the scratchpad (it loses files older than three days at midnight).

## 5. What needs Linux, downloads, and the first platform probe

**Needs Linux (x86_64 for anything measured):**
- the probe's `.so` and its checks (the C core has no macOS dependency);
- both Docker images, the cgroup and rlimit sandbox, the proxy's socket audit (`/proc`);
- stills under Xvfb and llvmpipe (`qa shot`, the QA-only visual review);
- calibration and replay hashes (a Mac trace is no evidence for x86_64 floats);
- speed and memory on a cloud vCPU (Phase 0 item 3 pinned to one core; GDD PF-6's TODO);
- the import time with the full art set in the image.

Local Docker on this Mac runs arm64 Linux: good for functional checks (the `.so` builds, Xvfb,
`/proc`, cgroups) but not for x86_64 numbers. Those need an x86_64 box: a cloud VM
(TODO(owner): allow one) or the platform probe.

**Downloads that need the owner's OK** (none made in Phase 1a):

| File | Source | Size | For |
| --- | --- | --- | --- |
| `Godot_v4.7.2-stable_linux.x86_64.zip` and `SHA512-SUMS.txt` | github.com/godotengine/godot/releases/tag/4.7.2-stable | about 70 MB, to confirm | images, Linux probe build, calibration |
| `kenney_watercraft-kit.zip` | kenney.nl/assets/watercraft-kit (403 to scripts: by hand) | a few MB, to confirm | boats, ferry |
| `kenney_city-kit-commercial.zip`, `kenney_city-kit-suburban.zip`, `kenney_city-kit-industrial.zip` | kenney.nl/assets (by hand) | a few MB each, to confirm | buildings, the port, the hills town |
| 50+ LowPoly Guns | quaternius.itch.io/50-lowpoly-guns | about 7 MB | weapon meshes |
| Downtown City MegaKit [Standard] | quaternius.itch.io/downtown-city-megakit | about 223 MB | Downtown buildings |
| Stylized Nature MegaKit [Standard] | quaternius.itch.io/stylized-nature-megakit | about 99 MB | Sable Hills |
| Universal Animation Library 2 [Standard], if a free tier exists | quaternius.com/packs/universalanimationlibrary2.html | to check | climbing and vaulting clips (optional; IK works without) |
| About 20 textures and 4 skies at 1K | polyhaven.com (CC0) | about 100-200 MB | materials, skies |
| Blender 4.x LTS for Linux x64 (`blender-4.x.y-linux-x64.tar.xz`) | download.blender.org/release | about 350 MB, to confirm | agent image only |
| Godot 4.7 HTML manual | docs.godotengine.org downloadable build | to confirm | offline docs (the class XML comes from `--doctool`, no download) |
| apt packages: Xvfb, Mesa (llvmpipe, lavapipe), Python 3.12 | Ubuntu mirrors, at image build | about 300 MB in the image | images |

Already here from Phase 0: Godot 4.7.2 macOS (170.6 MB), Kenney Car Kit (4.8 MB), City Kit Roads
(2.9 MB), Universal Base Characters Standard (129 MB), Universal Animation Library Standard
(15.9 MB). Without the new packs the game still works (primitive buildings, hulls and guns); the
packs matter for the owner's "the game is real" gate and the look.

**First platform probe** (owner's OK; after the five tasks are through; reference and no-op only):
- verifier resources granted: 8 vCPU, 32 GB, 5,400 s (else the 6-player fallback restated in the
  GDD);
- agent image size accepted (about 10 GB with Blender, the art and the cache);
- the platform's vCPU speed (the bench);
- artifact collection without the vendor sources, and its size;
- the heavy verifier image rebuilt and grading after an idle full-length session that the platform
  ends at `timeout_sec` (no task-side timer);
- Xvfb stills, loopback UDP and nine game processes inside the verifier, no network.

## 6. RAM-aware schedule

This Mac: 24 GB, shared with other tasks' work. A Godot run takes 0.3-1.9 GB (import peak 1.9 GB,
a headless instance 0.3-0.6 GB, a 9-process online session about 2.4 GB with the spike's art and
more with a full game). Rules:
- **One heavy job at a time**, through a lock (`scripts/heavy.sh`, WS3: `flock` on one lock file,
  then `memory_pressure` must show at least 30% free, then run). Heavy: any Godot import or run,
  online sessions, Docker (its Linux VM never runs beside Godot), calibration sweeps.
- **Online sessions** start processes one at a time, at least 30% free before the first and 25%
  between starts (Phase 0's item-5 practice), and nothing else heavy runs meanwhile.
- **Light work runs in parallel:** writing GDScript and Python, plan generation and checking, ruff,
  document work. Module agents write in parallel worktrees (at most three at once) and queue their
  Godot runs through the lock.
- A full local playtest pass (about 60 playtests, 5-30 s each) takes about 20 minutes of the heavy
  lane: run it nightly and on demand, not per edit.

| Weeks (from 2026-11-30) | Light lanes (parallel) | Heavy lane (one job at a time) |
| --- | --- | --- |
| W1-W2 | WS3 kit core on macOS; WS2 full Downtown and generator extensions; WS5 starter; WS6 modules 1-2 | starter import; kit smoke runs; world-builder plan compliance |
| W3-W5 | WS6 modules 3-5; WS4 playtests for A, B, C, H; GDD v2 notes | reference playtests per module; nightly full pass |
| W6-W8 | WS6 modules 6-9; WS2 Port, Hills, links; WS4 remaining playtests | nightly pass; first two-client sessions (alone on the machine) |
| W9-W10 | WS6 module 10 (online), 11; GDD v2 | online sessions up to nine processes, one at a time with the memory gate |
| W11 | WS8 instances; WS7 Dockerfiles; Linux work if a box is allowed | probe `.so`, images and first Linux replays (on the Linux box, not here) |
| W12-W13 | WS9 mutants; WS7 packaging; README | calibration and mutant runs (Linux box); local regression only |
| W14-W15 | WS10 QA passes and fix rounds | hostile-project runs; re-check runs |
| then | the owner's go | platform probe, Oddish gate, model trials |

## 7. Risks and the first check for each

| # | Risk | First check |
| --- | --- | --- |
| 1 | The reference costs more than planned (design: 95-190 days) | after W2, compare modules 1-2's actual days with this plan; replan scope with the owner if over by half |
| 2 | A GDD rule with no failing check (the audit's zero-coverage class) | `check_coverage.py` on every commit; one mutant per assertion in WS9 |
| 3 | Evaluation cues in anything the developer reads | `check_agent_text.py` on every agent-facing change, plus CLI output and binary strings in WS4; a solver's-eye QA read |
| 4 | Bands that only our reference fits (overfit) | the 15% margin rule; sweeps; the second implementation in WS9 |
| 5 | Exact replay (AC-17) failing legitimate games or failing on x86_64 | first Linux replay of the reference: ten runs, one hash; panel decision on a tolerance before v2 |
| 6 | Verifier resources or time refused | the platform probe; the 6-player fallback written down in GDD v2 |
| 7 | Grading time above 40 minutes for the reference | time the full grade on the Linux box at the end of W11 |
| 8 | In-process probe detection or tampering (YELLOW) | QA lens 07 tries to find and hook the probe; consequence checks and free play limit the gain |
| 9 | Bandwidth target infeasible with eight players | the reference's online module measures KB/s per client with interest management at W9 |
| 10 | The plan swap breaks missions | build the reference on the alternative plan as soon as WS2 has it |
| 11 | Floor effect: models score near 0 | the starter keeps the contract stubs; the GDD puts the contract first; check partial credit with a half-built mutant |
| 12 | Clip bands vs real art (Phase 0 found the design's bands wrong) | `people.locomotion` on the reference with the real art in W3 |
| 13 | Import time and cache size with the full art | measure the import after the downloads (one heavy job) |
| 14 | Agent-caused evaluation errors | the hostile-project set in WS3 acceptance and WS10 |
| 15 | Platform verdict rejecting any stop before `timeout_sec` | no timer anywhere in the task; grep the bundle for timers in WS7 |
| 16 | IP and originality | the denylist gate; the owner reviews names before v2 |
| 17 | The vendor folder cannot be left out of the artifact | the platform probe measures collection size; fall back to a copy step |
| 18 | Online sessions flaky on shared CPUs | time-shifted comparison, margins, the retry rule; repeat sessions ten times on the Linux box |
| 19 | Scope creep from "proper" | the GDD scope list; any new rule needs a coverage row first |
| 20 | The machine runs out of memory | the heavy lock and the 30% gate on every heavy job |

## 8. The task's failure mode in one sentence

**The agent gets the city's parts working on their own but not together: people, cars and the map
pass their checks while police response, missions, online play and free play, where the systems
meet, fail.**

How the per-family results will show it:
- Group the families: foundation (A people, B vehicles, H world, I time and weather), systems (C
  traffic, D combat, G economy, J UI, K saving), integration (E alert level, F missions, L online, M free
  play).
- Report per trial the three group means and the **integration gap**
  `mean(S_A, S_B, S_H, S_I) - mean(S_E, S_F, S_L, S_M)`.
- The failure mode shows as a staircase falling from foundation to integration, a gap of 0.3 or
  more, and in E and F a large share of instances zeroed by invariants (`inv.alert_honest`,
  `inv.mission_honest`, police origin and kinematics) rather than by missing features.
- A trial that breaks the pattern (integration close to foundation) is worth reading in full: either
  a strong model or a gap in the checks.
