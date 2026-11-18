#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
build="$(mktemp -d)"
cmake -S "$here/upstream" -B "$build" -DCMAKE_BUILD_TYPE=Release -DGOOSE_VERSION=745901f -DGOOSE_STDLIB_PATH=/usr/local/share/goose/stdlib >/dev/null
cmake --build "$build" --target goose -j "$(nproc)" >/dev/null
mkdir -p /app/rebuild
install -m 0755 "$build/goose" /app/rebuild/goose
rm -rf /app/rebuild/tcclib
cp -a "$build/tcclib" /app/rebuild/tcclib
install -m 0644 "$here/upstream/LICENSE" /app/rebuild/LICENSE
