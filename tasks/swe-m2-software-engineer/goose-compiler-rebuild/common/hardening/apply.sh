#!/bin/sh
# Hardens a Goose source tree before it is built: applies goose-hardening.patch, which sits
# beside this script, and removes the os and ffi modules from the tree's standard library.
# `git apply` changes all four files or none, and the check after it fails the build unless
# every file carries the change.
# usage: apply.sh <goose source tree>
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$1"
# Never the patch of an enclosing repository's paths: no repository above this tree is used.
GIT_CEILING_DIRECTORIES=$(dirname "$(pwd)") git apply "$here/goose-hardening.patch"
rm -f stdlib/os.goose stdlib/ffi.goose
for file in src/parser.h src/main.cpp src/packages.h src/jit.h; do
    grep -q "Hardened build" "$file" || { echo "hardening patch missing from $file" >&2; exit 1; }
done
if grep -qE 'getenv\("GOOSE_(TCCLIB|STDLIB)"\)|arg == "(-D|--include|--stdlib|--unsafe-no-rf-check)"' src/jit.h src/main.cpp; then
    echo "hardening patch incomplete" >&2
    exit 1
fi
test ! -e stdlib/os.goose && test ! -e stdlib/ffi.goose
echo "goose sources hardened"
