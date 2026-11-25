#!/bin/bash
# Item 4: 50 same-seed runs per case, one Godot process at a time (RAM-gated inside spread.py).
cd "$(dirname "$0")/.."
set -e
python3 measure/spread.py runs/game_art_1t runs/spread/one_worker scenarios/s1_wanted_red_light.yaml 1 50
python3 measure/spread.py runs/game_art_1t runs/spread/one_worker scenarios/s3_vehicle_handling.yaml 1 50
python3 measure/spread.py runs/game_art_1t runs/spread/one_worker scenarios/s3_vehicle_handling.yaml 5 50
python3 measure/spread.py runs/game_art runs/spread/default_pool scenarios/s1_wanted_red_light.yaml 1 50
python3 measure/spread.py runs/game_art runs/spread/default_pool scenarios/s3_vehicle_handling.yaml 1 50
python3 measure/spread.py runs/game_art runs/spread/default_pool scenarios/s3_vehicle_handling.yaml 5 50
echo ALL_DONE
