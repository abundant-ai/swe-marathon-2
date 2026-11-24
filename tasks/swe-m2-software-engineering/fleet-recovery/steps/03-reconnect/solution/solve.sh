#!/bin/sh
set -eu
solution="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p /app/fleet_recovery
cp "$solution"/fleet_recovery/*.py /app/fleet_recovery/
