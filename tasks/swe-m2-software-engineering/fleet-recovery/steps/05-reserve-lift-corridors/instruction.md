# Reserve the lift and its approach together

Two robots can reach different lifts through the same narrow vestibule. The
current lift schedule can send one robot into the only escape path while
another owns the lift. Add itinerary booking that acquires the entire set of
approach, cabin and exit resources before dispatch. During recovery, keep
the bundle held until its devices agree about the grant. Keep the earlier
delivery coordinator and `elevators` command working.

```bash
python3 -m fleet_recovery corridors --request REQUEST.json --state STATE.json --output REPORT.json
```

## Booking request

Each request has a nonempty `event_id`, nonnegative integer `tick`,
`resources`, and `jobs`. IDs are nonempty strings. `resources` maps one to eight
commissioned IDs to records with `windows` and `report`. The ID set stays fixed.
`windows` lists the current nonoverlapping half-open intervals `[begin,end)`
when entry is authorized. Endpoints are nonnegative integer ticks. An empty
list closes the resource to new bookings. A trip must fit in one window per
resource, even when two windows share an endpoint. It can finish at the end
of that window. `report` gives a nonnegative integer `sequence` and `receipt`, which
is null or `{"grant": id, "outcome": "delivered"|"returned"}`.

Each job gives `id`, `robot`, `priority` (0 for routine or 1 for urgent),
`ready`, `deadline`, and one to three alternative `routes`. A route has an
`id` unique within that job, a positive integer `duration` and a nonempty
list `resources` of distinct commissioned IDs. The route already includes
approach, ride and exit time. It starts and ends in separate holding areas.
Reserve its full resource set over `[depart,finish)` with
`finish = depart + duration`. There is no waiting inside a bundle. Different
routes may use different vestibules or cabins. Require `ready <= deadline`.
Consider only starts from the request tick through 32 ticks ahead, and only
trips finishing within that horizon. At most six jobs are supplied, one per
robot. Their fields remain fixed under a given job ID. A job may disappear
from a later request. A withdrawn job's issued grant still holds its route.

## Plan and grant

Exclude jobs already delivered or granted, jobs whose robot has an unsettled
grant, and any route touching a held resource. Respect readiness, deadline,
each resource's open windows, and exclusive occupancy between proposed trips.
Rank feasible combined plans in this order.

1. Maximize the number of urgent jobs scheduled.
2. Maximize the total number scheduled.
3. Prefer included jobs in descending priority and then first appearance
   order. First appearance is the position in the first accepted request
   that introduced the job, ordered by acceptance and then array index.
   Compare the membership bit vector in that order, preferring 1 over 0.
4. Minimize the latest finish, then minimize the sum of finish ticks.

Return `{"plan":[...],"grants":[...],"completed":[...]}`. A plan item has
`job`, `robot`, `route`, `depart`, and `finish`. Sort by `depart`, then `job`.
Grant exactly the items departing at the request tick and include a distinct
nonempty `id` on each grant. Future items are tentative. `completed` lists
confirmed job IDs in lexical order.

## Recovery

Only a report with a strictly newer sequence can update a resource. For an
issued grant, record fresh matching receipts from that grant's resources.
Ignore foreign and null receipts and delivery before `finish`. A valid newer
matching receipt supersedes the prior evidence from that resource. Release
the whole bundle only when every member has reported the same outcome for
the grant. `delivered` completes the job and `returned` allows redispatch.
Missing evidence, partial agreement, elapsed time and new calendars do not
release any part of a bundle.

Persist admission order, reports, held bundles, completed jobs and responses
before publishing. A retry with the same event ID and identical JSON gets its
original response, even when its tick is older. Reject an event ID reused
with different contents, a new event at an earlier tick, or a malformed request
with a nonzero exit. Preserve the previous journal and output on rejection.
The journal may initially be absent. Serialize concurrent uses of the same
journal. Keep parsing, planning and state transitions in focused modules.
