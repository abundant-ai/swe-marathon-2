# City plan format (`city-plan/1`)

Our level designers lay out every map of Merrow Bay as a plan file. The game builds its world from
these files when a map loads, so a designer can move a road, retime a signal or swap two shops
without touching code. Read the plans at load time and build everything they describe. Never
bake a plan into scenes: the files will keep changing until release.

The game design document (`../GDD.md`) says how the game must behave on top of a plan (chapter 12
and chapter 17). This file says what a plan contains and what each field means.

## Files

| File | Contents |
| --- | --- |
| `downtown.json` | Downtown (map id `downtown`) |
| `port.json` | Ashby Port (map id `port`) |
| `hills.json` | Sable Hills (map id `hills`) |
| `hills_height.png` | Sable Hills terrain, a 16-bit greyscale heightmap |
| `links.json` | Highway portals between maps and the ferry route (format `city-links/1`) |

The `--plan-dir=DIR` flag points the game at another folder with the same file names; the level
designers use it to try layouts. Plans there can have different roads, blocks and parcels and keep
the same point-of-interest ids.

The examples below are taken from `downtown.json`, except those for water, terrain and
`links.json`, which Downtown does not have.

## Conventions

- **Units and axes.** Metres and seconds. Godot axes: x east, y up, z south. Plan polygons are
  lists of `[x, z]` pairs; 3D points are `[x, y, z]`.
- **Headings.** Degrees clockwise from north. Heading `h` points along `(sin h, 0, -cos h)`: 0 is
  north (-z), 90 is east (+x).
- **Traffic** drives on the right.
- **Ids** are strings, unique within a plan. Point-of-interest ids stay the same across plan
  revisions; every other id (nodes, edges, lanes, parcels, blocks) can change when a designer edits
  the plan. Anything that must survive an edit, such as
  a mission objective, refers to a point of interest.
- **Unknown fields** are ignored, so designers can add notes.
- **Order.** Lists have no meaning in their order except where this file says so (signal phases,
  sidewalk rings, polygon vertices, intersection legs).
- **Polygons** are simple (no self-intersection), given in either winding, without repeating the
  first vertex.

## Top level

```json
{
  "format": "city-plan/1",
  "map": "downtown",
  "name": "downtown",
  "revision": 2,
  "bounds": {"min": [-420.0, -468.829], "max": [440.0, 400.0]},
  "ground_m": 0.0,
  "nodes": [], "edges": [], "intersections": [],
  "blocks": [], "sidewalks": [], "parcels": [],
  "water": [], "terrain": null,
  "districts": [], "turfs": [], "pois": [],
  "spawn": {}
}
```

- `bounds`: the playable area. Nothing the game builds from the plan lies outside it.
- `ground_m`: ground height outside roads, blocks and terrain. A map with `terrain` uses the
  heightmap instead.

## Road network

### Nodes

```json
{"id": "j_32", "p": [-70.0, 0.0, -180.0], "kind": "junction"}
```

`kind` is `junction` (three or more roads meet), `bend` (two roads meet), `end` (a dead end) or
`portal` (the road continues on another map; see `links.json`). `p` is the road surface height at
the node centre.

### Edges

```json
{
  "id": "e_22_32", "a": "j_22", "b": "j_32", "class": "street",
  "oneway": false, "lane_width_m": 3.25, "speed_kmh": 40, "surface": "asphalt",
  "structure": "ground", "points": [],
  "lanes": [{"id": "e_22_32:ab0", "dir": "ab", "index": 0},
            {"id": "e_22_32:ba0", "dir": "ba", "index": 0}]
}
```

- **Centreline.** The polyline from node `a` through `points` (each `[x, y, z]`, usually empty)
  to node `b`. Height along it is linear in distance between consecutive vertices.
- **`class`**: `arterial`, `street`, `highway`, `dock` or `track` (unpaved). Classes matter for
  traffic density and look, not for geometry.
- **`structure`**: `ground`, `bridge` or `tunnel`. A bridge has open space under its deck; a
  tunnel has a roof 5.0 m above its surface.
- **Lanes.** `dir` is `ab` (travelling from `a` to `b`) or `ba`. `index` 0 is the leftmost lane in
  the direction of travel.
  - Two-way edge (`oneway: false`): the centre of lane `index` lies `(index + 0.5) * lane_width_m`
    to the right of the centreline, seen in that lane's direction of travel.
  - One-way edge (`oneway: true`, every lane `ab`): with `n` lanes, the centre of lane `index`
    lies `(index + 0.5 - n / 2) * lane_width_m` to the right of the centreline.
  - The carriageway is the union of the lanes: it spans from the outer edge of the leftmost lane
    to the outer edge of the rightmost lane on each side.
- **Lane extent.** A lane starts where it leaves the box of its start intersection (`box_m` of
  that leg, measured along the centreline from the start node) and ends at the stop line of its
  approach at the end intersection (`stop_line_m` of that approach).
- **Lane coordinate `s`.** Distance along the centreline from the lane start, in the direction of
  travel, from 0 to the lane length (`centreline length - box_m(start) - stop_line_m(end)`). The
  lane point at `s` is the centreline point at that distance, moved sideways by the lane offset,
  at the centreline's height. The lane heading is the direction of travel there.
- **Speed limit** `speed_kmh` applies to every lane of the edge.

### Intersections

Every node with at least one edge has one intersection record.

```json
{
  "id": "j_32", "node": "j_32", "control": "signal",
  "legs": [
    {"edge": "e_32_42", "box_m": 7.0,
     "crosswalk": {"id": "cw_j_32_e_32_42", "from_m": 7.5, "to_m": 10.5},
     "approach": {"id": "j_32<e_32_42", "dir": "ba", "stop_line_m": 11.5}}
  ],
  "signal": {"phases": [{"green": ["j_32<e_32_42"], "walk": [], "green_s": 9.0}],
             "amber_s": 3.0, "all_red_s": 1.0, "offset_s": 31.2}
}
```

(One of the four legs and one of the five phases shown.)

- **Legs.** One per edge that touches the node, in a fixed order (clockwise from north).
  - `box_m`: how far the intersection box reaches along this edge from the node. Inside the box,
    vehicles may take any smooth path from an approach lane to an exit lane; the box surface is at
    the node's height.
  - `crosswalk` (or `null`): a band across the leg's whole carriageway, from `from_m` to `to_m`
    from the node along the centreline. People cross the road inside crosswalk bands.
  - `approach` (or `null` when no lane of this edge enters the node): the lanes of this edge that
    travel towards the node (`dir`), and their stop line, `stop_line_m` from the node.
- **Approach order.** The approaches of an intersection, in leg order, are numbered from 0. Anchors
  and the QA kit may refer to an approach by that number.
- **Turns.** From an approach, a vehicle may leave by any other leg that has lanes leaving the
  node. A turn is straight when the exit heading is within 30 degrees of the approach heading, a
  right turn when it turns clockwise by more than that, a left turn when it turns
  anticlockwise. U-turns are not allowed. At a `bend` the only movement is to continue.
  - Right turns use the rightmost approach lane and enter the rightmost exit lane.
  - Left turns use lane 0 and enter exit lane 0.
  - Straight on: approach lane `i` continues in exit lane `min(i, exit lanes - 1)`.
- **`control`**:
  - `signal`: traffic lights run the `signal` program below.
  - `stop`: every approach stops at its stop line, then goes when the box is clear (GDD chapter 7).
  - `none`: no control; used at bends, dead ends and portals. There is no crosswalk, and the stop
    line sits at the box edge (`stop_line_m` equals `box_m`), so lanes run straight into the
    turn. At dead ends and portals `box_m` is 0.
- **Signal program.** `phases` run in order and the cycle repeats. Each phase shows green to the
  approaches in `green` for `green_s` seconds, while the crosswalks in `walk` show walk. Then those
  approaches show amber for `amber_s` while every crosswalk shows don't walk, then everything is
  red for `all_red_s`. Approaches not listed in the running phase are red. Each approach appears in
  exactly one phase; a phase with no `green` is a walk-only phase.
  - Cycle length `C` is the sum over phases of `green_s + amber_s + all_red_s`.
  - Program time is `t = (physics ticks since the last world reset) / 60 + offset_s`, and the
    program is at `t mod C`. At program time 0 the first phase turns green.

## Blocks, sidewalks and parcels

```json
{"id": "b_22", "poly": [[-186.75, -176.75], [-77.0, -176.75], [-77.0, -63.25], [-186.75, -63.25]],
 "elevation_m": 0.15}
```

- **Blocks** are the raised areas enclosed by kerbs: everything between the roads. Their top
  surface is at `elevation_m`; the kerb is the drop from there to the road.
- **Sidewalks** run around the inside edge of a block:

  ```json
  {"id": "sw_22", "block": "b_22", "width_m": 3.0, "elevation_m": 0.15,
   "ring": [[-185.25, -175.25], [-78.5, -175.25], [-78.5, -64.75], [-185.25, -64.75]]}
  ```

  `ring` is the closed centreline of a band `width_m` wide. A sidewalk point at distance `s`
  follows the ring from `ring[0]` in list order and wraps around (`s` is taken modulo the ring
  length); its heading is the ring direction there.
- **Parcels** split the inside of a block (inside the sidewalks):

  ```json
  {"id": "p_12", "block": "b_23", "zoning": "commercial",
   "poly": [[-183.75, -53.75], [-137.23, -53.75], [-137.23, -15.69], [-183.75, -15.69]],
   "base_m": 0.15, "height_m": 35.3, "height_range_m": [14.0, 60.0], "setback_m": 3.0,
   "interior": {}}
  ```

  - `zoning`: `commercial`, `residential`, `civic`, `industrial`, `plaza`, `park` or `parking`.
  - A parcel with zoning `commercial`, `residential`, `civic` or `industrial` holds one building.
    Its footprint is the parcel polygon moved inwards by `setback_m`; its roof is flat at
    `base_m + height_m`. `height_range_m` is the zoning's allowed range; `height_m` is the value
    the designers picked inside it.
  - `plaza`, `park` and `parking` parcels hold no building (`height_m` is 0). Their surface is at
    `base_m`; plazas and parks are open to people on foot, parking lots to vehicles and people.
- **Interiors.** A parcel can have one interior (otherwise `null`): rooms at street level that
  people walk into. The weapons shop's parcel above has this one:

  ```json
  "interior": {
    "door": {"p": [-160.49, -50.75], "heading_deg": 180.0, "width_m": 2.0, "height_m": 2.6},
    "rooms": [{"id": "main", "poly": [[-166.49, -50.45], [-154.49, -50.45], [-154.49, -40.75],
                                     [-166.49, -40.75]], "floor_m": 0.15, "ceiling_m": 3.75}],
    "points": {"counter": [-160.49, 0.15, -43.75]}
  }
  ```

  - `door.p` lies on the footprint outline; `heading_deg` points from the street into the
    building. The doorway is open, at least `width_m` wide and `height_m` high above the floor
    of the room it opens into.
  - Each room is an empty space over `poly`, floor at `floor_m`, ceiling at `ceiling_m`. Rooms
    listed together are connected by openings at least 1.2 m wide (1.0 m above the floor).
  - `points` names spots that points of interest use (a shop counter, a bank vault, a save point).
  - The rest of the building is solid.

## Water and terrain

- **Water**, used on Ashby Port and Sable Hills:

  ```json
  {"id": "bay", "poly": [], "level_m": 0.0, "depth_m": 12.0,
   "shores": [{"from": 0, "to": 1, "kind": "quay"}], "ladders": [[x, y, z]]}
  ```

  The water surface is at `level_m` over `poly`; the bed is `depth_m` below it except near
  shores. Each entry of `shores` covers the polygon edges from vertex `from` to vertex `to`:
  - `quay`: a vertical wall from 1.0 m above the water to the bed. `ladders` are points on quays
    where a ladder leads out of the water.
  - `beach`: the ground rises evenly from 2.0 m below the water level, 20 m out from the shore
    line, to 0.5 m above it at the shore line.
- **Terrain**, used on Sable Hills:

  ```json
  "terrain": {"heightmap": "hills_height.png", "origin": [-1000.0, -1000.0],
              "size_m": [2000.0, 2000.0], "height_m": [0.0, 180.0]}
  ```

  The image covers the square from `origin` to `origin + size_m`, pixel (0, 0) at the north-west
  corner. A pixel value `v` (0 to 65535) means height `h0 + (h1 - h0) * v / 65535`. Heights
  between pixel centres are bilinear. Roads, blocks and parcels sit on their own heights and the
  terrain around them meets them.

## Districts and turfs

- **Districts** cover the map: `{"id": "downtown_core", "poly": [...]}`. A point belongs to the
  first district in list order whose polygon contains it. Density and population rules in the
  GDD are given per district.
- **Turfs** are gang territories: `{"id": "turf_crew_a", "crew": "crew_a", "poly": [...]}`.

## Points of interest

```json
{"id": "shop_weapons_downtown", "kind": "shop", "shop": "weapons",
 "p": [-160.49, 0.15, -43.75], "heading_deg": 180.0, "parcel": "p_12", "point": "counter"}
```

Every point of interest has `id`, `kind`, `p` (a spot on the ground where a person can stand or a
vehicle can stop) and `heading_deg`. Kinds and their extra fields:

| Kind | Extra fields | Meaning |
| --- | --- | --- |
| `police_station` | `parcel`, `exit` (`{"lane", "s"}`), `respawn` (`[x, y, z]`) | Police cars leave by `exit`; arrested players come back at `respawn` |
| `hospital` | `parcel`, `exit`, `respawn` | Ambulances leave by `exit`; players who die come back at `respawn` |
| `shop` | `shop` (`weapons`, `clothes` or `food`), `parcel`, `point` | `p` is at the counter inside the parcel's interior |
| `garage` | `zone` (`{"poly", "heading_deg"}`), `driveway` (`{"lane", "s"}`), `capacity` | Vehicles stop inside `zone` to be stored or repaired; they reach it from the lane point `driveway` |
| `safehouse` | `parcel`, `point` | `p` is at the save point inside the interior |
| `bank` | `parcel`, `vault` (a room id) | The bank's vault is the named room of its interior |
| `mission_giver` | `giver` | Where that mission contact stands |
| `mission_point` | `radius_m` | A place a mission objective uses |
| `checkpoint` | `race`, `index`, `radius_m` | Race checkpoints, numbered from 1 |
| `ferry_terminal` | `dock` (`[x, y, z]`), `ramp` (`{"poly"}`), `queue` (`{"lane", "s"}`) | Ashby Port and Sable Hills |
| `portal` | `node`, `link` | The map edge where a highway continues on another map |
| `plaza` | `parcel` | An open square |

## Spawning

```json
"spawn": {"vehicle_edges": "all", "pedestrian_areas": ["sw_22", "p_16"], "no_spawn": []}
```

- `vehicle_edges`: `"all"` or a list of edge ids whose lanes may receive new traffic.
- `pedestrian_areas`: sidewalk ids and parcel ids (plazas, parks) where new people may appear.
- `no_spawn`: polygons where nothing new appears.

## Links between maps (`links.json`)

```json
{
  "format": "city-links/1",
  "portals": [{"id": "hw_downtown_port",
               "a": {"map": "downtown", "node": "pt_east"},
               "b": {"map": "port", "node": "pt_west"}}],
  "ferry": {"terminals": ["ferry_terminal_port", "ferry_terminal_hills"],
            "routes": [{"map": "port", "points": [], "portal": "ferry_out_port"},
                       {"map": "hills", "points": [], "portal": "ferry_in_hills"}]}
}
```

- **Highway portals.** A portal pairs a `portal` node on one map with a `portal` node on another.
  Both nodes end an edge with the same lane layout. A vehicle that crosses portal node A continues
  on the other map from portal node B, on the lane with the same index, the same distance past B
  as it was past A, at the same speed and heading relative to the lane.
- **Ferry.** The ferry sails each map's route polyline (on water) between its terminal and the
  map's ferry portal, and changes map at the portal. The routes and terminal details arrive with
  the Ashby Port and Sable Hills plans.

## Anchors

Commands that place something (`at` in GDD chapter 17) take an anchor. Every anchor resolves to a
position and a heading.

| Anchor | Position | Heading |
| --- | --- | --- |
| `[x, y, z]` | that point | the command's `heading`, else north |
| `{"lane": id, "s": s}` | the lane point at `s` | along the lane |
| `{"sidewalk": id, "s": s}` | the sidewalk point at `s` | along the ring |
| `{"intersection": id, "approach": k, "before_m": d, "lane_index": i}` | on lane `i` of approach `k` (a number or an approach id; lane 0 when omitted), `d` metres before its stop line | along the lane, towards the node |
| `{"corner_of": id, "approach": k}` | the sidewalk point nearest to the right-hand end of approach `k`'s stop line (the outer edge of its rightmost lane) | towards the node |
| `{"poi": id}` | the point of interest's `p` | its `heading_deg` |
| `{"poi": id, "front_m": d}` | `d` metres in front of `p` along its heading, at the height of the ground there | the point of interest's heading |
| `{"portal": id, "before_m": d, "lane_index": i}` | `id` names a `portal` point of interest; on lane `i` of the lanes travelling into its node, `d` metres before the node | towards the portal |

When an anchor resolves on the ground, things are placed standing on that surface. A `heading`
argument given with a command overrides the anchor's heading.
