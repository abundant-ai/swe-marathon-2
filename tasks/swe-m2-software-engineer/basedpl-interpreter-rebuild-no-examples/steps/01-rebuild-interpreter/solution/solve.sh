#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# Installs the original interpreter, with the all-zero build marker; mark.py accepts only that build.
# source/ holds that build's source, to read: upstream's code at the pinned commit with the hardening changes.
mkdir -p /app/rebuild
python3 "$here/mark.py" "$here/bpl.xz" "$here/build.txt" - /app/rebuild/bpl
# mark.py writes the build's facts beside the binary; /app/rebuild keeps only the interpreter and its licence.
rm -f /app/rebuild/build.txt
install -m 0644 "$here/LICENSE" /app/rebuild/LICENSE
