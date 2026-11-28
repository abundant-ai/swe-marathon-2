#!/usr/bin/env bash
# Deliver Dogwood 1.2.0's own source as the implementation: the release's five crates laid out as
# one Cargo workspace, with the release's dependency versions and arithmetic switched on.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /app/dogwood-rebuild
cp -R "$here/upstream/." /app/dogwood-rebuild/
