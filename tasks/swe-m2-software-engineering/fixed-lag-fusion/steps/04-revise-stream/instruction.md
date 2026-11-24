# Restart the live estimator and revise recent evidence

A wheel or ranging producer can redeliver a packet after an interrupted reply. Survey processing can also replace or withdraw an observation that was provisionally accepted. Add a durable ingestion entry point while preserving the batch behavior. The workstation should restart without keeping all past pose states or applying the same measurement a second time.

```bash
python3 -m lagfusion ingest --spec PACKET.json --state STATE.json --output REPORT.json
```

## Packets and observations

Each packet contains the same `config`, optional `calibration` and `anchors`, and `events` as `smooth`, plus a nonempty `stream_id` and positive integer `sequence`. The first accepted packet for each stream has sequence 1. Subsequent packets are ordered consecutively. Model and calibration inputs remain fixed for each stream. Use one state file for multiple streams.

Ordinary events retain their behavior. In ingestion only, two event types denote revisions:

- `{"op":"upsert","id":string,"revision":integer,"first_tick":integer,"last_tick":integer,"factor":event}` adds or replaces one observation. The event must be an observation in the earlier linear or calibrated formats. The supplied tick extent must agree with the normalized factor. Identity is the tuple `(first_tick,last_tick,id)` within a stream.
- `{"op":"retract","id":string,"revision":integer,"first_tick":integer,"last_tick":integer}` retracts an active observation with that identity. A retraction removes the complete information contribution.

Revision integers start at 1 for each identity and increase by one. Classify an expired or future extent first. An exact repeat of a retained revision reports `duplicate`. Earlier revisions report `stale`. A changed event at the current revision, skipped revision, or a retraction of an absent observation reports `conflict`. An accepted upsert reports `accepted`, an accepted retraction reports `retracted`, and a supported invalid calibrated factor reports `invalid` without advancing the revision. A later valid revision can restore a retracted factor. A retraction must retain its revision while the extent is active so repeats stay idempotent. Discard revision records once their extent expires. The extent is one tick for a unary factor or two adjacent ticks for a delta. An expired factor cannot change the marginalized prior.

## Durable output

Write `{"stream_id":string,"sequence":integer,"status":string,"result":object_or_null}`. For a newly accepted packet use `status: "accepted"` and return the same result structure as `smooth`, restricted to outcomes and snapshots from that packet and the resulting final posterior. An exact retransmission of the latest accepted packet returns the identical response. JSON object key order is immaterial. Older and skipped packets, changed contents at the latest sequence, or changed model inputs in a later packet produce `status: "rejected"` and null result without changing state.

Persist accepted decisions before attempting the atomic output write. If a reply cannot be written, return nonzero and keep the accepted decision available for retry. Concurrent invocations on the same state file must be equivalent to a serial order. A malformed packet returns nonzero and leaves both existing files unchanged. State starts absent and must retain only active factors and revision records, a summarized prior, and the latest request and reply per stream. The file can contain the latest packet contents for retransmission and must not accumulate past packets. Use distinct state and output paths. Reserve the state path with suffix `.lock` for synchronization.
