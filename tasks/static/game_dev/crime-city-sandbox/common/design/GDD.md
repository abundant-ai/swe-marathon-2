# Merrow Bay: game design document, version 1

Merrow Bay is our open-world crime game for PC with online play. Design and art are done; this
document is what engineering builds against. It goes with the plan files in `plan/` (their format
is in `plan/FORMAT.md`) and the art library in the game project's `assets/vendor/`.

Every name in this document (the game, the maps, the cast, the crews) is a working name.
TODO(owner): final names.

## How to use this document

- **Rules have ids** such as **FT-3**. Our tickets and the QA kit's playtest notes cite them.
- **Numbers are limits.** Where a rule gives a number or a range, the game stays inside it. Ranges
  include their ends. Distances are metres, speeds m/s unless marked km/h, times seconds of play
  (60 physics ticks per second).
- **Measured how** is part of a rule when it matters, so the design team and QA read it the same
  way. "p95" is the 95th percentile of the samples.
- **Places.** An entity's position is its node's origin, the point QA reads. Where this document
  puts something at a point (an anchor, a point of interest, a respawn point), its position ends
  within 0.5 m of that point, measured horizontally.
- **QA.** Our QA team plays every build with bots: they run the game headless, press the same
  input actions a player presses (chapter 4), and read what the game exposes for them
  (chapter 17). The kit they use is in `/app/qa-kit`, with its playtests; run them yourself as
  often as you like.
- **Open items** are marked TODO(owner) or TODO(panel) and will be settled before the next
  version of this document.

## Scope of this milestone

In: three maps (Downtown, Ashby Port, Sable Hills) joined by two highways and a ferry; six playable
leads and 35 kinds of city people built from the library's two base bodies; cars, a motorbike, two
boats and the ferry; traffic, signals and pedestrians; on-foot movement, climbing, swimming and
ragdolls; guns, melee and cover; crimes, witnesses and police response on a five-badge police
alert scale; eight missions; money, shops, garages and outfits; a day-night clock and four weathers;
HUD, minimap, phone and menus; saving; online play for two to eight players on a dedicated server.

Out: aircraft; interiors other than shops, safehouses and the bank; cutscenes; voice and music
(sound is welcome but nothing in this document depends on it); radio; property; side activities;
character creation beyond the outfits in chapter 11.

---

## 1. Pitch, tone and originality

Merrow Bay is a coastal city of three districts: a dense Downtown, the docks and warehouses of
Ashby Port, and the farms and dry hills of Sable Hills across the bay. You play one of six people
who take jobs from four contacts: deliveries, chases, races and two heists. The tone is grounded
and wry; the city is busy and reacts to what you do. The city, cast and missions are the ones in
this document and the plans; the art is the CC0 library we ship plus what the team makes.

- **OR-1** No name or text from any existing game, film or franchise appears in the project: not in
  text the player sees, and not in file, node, class or asset names. Use the working names in this
  document.
- **OR-2** The police alert level is shown as a row of badges: one visible child of `hud_alert` per
  level (UI-1).

## 2. Cast: the six leads

The player is one of six leads. Each uses one of the two library bodies, one of its hairstyles and
an outfit palette (chapter 17, AC-11, says how looks are exposed). Leads share one wallet, one set
of weapons and one garage list; switching changes who you are, not what you own.

| Id | Working name | Body | Hair | Skin | Top | Bottom | Shoes | Unlocked |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `lead_1` | Rosa Vell | `female` | `long` | `#8d5524` | `#b03a2e` | `#1c2833` | `#17202a` | from the start |
| `lead_2` | Teo Marsh | `male` | `buzzed` | `#c68642` | `#f4d03f` | `#34495e` | `#ecf0f1` | when D1 is passed |
| `lead_3` | Dara Lund | `female` | `buns` | `#f1c27d` | `#1e8449` | `#2c3e50` | `#6e2c00` | when C1 is passed |
| `lead_4` | Ike Brannock | `male` | `beard` | `#e0ac69` | `#2471a3` | `#5d4037` | `#1b1b1b` | when R1 is passed |
| `lead_5` | Nell Okafor | `female` | `buzzed_female` | `#5c3a21` | `#7d3c98` | `#212f3d` | `#f5f5f5` | when D2 is passed |
| `lead_6` | Bram Ostrow | `male` | `simple_parted` | `#ffdbac` | `#d35400` | `#1b2631` | `#6e2c00` | when H1 is passed |

Bodies: `male` is `Superhero_Male_FullBody`, `female` is `Superhero_Female_FullBody` from the base
characters pack. Hair ids are the pack's hair meshes in snake case (`Hair_BuzzedFemale` is
`buzzed_female`). Leads are shown at scale 1.0. TODO(owner): names and biographies.

- **CA-1** Each lead can be spawned (`player.spawn`) with the body, hair and palette in the table;
  its exposed look matches the table, colours within 0.02 per channel (0-1 scale).
- **CA-2** Any two leads differ in body or hair, and their tops differ by at least 0.20 (RGB
  distance, channels 0-1).
- **CA-3** A new game has only `lead_1` unlocked; each other lead unlocks when the listed mission
  is passed (`state.player.leads_unlocked`).
- **CA-4** At a safehouse, the safehouse menu's "Switch lead" lists the unlocked leads. Choosing
  one changes `state.player.lead` and the player's look within 2 s and leaves money, weapons, ammo
  and garages unchanged.
- **CA-5** Online, each client plays the lead given by `--lead` (or chosen in the Join menu), and
  every other client shows that lead's look on that player.

## 3. People of the city

Everyone else in the city belongs to one of these 35 archetypes. Members of an archetype share its
signature (top colour, bottom colour and props) and vary in skin, hair, hair colour and scale
(0.92 to 1.08). Props are small meshes made in the project (a cap, a bag, a hard hat) attached to
a bone; chapter 17 says how they are exposed. Hours wrap past midnight (20:00-04:00 is overnight).

| Id | Faction | Top | Bottom | Props | Behaviour | Where | Hours | At least |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `office_worker` | civilian | `#e5e8e8` | `#2e4053` | bag | wander | downtown_core | 07:00-19:00 | 2 |
| `shopper` | civilian | `#f5b041` | `#34495e` | bag | wander | downtown_core | 09:00-21:00 | 2 |
| `tourist` | civilian | `#48c9b0` | `#d4ac0d` | cap, backpack | wander | downtown_core | 10:00-18:00 | 1 |
| `jogger` | civilian | `#e74c3c` | `#17202a` | none | jog | downtown_residential, hills_town | 06:00-09:00, 17:00-20:00 | 1 |
| `student` | civilian | `#5dade2` | `#1b4f72` | backpack | wander | downtown_residential | 07:00-17:00 | 1 |
| `elder` | civilian | `#a1887f` | `#5d6d7e` | glasses | stroll | downtown_residential, hills_town | 08:00-18:00 | 1 |
| `street_vendor` | civilian | `#f7dc6f` | `#6e2c00` | apron | stand (5 m) | downtown_core | 08:00-20:00 | 1 |
| `night_owl` | civilian | `#8e44ad` | `#1c2833` | none | wander | downtown_core | 20:00-04:00 | 2 |
| `construction_worker` | civilian | `#f39c12` | `#5d6d7e` | hard_hat, vest | work | downtown_core, port_industrial | 07:00-17:00 | 1 |
| `dock_worker` | civilian | `#2e86c1` | `#212f3d` | hard_hat | work | port_docks | 06:00-22:00 | 2 |
| `warehouse_worker` | civilian | `#7f8c8d` | `#2c3e50` | vest | work | port_industrial | 06:00-22:00 | 1 |
| `fisher` | civilian | `#117a65` | `#4d5656` | cap | stand (5 m), within 3 m of water | port_docks, hills_town | 05:00-12:00 | 1 |
| `farmer` | civilian | `#a04000` | `#1a5276` | cap | work | hills_farms | 05:00-20:00 | 1 |
| `hiker` | civilian | `#58d68d` | `#6e2c00` | backpack | wander | hills_open | 08:00-18:00 | 1 |
| `commuter_driver` | civilian | `#d5d8dc` | `#283747` | none | drive | every district | all day | - |
| `taxi_driver` | civilian | `#fad7a0` | `#212121` | cap | drive (taxi) | downtown_core, downtown_residential, port_docks | all day | - |
| `truck_driver` | civilian | `#c0392b` | `#1c2833` | cap | drive (van, pickup) | port_docks, port_industrial, highway, hills_farms | 05:00-22:00 | - |
| `paramedic` | service | `#fdfefe` | `#1f618d` | none | stand (12 m) at a hospital; drive (ambulance) | hospitals | all day | 1 |
| `shopkeeper_weapons` | service | `#212f3d` | `#17202a` | apron | stand (4 m) at the counter | weapons shops | all day | 1 |
| `shopkeeper_clothes` | service | `#f1948a` | `#4a235a` | none | stand (4 m) at the counter | clothes shops | all day | 1 |
| `shopkeeper_food` | service | `#fbeee6` | `#922b21` | apron | stand (4 m) at the counter | food shops | all day | 1 |
| `mechanic` | service | `#154360` | `#154360` | cap | stand (10 m) at the garage zone | garages | all day | 1 |
| `bank_guard` | service | `#424949` | `#1b2631` | guard_cap | stand (12 m) inside the bank | bank | all day | 1 |
| `police_officer` | police | `#1a2a4f` | `#1a2a4f` | police_cap | patrol (foot and car) | every district | all day | 1 |
| `police_tactical` | police | `#17202a` | `#17202a` | helmet, vest | responds at levels 4-5 | anywhere | - | - |
| `crew_a_lookout` | crew_a | `#148f77` | `#0b5345` | bandana | guard turf | turf_crew_a | all day | 2 |
| `crew_a_enforcer` | crew_a | `#0b5345` | `#0b5345` | bandana | guard turf, armed | turf_crew_a | all day | 1 |
| `crew_b_lookout` | crew_b | `#b7950b` | `#4d5656` | beanie | guard turf | turf_crew_b | all day | 2 |
| `crew_b_enforcer` | crew_b | `#7d6608` | `#4d5656` | beanie | guard turf, armed | turf_crew_b | all day | 1 |
| `crew_c_lookout` | crew_c | `#922b21` | `#3b0d0b` | bandana | guard turf | turf_crew_c | all day | 2 |
| `crew_c_enforcer` | crew_c | `#641e16` | `#3b0d0b` | bandana | guard turf, armed | turf_crew_c | all day | 1 |
| `giver_delivery` | contact | `#6c3483` | `#d5d8dc` | glasses | stand (3 m) at its point | `giver_delivery` | all day | 1 |
| `giver_chase` | contact | `#1abc9c` | `#17202a` | cap | stand (3 m) at its point | `giver_chase` | all day | 1 |
| `giver_race` | contact | `#ff5733` | `#1c2833` | glasses | stand (3 m) at its point | `giver_race` | all day | 1 |
| `giver_heist` | contact | `#273746` | `#7b7d7d` | glasses | stand (3 m) at its point | `giver_heist` | all day | 1 |

"Where" names districts and turfs from the plans, kinds of place (every weapons shop), or a point
of interest id. "At least" is how many must be present within 200 m of the player while the
player is in one of those places during those hours.

Behaviours:
- **wander**: walks the sidewalks, plazas and parks at walking pace (FT-1), crossing roads at
  crosswalks (TR-10). **stroll** is wander at 0.50-0.90 m/s. **jog** is wander at running pace
  (FT-1).
- **stand (r)**: stays within r metres of its spot (for contacts, their point of interest).
- **work**: moves about its district on foot.
- **patrol**: police walk the sidewalks of their district or drive its roads in police cars, two
  officers per car.
- **guard turf**: stays inside its crew's turf, unless it is fighting or fleeing.
- **drive**: drives a vehicle in traffic (chapter 7).

- **AR-1** Every archetype in the table is present, with at least the listed count, within 200 m of
  the player at its places and hours (median over one minute, sampled every 10 s).
- **AR-2** Every member of an archetype shows its signature: top and bottom within 0.05 per
  channel of the table, and exactly the listed props. Signatures differ between archetypes.
- **AR-3** Every person is a humanoid whose skinned body mesh comes from one of the two library
  body files: height 1.50-2.00 m (top of the head to the soles, standing), scale 0.92-1.08 except
  leads at 1.0.
- **AR-4** Behaviours hold: wander, stroll and jog keep FT-1's paces and TR-9; stand stays within
  its radius for at least 95% of samples; work stays in its districts for at least 95%; guard turf
  stays inside the turf for at least 90% while not fighting or fleeing; patrol stays in its
  district while the alert level is 0; drive follows chapter 7.
- **AR-5** Armed archetypes (enforcers, the bank guard, police) carry a gun (their `weapon`
  metadata, AC-5, names it); nobody else does.

## 4. Controls and camera

The game reads player input through these InputMap actions. Each has default keyboard-and-mouse
and gamepad bindings.

`move_forward move_back move_left move_right look_left look_right look_up look_down sprint jump
crouch interact attack aim lock_target reload weapon_next weapon_prev cover accelerate brake
steer_left steer_right handbrake horn phone map pause`

Menus and the phone use Godot's `ui_up ui_down ui_left ui_right ui_accept ui_cancel`.

- **IN-1** All 28 actions above exist in the project's InputMap, each with at least one keyboard or
  mouse event and at least one gamepad event.
- **IN-2** Movement reads action strength: a move strength up to 0.5 walks, above 0.5 runs, and
  `sprint` held while running sprints. `move_*` and `look_*` act on foot; `accelerate`, `brake`,
  `steer_*` and `handbrake` act in vehicles. `handbrake` brakes the rear wheels: held alone, it
  slows a car at 2-6 m/s² (on level dry asphalt, from 40 km/h, over its first second).
- **IN-3** An action pressed in physics tick t takes effect in tick t (read input in
  `_physics_process`; the QA kit's input arrives before the tick runs).
- **CM-1** The camera is a third-person camera behind and above the player: 2.5-6.0 m from the
  player's head on foot (nearer only where a wall pulls it in, CM-4) and 5.0-10.0 m from the
  vehicle's centre (its position) when driving, and the player (the
  `Hips` bone) stays inside the middle 40% of the view (by width and height, on the project's
  1280 x 720 window with the camera's `fov` vertical, Godot's default).
- **CM-2** At full strength, `look_left` and `look_right` turn the camera around the player at
  120-240 degrees per second; `look_up` and `look_down` tilt it between -60 and +30 degrees (the
  pitch of the view, positive looking up). At lower strengths the look actions turn the camera in
  proportion to their strength.
- **CM-3** On foot, movement is relative to the camera: `move_forward` moves the player within 15
  degrees of the camera's horizontal forward direction.
- **CM-4** The camera never ends up inside a wall: the segment from the player's head to the camera
  is free of static geometry in at least 99% of physics ticks (pull the camera in when a wall is
  behind).
- **CM-5** `lock_target` locks onto the nearest person within 30 m and within 45 degrees of the
  camera's forward direction, preferring hostiles. While locked, the camera keeps the target (its
  `Chest` bone, measured as CM-1 measures the player's `Hips`) inside the middle 30% of the view
  and the player's aim point (`state.player.aim`, AC-12) is within 0.3 m of the target's `Chest`
  bone. Distances are horizontal, from the player's position to the person's. The lock holds
  from 0.5 s after `lock_target` is pressed for as long as it is held and the target stands.

## 5. On foot

Measure speeds on level ground after the gait has settled (1.5 s), as horizontal speed of the
hips. The library's clips set our paces: its walk, jog and sprint cycles move at about 1.0, 5.5
and 8.5 m/s, its crouch walk at about 0.75 and its swim at about 2.2.

- **FT-1** Paces: walk 0.80-1.50 m/s, run 4.60-6.40, sprint 7.40-9.60, crouched 0.50-1.10.
- **FT-2** Feet are planted: in each gait the feet alternate (at least 90% of steps alternate
  left and right), and a planted foot's toe slides at most 0.25 m/s at a walk, 0.40 running and
  0.60 sprinting (p95, measured in the middle 60% of each stance). A foot is planted while its
  `LeftToes` or `RightToes` bone is within 0.04 m of its lowest height in the gait; a step is a
  foot coming down to plant.
- **FT-3** `jump` from standing lifts the hips 0.40-0.80 m and keeps the player off the ground (its
  position more than 0.02 m above it) for 0.50-0.90 s on level ground.
- **FT-4** Climbing: moving into a wall or ledge 1.0-2.4 m high and pressing `jump` climbs on top
  (the player's position over its top, within 0.10 m of its height) within 3.5 s. During the climb
  a hand comes within 0.35 m of the top edge on the player's side while the hips are below it, and
  no bone passes more than 0.05 m into the obstacle.
- **FT-5** Vaulting: running at an obstacle 0.5-1.0 m high and pressing `jump` 1.0-1.5 m before it
  (from the player's position to its near side) takes the player over it (the position past its
  far side) in at most 1.2 s, the hips at least 0.10 m above its top while crossing, with no bone
  passing more than 0.05 m into it.
- **FT-6** `crouch` toggles crouching; crouched, the hips are at most 75% of their standing height
  above the ground.
- **FT-7** Swimming: in water deeper than 1.4 m the player swims. The head bone stays no lower than
  0.10 m below the surface, the torso pitches at most 45 degrees from horizontal, and the swim pace
  is 1.50-3.00 m/s. The player can leave the water up a ladder or a beach.
- **FT-8** Falls: a fall of h metres (from the ground the player leaves to the ground it lands on)
  does no damage when h is less than 3.0; from 3.0 m to 15.0 m it takes `100 * (h - 3) / 12`
  health (within 10%); 15 m or more kills.
- **FT-9** Ragdoll: a person goes limp under physics within 0.2 s of dying, of an explosion within
  6 m, of landing from a fall of 6 m or more (going limp earlier in such a fall is fine), or of
  being hit by a vehicle at 20 km/h or more. A person's `limp` metadata (AC-5) is true exactly while
  its body is under ragdoll physics: from the tick it goes limp until physics stops driving the
  body, before any blend into getting up; it is false at all other times. While limp, the hips move
  under physics (in free fall their vertical acceleration is within 20% of gravity, and they never
  move more than 1 m between two ticks), no bone goes more than 0.05 m below the ground, and the
  body stays limp for at least 1.0 s. A person still alive gets up within 6.0 s of going limp
  (`limp` false again and the hips back to at least 90% of standing height).
- **FT-10** Getting in and out: `interact` within 3.0 m of a vehicle door walks the player to that
  door (the path passes within 1.0 m of it; these distances are horizontal) and seats them within
  1.0-4.0 s. The door nearest the
  player picks the seat. Seated means the state report's `player.vehicle` and `player.seat` name
  the vehicle and seat (AC-12), as the `vehicle_entered` event says; for anyone else, their
  `vehicle` and `seat` metadata do (AC-5). Seated, until `interact` is
  pressed to get out, the hips stay within 0.35 m of the seat point and a driver's hands within
  0.30 m of the steering wheel point; city people in seats hold the same pose. `interact` in a vehicle gets out within 1.0-3.0 s (until
  `player.vehicle` is `null`, with the `vehicle_exited` event), ending on foot within 2.5 m of that
  door.
- **FT-11** Aiming: holding `aim` with a gun raises it; the gun hand is within 0.25 m of shoulder
  height and the forearm points within 20 degrees of the direction from the gun hand to the aim
  point (`state.player.aim`). People hold guns in the right hand (two-handed guns by the grip):
  the gun hand is the `RightHand` bone, the forearm runs from `RightLowerArm` to `RightHand`, and
  shoulder height is the height of `RightUpperArm` at the same moment. This holds for every gun,
  from 0.5 s after `aim` is pressed for as long as it is held.
- **FT-12** Cover: pressing `cover` within 1.5 m of an obstacle 0.8-1.4 m high moves the player to
  it within 1.0 s. In cover the player is within 0.6 m of the obstacle with the hips at most 75% of
  standing height. Moving away from the obstacle leaves cover. `state.player.cover` is true exactly
  while the player is in cover. Distances to the obstacle are horizontal, from the player's
  position to the nearest point of the obstacle. Leaning out to aim from cover (CB-8) is still
  cover (`cover` stays true); the hips clause holds while `aim` is not held. A move action pointing
  away from the obstacle leaves cover within 0.5 s.

## 6. Vehicles

Cars are built on the Kenney car kit's models (the table's library model). The motorbike is ours:
there is no motorbike in the library, so build a simple one from primitive meshes; the art team
replaces it later. Boats come from the watercraft kit (TODO(owner): approve that download; until
then, primitive hulls). Every vehicle is registered with its `model` id (chapter 17).

Handling, measured on level dry asphalt (a road or a parking lot) with the driver alone:

| Model | Library model | Seats | Mass kg | 0-60 km/h s | Top km/h | Brake from 60 km/h, dry m | Turning circle m |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sedan` | `sedan` | 4 | 1,350 | 4.5-6.5 | 150-185 | 13.5-19.5 | 10.0-13.0 |
| `hatchback` | `hatchback-sports` | 4 | 1,150 | 4.0-6.0 | 145-180 | 13.0-19.0 | 9.0-12.0 |
| `sports` | `sedan-sports` | 2 | 1,300 | 2.8-4.2 | 200-245 | 12.0-17.0 | 10.5-13.5 |
| `suv` | `suv` | 4 | 1,900 | 5.0-7.5 | 150-180 | 14.5-21.0 | 11.0-14.0 |
| `van` | `van` | 2 | 2,300 | 6.0-9.0 | 125-155 | 16.0-23.0 | 12.0-15.5 |
| `pickup` | `truck` | 2 | 2,000 | 5.5-8.0 | 135-165 | 15.5-22.0 | 12.0-15.0 |
| `taxi` | `taxi` | 4 | 1,350 | 4.5-6.5 | 150-185 | 13.5-19.5 | 10.0-13.0 |
| `police` | `police` | 4 | 1,500 | 3.8-5.6 | 175-210 | 13.0-18.5 | 10.5-13.5 |
| `ambulance` | `ambulance` | 2 | 2,800 | 6.5-9.5 | 130-160 | 17.0-24.0 | 12.5-16.0 |
| `tactical_van` | `van` (police palette) | 2 | 3,000 | 7.0-10.0 | 125-150 | 17.0-24.0 | 12.5-16.0 |
| `motorbike` | ours | 2 | 220 | 2.5-4.0 | 170-210 | 12.0-17.0 | 6.0-9.0 |

The turning circle is the diameter of the path of the vehicle's centre (its position, chapter 17) at
8 km/h with full lock.
Top speed is reached on a straight of at least 1.5 km (the highways and the Sable Hills drag
strip have one).

- **VH-1** Each model reaches 60 km/h from rest in the time band, tops out inside its top-speed
  band, stops from 60 km/h within its dry braking band, turns inside its turning-circle band, and
  has its listed mass within 10%. A car's body mesh comes from its library model's file.
- **VH-2** In rain the same vehicle needs at least 1.15 and at most 1.60 times its dry braking
  distance from 60 km/h.
- **VH-3** Each vehicle exposes `damage` from 0.0 (new) to 1.0. Damage rises only from impacts and
  explosions, and never falls except by repair. An impact that changes the vehicle's velocity by Δv
  km/h within 0.2 s (Δv is the size of the change from just before the impact to 0.2 s after it,
  so a bounce back counts) adds `0.004 * (Δv - 8)` damage (within 25%) when Δv is above 8, and
  nothing below that; bigger impacts add more.
- **VH-4** Parts come off: an impact of Δv 25 km/h or more that leaves damage at 0.25 or above
  detaches one part (bumper, door, plate, spoiler, wheel) within 0.5 s as a separate physics body
  registered as `debris`; at most six parts per vehicle.
- **VH-5** At damage 0.75 or more the engine fails: full throttle gives at most 10 km/h.
- **VH-6** At damage 0.80 or more the vehicle burns (`burning` true) and explodes 8-12 s later
  (event `vehicle_exploded`). The explosion pushes every physics body within 8 m away from it (a
  parked car 5 m away ends at least 0.3 m further off), kills people within 3 m, takes
  `100 * (6 - d) / 3` health from people at d = 3-6 m (d from the vehicle's position to theirs),
  ragdolls everyone within 6 m (FT-9), and adds 0.30 damage to vehicles within 6 m (that is all
  the damage it adds: its push is not an impact of VH-3). The wreck stays, at damage 1.0, and
  cannot be driven.
- **VH-7** Repair: in a garage zone, the garage menu's "Repair" sets damage to 0 and restores the
  parts, for `800 * damage` dollars rounded to the nearest $10, at least $50. Wrecks cannot be
  repaired.
- **VH-8** Taking a car: `interact` at the driver's door of a car with an NPC driver pulls the
  driver out within 2.0 s and seats the player within 4.0 s. The driver lands on foot, then flees
  (at least 10 m away within 10 s); a crew member turns hostile within 2.0 s instead (CB-9), and a
  police officer acts by the alert level (AL-9, CB-10). This is the crime `vehicle_theft`
  (chapter 9).
- **VH-9** The motorbike leans into turns: at least 10 degrees of roll when cornering at 2 m/s² or
  more of lateral acceleration. An impact of Δv 40 km/h or more throws the rider off (FT-9).
- **VH-10** Boats: `speedboat` (0-40 km/h in 3.0-6.0 s, top 70-90 km/h) and `fishing_boat` (0-20
  km/h in 3.0-8.0 s, top 30-45 km/h). A boat floats with its waterline (metadata `waterline_m`,
  the waterline's height in the boat's own space) within 0.50 m of the surface (within 0.25 m at
  rest), only moves under power on water, and run onto a beach at up to 40 km/h stops within 15 m
  of the shore line.
- **VH-11** The ferry is a registered vehicle with model `ferry`, running between
  `ferry_terminal_port` and `ferry_terminal_hills`. It leaves Ashby Port at 00:00, 06:00, 12:00 and
  18:00 and Sable Hills at 03:00, 09:00, 15:00 and 21:00 game time, each within 5 game minutes of
  the hour. A crossing takes 120-150 s of play, so it is docked for at least 20 game minutes before
  each departure; its ramp is open for boarding while it is docked. It carries up to 6 vehicles
  and 30 people; boarding is refused beyond that.
- **VH-12** Vehicles and people on the ferry ride with it: over a crossing, each moves at most
  1.0 m relative to the deck unless driven or walked; they arrive at the other terminal with it
  (the deck within 15 m of the terminal's dock point).

## 7. Traffic and pedestrians

Count moving NPC vehicles (above 1 km/h) and NPC people on foot within 150 m of the player, as the
median of samples taken every second over a minute. NPC vehicles are those that carry no player;
people on foot are living NPCs whose `vehicle` metadata is null (AC-5). The table is for
`traffic.set` density 1, the default, and counts start a minute after the last setup command.

| District | Day 07:00-19:00 vehicles / people | Evening 19:00-23:00 | Night 23:00-07:00 |
| --- | --- | --- | --- |
| `downtown_core` | 10-30 / 20-60 | 8-24 / 15-45 | 3-12 / 3-18 |
| `downtown_residential` | 6-18 / 10-35 | 4-14 / 6-25 | 1-8 / 1-10 |
| `port_docks` | 4-14 / 6-20 | 2-10 / 2-10 | 1-6 / 0-6 |
| `port_industrial` | 4-14 / 4-16 | 2-10 / 1-8 | 0-6 / 0-4 |
| `hills_town` | 3-10 / 6-20 | 2-8 / 3-12 | 0-4 / 0-6 |
| `hills_farms` | 1-5 / 1-6 | 0-4 / 0-4 | 0-2 / 0-2 |
| `hills_open` | 0-4 / 0-4 | 0-3 / 0-2 | 0-2 / 0-1 |
| `highway` | 4-16 / 0 | 3-12 / 0 | 1-8 / 0 |

TR-5 to TR-8, TR-11 and TR-12 are about ordinary traffic: police responding to an alert, mission
targets and racers are exempt. A vehicle's place is its position (its origin, the middle of the
vehicle as chapter 6 has it): it crosses a stop line when its position passes the line, and it is
on a lane when its position is within half the lane's width of the lane's centre line, between
the lane's start box and its stop line (plan/FORMAT.md). A vehicle's body is its collision
shapes, each taken as the box its shape fills (in the shape's own axes).

- **TR-1** Densities stay inside the table in clear and overcast weather.
- **TR-2** In rain, the number of people on foot is 40-80% of the clear-weather count at the same
  place and hour.
- **TR-3** Density holds steady: under unchanged conditions, the median of any later minute is
  within 30% of the first minute's.
- **TR-4** Signals run their plan program (FORMAT.md): each approach's signal shows green, amber
  and red at the program times, within one tick; no two approaches are green unless the plan puts
  them in the same phase; walk signals show walk only during their phase's green.
- **TR-5** NPC drivers obey signals: none crosses a stop line after the light has been red for
  0.5 s, and traffic flows on green (at day density at least 3 vehicles enter from each approach
  per 3 minutes). At amber a driver stops if it can do so braking at 4 m/s² or less. The flow
  leaves out an approach whose lanes start at a highway portal (WD-9): its traffic comes from the
  next map.
- **TR-6** All-way stops: NPC drivers come to a stop (1 km/h or less) within 4 m before the stop
  line, then go in order of arrival (the vehicle on the right first when two arrive together); no
  two vehicles on crossing paths are in the box at once; no vehicle waits more than 30 s at a stop
  line. A vehicle arrives when it first stands within 4 m before its stop line with no vehicle
  ahead of it in its lane; arrivals within 1.0 s of each other are together. The order binds
  vehicles whose paths through the box cross; where the right-hand rule cannot decide (opposite
  approaches, three or four arriving together) any of them may go first.
- **TR-7** Lane keeping: on lanes, NPC vehicles' offset from the lane centre is at most 1.0 m (p95),
  their heading is within 15 degrees of the lane's for at least 98% of samples, and none drives
  against a lane's direction. The heading and direction clauses leave out each lane's first
  10 m, where turns out of a junction end.
- **TR-8** NPC vehicles keep to the speed limit plus 10%, except police responding, chase targets
  and racers (speeds taken over 0.1 s, 6 ticks, on the lane the vehicle is on).
- **TR-9** People on foot are on walkable ground (sidewalk, crosswalk, plaza, park, parking lot,
  the interiors of shops and the bank, terrain off-road) for at least 95% of samples.
- **TR-10** People cross roads at crosswalks: at least 90% of road crossings start and end inside a
  crosswalk band. At signals they start crossing only during walk; at all-way stops, only when no
  vehicle is within 15 m approaching that crosswalk (moving faster than 1 km/h with its line of
  travel entering the band within 15 m).
- **TR-11** Drivers yield to people on crosswalks: no NPC vehicle hits a person on a crosswalk (its
  body comes within 0.3 m of the person's position).
- **TR-12** NPC vehicles stop for anything in their lane (a stopped vehicle, a person, an object):
  no NPC vehicle hits a stationary obstacle, and NPC vehicles collide with each other at most 0.02
  times per vehicle per minute. Two vehicles collide when their bodies start touching, at any
  speed; each such contact counts once for each of the two, the same two count again only after
  being apart for 1 s, and the rate is per minute of moving NPC vehicles. A person is hit when a
  body comes within 0.3 m of the person's position.
- **TR-13** Panic: within 2 s of a gunshot within 30 m, people on foot run away from the shooter (at
  least 3 m/s, moving away) for at least 10 s. People within 8 m ahead of a vehicle driving on a
  sidewalk at 20 km/h or more step out of its path (it does not hit them, TR-12). A gunshot is a
  round leaving a gun's magazine (CB-2), whoever fires it. Those who run are the people on foot
  other than crew members, police and anyone in a fight (they act by CB-9 and chapter 9): from 2 s
  after the shot until 12 s after it, each runs at least 3 m/s on average, ends at least 20 m
  farther from where the shooter stood, and gets farther from it over at least 90% of the half
  seconds. TR-9 and TR-10 do not bind people while they run.
- **TR-14** `horn`: people on foot standing in the lane within 20 m ahead of the honking vehicle step
  out of the lane within 3 s. People on foot react to gunshots, vehicles on sidewalks and the horn
  whatever their behaviour (chapter 17's `idle` included).
- **TR-15** Pop-in: NPC people and vehicles never appear within 80 m of the player, nor inside the
  camera's view closer than 200 m; they never vanish under those conditions either. Inside the
  camera's view means the point 1 m above the entity's position is inside the camera's frustum,
  whatever stands in between. In the tick a setup command runs (`world.reset`, `traffic.set`,
  `player.spawn`, `vehicle.spawn`, `npc.spawn`, `prop.spawn`, `load`; `world.reset` and `load`
  until they finish), the game may add or remove city people and vehicles anywhere, for example to
  fill the streets around a player `player.spawn` has moved.
- **TR-16** Every moving NPC vehicle has a driver: an NPC of a driving archetype (`commuter_driver`,
  `taxi_driver`, `truck_driver`, `paramedic`, and `police_officer` and `police_tactical` in police
  vehicles), seated (FT-10).

## 8. Combat

| Weapon | Kind | Damage per hit | Rate per s | Magazine | Reload s | Range m | Reserve max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fists` | melee | 10 | 2.0 | - | - | 1.5 | - |
| `bat` | melee | 25 | 1.25 | - | - | 1.8 | - |
| `pistol` | gun | 25 | 3.0 | 12 | 1.6 | 50 | 120 |
| `smg` | gun | 14 | 12.0 | 30 | 2.2 | 40 | 300 |
| `shotgun` | gun | 8 pellets of 10 | 1.2 | 6 | 3.0 | 20 | 60 |
| `rifle` | gun | 32 | 6.0 | 30 | 2.6 | 120 | 300 |

Everyone has 100 health. Armour goes from 0 to 100. Health and armour are whole numbers. People hold
guns in the right hand (FT-11).

- **CB-1** Weapons follow the table: damage per hit exactly (before armour), rate of fire within 5%
  when `attack` is held, magazine size exactly, reload time within 10%. Hits beyond the range do no
  damage. A weapon's range is the distance from the attacker's position to the position of the
  person hit; a round or a blow that reaches a person beyond it is no hit (no damage and no
  `damaged` event). The shotgun's round is eight pellets, and each pellet that hits is a hit of
  10. The rate counts rounds leaving the magazine (guns) or blows that land (melee weapons). A
  reload refills the magazine in one go: its time runs from the tick `reload` is pressed, or the
  magazine runs empty, to the tick the state report shows the magazine refilled.
- **CB-2** Ammo: firing takes rounds from the magazine; `reload` (or an empty magazine) refills it
  from the reserve; with nothing left `attack` does nothing. `state.player.ammo` shows magazine and
  reserve.
- **CB-3** `weapon_next` and `weapon_prev` cycle through the weapons the player owns in table order;
  the switch takes at most 0.5 s. Fists are always owned.
- **CB-4** With lock-on, at 15 m, at least 60% of pistol and rifle shots and 45% of SMG rounds hit
  a standing person.
- **CB-5** Armour absorbs 60% of each hit's damage until it runs out; health takes the rest. Where
  60% of a hit is not a whole number it is rounded. With less armour left than that, the armour
  takes what it has and health the rest of the hit. Armour takes weapon hits only: falls and
  explosions take health (FT-8, VH-6).
- **CB-6** Shots need a clear line from the muzzle: nothing is hit through walls or vehicles' solid
  bodies.
- **CB-7** Health 0 means death: event `died` and a ragdoll (FT-9).
- **CB-8** In cover, the player takes at most 40% of the damage the same attackers deal in the open
  over the same time. From cover, holding `aim` leans out (the `Head` bone rises at least 0.30 m)
  and `attack` fires. "The same attackers over the same time" means the same people, from the same
  start, firing over the same span of play: once with the player standing a step behind the
  obstacle (not in cover), once with the player in cover behind it, with the attackers in front of
  the obstacle. The damage is the sum of the `amount`s of the `damaged` events those attackers
  cause the player (AC-13), so cover cuts it by keeping hits off the player.
- **CB-9** Crew members turn hostile (their `hostile` metadata, AC-5) when the player attacks any
  member of their crew, or aims a gun inside their turf for more than 5 s. Hostile enforcers attack
  from up to 40 m, and at least half of them reach cover (within 1.0 m of an obstacle 0.8-1.4 m
  high) within 10 s of a fight starting; hostile lookouts flee (at least 20 m away within 10 s).
  Below 30 health an enforcer moves at least 10 m away from the player. In detail: attacking a
  member means hitting it, and every member of that crew within 100 m of the player turns hostile
  within 2.0 s of the hit. Once the player has aimed a gun (`aim` held) while standing inside the
  turf for more than 5 s in one go, the members of that crew within 100 m turn hostile within
  2.0 s, not before, whatever behaviour they were given (chapter 17). A fight starts when the first
  member turns hostile. A hostile enforcer with the player within 40 m and in sight fires at the
  player and lands at least one hit within 15 s; reaching cover counts at any moment within the
  10 s. A hostile lookout keeps `hostile`
  true while it flees and ends at least 20 m farther from the player within 10 s of turning
  hostile; an enforcer below 30 health ends at least 10 m farther from the player within 10 s of
  dropping below it.
- **CB-10** Police fight only at alert level 3 or more; at levels 1 and 2 they try to arrest
  (AL-9).

## 9. Crime and the alert level

| Crime | Committed when | Level if witnessed |
| --- | --- | --- |
| `red_light` | a vehicle the player drives crosses a stop line 0.5 s or more after its light turned red | 1 |
| `speeding` | the player drives 30 km/h or more above the limit within sight of police | 1 |
| `vehicle_theft` | the player pulls a driver out (VH-8) | 1 |
| `assault` | the player damages a person who is not police | 1 |
| `hit_person` | a vehicle the player drives hits a person at 20 km/h or more | 1 |
| `shots_fired` | the player fires a gun | 2 |
| `murder` | the player kills a person who is not police | 2 |
| `vehicle_destroyed` | a vehicle explodes because of the player | 2 |
| `assault_police` | the player damages a police officer | 3 |
| `kill_police` | the player kills a police officer | 4 |

Witnesses are police officers and everyone else except crew members (civilians, service staff and
contacts). A witness sees a crime when there is a clear line from
its head bone to any part of the player (or the player's vehicle) within its sight range at that
moment. Gunshots are also heard: anyone within 40 m witnesses `shots_fired` without a clear line.

| Weather | Sight range by day (06:00-20:00) | By night (20:00-06:00) |
| --- | --- | --- |
| clear, overcast | 60 m | 40 m |
| rain | 45 m | 30 m |
| fog | 30 m | 30 m |

| Level | Police cars (two officers each) | Tactical vans | First unit within 25 m of the player | Search zone radius | Cooling-off time |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 0 | 60 s | 100 m | 20 s |
| 2 | 2 | 0 | 50 s | 150 m | 30 s |
| 3 | 4 | 0 | 45 s | 200 m | 45 s |
| 4 | 6 | 1 | 40 s | 260 m | 60 s |
| 5 | 8 | 2 | 40 s | 320 m | 90 s |

- **AL-1** Every crime in the table emits a `crime` event with its type and the ids of its
  witnesses, witnessed or not.
- **AL-2** A crime seen by a police officer raises the alert level within 1.0 s. A crime seen only
  by other witnesses is phoned in: the level rises 10 s (within 1 s) after the crime if at least one
  of those witnesses is still alive then.
- **AL-3** A crime nobody witnesses never raises the level.
- **AL-4** A witnessed crime sets the level to the higher of the current level and the crime's
  level; if the player is already at or above the crime's level, the level goes up by one, to at
  most 5. Mission events can set the level directly (chapter 10).
- **AL-5** Sight ranges follow the table: a crime committed just outside every witness's range is
  not seen, and one just inside is.
- **AL-6** Response: the first police unit gets within 25 m of the player within the table's time
  after the level is reached; within 90 s the number of police vehicles moving towards the player
  or within 100 m of them reaches the table's count, and never exceeds it by more than 2.
- **AL-7** Police come from police stations or from patrols already in the world: a unit new to the
  world first appears at least 100 m from the player and outside the camera's view. Units move
  continuously (never more than 1.1 times their model's top speed), drive on roads, and never pass
  through buildings or other static geometry.
- **AL-8** From level 3, within 90 s of reaching it, police set at least one roadblock ahead of the
  player: at least two police vehicles stopped across the road (within 30 degrees of square to the
  lanes, covering at least 70% of the carriageway's width) on a lane within 300 m ahead of the
  player, along the lanes the player's vehicle can reach.
- **AL-9** Arrest: while the level is 1 or 2, a player on foot or in a vehicle stopped below 1 km/h
  with a police officer within 2.0 m for 3.0 s is arrested (event `arrested`). The player comes back
  at the nearest police station's respawn point within 10 s, at level 0, having lost every weapon
  except fists and paid a $500 fine (or all their money if they have less).
- **AL-10** Death: the player comes back at the nearest hospital's respawn point within 10 s (event
  `respawned`), with 100 health, 0 armour and level 0, having paid a $250 fee (or all their money
  if less), keeping weapons.
- **AL-11** Escape: the search zone is centred where a unit last saw the player, or where the crime
  happened if no unit has seen the player yet. The level drops to 0 only once the player has stayed
  outside the zone and out of every unit's sight for the cooling-off time; being seen re-centres the
  zone and restarts the time. The level never drops in any other way except arrest and death.
- **AL-12** At level 0 police leave the player alone: no police unit keeps moving towards the
  player for more than 10 s, and no officer stays within 5 m of the player for more than 5 s.

## 10. Missions

Four contacts give missions. A contact offers each mission once it is unlocked and until it is
passed. Every stage that is about a place uses a point of interest from the plans; the ones not
yet in the plan files arrive with the Ashby Port and Sable Hills plans.

| Id | Type | Contact | Unlocked by | Stages | Fails when | Payout |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | delivery | `giver_delivery` | new game | 1. get in the van at `d1_pickup`; 2. drive it to `d1_dropoff` within 120 s and stop inside the point | timer runs out; van damage reaches 0.75 or the van enters water; death; arrest | $1,500 |
| C1 | chase | `giver_chase` | D1 | 1. get to `c1_start`; 2. stop the target car before it escapes, within 180 s | target more than 400 m away for 10 s; timer; death; arrest | $2,000 |
| R1 | race | `giver_race` | D1 | 1. get a car to `r1_start`; 2. two laps through `r1_cp1`-`r1_cp8` in order, back to `r1_start`, within 180 s | time runs out; car wrecked; death; arrest | $1,200 |
| D2 | delivery | `giver_delivery` | C1 and R1 | 1. take the sports car at `d2_pickup`; 2. deliver it to `d2_dropoff` within 600 s with damage under 0.50 | timer; damage 0.50 or more at delivery; car wrecked or in water; death; arrest | $3,000 |
| C2 | chase on foot | `giver_chase` | C1 | 1. get to `c2_start`; 2. catch the runner (within 2.0 m, then `interact`) within 120 s | runner more than 150 m away for 10 s; timer; death; arrest | $1,800 |
| R2 | race | `giver_race` | R1 and D2 | 1. get a car to `r2_start`; 2. one lap through `r2_cp1`-`r2_cp12` against three NPC racers, finishing first | not first; car wrecked; death; arrest | $4,000 |
| H1 | heist | `giver_heist` | D2 and C2 | 1. take the getaway car at `h1_car`; 2. drive to `bank_downtown`; 3. go into the bank; 4. hold the vault for 30 s (leaving the vault restarts the hold); 5. get the alert level back to 0; 6. take the cash to `h1_stash` | death; arrest | $16,000 haul, $4,000 crew share |
| H2 | heist | `giver_heist` | H1 and R2 | 1. take the cargo van at `h2_van`; 2. get the alert level back to 0; 3. drive it to `h2_stash` | van damage reaches 0.75; death; arrest | $15,000 |

- **MS-1** A contact offers its unlocked missions: walking within 3.0 m and pressing `interact`
  starts the mission it offers (event `mission` with state `active` within 1.0 s). Locked missions
  are not offered.
- **MS-2** Each active stage that is about a place shows one marker (a registered `marker`) within
  5 m of its point of interest; stages without a place (holding the vault, getting the alert level
  back to 0, stopping or catching a target) show none. The next stage's marker appears only when
  the current stage is done, and the minimap route leads to the current marker (UI-3).
- **MS-3** Stages complete in order. A stage about a place completes only when the player (or the
  mission vehicle, for driving stages) is within the point's `radius_m` (6 m unless the plan says
  otherwise); getting in a vehicle needs the player seated in it (FT-10).
- **MS-4** A timed stage shows the remaining time on the HUD (UI-8) and fails within 2.0 s after
  the time runs out; a stage passed in time does not fail.
- **MS-5** Each listed failure fails the mission within 2.0 s of happening: event `mission` with
  state `failed`, no payout, markers removed, and the contact offers it again.
- **MS-6** Passing pays the payout (event `mission` with state `passed`, then `money_changed` with
  reason `payout`), unlocks what the tables say (missions and leads) and autosaves (SV-1).
- **MS-7** Starting a mission sends a phone message from its contact (event `phone_message`; the
  phone's Messages app lists it).
- **MS-8** Race checkpoints count only in order: passing a later one first does nothing, and the
  finish does not count until every checkpoint of the lap has been passed.
- **MS-9** R2's NPC racers drive the course through every checkpoint in order at racing speed and
  finish the lap within 250 s if nothing stops them.
- **MS-10** C1's target drives away along roads at up to 120 km/h, ignoring signals. It is stopped
  when its damage reaches 0.75 or when it stays below 1 km/h for 3 s with the player within 10 m.
  C2's runner keeps to walkable ground at 5.0-6.0 m/s, so a sprinting player can catch it.
- **MS-11** H1's vault hold sets the alert level to 3 at once (no witness needed). H1 pays the haul
  and the crew share as two `money_changed` events (`payout` +16,000, `crew_share` -4,000).
- **MS-12** `state.missions` reports each mission as `locked`, `available`, `active` (with the
  stage number), `passed` or `failed`.

## 11. Economy

A new game starts with $500. Shops are open around the clock.

| Shop | Item | Price | Effect |
| --- | --- | --- | --- |
| weapons | `bat` | $100 | owned |
| weapons | `pistol` | $400 | owned, one magazine |
| weapons | `smg` | $1,200 | owned, one magazine |
| weapons | `shotgun` | $1,000 | owned, one magazine |
| weapons | `rifle` | $2,500 | owned, one magazine |
| weapons | ammo for a gun you own | pistol $20, smg $40, shotgun $35, rifle $60 | one magazine's worth into the reserve |
| weapons | `armour` | $250 | armour to 100 |
| food | `meal` | $20 | +40 health, up to 100 |
| food | `medkit` | $120 | health to 100 |
| clothes | outfit `street` | $150 | owned outfit |
| clothes | outfit `sport` | $180 | owned outfit |
| clothes | outfit `work` | $200 | owned outfit |
| clothes | outfit `night` | $300 | owned outfit |
| clothes | outfit `smart` | $450 | owned outfit |
| clothes | outfit `formal` | $600 | owned outfit |

| Outfit | Top | Bottom | Shoes |
| --- | --- | --- | --- |
| `street` | `#5d6d7e` | `#1b2631` | `#f8f9f9` |
| `sport` | `#2ecc71` | `#212f3d` | `#fdfefe` |
| `work` | `#e67e22` | `#2c3e50` | `#4e342e` |
| `night` | `#212121` | `#212121` | `#7b241c` |
| `smart` | `#d6eaf8` | `#1a237e` | `#3e2723` |
| `formal` | `#17202a` | `#17202a` | `#000000` |

Every lead also owns its own outfit (`default`, chapter 2).

- **EC-1** A new game starts with $500, fists only, 100 health and 0 armour.
- **EC-2** Prices and effects follow the table exactly. Buying a weapon you own, ammo that would
  take the reserve past the weapon's maximum, armour at 100 or health at 100 is refused.
- **EC-3** A purchase you cannot afford is refused: money and possessions unchanged, and the shop
  shows the notice "Not enough money".
- **EC-4** Every change of money is announced by a `money_changed` event (amount, reason, new
  balance); the reasons are `purchase`, `payout`, `crew_share`, `fine`, `fee`, `repair`, `setup`,
  `load` (loading a save) and `rejoin` (reconnecting online). Money changes in no other way.
- **EC-5** Clothes: buying an outfit adds it to `state.player.outfits`; wearing one (the clothes
  shop's "Wear" or the safehouse's "Wardrobe") changes the player's top, bottom and shoes to the
  outfit's colours within 1.0 s. Outfits are owned by all leads.
- **EC-6** Garages (`garage_downtown`, `garage_port`, `garage_hills`) hold two vehicles each. Stop a
  vehicle inside the garage zone and choose "Store" in the garage menu: the vehicle leaves the world
  within 2.0 s and is listed in `state.garages` with its model, colour and damage. "Retrieve"
  brings it back inside the zone as it was. A third vehicle is refused. Police vehicles, tactical
  vans and wrecks cannot be stored.
- **EC-7** Stored vehicles stay stored when the player goes away and comes back, and across saving
  and loading (SV-3).

## 12. World, clock and weather

The world is built from the plan files when a map loads (`plan/FORMAT.md`). Static colliders carry
a `surface` tag (chapter 17) so QA can tell what a probe hits.

- **WD-1** Roads: along every lane centre, the road surface (tagged `road`) is at the plan's height
  within 0.10 m, for at least 98% of points sampled every 10 m.
- **WD-2** Sidewalks (tagged `sidewalk`) are at their elevation within 0.05 m along every ring;
  crosswalk bands are road surface (at the road's height within 0.10 m, as in WD-1) tagged
  `crosswalk`.
- **WD-3** Buildings: every parcel zoned commercial, residential, civic or industrial has one
  building (tagged `building`) whose roof is at `base_m + height_m` within 0.5 m over at least 95%
  of its footprint, and no building surface lies outside its parcel. Plazas, parks and parking lots
  are open ground at `base_m` within 0.05 m (tagged `plaza`, `park`, `parking`).
- **WD-4** Interiors: each door is an opening at least as wide and high as the plan says; rooms are
  empty from the floor (at `floor_m` within 0.10 m, tagged `interior`) to at least 0.10 m under
  `ceiling_m`; connected rooms have openings at least 1.2 m wide (1.0 m above the floor).
- **WD-5** Every point of interest stands on a surface: a ray down from 0.6 m above `p` hits within
  0.30 m of its height.
- **WD-6** Water: each plan water polygon is covered by a water area (chapter 17) with its surface
  at `level_m` within 0.05 m; the bed is at `level_m - depth_m` within 0.30 m away from shores.
- **WD-7** Terrain: away from roads, blocks and parcels, the ground is within 1.0 m of the
  heightmap at at least 98% of sampled points.
- **WD-8** Plan changes: given another plan folder (`--plan-dir`) with different roads and parcels
  and the same point-of-interest ids, the game builds that world instead, and WD-1 to WD-7 and the
  missions hold on it.
- **WD-9** Highways: driving through a portal node moves the player, the vehicle and its passengers
  to the linked map within 10 s (event `map_transition`). The vehicle keeps its id, its damage
  (within 0.02) and its passengers in their seats; the player keeps the alert level; the vehicle
  appears on the matching lane within 30 m past the linked portal, at its speed within 20%.
- **WD-10** The ferry changes map at its portal the same way, carrying everything on its deck.
- **WD-11** Clock: game time advances one minute per second of play (within 1%) and is reported as
  `hh:mm`. `time.set` changes it at once.
- **WD-12** Street lights: a lamp post (an `OmniLight3D` or `SpotLight3D` in group `street_light`)
  at most every 35 m along every sidewalk ring; lights are on (visible, energy above 0) from 19:30
  to 06:30 and off otherwise, within one game minute.
- **WD-13** The sun is a `DirectionalLight3D` in group `sun`. Its elevation follows the clock: up
  from 06:00 to 19:00, `65 * sin(pi * (t - 6) / 13)` degrees at hour t (within 3 degrees), and at
  least 5 degrees below the horizon from 20:00 to 05:00.
- **WD-14** Weather is `clear`, `overcast`, `rain` or `fog`. It changes only when set (`weather.set`
  or a mission) and is reported in `state.weather`. In this milestone there is no automatic weather
  cycle.
- **WD-15** Rain: wet braking (VH-2), fewer people (TR-2), the witness ranges of chapter 9, and a
  rain effect (a particle node in group `fx_rain`, emitting) within 20 m of the camera while it
  rains, none otherwise.
- **WD-16** Fog: the world environment's fog is on with a density of at least 0.01 while it is
  foggy and off in clear weather; witness ranges follow chapter 9.
- **WD-17** Overcast: the sun's light energy is at most half of clear weather's at the same time of
  day.

## 13. UI

Every menu and the phone work with the `ui_*` actions alone (no mouse needed). A menu item's text
starts with the item's name from this document (for example "Pistol" or "Slot 2"); the QA bots
find items by that text.

- **UI-1** HUD: `hud_health` shows health and `hud_armour` armour as whole numbers; `hud_money`
  shows money as "$" with comma thousands separators (`$1,250`); `hud_weapon` shows the weapon's
  name and, for guns, "magazine/reserve" (`Pistol 12/36`); `hud_alert` has one visible badge per
  alert level and none at 0. Each matches the state report within 0.5 s.
- **UI-2** Minimap (`hud_minimap`): it shows the area within 150-400 m around the player, with icons
  (`minimap_icon`, each with metadata `poi` or `entity_id` naming what it stands for) for the
  player, every police station, hospital, shop, garage and safehouse in that area, the contacts with
  a mission to offer, the current mission marker and, while the alert is up, police units. Icon
  positions fit the world positions with one rotation, scale and offset to within 3 px for at least
  95% of icons.
- **UI-3** Route (`minimap_route`): a line from the player to the current destination (a mission
  marker, or a place picked in the phone's Map app). At least 90% of its points lie within 8 m of a
  lane, and its length is at most 1.25 times the shortest path over the plan's lanes.
- **UI-4** While the alert is up, the minimap shows the search zone (`minimap_search_zone`) as a
  circle whose centre and radius fit the zone within 10%.
- **UI-5** Phone (`phone`, opened and closed with the `phone` action or `ui_cancel`): the apps
  "Contacts" (contacts whose missions the player has started), "Messages" (their messages, newest
  first) and "Map" (pick a point of interest to set the route). The phone works while walking and
  driving.
- **UI-6** Main menu: started without `--role`, the game shows the main menu (`main_menu`) with
  "New game", "Load", "Host", "Join" and "Quit". "New game" starts at `safehouse_downtown` with
  `lead_1`, $500, 08:00 and clear weather, with D1 available. "Load" lists the save slots. "Host"
  asks for a port and starts a server the menu's player joins; "Join" asks for an address, a name
  and a lead.
- **UI-7** Pause (`pause`): solo, the world stops (no entity moves and the clock stands still) and
  the pause menu shows "Resume" and "Quit to menu"; `state.ui.paused` is true. Online, the menu
  opens and the world goes on.
- **UI-8** `hud_mission_timer` shows the time left of a timed stage as "m:ss"; `hud_notice` shows
  notices (such as "Not enough money") for at least 2.0 s.
- **UI-9** Shop, garage and safehouse menus: interacting at a shop counter, in a garage zone or at a
  safehouse save point opens that place's menu. Shop menus list the shop's items with prices; an
  item opens "Buy" and "Back" (the clothes shop adds "Wear" for owned outfits). The garage menu
  has "Store", "Retrieve" (one entry per stored vehicle, named by model) and "Repair". The safehouse
  menu has "Save", "Switch lead" and "Wardrobe".
- **UI-10** Online, `hud_net_warning` appears within 1.5 s of the client receiving no update from
  the server and hides within 1.5 s after updates resume.
- **UI-11** The `map` action opens a full-screen map (`map_screen`) of the whole map with the same
  icons as the minimap, fitting the world the same way; `state.ui.map` is true while it is open, and
  `map` or `ui_cancel` closes it.

## 14. Saving and loading

- **SV-1** The player saves at a safehouse ("Save", then "Slot 1", "Slot 2" or "Slot 3"). The game
  also saves to the slot "Auto" after every mission passed, as soon as the alert level is 0.
- **SV-2** Saving is refused, with a notice, while the alert level is above 0 or a mission is
  active.
- **SV-3** A save holds money, weapons and ammo, armour and health, owned and worn outfits, the
  current lead and unlocked leads, garages and their vehicles, every mission's state, the time of
  day and the weather. Loading puts the player at the safehouse where the save was made (Auto: the
  safehouse nearest to where the mission ended) at alert level 0, with all of that restored.
- **SV-4** Saves are atomic: once the `saved` event fires, killing the process at any moment leaves
  that slot loadable with that state; a kill during a save leaves the slot's previous save loadable.
- **SV-5** A damaged save file does not crash the game: loading it shows "Slot n is damaged" (the
  `load` command answers `{"ok": false, "error": "Slot n is damaged"}`), the game stays
  responsive, and other slots still load.
- **SV-6** `--save-dir=DIR` keeps saves in DIR (default `user://saves`).

## 15. Online play

A session is one dedicated server (`--role=server`, headless) and two to eight clients on one map
(the server's `--map`). Use Godot's ENet transport (`ENetMultiplayerPeer`, UDP). Travel between
maps is solo-only in this milestone (NT-15). TODO(owner): eight players, or six if server costs
require it.

Our network targets: players up to 250 ms round trip, 10% packet loss in bursts, and short
drop-outs of a few seconds. Plan bandwidth from the start: full snapshots of about 160 entities at
20 per second already use about 48 KB/s per client, so send each client what is near it and send
changes, not everything.

- **NT-1** Roles: `--role=server --port=P [--max-players=N] [--pvp=on|off] [--dev-commands=on|off]`
  and `--role=client --connect=HOST:P --name=NAME [--lead=ID]`. Up to `--max-players` (2-8,
  default 8) clients play at once.
- **NT-2** The server is in charge: it simulates the world and clients send input. A position a
  client writes for its own player never reaches the server or other clients; the server corrects
  that client within 2.0 s and no other client sees the player jump more than 5 m.
- **NT-3** DevConsole commands that would change the world are refused on clients unless the server
  runs with `--dev-commands=on` (default off).
- **NT-4** Damage counts only when the server confirms the hit.
- **NT-5** A joining client sees the server's world (every entity within 150 m of its player, the
  clock and the weather) within 5 s of joining.
- **NT-6** What clients show converges on the server: for every remote entity, the distance between
  the client's position and the server's position at some moment in the last (2 x round trip + 250
  ms) is at most 1.5 m on foot and 3.0 m in vehicles (p95) at 120 ms round trip with 5% loss, and
  at most 2.5 m and 5.0 m at 250 ms with 10% bursty loss.
- **NT-7** The local player responds at once: on the client it starts moving within 100 ms of the
  input and agrees with the server within 1.0 m (p95) once it has stopped for 1 s.
- **NT-8** Deaths, alert-level changes, mission states and vehicle entries reach every client that
  shows the entity within 2.0 s (p95 at 120 ms with 5% loss), in order for each entity.
- **NT-9** A player who drops out disappears from other clients within 10 s. Reconnecting under the
  same name within 5 minutes restores their money, weapons, lead and position (within 10 m).
- **NT-10** A client cut off for 3 s stays in the session (set the ENet peer timeouts so a few
  seconds of silence never disconnects), shows `hud_net_warning`, and converges again (NT-6)
  within 3 s after the connection returns, with no duplicate or ghost entities and no back-and-forth
  correction larger than 2 m.
- **NT-11** With `--pvp=on` players can damage each other: the victim's health drops on the server
  and on the victim's client within 1.0 s (p95), and the shooter's client shows the hit. With
  `--pvp=off` they cannot.
- **NT-12** An online session starts with every mission available at its contact, and H1 can be
  played together: the players within 30 m of the contact when it starts form the crew; every crew
  member sees the markers and gets the full payout; the mission fails only when every crew member is
  dead or arrested.
- **NT-13** Bandwidth with eight players: each client receives at most 48 KB/s (median) and 96 KB/s
  (p95), and sends at most 16 KB/s (median).
- **NT-14** The server's physics tick takes at most 16.7 ms (p95) with eight players.
- **NT-15** An online session stays on its map: no player changes map, and the ferry stays docked at
  its terminal.

## 16. Performance and project settings

- **PF-1** The project is Godot 4.7.2 (`/opt/godot`), written in GDScript and shaders only: no C#,
  no GDExtension or other native libraries.
- **PF-2** Project settings: Jolt Physics, 60 physics ticks per second, `physics_jitter_fix` 0,
  physics on the main thread, the Compatibility renderer.
- **PF-3** A clean import (no `.godot` folder; the vendor library's import cache is supplied)
  finishes within 10 minutes, and the import cache of the project's own files stays under 1 GB.
  Headless imports never run the editor's "detect 3D" step, so keep texture compression explicit in
  the `.import` files of anything you add (the vendor files already are).
- **PF-4** Boot: from process start to a playable world (solo: the player is registered and `state`
  answers; server: listening, world built) takes at most 60 s.
- **PF-5** `world.reset` takes at most 3 s.
- **PF-6** Our QA runs each game process with one worker thread
  (`threading/worker_pool/max_threads=1`, set in `override.cfg`). Under that setting, with the day
  population of the busiest district around the player, a solo physics tick takes at most 8 ms on
  average and 12 ms at p95 on one core. TODO(panel): confirm both limits on the target server
  hardware.
- **PF-7** Each game process (solo, server or client) stays under 1.5 GB of resident memory.
- **PF-8** No crash: in an hour of play the process never exits or stops answering, whatever the
  player does.
- **PF-9** Everything works headless (`--headless`): no game rule may depend on a rendered frame.

Release builds take the vendor library as we ship it: only the `.import` and `.tres` files under
`assets/vendor/` carry over from the project. Put meshes, materials and scenes you make under
`assets/` outside `vendor/`.

## 17. Automation contract

This is what the game exposes to QA's bots and tools. Keep it small and stable; it is a product
feature like any other.

### Command line

```
godot --path /app/game -- --role=solo [--variation=N] [--map=downtown|port|hills] [--plan-dir=DIR] [--save-dir=DIR]
godot --headless --path /app/game -- --role=server --port=P [--variation=N] [--map=M] [--max-players=N] [--pvp=on|off] [--dev-commands=on|off] [--plan-dir=DIR] [--save-dir=DIR]
godot [--headless] --path /app/game -- --role=client --connect=HOST:P --name=NAME [--lead=ID]
```

`--variation` picks the starting population (any whole number; default 1). With no `--role`, players get the main
menu (UI-6); `--role=solo` starts a new game at once, as the menu's "New game" does. Without
`--plan-dir` the game reads the plans in `/app/design/plan`.

- **AC-1** The game accepts the flags above with these meanings.

### DevConsole

An autoload named `DevConsole` (also on a console key in development builds) with
`exec(command: String, args: Dictionary) -> Dictionary` and `signal event(name: String,
data: Dictionary)`. The commands set up situations for development and QA.

| Command | Arguments | Effect |
| --- | --- | --- |
| `world.reset` | `variation`, `map` | Rebuild people, vehicles, missions, clock (08:00) and weather (clear) from the variation; the static world stays |
| `time.set` | `hhmm` (a string such as `"21:30"`) | Set the clock |
| `weather.set` | `kind` | Set the weather |
| `player.spawn` | `lead`, `at`, `heading` | Spawn the player, or move the existing one; with `lead`, the player becomes that lead (its body, hair and colours, chapter 2) |
| `player.give` | `weapon`, `ammo`, `money`, `outfit`, `health`, `armour` | Give or set: `weapon` and `outfit` become owned (a gun the player did not own comes with a full magazine; the weapon given is put in hand), `ammo` rounds go into the reserve of `weapon` (or of the gun in hand), `money` is added; `health` and `armour` are set (health 0 is death, CB-7) |
| `vehicle.spawn` | `model`, `at`, `heading`, `driver` (`player`, an archetype or `none`), `damage`, `colour` | Spawn a vehicle; an archetype as `driver` sits in seat 0 with `wander`, so a driving archetype drives it in traffic at once. The city's own vehicles in its spot make way (TR-15 lets them leave at once) |
| `npc.spawn` | `archetype`, `at`, `heading`, `behaviour` (`idle`, `wander`, `guard`, `hostile`, `reckless`), `seat` (`{"vehicle": id, "index": i}`) | Spawn a person |
| `prop.spawn` | `kind` (`wall`, `crate`, `low_cover`, `ramp`, `barrier`, `tower`), `at`, `size` (`[x, y, z]`), `heading` | Spawn a solid object (static, layer 5) standing on `at`, the middle of its base; `size` is its width, height and depth, the depth along `heading` |
| `traffic.set` | `density` (0 to 2) | Scale traffic and people around the player |
| `mission.start` | `id`, `stage` | Start a mission at a stage, skipping its contact |
| `save`, `load` | `slot` | Save or load |
| `state` | none | The state report |

`at` takes any anchor from `plan/FORMAT.md`, or `"player"` for the player's position. NPC
behaviours: `idle` stands still; `wander` is the archetype behaviour of chapter 3; `guard` stands
and turns hostile when attacked; `hostile` attacks the player; `reckless` drives at up to 1.3 times
the speed limit, ignoring signals. In seat 0 (`seat`), `wander` drives in traffic (a driving
archetype), `reckless` drives that way, and `idle` holds the vehicle still.

- **AC-2** `exec` answers `{"ok": true, ...}` or `{"ok": false, "error": "..."}` and never crashes on
  unknown commands or bad arguments. Arguments arrive from JSON, so numbers may be floats: accept
  `12.0` wherever an id or an integer is expected.
- **AC-3** Every command does what the table says, immediately (within the same tick, except that
  `world.reset` and `load` may take up to 3 s). `player.spawn`, `vehicle.spawn`, `npc.spawn` and
  `prop.spawn` answer with the entity's id: `{"ok": true, "id": 42}`.

### Entities

- **AC-4** Every gameplay object is a `Node3D` in group `entity` with metadata `entity_id` (an int,
  unique for the life of the process: never reused, not even after `world.reset`), `kind`
  (`player`, `npc`, `vehicle`, `signal`, `pickup`, `marker`, `debris`, `light`, `prop`),
  `archetype` (a lead id, an archetype id, a vehicle model, or a short name) and `faction`.
- **AC-5** People (`player`, `npc`) have exactly one `Skeleton3D` using the humanoid profile's bone
  names (`Hips`, `Spine`, `Chest`, `Neck`, `Head`, `LeftUpperArm`, `LeftHand`, `LeftUpperLeg`,
  `LeftFoot`, `LeftToes` and the rest), skinned meshes bound to it, and a physics body on the people
  layer, plus metadata `weapon` (the weapon in hand, or `none`), `hostile` (true while they
  attack or are about to attack the player; a crew member that has turned hostile keeps it, CB-9),
  `limp` (true while the body is under ragdoll
  physics, FT-9), and `vehicle` and `seat` (the id of the vehicle they sit in and the seat's index
  while seated, FT-10, otherwise `null`; for the player, what `player.vehicle` and `player.seat`
  report). Nothing outside the registry has a `Skeleton3D`, a `CharacterBody3D` or a
  `VehicleBody3D`. The library bodies and clips use their own bone names;
  import them through a `BoneMap` with Godot's `SkeletonProfileHumanoid` so the skeleton gets the
  profile's names (it works headless, from the `.import` files alone). The project as handed over
  already does this: `assets/vendor/humanoid_bone_map.tres`, referenced from the `.import` files
  of the bodies, the hair and the animation library. Keep them or replace them.
- **AC-6** Vehicles have a physics body at their root on the vehicles layer, metadata `model`,
  `damage`, `burning` and `colour`, and one `Marker3D` per seat in group `seat` with metadata `index`
  (0 is the driver: a car's front left seat, as traffic drives on the right; the motorbike's
  front seat) and `door` (a door point in vehicle space). The driver's seat also has metadata
  `wheel` (the steering wheel point, in vehicle space). A seat's position is its seat point (FT-10).
  Boats also have `waterline_m` (VH-10).
- **AC-7** Each signalised approach has a `signal` entity with metadata `intersection`, `approach`
  and `state` (`red`, `amber`, `green`); each crosswalk with walk signals has one with `crosswalk`
  and `state` (`walk`, `dont_walk`).
- **AC-8** Collision layers: world 1, vehicles 2, people 3, water 4 (areas), props 5. Static colliders
  of the world have metadata `surface` (`road`, `crosswalk`, `sidewalk`, `building`, `interior`,
  `plaza`, `park`, `parking`, `terrain`, `dock`). Water areas are `Area3D` on layer 4 with metadata
  `water_level`.
- **AC-9** Groups: `street_light`, `sun`, `fx_rain` (chapter 12); HUD groups (chapter 13).
- **AC-10** Mission markers are `marker` entities with metadata `mission`, `stage` and `poi`.
  Detached parts are `debris` entities with metadata `vehicle`.

### Looks

- **AC-11** People have metadata `look`: `{"body", "hair", "skin", "top", "bottom", "shoes",
  "hair_colour", "props", "scale"}` with colours as `#rrggbb` and props as a list of ids. The body's
  skinned meshes carry per-instance shader parameters `look_skin`, `look_top`, `look_bottom` and
  `look_shoes`, and the hair mesh `look_hair`, set to those colours and used by their shaders. Each
  prop is a mesh attached to a bone with metadata `prop` (its id).

### State report

- **AC-12** `state` returns: `tick`, `map`, `clock` (`hh:mm`), `weather`, `variation`; `player`
  (`id`, `lead`, `health`, `armour`, `money`, `alert`, `weapon`, `weapons`, `ammo`
  (`{"magazine", "reserve"}`), `aim` (the world point the player aims at while `aim` or a lock-on
  is held: the first thing the line of aim meets, a person, a vehicle or the world, at any
  distance; locked on, the point aimed at on the target, CM-5; otherwise `null`), `cover`,
  `vehicle`, `seat`, `limp`, `outfit`, `outfits`, `leads_unlocked`); `missions` (per id: `state`, `stage`);
  `garages` (per garage id: a list of `{"model", "colour", "damage"}`); `ui` (`phone`, `map`,
  `paused`, `menu`); `network` (`role`, `peers`, `id`). Values are read live when `state` is
  called; nothing is cached.

### Events

- **AC-13** `DevConsole.event` fires: `crime` (`type`, `witnesses`, `pos`), `alert_changed`
  (`level`, `reason`), `police_dispatched` (`unit`, `from`), `vehicle_entered` and
  `vehicle_exited` (`entity`, `vehicle`, `seat`), `damaged` (`entity`, `source`, `amount`,
  `health`, `armour`), `died` (`entity`, `cause`), `arrested`, `respawned` (`entity`, `poi`),
  `mission` (`id`, `state`, `stage`), `money_changed` (`amount`, `reason`, `balance`),
  `phone_message` (`from`, `text`), `vehicle_exploded` (`vehicle`), `part_detached` (`vehicle`,
  `debris`), `saved` and `loaded` (`slot`), `map_transition` (`from`, `to`, `vehicle`), and
  `teleport` (`entity`, `reason`). Every event carries `tick`. A `damaged` event is one hit on one
  person (NPCs included; each shotgun pellet that hits is one): `amount` is the hit's damage before
  armour (a weapon's table damage; for a fall or a blast, the health it takes), `health` and
  `armour` are that person's values after it, and `source` is the attacker's entity id when a person
  dealt it, otherwise `fall`, `explosion` or `vehicle`. None comes after the person's `died`.
- **AC-14** The player, or a vehicle carrying the player, moves discontinuously only with a
  `teleport` event, and only for setup commands, respawns, map transitions, loading a save,
  rejoining online and (on clients) the server's corrections.

### Timing and randomness

- **AC-15** Game logic runs in `_physics_process` at 60 Hz and never reads the wall clock.
- **AC-16** All randomness comes from the variation number: the same variation gives the same
  starting population (every entity's kind, archetype and position, in creation order, at the first
  tick after `world.reset`), and a different variation a different one.
- **AC-17** Runs replay: with the same plan files, variation and input timeline, the game does the
  same thing tick for tick, however fast or slow the engine is driven (`--fixed-fps 60` with the
  QA kit pacing it). TODO(panel): exact replay, or replay within a small position tolerance.

### The QA kit's telemetry

- **AC-18** Don't free, move or rename nodes your code didn't create; QA's telemetry autoload and
  tools rely on this. (The QA kit adds its autoload ahead of the game's and runs one worker
  thread, PF-6.)
