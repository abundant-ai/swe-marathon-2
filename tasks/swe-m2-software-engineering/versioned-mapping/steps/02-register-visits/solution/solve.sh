#!/bin/sh
set -eu
solution=$(dirname "$0")
app=${1:-/app}
mkdir -p "$app/versioned_mapping"
cp "$solution"/versioned_mapping/*.py "$app/versioned_mapping/"
