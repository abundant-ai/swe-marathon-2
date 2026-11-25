#!/bin/sh
# Builds goose from a source tree that apply.sh has hardened, the same way wherever it is built, and
# checks the result with smoke.sh against the installed standard library.
#
# The link is a static PIE, stripped, where that works: no dynamic loader, and the binary's own
# addresses still differ from run to run. Failing that it is static, failing that dynamic, each from
# the same objects and checked by smoke.sh. A static binary has no dynamic loader, so
# LD_PRELOAD and LD_AUDIT cannot put code into the compiler's process, whatever a sandbox does with
# its set-group-id exec. The JIT needs no dlsym for it: the compiler hands TinyCC every host symbol
# itself (src/jit_runtime.c, under -nostdlib), and the standard library's extern fns bind to those or
# to the runtime's own C. Where the static link fails or does not pass smoke.sh, the same objects are
# linked again dynamically, stripped and checked the same way.
#
# Every path that would enter the binary is fixed (the TinyCC fallback directory; the source and
# build directories, mapped), so builds from one toolchain differ only in their marker. A file named
# marker beside this script, where there is one, becomes the build's marker (src/main.cpp), which
# names that build; without it the marker is all zeros. The build writes <build>/link (static-pie,
# static or dynamic) and <build>/build.txt: the link, the binary's sha256, and its sha256 with the
# marker zeroed, which builds of one toolchain share.
# usage: build.sh <hardened source tree> <build dir> <parallel jobs>
set -eu
here=$(cd "$(dirname "$0")" && pwd)
src=$1
build=$2
jobs=$3
marker=""
if [ -f "$here/marker" ]; then
    marker="GOOSE-BUILD-MARKER-$(tr -dc 0-9a-f < "$here/marker" | head -c 32)"
    printf '#define GOOSE_BUILD_MARKER "%s"\n' "$marker" > "$src/src/goose_marker.h"
fi
flags="-ffile-prefix-map=$src=/src -ffile-prefix-map=$build=/build"

make_goose() {
    cmake -S "$src" -B "$build" -DCMAKE_BUILD_TYPE=Release -DGOOSE_VERSION=745901f \
        -DGOOSE_STDLIB_PATH=/usr/local/share/goose/stdlib -DGOOSE_TCC_LIB_PATH=/usr/local/lib/goose/tcclib \
        "-DCMAKE_C_FLAGS=$flags" "-DCMAKE_CXX_FLAGS=$flags" "-DCMAKE_EXE_LINKER_FLAGS=$1" \
        && cmake --build "$build" --target goose -j "$jobs" \
        && test -f "$build/tcclib/include/tccdefs.h" \
        && bash "$here/smoke.sh" "$build/goose"
}

rm -rf "$build"
if make_goose "-static-pie -s"; then
    link=static-pie
elif echo "goose: no static PIE link (or it failed smoke.sh); linking the same objects static" >&2 \
        && make_goose "-static -s"; then
    link=static
else
    echo "goose: no static link either; linking the same objects dynamically" >&2
    make_goose "-s"
    link=dynamic
fi
if [ -n "$marker" ] && ! grep -qF "$marker" "$build/goose"; then
    echo "goose: the build's marker is not in the binary" >&2
    exit 1
fi
echo "$link" > "$build/link"
python3 - "$build/goose" "$link" > "$build/build.txt" <<'EOF'
import hashlib, re, sys
data = open(sys.argv[1], "rb").read()
zeroed = re.sub(rb"GOOSE-BUILD-MARKER-[0-9a-f]{32}", b"GOOSE-BUILD-MARKER-" + b"0" * 32, data)
print(f"link {sys.argv[2]}\nsha256 {hashlib.sha256(data).hexdigest()}\nsha256_without_marker {hashlib.sha256(zeroed).hexdigest()}")
EOF
cat "$build/build.txt"
