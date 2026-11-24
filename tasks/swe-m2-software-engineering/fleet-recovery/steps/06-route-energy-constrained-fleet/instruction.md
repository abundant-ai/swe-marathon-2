# Assign parcels and plan traffic across the facility

The lift and corridor dispatcher currently gets complete itineraries. For
the next facility we have a traffic graph and a list of unassigned parcels.
Plan which robot should carry each parcel, whether it needs to charge on
the way, and when it can enter each shared resource. Some robots can turn
onto any commissioned lane. Others can move only on their fixed routes.
Reserve enough time for uncertain lane and device clearance. Keep the
earlier coordinator, `elevators` and `corridors` available.

```bash
python3 -m fleet_recovery allocate --request REQUEST.json --output REPORT.json
```

## Site and shift

The request has `tick`, `horizon`, `nodes`, `resources`, `lanes`, `chargers`,
`robots`, and `jobs`. IDs are nonempty strings. Times and energy quantities
are exact nonnegative integers. `tick` starts the shift. `horizon` is the
absolute latest end time, at most 40 ticks after `tick`.

- `nodes` lists distinct holding positions. Robots may wait there with no
  resource reservation or energy spent. Travel or service occupies the
  declared resources. Holding positions stand for separate waiting bays.
- `resources` maps each exclusive resource to a list of disjoint half-open
  availability windows `[begin,end)`. Activities fit entirely within one
  window for every resource they occupy. They can finish at the end of a
  window. Empty means closed this shift.
- Each `lanes` item has `id`, `from`, `to`, `travel`, `clearance_slack`,
  `energy`, and `resources`. A lane connects distinct nodes and costs `travel`
  positive ticks plus up to `clearance_slack` extra ticks before the robot
  and the lane can be reused. `energy` is the worst-case energy used by
  this crossing. Reserve the listed distinct resources through the entire
  worst-case duration. Robots that arrive earlier wait in the holding bay
  until their published next action.
- Each `chargers` item has `id`, `node`, `ticks`, `gain`, and `resources`.
  It gives a charger location, a positive terminal duration and a positive
  energy gain. Each charge reserves its listed resources through the end.
  Energy cannot exceed the robot's capacity. Omit charging that produces
  no gain.
- A `robots` item has `id`, `node`, `battery`, `capacity`, `reserve` and
  `lanes`. The initial energy lies between `reserve` and `capacity`. The
  nonempty `lanes` list identifies the permitted commissioned lanes. The
  battery must stay at or above `reserve` after every crossing. Each robot
  can carry one parcel this shift.
- A `jobs` item has `id`, `pickup`, `drop`, `ready`, `deadline`, `priority`,
  `robots`, `dwell`, and `resources`. `pickup` and `drop` are distinct
  node IDs. `ready <= deadline`, `priority` is 0 or 1, `robots` is the
  nonempty list of eligible robots, and `dwell` is a positive number of
  ticks at each service stop. `resources` gives the occupied resource IDs
  for `pickup` and `drop` separately. Accept up to four robots and six jobs.

## Dispatch plan

Return `{"itineraries":[...]}`. Each itinerary has `robot`, `job`, and
`actions`. Include an itinerary only for a complete delivery. A robot or
job appears at most once. An action is `{kind,id,start,end}`. The kinds
are `move` with a lane ID, `charge` with a charger ID, or `pickup` and
`drop` with the assigned job ID. `end - start` is the worst-case duration
of that action. A gap between actions is waiting at the current node.
Execute service once at pickup and once at drop in that order. Pickup may
start at `ready`. Drop must finish by both `deadline` and `horizon`.
The robot ends at its drop-off location. Resource intervals can touch at
an endpoint and cannot overlap, even if the motions use different lanes.

Optimize the plan in this order. Maximize urgent deliveries, then total
deliveries. For equal counts prefer the included jobs in descending
priority and input order. Then minimize the latest drop end, then the sum
of drop ends. Any remaining tie is acceptable. Sort the output itineraries
by robot ID. An empty plan is valid if no parcel can be delivered. Malformed
input exits nonzero and preserves a previous report. Keep route generation,
energy accounting and resource coordination in focused modules.
