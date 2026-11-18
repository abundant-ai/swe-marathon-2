#!/bin/sh
# Builds goose from a source tree that apply.sh has hardened, the same way for both images and the
# reference solution, and checks the result with smoke.sh against the installed standard library.
#
# The link is static and stripped where that works. A static binary has no dynamic loader, so
# LD_PRELOAD and LD_AUDIT cannot put code into the compiler's process, whatever a sandbox does with
# its set-group-id exec. The JIT needs no dlsym for it: the compiler hands TinyCC every host symbol
# itself (src/jit_runtime.c, under -nostdlib), and the standard library's extern fns bind to those or
# to the runtime's own C. Where the static link fails to build or to pass smoke.sh, the dynamic link
# is built instead, stripped and checked the same way. The link used is written to <build>/link.
# usage: build.sh <hardened source tree> <build dir> <parallel jobs>
set -eu
here=$(cd "$(dirname "$0")" && pwd)
src=$1
build=$2
jobs=$3

make_goose() {
    rm -rf "$build"
    cmake -S "$src" -B "$build" -DCMAKE_BUILD_TYPE=Release -DGOOSE_VERSION=745901f \
        -DGOOSE_STDLIB_PATH=/usr/local/share/goose/stdlib "-DCMAKE_EXE_LINKER_FLAGS=$1" \
        && cmake --build "$build" --target goose -j "$jobs" \
        && test -f "$build/tcclib/include/tccdefs.h" \
        && bash "$here/smoke.sh" "$build/goose"
}

if make_goose "-static -s"; then
    echo static > "$build/link"
else
    echo "goose: the static link did not build or did not pass smoke.sh; building the dynamic link" >&2
    make_goose "-s"
    echo dynamic > "$build/link"
fi
echo "goose built ($(cat "$build/link") link): $build/goose"
