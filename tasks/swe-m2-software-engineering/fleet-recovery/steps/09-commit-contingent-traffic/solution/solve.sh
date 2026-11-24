#!/bin/sh
set -eu
solution="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p /app/fleet_recovery
cp "$solution"/fleet_recovery/*.py "$solution"/fleet_recovery/*.cpp /app/fleet_recovery/
cd /app
python3 -B -c 'from pathlib import Path; from fleet_recovery.competition import native_binary as competition; from fleet_recovery.contingent import native_binary as contingent; p = Path("/app/fleet_recovery"); competition(p); contingent(p)'
