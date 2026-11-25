#!/usr/bin/env python3
"""Prepare (or refresh) a probe-inserted copy of a game project, then import it headless.

usage: prep.py SRC_PROJECT DST [--seed N] [--override section.key=value ...]
A refresh syncs SRC into DST (no deletions of the probe), re-inserts the probe autoload first
and re-imports. The probe's random folder and name are kept in DST/.qa_probe.json.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import GODOT, insert_probe, PROBE_SRC, memgate, add_native_core  # noqa: E402
import shutil  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--override", action="append", default=[])
    ap.add_argument("--mem-floor", type=int, default=30)
    ap.add_argument("--native", action="store_true", help="add the native core (GDExtension) next to the probe")
    a = ap.parse_args()
    memgate(a.mem_floor, wait_s=900)
    state_path = os.path.join(a.dst, ".qa_probe.json")
    os.makedirs(a.dst, exist_ok=True)
    subprocess.run(["rsync", "-a", "--exclude", ".godot", "--exclude", ".qa_probe.json", "--exclude", "override.cfg",
                    a.src.rstrip("/") + "/", a.dst + "/"], check=True)
    if os.path.exists(state_path):
        st = json.load(open(state_path))
        folder, name = st["folder"], st["name"]
        shutil.copy(PROBE_SRC, os.path.join(a.dst, folder, name + ".gd"))
        pg = os.path.join(a.dst, "project.godot")
        text = open(pg).read()
        entry = f'{name}="*res://{folder}/{name}.tscn"\n'
        text = text.replace("[autoload]\n\n", "[autoload]\n\n" + entry, 1)
        open(pg, "w").write(text)
    else:
        folder, name = insert_probe(a.dst, random.Random(a.seed))
        json.dump({"folder": folder, "name": name}, open(state_path, "w"))
    if a.native:
        add_native_core(a.dst, folder, name)
    ov = {}
    for o in a.override:
        k, v = o.split("=", 1)
        sec, key = k.split(".", 1)
        ov.setdefault(sec, {})[key] = v
    ovp = os.path.join(a.dst, "override.cfg")
    if ov:
        with open(ovp, "w") as f:
            for sec, kv in ov.items():
                f.write(f"[{sec}]\n\n" + "".join(f"{k}={v}\n" for k, v in kv.items()) + "\n")
    elif os.path.exists(ovp):
        os.remove(ovp)
    t0 = time.time()
    r = subprocess.run([GODOT, "--headless", "--path", a.dst, "--import"], capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    print(json.dumps({"dst": a.dst, "probe": [folder, name], "import_s": round(time.time() - t0, 2),
                      "errors": errs[:20]}))


if __name__ == "__main__":
    main()
