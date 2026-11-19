#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
src="$(mktemp -d)"
build="$(mktemp -d)"
# The images' build: the same sources and hardening, the same flags, the same check of the result.
cp -R "$here/upstream/." "$src/"
sh "$here/hardening/apply.sh" "$src"
sh "$here/hardening/build.sh" "$src" "$build" "$(nproc)" > "$build.log" 2>&1 || { cat "$build.log" >&2; exit 1; }
mkdir -p /app/rebuild
install -m 0755 "$build/goose" /app/rebuild/goose
rm -rf /app/rebuild/tcclib
cp -a "$build/tcclib" /app/rebuild/tcclib
install -m 0644 "$src/LICENSE" /app/rebuild/LICENSE
# The installed layout passes the same smoke test; the build's link and hashes (build.sh's build.txt:
# its sha256 without the marker matches the recording compiler's where the toolchains match) go to
# the trial's logs, to set beside recording.json's.
bash "$here/hardening/smoke.sh" /app/rebuild/goose
cat "$build/build.txt"
(mkdir -p /logs/agent && cp "$build/build.txt" /logs/agent/build.txt && cp "$build.log" /logs/agent/build.log) || true
rm -rf "$build" "$src" "$build.log"

# Not part of the solution: probe.c records how this sandbox treats the released compiler's
# set-group-id exec (ids, AT_SECURE, LD_PRELOAD, ptrace and /proc/<pid>/mem reads), as the agent's
# user, into /logs/agent/probe.txt for the task's authors. Nothing in it can change the result.
(
    set +e
    probe="$(mktemp -d)"
    chmod 0755 "$probe"
    gcc -O1 -o "$probe/probe" "$here/probe.c" && gcc -O1 -shared -fPIC -DPRELOAD -o "$probe/preload.so" "$here/probe.c"
    chmod 0755 "$probe/probe" "$probe/preload.so"
    if [ "$(id -u)" = 0 ]; then
        timeout 60 setpriv --reuid dev --regid dev --init-groups "$probe/probe" "$probe/preload.so" > "$probe/probe.txt" 2>&1
    else
        timeout 60 "$probe/probe" "$probe/preload.so" > "$probe/probe.txt" 2>&1
    fi
    mkdir -p /logs/agent && cp "$probe/probe.txt" /logs/agent/probe.txt
    rm -rf "$probe"
) || true
