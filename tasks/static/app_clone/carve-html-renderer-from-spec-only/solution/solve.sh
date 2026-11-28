#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# Install the renderer in carve/ (Python 3.12, standard library only) as /app/rebuild: the
# `carve` launcher and the carvelib package beside it, with its modules compiled ahead of time
# (hash-checked, so a copy that changes the files' times still uses them).
mkdir -p /app/rebuild
rm -rf /app/rebuild/carvelib
cp -R "$here/carve/carvelib" /app/rebuild/carvelib
install -m 0755 "$here/carve/carve" /app/rebuild/carve
find /app/rebuild/carvelib -type d -exec chmod 0755 {} +
find /app/rebuild/carvelib -type f -exec chmod 0644 {} +
python3 -I -m compileall -q --invalidation-mode checked-hash /app/rebuild/carvelib
