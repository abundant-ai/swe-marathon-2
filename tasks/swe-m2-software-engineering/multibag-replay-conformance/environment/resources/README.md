# Replay format

Read ROS 2 bags in native MCAP or SQLite3 storage. Use their CDR record bytes and
the playback QoS declared in the experiment manifest. The tool runs offline, and
its monotonically advancing record clock is separate from the recorded ROS clock.

The native stage includes ROS 2 Jazzy and Cyclone DDS scoped to localhost. From `/app`, run `python3 /app/examples/live_example.py`. It creates and seals a temporary SQLite TF recording through the public CLI, starts the live worker, and then subscribes after publication to check the original CDR. The probe uses authored data and no external peers.
