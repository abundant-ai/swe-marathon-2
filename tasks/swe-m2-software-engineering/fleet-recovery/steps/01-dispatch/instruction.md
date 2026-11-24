# Coordinate deliveries across two robot fleets

Build the delivery coordinator for our facility simulator. One fleet supports routing through any open directed lane. The other follows a fixed loop and waits for permission before each lane. They share narrow passages and station access. Deliver parcels from pickup to drop-off while keeping compatible work moving in parallel.

Place the application under `/app/fleet_recovery`. Launch it from `/app` using `python3 -m fleet_recovery --site SITE.json --state STATE_DIR`. Python 3.12 is installed. The program reads one JSON event per stdin line and writes one JSON response `{"commands":[...]}` per line. Flush each response. Keep diagnostic output on stderr. The site and the writable state directory may be outside `/app`. `/app/example/site.json` describes a small network using lanes from the Open-RMF Office demo.

## Site and input events

The site JSON contains three objects or arrays.

| Field | Structure |
| --- | --- |
| `nodes` | Object keyed by node ID. Each value is a list of resource IDs occupied by a robot stopped at that node. Every node also has an implicit exclusive resource `node:ID`. |
| `lanes` | Array of `{from, to, ticks, resources}` objects. A lane is directed, running time is a positive integer number of ticks, and `resources` lists additional exclusive resources. There is at most one lane for a given ordered pair. |
| `robots` | Object keyed by robot ID. Each value has `start` and `mode`, either `route` or `loop`. A `loop` robot also supplies `loop`, a cycle of distinct node IDs with a directed lane for every advance, including wraparound. |

Each event has a nonempty `id`, integer `time` in simulation ticks, and `kind`. Time is nondecreasing. The initial positions are the `start` nodes and all robots are online. An event other than `tick` returns an empty commands list.

| Kind | Additional fields |
| --- | --- |
| `job` | `job` ID, `pickup` and `dropoff` node IDs, and nonempty `eligible` robot ID list. An eligible route robot still needs a directed path from its position to pickup and from pickup to drop-off. An eligible loop robot needs both stations on its loop. |
| `telemetry` | `robot` ID, integer `seq`, boolean `online`, `node` ID or null, and `settled` command ID or null. Sequence increases per robot in this version. A successful command produces online telemetry with the command ID and measured node. |
| `tick` | No additional fields. Consider all waiting jobs and eligible robots. |

## Commands and reservations

Commands are `{command, robot, job, kind, ...}` objects. `command` is a unique nonempty ID. A `move` adds `from` and `to` node IDs for one lane. A `pickup` or `drop` adds `node`, the relevant station. The first command for a job assigns it to that robot until drop-off. One robot can carry one job at a time and must acknowledge pickup before drop-off. Acknowledge a drop only by processing telemetry for that command. Complete all reachable work in finite time and advance multiple compatible jobs on the same tick when they can each take an available next step.

At most one command per robot is outstanding. A settled move must report arrival at its destination. A settled pickup or drop must report its station. A move claims the union of the lane resources and the resources of both endpoints, including their implicit node resources. Hold them from command emission until the matching arrival is acknowledged. A stopped robot holds its node resources. These claims are exclusive across robots. Reuse a robot's own occupied resources when advancing it. Do not give a loop robot a move other than its next configured loop lane. Use the returned results to exercise both fleet modes before handing over the code.
