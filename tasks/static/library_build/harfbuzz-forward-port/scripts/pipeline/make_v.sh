#!/bin/sh
# make_v PATCH_DIR OUT_TREE
#
# The verification-gap mutant V as a tree: 15.2.0 (without test/) with every tier-C unit's change taken out, the units
# an agent cannot confirm on its own 14.3.0 build and shipped tools (notes/DESIGN.md, "Tiers"). Upstream commits
# (*.patch) are reverted newest first and skipped when they no longer revert cleanly (listed in OUT_TREE.skipped);
# hand-resolved reverts (*.fwd.patch) are applied after. The same patches build mut-V in the pipeline.
# Runs inside the pipeline image only.
set -eu
PATCHES=$1
OUT=$2
test ! -e "$OUT"
mkdir -p "$OUT"
tar -xJf /dl/harfbuzz/harfbuzz-15.2.0.tar.xz -C "$OUT" --strip-components=1 --exclude=harfbuzz-15.2.0/test
cd "$OUT"
: > "$OUT.skipped"
for p in $(ls -r "$PATCHES"/*.patch | grep -v '[.]fwd[.]patch$'); do
  if patch -R -p1 -s --dry-run -r - < "$p" > /dev/null 2>&1; then
    patch -R -p1 -s --no-backup-if-mismatch -r - < "$p"
  else
    basename "$p" >> "$OUT.skipped"
  fi
done
for p in $(ls "$PATCHES"/*.fwd.patch); do
  patch -p1 -s --no-backup-if-mismatch -r - < "$p"
done
echo "V tree: $(wc -l < "$OUT.skipped") patches skipped"
