#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# The reference solution delivers the original renderer itself: carve-rs 0.1.14's own static Linux
# release build, installed from the release archive as published. install.py refuses any archive or
# binary whose sha256 is not build.txt's.
mkdir -p /app/rebuild
python3 -I "$here/install.py" "$here/carve.tar.gz" "$here/build.txt" /app/rebuild/carve
install -m 0644 "$here/LICENSE" /app/rebuild/LICENSE
(mkdir -p /logs/agent && cp "$here/build.txt" /logs/agent/build.txt) || true
