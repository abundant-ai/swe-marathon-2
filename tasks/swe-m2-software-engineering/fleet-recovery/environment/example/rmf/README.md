# Native Open-RMF starter

The container includes the exact pinned Jazzy libraries under `/opt/fleet-rmf` and the compiled starter `rmf-native`. The provided C++ source wraps actual `Interpolate::positions` and `DetectConflict::between`. To rebuild from `/app`:

```sh
sh example/rmf/build_rmf_native.sh /tmp/rmf-native
printf '0.37 0.65 0.54 0.65 0.47 3\n-2 0 0\n0 0 0\n2 0 0\n' | /tmp/rmf-native interpolate
python -m fleet_recovery rmf-handover --spec example/rmf/manifest.json \
  --state /tmp/rmf-starter < example/rmf/observations.ndjson
```

The first command prints a waypoint count, then `time_ns x y yaw vx vy omega` rows. Times are relative to zero. For `rmf-native conflict`, send two route descriptions. Each begins with `map radius count` and then its count of absolute-time native rows. The result is the first native conflict time in nanoseconds or `clear`. Keep the computed native points to associate measured vendor poses with their commissioned checkpoint indexes.

`rmf-native schedule` takes the same route descriptions after one line containing `delay_ns observed_checkpoint release_checkpoint`. It registers both routes in a native database, mirrors the accepted carrier delay, and confirms the reported dependency with the current plan. A missing checkpoint uses −1. The output is the native collision time or `clear`, then `ready` or `blocked`. The coordinator determines which updates and captures have authority before passing them to this operation.

The sample observations keep the courier's initial position while its first authority is outstanding. They exercise idempotent command identity and schedule version handling. The actor-side protocol, C++ helper and Open-RMF library are available locally. [Native package pins](../../native-rmf/SOURCES.md) · [Measured read-only fleet issue](https://github.com/open-rmf/rmf_ros2/issues/584)

Submit the practice crossing's first schedule snapshot with a fresh state path after implementing `rmf-negotiate`:

```sh
python3 -m fleet_recovery rmf-negotiate --site example/rmf/competition-site.json \
  --state /tmp/practice-crossing.state.json --event example/rmf/competition-open.json \
  --output /tmp/practice-crossing.reply.json
cat /tmp/practice-crossing.reply.json
```

The sample declares two courier requests and a carrier approach that starts at mission time zero. The two couriers have different motion limits. The candidate command schedules both against the carrier itinerary and emits the two initial leg authorities. Running the same command a second time returns the original reply.

To inspect common movement authority before either of the practice
transfer's two observations, run the contingent command with a fresh
journal after implementing it.

```sh
python3 -m fleet_recovery rmf-contingent --site example/rmf/contingent-site.json \
  --state /tmp/practice-contingent.state.json --event example/rmf/contingent-open.json \
  --output /tmp/practice-contingent.reply.json
cat /tmp/practice-contingent.reply.json
```

The policy lists both carrier and lift alternatives. The initial commands
authorize only the two shared approaches. Later commands use the actual
carrier itinerary, lift dispatch and door observations.
