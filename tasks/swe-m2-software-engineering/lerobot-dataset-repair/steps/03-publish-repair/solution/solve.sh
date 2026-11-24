#!/bin/sh
set -eu
solution=$(dirname "$0")
app=${1:-/app}
mkdir -p "$app/lerobot_repair"
cp "$solution"/lerobot_repair/*.py "$app/lerobot_repair/"
