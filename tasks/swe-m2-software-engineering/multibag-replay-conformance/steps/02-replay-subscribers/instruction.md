# Execute deterministic subscriptions, playback, and seeks

Add an offline replay driver for testing consumers. Keep index available.
Use the shared record timeline and clock epochs from the earlier command.

```bash
python3 -m bag_conformance replay --spec SPEC.json --script SCRIPT.json --output TRACE.json
```

SCRIPT.json has start_ns, an integer record-time cursor, and operations, an
ordered array. A subscription is keyed by subscriber ID and exact topic.
Its reliability and durability use the earlier values. An offer satisfies
best_effort or volatile requests with either respective setting. A reliable
request needs a reliable offer, and a transient_local request needs a
transient_local offer.

- {kind:"subscribe",subscriber,topic,reliability,durability} creates a new
  subscriber-topic pair. Reject duplicates. Ordinary topic names must be
  declared by at least one source. For a transient_local request, immediately
  deliver compatible cached events for that topic in original replay order.
- {kind:"advance",until_ns} consumes all unplayed events with record_ns
  less than until_ns. Move the cursor to until_ns. The cursor may stay in
  place or advance. Deliver each ordinary event to compatible subscriptions,
  ordered by subscriber ID when several receive the same event.
- {kind:"seek",record_ns} moves the cursor to any integer. Restore clock and
  publisher history from events strictly before that position. Keep the
  subscriptions. Emit no ordinary or cached deliveries on the seek.

Initialize playback as a seek to start_ns. On each epoch reset, discard all
publisher history from older epochs. A transient-local publisher retains its
last depth events in the current epoch, independently for each source and
topic. No ordinary /clock subscription is needed.

Write {schema_version:1,deliveries:[...],cursor_ns}. A delivery consists of
the seven index fields plus operation, subscriber and retained. operation
is the zero-based script row that caused delivery. retained is true for
subscription history and false during advance. Reject malformed scripts and
preserve an existing trace.
