#!/bin/sh
set -eu
solution="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p /app/dock_recovery
cp "$solution"/dock_recovery/*.py /app/dock_recovery/
