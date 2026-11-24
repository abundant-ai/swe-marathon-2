# Diagnose divergence between simulator exports

The deployment team needs to locate the first point where two exports of the same policy stop agreeing. Add a report that runs two complete raw streams using the earlier controller semantics, with a separate fresh state for each side.

```bash
python3 -m policy_bridge compare --left-spec A.json --right-spec B.json --left A.ndjson --right B.ndjson --tolerance EPS --output REPORT.json
```

EPS is a finite nonnegative absolute tolerance. Both streams may use different physics rates and actuator layouts. Compare only policy updates, in encounter order, and use their physical timestamp in integer nanoseconds, `tick * physics_dt_ns`. An absent update or unequal timestamp is a difference regardless of EPS. At equal timestamps compare the stacked observation, action, and canonical target, in that order and from index zero within each vector. A vector length difference is a mismatch at the first missing component. Other stream replies and repeated copies of an already accepted event do not take positions in this comparison.

Write `{"status":"match"|"mismatch","compared":integer,"first":object_or_null}`. The count is the number of fully matching updates before the first difference, or every compared update on a match. The first difference is `{"index":integer,"field":"time_ns"|"observation"|"action"|"target","channel":integer_or_null,"left":number_or_null,"right":number_or_null}`. Index is the zero-based policy update index. Channel is null for time mismatches. A missing update or component is represented by null on the relevant side. Strictly greater absolute difference than EPS is a vector mismatch. An empty pair of streams matches with count zero.

Reject malformed streams or specs without replacing an existing report. Keep observe and stream working. This task uses a frozen actor and offline simulator exports. It does not require model training or a hardware deployment.
