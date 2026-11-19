#!/usr/bin/env bash
# Proves, wherever the original is installed (both images' builder stages and the reference
# solution), that a bpl binary is the hardened build (apply.sh): ordinary programs still run, and
# every way for a program to read outside the directory it runs in, under /proc, /sys or /dev, to
# write a file, to reach the network, to start a program, to compile machine code, or to use the
# command line's removed modes and the worker's test requests is refused.
# usage: smoke.sh <bpl binary>
set -euo pipefail
bpl="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/run"
cd "$work/run"

fail() {
    echo "hardening smoke test failed: $*" >&2
    exit 1
}

# expect CODE TEXT COMMAND...: the command exits with CODE and prints TEXT on stdout or stderr.
expect() {
    local code=$1 text=$2 out status=0
    shift 2
    out="$(timeout 120 "$@" 2>&1)" || status=$?
    [ "$status" -eq "$code" ] || fail "'$*' exited $status, expected $code: $out"
    [[ "$out" == *"$text"* ]] || fail "'$*' did not print '$text': $out"
}

# It runs: a value, a script, a module under the working directory, standard input.
expect 0 "basedpl 0.1.95" "$bpl" --version
expect 0 "45" "$bpl" -e '+/ι10'
printf 'mean←+/÷≢\n' > stats.bpl
printf '[mean:]←•load "stats.bpl"\n⎕←mean 2 4 9\n' > main.bpl
expect 0 "5" "$bpl" main.bpl
printf 'red,3\n' > data.csv
expect 0 "red,3" "$bpl" -e '•nget "data.csv"'
expect 0 "piped" "$bpl" -e '•nget "-"' < <(printf 'piped\n')
expect 0 "written" "$bpl" -e '"-" •nput "written"'

# Files outside the working directory, by path, by "..", by a link, as the program itself or a
# module; and the kernel's trees even where the working directory is /.
mkdir -p "$work/outside" && printf 'secret-smoke-7d1e9c\n' > "$work/outside/secret.txt"
ln -s "$work/outside/secret.txt" link.txt
printf '⎕←1\n' > "$work/outside/prog.bpl"
for read in "\"$work/outside/secret.txt\"" '"../outside/secret.txt"' '"link.txt"'; do
    expect 1 "reads only files under its working directory" "$bpl" -e "•nget $read"
done
expect 1 "reads only files under its working directory" "$bpl" -e "•load \"$work/outside/prog.bpl\""
expect 1 "reads only files under its working directory" "$bpl" "$work/outside/prog.bpl"
expect 1 "reads only files under its working directory" "$bpl" "../outside/prog.bpl"
for path in /proc/self/maps /proc/self/environ /proc/self/mem /sys/kernel/mm/transparent_hugepage/enabled /dev/null /dev/stdin; do
    status=0
    out="$(cd / && BPL_SMOKE_SECRET=secret-smoke-env timeout 60 "$bpl" -e "•nget \"$path\"" 2>&1)" || status=$?
    [ "$status" -eq 1 ] || fail "•nget $path exited $status"
    case "$out" in *"secret-smoke-env"*|*"[stack]"*|*"[heap]"*) fail "•nget $path printed the process's own files: $out" ;; esac
    status=0
    out="$(cd / && timeout 60 "$bpl" "$path" 2>&1 < /dev/null)" || status=$?
    [ "$status" -eq 1 ] || fail "bpl $path exited $status"
    case "$out" in *"[stack]"*|*"[heap]"*) fail "bpl $path printed the process's own files: $out" ;; esac
done
ln -s /proc/self/maps maps.bpl
expect 1 "reads only files under its working directory" "$bpl" maps.bpl

# No file is written, listed, copied, moved, removed or made.
expect 1 "this build of bpl writes no files" "$bpl" -e '"out.txt" •nput "x"'
[ ! -e out.txt ] || fail "•nput wrote a file"
for call in '•readdir "."' '•metadata "data.csv"' '"copy.csv" •copy "data.csv"' '"moved.csv" •rename "data.csv"' \
            '•remove "data.csv"' '•mkdir "made"'; do
    expect 1 "no file system functions apart from •path" "$bpl" -e "$call"
done
[ -e data.csv ] && [ ! -e copy.csv ] && [ ! -e moved.csv ] && [ ! -e made ] || fail "a file system function changed the directory"
expect 0 "parent" "$bpl" -e '•path "a/b.txt"'

# No network and no program started: •fetch refuses before any transport, with a curl on PATH.
mkdir -p "$work/bin" && printf '#!/bin/sh\ntouch %s/curl-ran\n' "$work" > "$work/bin/curl" && chmod +x "$work/bin/curl"
expect 1 "this build of bpl has no network access" env PATH="$work/bin:$PATH" "$bpl" -e '•fetch "http://127.0.0.1:9/"'
[ ! -e "$work/curl-ran" ] || fail "•fetch started curl"

# No machine code: a stage large enough to compile, with compiling forced, takes no compiled route
# (upstream's build reports "compiled" among the routes here).
out="$(env BASEDPL_COMPILE=always timeout 120 "$bpl" -e '(•explain "+/2×(ι400000)+1.5").routes' 2>&1)" || fail "•explain failed: $out"
[ -n "$out" ] || fail "•explain printed nothing"
case "$out" in *compiled*) fail "a stage was compiled to machine code: $out" ;; esac

# No Jupyter kernel, no --costs, and the worker serves only code, call and bindings.
expect 2 "" "$bpl" --kernel -f connection.json
expect 2 "" "$bpl" --costs main.bpl
out="$("$bpl" --help)"
case "$out" in *"--costs"*|*"--kernel"*) fail "the usage still offers a removed mode: $out" ;; esac
out="$(printf '{"id":1,"case":{"code":"1+1","expected_code":"2"}}\n{"id":2,"check":{"path":"main.bpl"}}\n{"id":3,"code":"1+2"}\n' | "$bpl" --worker)"
[ "$(printf '%s\n' "$out" | grep -c '"expected code, call or bindings"')" -eq 2 ] || fail "the worker ran a test request: $out"
[[ "$out" == *'"id":3,"result":{"value":3.0'* ]] || fail "the worker did not evaluate code: $out"

echo "bpl hardening verified: $bpl"
