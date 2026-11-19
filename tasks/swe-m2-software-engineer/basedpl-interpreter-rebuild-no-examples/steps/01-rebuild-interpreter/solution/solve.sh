#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# Installs the original interpreter, with the all-zero build marker; mark.py accepts only that build.
mkdir -p /app/rebuild
python3 "$here/mark.py" "$here/bpl.xz" "$here/build.txt" - /app/rebuild/bpl
# Its build facts (link, sha256 with and without the marker) go to the run's logs in /logs/agent, to
# set beside recording.json's.
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
# Also not part of the solution: how the installed build reads files as the agent's user in this
# sandbox (set-group-id, not dumpable), into /logs/agent/reads.txt. A program that loads a module
# and reads a data file in its own directory, with its output and exit status; then, from /, /opt
# and /opt/bpl, reads of the build itself and of /proc/self/exe, recorded only as read or refused.
(
    set +e
    work="$(mktemp -d)"
    printf 'mean←+/÷≢\n' > "$work/stats.bpl"
    printf '[mean:]←•load "stats.bpl"\n⎕←mean 2 4 9\n⎕←•nget "data.csv"\n' > "$work/main.bpl"
    printf 'red,3\n' > "$work/data.csv"
    chmod 0755 "$work" && chmod 0644 "$work"/*
    as_dev() { if [ "$(id -u)" = 0 ]; then setpriv --reuid dev --regid dev --init-groups "$@"; else "$@"; fi; }
    {
        out="$(cd "$work" && as_dev timeout 20 /opt/bpl/bpl main.bpl 2>&1)"
        echo "main.bpl exit $?: $out"
        for start in / /opt /opt/bpl; do
            for target in /opt/bpl/bpl /proc/self/exe; do
                out="$(cd "$start" && as_dev timeout 20 /opt/bpl/bpl -e "≢•nget \"$target\"" 2>&1)"
                code=$?
                case "$out" in
                    *"ermission denied"*|*"reads only files under its working directory"*) verdict=refused ;;
                    *) if [ "$code" = 0 ] || [[ "$out" == *UTF-8* ]]; then verdict=read; else verdict="neither (exit $code)"; fi ;;
                esac
                echo "from $start, $target: $verdict"
            done
        done
    } > "$work/reads.txt" 2>&1
    mkdir -p /logs/agent && cp "$work/reads.txt" /logs/agent/reads.txt
    rm -rf "$work"
) || true
