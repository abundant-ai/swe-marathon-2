# Serve sealed recording snapshots to restartable replay clients

Our recorders close split files while researchers are already replaying
an earlier cut of the same run. A reopened reader must see its original
recording and pick up after its last acknowledged batch. An open reader
must also get the `/tf_static` and other latched data it would have seen
at its chosen start time. Build the service over native ROS 2 MCAP and
SQLite recordings. Keep the earlier commands working.

```bash
python3 -m bag_conformance serve --request REQUEST.json --state STATE --output REPORT.json
```

`STATE` is a service directory. It can start absent. `REQUEST.json` contains
a nonempty `request_id` and an `operation`. A caller may send a new request
from a fresh process. A retry of an accepted request with the same JSON
contents returns its original response. Reusing an ID with changed contents,
using invalid data or naming an unknown reader or generation exits nonzero
and preserves all accepted state and any previous response. Two requests
can run concurrently. Commit valid requests before checking and writing the
reply destination. If the response cannot be published, including when a
directory occupies the output path, return nonzero and keep the accepted
decision available for an exact retry. Never replace the live recording
database with a response.

## Seal a recording split

An `attach` request gives `base_generation` and `shards`, a nonempty array.
The first base generation is zero. Accept only the current generation and
advance it by one. Publish the whole new generation atomically.

Each shard has a unique `id`, a native bag `path` relative to the attach
request file, `stream`, `boot`, `latched_topics`, and `repeats`. `stream` and
`boot` are nonempty strings. The shard belongs to one publisher stream and
boot. An ordered list of sealed shards for a stream can introduce a new
boot. A retired boot cannot contribute later shards to that stream.
`latched_topics` lists the topic names with transient-local semantics in
this shard. Timestamps are already in a shared time base. Source paths can
go away after a successful attach. Retain their immutable recorded bytes
for all generations that readers may open. Native message payloads fit in
16 MiB. MCAP chunks fit in 32 MiB uncompressed.

Number native messages in their reader order within each shard, starting
with ordinal zero. A `repeats` array entry gives `ordinal`, `from_shard`,
and `from_ordinal`. It identifies a transient-local copy inserted when
the recorder split or took a snapshot. The source must be an original
event from the same stream, boot and latched topic, in a previously sealed
shard. The recorded type and exact CDR bytes must agree. The appearance of
an identical CDR payload without this explicit repeat record still counts
as a separate event. The ordinal of an original or repeated occurrence
always refers to the native file, including skipped repeats.

Use the native record timestamps for replay. Events from all sealed shards
in a generation sort by timestamp, then shard ID, then ordinal. Original
messages within a stream and prior boot must all sort before the first
original message of the next boot. A repeated copy does not affect that
order. The attach response is `{"generation":n,"events":m}`, where `m` is
the total number of original events visible in generation `n`.

## Open a replay and acknowledge delivery

An `open` request gives a new nonempty `reader`, `generation` (an existing
positive integer or null for the current one), `topics` (a distinct list
of selected topic names), `begin_ns`, and `end_ns`. The range is half-open
with nonnegative integer endpoints, `begin_ns < end_ns`. Return
`{"reader":id,"generation":n}`. The pinned generation cannot change
during the reader's lifetime.

Before regular events, queue cached latched values from just before
`begin_ns`. For each stream, select only its latest boot with any original
event strictly before the cut, including events on unselected topics.
Emit the latest selected latched event per stream and topic from that
boot. A retired boot's cached values must not return. Order these cached
deliveries by source timestamp, shard ID, ordinal. Then queue the original
selected events in the reader's window in the normal event order.

A `poll` request gives `reader`, `max_events` (1 to 1,024), and
`max_bytes` (1 to 16 MiB, inclusive). Return `{"reader":id,"batch":id_or_null,
"events":[...],"done":boolean}`. Each event has `shard`, `ordinal`, `stream`,
`boot`, `topic`, `type`, `stamp_ns`, `cdr_b64`, `sha256`, and `latched`. Use
standard base64 with the native CDR bytes. `sha256` is lowercase hex of
those bytes. Set `latched` only on the cached delivery. Each nonempty batch
has a distinct nonempty ID per reader. It contains the next prefix of
events bounded by both event count and the sum of decoded payload byte
lengths. If the first event alone is too large, reject the request so
the caller can increase its budget. When nothing remains, return an
empty array, null batch and `done: true`. A pending batch has `done: false`.
While the same batch is pending, any poll returns it as issued even if
the reader's requested batch limits have changed.

An `ack` request gives `reader` and the currently pending `batch`. Only
that acknowledgement advances the reader. Return `{"reader":id,
"batch":id,"acknowledged":true}`. A read process can be replaced before
poll or ack at any point. Replay of a pinned reader must use only its
generation, including its latch prelude and still-pending batch, while
new shards are concurrently attached. Use an on-disk index and stream
large payloads without holding a complete recording in memory. A service
worker must be usable with 256 MiB resident memory for recordings larger
than that. Separate native ingestion, replay selection and transactional
client handling.
