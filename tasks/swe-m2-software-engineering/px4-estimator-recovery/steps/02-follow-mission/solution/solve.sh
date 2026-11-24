#!/bin/sh
set -eu
solution="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p /app/px4_recovery
cp "$solution"/px4_recovery/*.py /app/px4_recovery/
