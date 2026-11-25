#!/bin/bash
# Build the probe's native core against the header dumped from the pinned Godot binary.
#   macOS: universal libqacore.dylib     Linux: libqacore.so (x86_64)
# Regenerate the header with:  <godot> --headless --dump-gdextension-interface  (inside gen/)
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(uname)" = "Darwin" ]; then
  clang -shared -fPIC -O2 -Wall -Wextra -Wno-unused-parameter -Wno-cast-function-type-mismatch \
    -arch arm64 -arch x86_64 -o libqacore.dylib qa_core.c
else
  cc -shared -fPIC -O2 -Wall -Wextra -Wno-unused-parameter -fvisibility=hidden -o libqacore.so qa_core.c
  strip --strip-unneeded libqacore.so
fi
ls -la libqacore.*
