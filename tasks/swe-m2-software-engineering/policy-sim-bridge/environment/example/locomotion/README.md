# Free-base locomotion starter

Run from `/app` with a fresh writable state directory.

```sh
python -m policy_bridge locomote --spec example/locomotion/manifest.json \
  --state /tmp/go2-starter < example/locomotion/starter.ndjson
```

The sample uses separate signed sensor and motor-wire orders. It exercises standing, arming on fresh load evidence, limiting on a loaded slipping foot, recovery and an expiring motion lease. The frozen actor runs on all thirteen accepted observations. Resend the last line to the same state directory to exercise exact retry.

## Pinned assets

| Artifact | Source and rights |
| --- | --- |
| `policy.onnx` | Go2 RL Lab, mixed1.3.2resume 82.5k, HF revision `d1f19f0a486e171c327d8c3da2d31dba294e6586`, MIT model repository. ONNX LFS SHA-256 `6ad8e4672301be9d2e3c610b2c9a79cf2833993fd0a6b253622e96faab1a8f95`. The published model takes 450 float32 observations and returns twelve float32 actions. |
| `go2-headless.xml` | Derived from the Go2 RL Lab deployment MJCF at commit `6c95d9feef4814c25eb6536e61bb38e1d1d718d4`, original SHA-256 `baad6bab8c359d5ac040c0eec7d5235574d60e748d54b121a08512e09816f829`. This headless asset has SHA-256 `9d8fce1764ff045eb31e4b71cac6716983731eecb5067b42dc96587ec70ec64e`. It names the foot collision geometries and preserves joint ranges, mass, inertia and contact geometry. The upstream MIT and Apache notices and Unitree BSD model notice are included. |

[Publisher’s actor and export configuration](https://huggingface.co/wty-yy/go2_rl_gym_data/tree/d1f19f0a486e171c327d8c3da2d31dba294e6586/go2_rl_lab/2026-10-13_15-35-09_mixed1.3.2resume_82.5k_0.6929/exported) · [Deployment MJCF](https://github.com/wty-yy/go2_rl_lab/blob/6c95d9feef4814c25eb6536e61bb38e1d1d718d4/deploy/deploy_mujoco/assets/go2.xml) · [Unitree model license](https://github.com/google-deepmind/mujoco_menagerie/blob/6da8b971844845de6ab27315aacc3a3fea4ddb8e/unitree_go2/LICENSE)

For the course checkpoint, run
`python3 /app/examples/locomotion/course_example.py /tmp/course-example`.
It creates `course.json` and `course-start.ndjson` for the `navigate` stream.
