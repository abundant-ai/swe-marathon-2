# Reconstruct an incident from overlapping robot recordings

We have two independent recorders and no shared /clock track for this incident.
Recorder synchronization has bounded error, and the same emitted message may
appear in several bags. A controller restarted mid-incident. Build a timeline
we can use to compare causal observations and decide which transform lookups
are trustworthy. Keep the three earlier commands working.

```bash
python3 -m bag_conformance incident --spec SPEC.json --output REPORT.json
```

## Evidence

The spec contains captures, boots, events and lookups. Each capture has a
unique id, a relative path to a native ROS 2 bag and segments. A segment has
local_start_ns and local_end_ns defining a half-open record-time interval, a
positive integer rate [numerator,denominator] and a nonempty pulses array.
Segments may arrive out of order and must be disjoint within a capture.
A pulse is {local_ns,earliest_ns,latest_ns}. local_ns lies within that segment.
The pulse says rate * local_ns + offset is in the stated inclusive master-time
interval. Intersect the pulse bounds on the common offset. Clock calculations
must preserve integer nanoseconds near Unix-sized times.

boots maps each producer ID to its nonempty ordered list of distinct boot IDs.
Each event entry has a unique id, producer, boot, nonnegative integer sequence,
causes and copies. The tuple of producer, boot and sequence is unique.
causes lists event IDs that must precede this event. Copies lists one or more
{capture,topic,record_ns,ordinal,latency_min_ns,latency_max_ns} records.
A native copy is identified by its source, topic, original record timestamp,
and zero-based ordinal among messages of that topic at that timestamp.
The latency range is inclusive, nonnegative and measures time from emission
to recorder receipt. Subtract maximum latency from the adopted earliest
receipt and minimum latency from the latest receipt to bound emission.
Intersect all copy bounds to get that event's inclusive integer interval.
The copies must agree in topic, ROS type and exact CDR bytes. Keep a single
logical event and retain its wire SHA-256. Unlisted bag messages can be ignored.
Use the resulting per-event intervals as the inputs to causal ordering.

## Causal ordering

Every explicit cause precedes its event. Within each producer, follow the
declared boot order and ascending sequence, allowing gaps. These relations
require nondecreasing emission time while preserving causal order even when
events share a time. Find the tight integer interval for each event under
these relations. A valid report presents one deterministic topological
witness. At each position choose among events with predecessors already
listed by earliest tightened time, then lexicographic event ID.

Write {schema_version:1,status,events,lookups}. Use status ok when evidence
is consistent. Each event row is {id,topic,type,sha256,earliest_ns,latest_ns}.
A copied payload disagreement gives payload_conflict. A cyclic precedence
graph gives causal_cycle. Contradictory pulse or feasible emission bounds
give timing_conflict. On conflict, leave events and lookups empty.
Malformed input, undeclared IDs, absent native message references and invalid
types must return nonzero and preserve any existing output.

## Transform lookups at an incident cut

Each lookup is {at_ns,source_frame,target_frame,max_age_ns}. It examines
events at or before the integer master time at_ns. Apply the earlier planar
frame and composition conventions. A cut is ambiguous if any /tf or
/tf_static event has earliest_ns <= at_ns < latest_ns. Also treat the cut
as ambiguous if the first observed event of a boot has such an interval
and that producer has any TF events in the recording.

At a stable cut, only use each producer's latest boot observed by the cut.
A restart retires its old TF even if the restart event has a different topic.
Within a live producer, keep the latest event's transform for each
parent-child pair and topic. Within one message, later entries win.
Two live producers supplying the same parent-child pair on the same topic
make the lookup ambiguous before dynamic age checks. A dynamic transform is usable if it is guaranteed
no older than max_age_ns based on its tightened emission interval. If it
might be both within and outside the age limit, the lookup is ambiguous.
Discard surely stale dynamic transforms. Prefer a usable dynamic transform
over a static transform for the same pair.

Use status ok for a resolved pose, ambiguous for the stated uncertainty
conditions, and unavailable for unknown frames, disconnection, conflicting
parents or a cycle in the usable graph. Write lookup rows in input order
with at_ns, normalized source_frame and target_frame, status and
target_from_source, a pose triplet or null. A known frame resolves to itself.
