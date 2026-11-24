#!/bin/sh
set -eu
solution=$(dirname "$0")
app=${1:-/app}
mkdir -p "$app/bag_conformance"
cp "$solution"/bag_conformance/*.py "$app/bag_conformance/"
