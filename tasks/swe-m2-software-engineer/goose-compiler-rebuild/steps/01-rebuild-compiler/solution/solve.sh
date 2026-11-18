#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
src="$(mktemp -d)"
build="$(mktemp -d)"
# The images' build: the same sources and hardening, the same flags, the same check of the result.
cp -R "$here/upstream/." "$src/"
sh "$here/hardening/apply.sh" "$src"
cmake -S "$src" -B "$build" -DCMAKE_BUILD_TYPE=Release -DGOOSE_VERSION=745901f -DGOOSE_STDLIB_PATH=/usr/local/share/goose/stdlib >/dev/null
cmake --build "$build" --target goose -j "$(nproc)" >/dev/null
bash "$here/hardening/smoke.sh" "$build/goose"
mkdir -p /app/rebuild
install -m 0755 "$build/goose" /app/rebuild/goose
rm -rf /app/rebuild/tcclib
cp -a "$build/tcclib" /app/rebuild/tcclib
install -m 0644 "$src/LICENSE" /app/rebuild/LICENSE
