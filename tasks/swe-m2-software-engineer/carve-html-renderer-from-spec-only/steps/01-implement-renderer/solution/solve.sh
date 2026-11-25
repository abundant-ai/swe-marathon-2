#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# Install carve-rs 0.1.14's static Linux release build as /app/rebuild/carve, from the release
# archive beside this script: install.py checks the archive's and the binary's sha256 against
# build.txt and overwrites in place, byte for byte, the strings listed in blank.json (text of the
# command's own usage and of the parts the HTML path never prints); then install the licence.
mkdir -p /app/rebuild
python3 -I "$here/install.py" "$here/carve.tar.gz" "$here/build.txt" /app/rebuild/carve --blank "$here/blank.json"
install -m 0644 "$here/LICENSE" /app/rebuild/LICENSE
