#!/bin/bash
# Build the QA telemetry node's native library against the interface header dumped from
# the pinned engine binary (gen/). No godot-cpp; plain C11.
#
#   build.sh [OUT_DIR]
#
# macOS: OUT_DIR/libtelemetry.dylib, universal (arm64 + x86_64), local symbols stripped.
# Linux: OUT_DIR/libtelemetry.so, x86_64, stripped, no build id, no compiler banner.
# OUT_DIR defaults to ../build/<os>-<arch> next to this folder.
#
# Only the entry symbol is exported. Regenerate gen/ after an engine upgrade:
#   <engine> --headless --dump-extension-api --dump-gdextension-interface
#   python scripts/gen_telemetry_binds.py --api extension_api.json
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
os="$(uname -s)"
arch="$(uname -m)"
out="${1:-$here/../build/$(echo "$os" | tr '[:upper:]' '[:lower:]')-$arch}"
mkdir -p "$out"
src=("$here/telemetry.c" "$here/sha256.c" "$here/jw.c")
common=(-std=c11 -O2 -fPIC -shared -fvisibility=hidden -Wall -Wextra -Werror
  -Wno-unused-parameter -Wno-unused-function -I"$here")
if [ "$os" = "Darwin" ]; then
  clang "${common[@]}" -arch arm64 -arch x86_64 -Wno-cast-function-type-mismatch \
    -install_name @rpath/libtelemetry.dylib -Wl,-dead_strip \
    -o "$out/libtelemetry.dylib" "${src[@]}"
  strip -x "$out/libtelemetry.dylib"
  codesign --force --sign - "$out/libtelemetry.dylib" 2>/dev/null || true
  ls -la "$out/libtelemetry.dylib"
else
  cc "${common[@]}" -D_GNU_SOURCE -fno-ident -ffunction-sections -fdata-sections \
    -Wl,--gc-sections -Wl,--build-id=none -Wl,-z,noexecstack -s \
    -o "$out/libtelemetry.so" "${src[@]}" -lpthread -lm -ldl
  strip --strip-unneeded "$out/libtelemetry.so"
  ls -la "$out/libtelemetry.so"
fi
