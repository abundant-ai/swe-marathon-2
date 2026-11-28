#!/bin/bash
# Stage the reference solution into solution/upstream/ (git-ignored): the tag's own source, patched
# by scripts/oracle_patch.py to build from the offline registry, with the lock it was built with.
# Usage: scripts/stage_upstream.sh PATH/TO/weave-v0.7.1.tar.gz
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
tarball="$1"
want=2c3c913b1b2ae8c2c90ec152211a5818828714f142436c32df6b21391ad9cc35
if command -v sha256sum > /dev/null; then got=$(sha256sum "$tarball" | cut -d' ' -f1); else got=$(shasum -a 256 "$tarball" | cut -d' ' -f1); fi
[ "$got" = "$want" ] || { echo "checksum mismatch: $got" >&2; exit 1; }
dest="$here/solution/upstream"
[ ! -e "$dest" ] || { echo "$dest already exists; remove it first" >&2; exit 1; }
mkdir -p "$dest"
tar -xzf "$tarball" -C "$dest" --strip-components=1
python3 -I "$here/scripts/oracle_patch.py" "$dest"
cp "$here/solution/oracle.Cargo.lock" "$dest/Cargo.lock"
echo "staged $(find "$dest" -type f | wc -l | tr -d ' ') files in $dest"
