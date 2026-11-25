#!/bin/bash
# Copy the CC0 art subset the spike imports into project/assets/vendor (vendor/ stays untouched).
set -euo pipefail
V="$(cd "$(dirname "$0")/.." && pwd)/vendor"
D="$(cd "$(dirname "$0")/.." && pwd)/project/assets/vendor"
mkdir -p "$D/kenney_car_kit" "$D/kenney_city_roads" "$D/ubc" "$D/ubc_hair" "$D/ual"
rsync -a "$V/kenney-car-kit/extracted/Models/GLB format/" "$D/kenney_car_kit/"
rsync -a "$V/kenney-city-kit-roads/extracted/Models/GLB format/" "$D/kenney_city_roads/"
rsync -a "$V/quaternius-universal-base-characters/extracted/Universal Base Characters[Standard]/Base Characters/Godot - UE/" "$D/ubc/"
rsync -a "$V/quaternius-universal-base-characters/extracted/Universal Base Characters[Standard]/Hairstyles/Rigged to Head Bone/glTF (Godot -Unreal)/" "$D/ubc_hair/"
rsync -a "$V/quaternius-universal-animation-library/extracted/Universal Animation Library[Standard]/Unreal-Godot/" "$D/ual/"
cp "$V/kenney-car-kit/extracted/License.txt" "$D/kenney_car_kit/License.txt"
cp "$V/kenney-city-kit-roads/extracted/License.txt" "$D/kenney_city_roads/License.txt"
cp "$V/quaternius-universal-base-characters/extracted/Universal Base Characters[Standard]/License_Standard.txt" "$D/ubc/License.txt"
cp "$V/quaternius-universal-animation-library/extracted/Universal Animation Library[Standard]/License.txt" "$D/ual/License.txt"
du -sh "$D"/*
