#!/bin/sh
# make_mutant BASE_TREE PATCH_DIR OUT_TREE
#
# A mutant tree for the verifier: a copy of BASE_TREE (the reference tree, so it carries what the reference carries;
# test/ is left out, the verifier does not build it) with PATCH_DIR applied the way hb_build.sh applies it: upstream
# commits (*.patch) reverted newest first, skipped when they no longer revert cleanly (listed in OUT_TREE.skipped),
# then our own patches (*.fwd.patch) applied forward. Mutant V is patches-lib/ALLV (every tier-C unit's change
# taken out, notes/DESIGN.md section 10); mutant W is mutants/W (every conditional note widened).
# Runs inside the pipeline image only.
set -eu
BASE=$1
PATCHES=$2
OUT=$3
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
cd "$OUT"
: > "$OUT.skipped"
for p in $(ls -r "$PATCHES"/*.patch 2>/dev/null | grep -v '[.]fwd[.]patch$'); do
  if patch -R -p1 -s --dry-run -r - < "$p" > /dev/null 2>&1; then
    patch -R -p1 -s --no-backup-if-mismatch -r - < "$p"
  else
    basename "$p" >> "$OUT.skipped"
  fi
done
for p in $(ls "$PATCHES"/*.fwd.patch 2>/dev/null); do
  patch -p1 -s --no-backup-if-mismatch -r - < "$p"
done
echo "$(basename "$OUT"): $(wc -l < "$OUT.skipped") upstream patches skipped"
