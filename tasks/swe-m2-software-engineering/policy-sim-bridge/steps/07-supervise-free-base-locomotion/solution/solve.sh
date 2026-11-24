#!/bin/sh
set -eu
solution="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p /app/policy_bridge
cp "$solution"/policy_bridge/*.py /app/policy_bridge/
