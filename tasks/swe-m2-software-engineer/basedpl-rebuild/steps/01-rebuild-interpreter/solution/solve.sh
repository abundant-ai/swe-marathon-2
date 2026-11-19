#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# The reference solution delivers the original interpreter: the one hardened build that both images
# install, here with the all-zero build marker. mark.py refuses anything but that build.
mkdir -p /app/rebuild
python3 "$here/mark.py" "$here/bpl.xz" "$here/build.txt" - /app/rebuild/bpl
# Its build facts (link, sha256 with and without the marker) go to the trial's logs, to set beside
# recording.json's.
(mkdir -p /logs/agent && cp /app/rebuild/build.txt /logs/agent/build.txt) || true
rm -f /app/rebuild/build.txt
install -m 0644 "$here/LICENSE" /app/rebuild/LICENSE
# The images' smoke test, on the installed copy in this sandbox, for the logs: the images' builds
# have already proved the same binary, so a sandbox that treats /proc or /dev differently does not
# fail the solution.
(mkdir -p /logs/agent && bash "$here/smoke.sh" /app/rebuild/bpl > /logs/agent/smoke.txt 2>&1) \
    || echo "the smoke test did not pass here; see /logs/agent/smoke.txt" >&2

# Not part of the solution: probe.c records how this sandbox treats the released interpreter's
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
