#!/bin/bash
# Items 2, native core, ferry: one Godot process at a time (each driver RAM-gates itself).
cd "$(dirname "$0")/.."
set -e
python3 qa/prep.py project runs/game_art_1t --override "threading.worker_pool/max_threads=1"
python3 qa/prep.py measure/foreign_project runs/foreign --seed 5
python3 qa/prep.py measure/foreign_project runs/foreign_native --seed 6 --native
python3 measure/item2_probe.py runs/foreign runs/game_art_1t runs/item2.json
python3 measure/native_probe_test.py runs/foreign_native runs/native_foreign.json foreign
python3 measure/ferry.py runs/game_art_1t runs/ferry.json
echo AFTER_DONE
