# Index two or more ROS 2 recordings on one replay timeline

I need to replay camera, IMU, and calibration bags from the same experiment.
Their record clocks have known offsets. The replay needs to reproduce the
recording order and distinguish ROS time from when a sample appeared in the
recording. Build a modular Python package at /app/bag_conformance.

```bash
python3 -m bag_conformance index --spec SPEC.json --output INDEX.json
```

The spec has sources and clock_source. sources is a nonempty ordered array of
{id,path,offset_ns,publishers}. IDs are unique nonempty strings, paths to
rosbag2 directories are relative to the spec, and offset_ns is an integer
added to the source record timestamp. Read native SQLite3 or MCAP bags.
publishers maps each recorded topic other than /clock to its effective replay
QoS {reliability,durability,depth}. Reliability is reliable or best_effort,
durability is volatile or transient_local, and depth is a positive integer.
One source may have only one connection per topic. All sources offering the
same topic must use the same type. Keep the original CDR payload.

clock_source is the source ID authorized to supply /clock messages of type
rosgraph_msgs/msg/Clock. Other sources must omit /clock. Sort events by shared
record time, clock events before other events, input source order, then the
message's order within that source at equal time. There must be a /clock
event before an ordinary event can be indexed. Each clock value applies to
subsequent events until the next clock event. A strictly decreasing clock
value starts a new epoch. The first epoch is zero.

Write an object with schema_version 1 and events. Each event is
{source,topic,type,record_ns,clock_ns,epoch,sha256}. record_ns is the common
record time, clock_ns is the latest authorized clock value including the
event's own value if it supplies one, and sha256 hashes the original CDR
bytes. Include /clock rows. Reject malformed inputs and preserve an existing
destination. Identical inputs must produce identical output bytes.
