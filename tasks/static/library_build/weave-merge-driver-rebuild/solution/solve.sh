#!/bin/bash
# Reference solution: the original's own source at tag v0.7.1, patched only to build from the
# offline registry (no git2, rayon, memmap2 or env_logger; three grammars), placed in /app/driver.
# Packaging stages it into solution/upstream/ (never committed).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /app/driver
cp -R "$here/upstream/." /app/driver/
cd /app/driver && cargo build --release --offline -q
