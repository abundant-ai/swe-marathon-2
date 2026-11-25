#!/usr/bin/env python3
"""Print the headline numbers of items 2, 4 (default pool), 5, 6 and the ferry for PHASE0.md."""
import glob, json, os

R = "runs"


def load(p):
    try:
        return json.load(open(os.path.join(R, p)))
    except FileNotFoundError:
        return None


i2 = load("item2.json")
if i2:
    print("== item 2")
    h = i2["foreign_hello"]
    print("foreign hello:", {k: h[k] for k in ("physics_engine", "ticks", "jitter_fix", "autoload_first", "renderer",
                                                "display", "native_core", "key_in_environment", "key_in_script")})
    print("skeleton max err m:", i2["skeleton_pose_max_err_m"], "samples", i2["skeleton_samples"])
    print("input same tick dz:", i2["input_same_tick_dz_m"], "release:", i2["input_release_dz_m"])
    print("deltas:", i2["foreign_deltas"], "phys-proc frames:", i2["foreign_physics_minus_process_frames"])
    print("tick advance after 1 s hold:", i2["tick_advance_after_1s_hold"], "forged exit:", i2["forged_message_exit_code"])
    for o in i2["overhead"]:
        print("overhead:", o)
    print("pace independent:", i2["pace_independent"]["identical"], i2["pace_independent"]["fast"]["hash"],
          i2["pace_independent"]["slow"]["hash"])
nat = load("native_foreign.json")
if nat:
    print("== native core")
    h = nat["hello"]
    print({k: h.get(k) for k in ("native_core", "key_in_environment", "key_in_script", "autoload_first", "physics_engine")},
          "ticks", nat["ticks"], "wall", nat["wall_s_600_ticks_every_tick"], "rtt p50", nat["rtt_ms_p50"], "forged exit",
          nat["forged_exit_code"])
fer = load("ferry.json")
if fer:
    print("== ferry")
    for k, v in fer.items():
        print(k, v.get("max_drift_m"), "final_up", v.get("final_up"), "samples tail", (v.get("samples") or [])[-2:])
print("== item 4 default pool")
for p in sorted(glob.glob(os.path.join(R, "spread", "default_pool", "*.json"))):
    s = json.load(open(p))["summary"]
    print(os.path.basename(p), "unique", s["unique_traces"], "score", s["mean_score"],
          {k: (round(v["min"], 4), round(v["max"], 4)) for k, v in s.items() if isinstance(v, dict)})
