"""Write a two-frame live stream with one landmark at a known optical depth."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    identity = {"translation": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]}
    manifest = {
        "lag_frames": 4,
        "initial_pose": identity,
        "initial_sigmas": [0.01] * 6,
        "odometry_sigmas": [0.04] * 6,
        "calibrations": {
            "left": {
                "body_from_camera": identity,
                "intrinsics": [400, 400, 0, 320, 240],
            }
        },
        "landmarks": {"post": {"point": [0, 0, 4], "sigma": 0.1}},
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    packets = [
        {"request_id": 1, "operation": "frame", "frame": 0},
        {
            "request_id": 2,
            "operation": "frame",
            "frame": 1,
            "odometry": {**identity, "translation": [0.2, 0, 0]},
        },
        {
            "request_id": 3,
            "operation": "tracks",
            "updates": [
                {
                    "id": "post-0",
                    "action": "put",
                    "version": 1,
                    "frame": 0,
                    "landmark": "post",
                    "camera": "left",
                    "pixel": [320, 240],
                    "sigma_px": 0.7,
                },
                {
                    "id": "post-1",
                    "action": "put",
                    "version": 1,
                    "frame": 1,
                    "landmark": "post",
                    "camera": "left",
                    "pixel": [300, 240],
                    "sigma_px": 0.7,
                },
            ],
        },
    ]
    for packet in packets:
        print(json.dumps(packet))


if __name__ == "__main__":
    main()
