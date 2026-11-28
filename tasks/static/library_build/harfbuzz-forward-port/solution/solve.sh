#!/usr/bin/env bash
# Reference solution: the library sources of upstream 15.2.0 for every file the change touches (src/ and the top-level
# meson.build, with the speed-measurement wiring left out as in our tree), copied over /app/harfbuzz, and the files
# 15.2.0 no longer has removed.
set -euo pipefail
cp -R /solution/private/tree/. /app/harfbuzz/
while IFS= read -r path; do
  [ -n "$path" ] && rm -f -- "/app/harfbuzz/$path"
done < /solution/private/deleted.txt
