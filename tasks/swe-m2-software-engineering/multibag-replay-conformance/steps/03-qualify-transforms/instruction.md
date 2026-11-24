# Qualify the pose stream that a subscriber actually sees

The same bag can look correct in isolation while a late subscriber misses its
calibration, or while a seek leaves transforms from a previous clock epoch.
Add a consumer-level check. Keep both earlier commands working.

```bash
python3 -m bag_conformance qualify --spec SPEC.json --script SCRIPT.json --output REPORT.json
```

Accept the replay operations and an additional
{kind:"lookup",subscriber,source_frame,target_frame,max_age_ns}. max_age_ns
is a nonnegative integer. Each lookup returns target_from_source as
[x_m,y_m,yaw_rad]. Use only /tf and /tf_static messages delivered to the
named subscriber. They use tf2_msgs/msg/TFMessage with planar transforms.
A transform describes the child pose in its parent frame. Drop leading
slashes from frame names. Track the latest delivered transform for each
parent-child pair and topic. Static transforms are valid throughout their
epoch. Dynamic transforms must have a header time at or before the latest
ROS clock, and an age at most max_age_ns. If both topics supply the same
pair, prefer a usable dynamic transform. If different usable parents claim
the same child, or the usable graph contains a cycle, the lookup is
unavailable. Clear the consumer's transform buffer on seek and epoch reset.
A restored publisher cache becomes visible to a consumer through the
subscription's retained deliveries. The replay script can use a different
subscriber ID after seeking.

Traverse the usable graph in either direction. A known frame resolves to
itself with zero translation and yaw. Normalize output yaw to [-pi,pi).
Write the replay report with an additional lookups array, in operation order.
Each lookup has operation, subscriber, source_frame, target_frame, status
ok or unavailable, and target_from_source, which is null if unavailable.
Include lookups even when the consumer has received no calibration.
