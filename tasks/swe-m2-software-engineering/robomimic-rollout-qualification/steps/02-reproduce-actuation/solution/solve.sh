#!/bin/sh
set -eu
solution=$(dirname "$0")
app=${1:-/app}
mkdir -p "$app/rollout_qualification"
cp "$solution"/rollout_qualification/*.py "$app/rollout_qualification/"
