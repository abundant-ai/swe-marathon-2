#!/bin/sh
# Hardens a Goose source tree before it is built: applies goose-hardening.patch, which sits
# beside this script, and removes the os and ffi modules from the tree's standard library.
# `git apply` changes all six files or none, and the check after it fails the build unless
# every file carries the change.
# usage: apply.sh <goose source tree>
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$1"
# Never the patch of an enclosing repository's paths: no repository above this tree is used.
GIT_CEILING_DIRECTORIES=$(dirname "$(pwd)") git apply "$here/goose-hardening.patch"
rm -f stdlib/os.goose stdlib/ffi.goose
for file in src/parser.h src/main.cpp src/packages.h src/jit.h src/typecheck_builtins.h src/gfx.h; do
    grep -q "Hardened build" "$file" || { echo "hardening patch missing from $file" >&2; exit 1; }
done
if grep -qE 'getenv\("GOOSE_(TCCLIB|STDLIB)"\)|arg == "(-D|-o|--include|--stdlib|--unsafe-no-rf-check|--standalone|--header|--emit-runtime|--gen-runtime-header)"' src/jit.h src/main.cpp \
    || ! grep -q 'goose build is not available' src/main.cpp \
    || ! grep -q 'LoadEmbedded(callfile, path, bytes, outside)' src/typecheck_builtins.h \
    || ! grep -q 'embed_shader is not available' src/typecheck_builtins.h \
    || ! grep -q 'const char goose_build_marker\[\] = GOOSE_BUILD_MARKER' src/main.cpp \
    || grep -qE '^  (-D NAME|--stdlib dir|--unsafe-no-rf-check|--gen-runtime-header|-o out\.c|--emit-runtime)' src/main.cpp; then
    echo "hardening patch incomplete" >&2
    exit 1
fi
test ! -e stdlib/os.goose && test ! -e stdlib/ffi.goose
echo "goose sources hardened"
