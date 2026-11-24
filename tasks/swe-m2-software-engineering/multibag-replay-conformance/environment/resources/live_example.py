"""Create a small native archive and read an actual late transient-local DDS sample.

Run from /app with the task's Jazzy environment. No external peers are required.
"""

from hashlib import sha256
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
from time import monotonic

from geometry_msgs.msg import TransformStamped
from rclpy import create_node, init, shutdown, spin_once
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.serialization import deserialize_message, serialize_message
from rosbags.rosbag2 import StoragePlugin, Writer
from rosbags.typesys import Stores, get_typestore
from tf2_msgs.msg import TFMessage


def send(worker, operation, **fields):
    """Send and read one request without relying on middleware callback timing."""
    worker.stdin.write(json.dumps({"operation": operation, **fields}) + "\n")
    worker.stdin.flush()
    if not select.select([worker.stdout], [], [], 8)[0]:
        raise RuntimeError("live worker did not reply")
    reply = json.loads(worker.stdout.readline())
    if "error" in reply:
        raise RuntimeError(reply["error"])
    return reply


def demonstration(directory):
    """Seal a TF sample, prepare a batch, and subscribe only after it was published."""
    archive, state = directory / "recording", directory / "state"
    transform = TransformStamped()
    transform.header.frame_id = "map"
    transform.child_frame_id = "bench_sensor"
    transform.transform.translation.x = 1.25
    transform.transform.rotation.w = 1.
    raw = serialize_message(TFMessage(transforms=[transform]))
    kind = "tf2_msgs/msg/TFMessage"
    with Writer(archive, version=9, storage_plugin=StoragePlugin.SQLITE3) as writer:
        connection = writer.add_connection("/tf_static", kind, typestore=get_typestore(Stores.ROS2_JAZZY))
        writer.write(connection, 5, raw)
    attach = {"request_id": "attach-example", "operation": "attach", "base_generation": 0,
              "shards": [{"id": "calibration", "path": "recording", "stream": "bench", "boot": "first",
                          "latched_topics": ["/tf_static"], "repeats": []}]}
    request = directory / "attach.json"
    request.write_text(json.dumps(attach), encoding="utf-8")
    cli = [sys.executable, "-B", "-m", "bag_conformance"]
    subprocess.run([*cli, "serve", "--state", str(state), "--request", str(request), "--output",
                    str(directory / "seal.json")], check=True)
    with subprocess.Popen([*cli, "live", "--state", str(state)], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, text=True) as worker:
        try:
            opened = send(worker, "open", request_id="example-open", reader="research",
                          generation=None, topics=["/tf_static"], begin_ns=6, end_ns=10)
            prepared = send(worker, "prepare", request_id="example-prepare", reader="research", max_events=2, max_bytes=4096)
            send(worker, "emit", reader="research", epoch=opened["epoch"], batch=prepared["batch"])
            send(worker, "ack", request_id="example-ack", reader="research", epoch=opened["epoch"], batch=prepared["batch"])
            init()
            listener = create_node("native_example_listener")
            try:
                observed = []
                name = opened["prefix"] + "/tf_static"
                qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
                listener.create_subscription(TFMessage, name, observed.append, qos, raw=True)
                expires = monotonic() + 7
                while not observed and monotonic() < expires:
                    spin_once(listener, timeout_sec=.03)
                if observed != [raw]:
                    raise RuntimeError("late subscriber did not receive the archived CDR")
                child = deserialize_message(observed[0], TFMessage).transforms[0].child_frame_id
                print(json.dumps({"generation": opened["generation"], "topic": name, "child_frame": child,
                                  "cdr_sha256": sha256(observed[0]).hexdigest()}, indent=2))
            finally:
                listener.destroy_node()
                shutdown()
        finally:
            worker.stdin.close()
            try:
                worker.wait(timeout=4)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="live-dds-example-") as temp:
        os.environ.setdefault("ROS_LOG_DIR", str(Path(temp) / "ros-logs"))
        os.environ.setdefault("ROS_DOMAIN_ID", str(17 + os.getpid() % 79))
        demonstration(Path(temp))
