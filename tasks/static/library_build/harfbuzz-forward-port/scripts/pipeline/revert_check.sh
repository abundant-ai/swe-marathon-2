#!/bin/sh
# revert_check PATCH_ROOT OUT_TSV
# S6: for every unit in /pipe/units.tsv, reverse-apply its patches (newest first) to a fresh copy of its
# release's build inputs (src/, meson.build, meson_options.txt) and record whether they apply cleanly.
# Runs inside the pipeline image only; trees live in the container's /tmp.
set -u
ROOT=$1
OUT=$2
printf 'unit\trelease\tpatches\tstatus\tdetail\n' > "$OUT"
for rel in 15.0.0 15.1.0 15.2.0; do
  mkdir -p "/tmp/base-$rel"
  tar -xJf "/dl/harfbuzz/harfbuzz-$rel.tar.xz" -C "/tmp/base-$rel" --strip-components=1 \
    "harfbuzz-$rel/src" "harfbuzz-$rel/meson.build" "harfbuzz-$rel/meson_options.txt"
done
tail -n +2 /pipe/units.tsv | while IFS="$(printf '\t')" read -r unit window rel family commits note; do
  dir="$ROOT/$unit"
  n=$(ls "$dir"/*.patch 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n" = 0 ]; then
    printf '%s\t%s\t0\tno-patch\t\n' "$unit" "$rel" >> "$OUT"
    continue
  fi
  work="/tmp/u-$unit"
  mkdir -p "$work"
  cp -a "/tmp/base-$rel/." "$work/"
  status=clean
  detail=
  for p in $(ls -r "$dir"/*.patch); do
    if ! (cd "$work" && patch -R -p1 -s --no-backup-if-mismatch -r - < "$p" > /tmp/patch.out 2>&1); then
      status=conflict
      detail="$(basename "$p"): $(head -c 160 /tmp/patch.out | tr '\n\t' '  ')"
      break
    fi
  done
  printf '%s\t%s\t%s\t%s\t%s\n' "$unit" "$rel" "$n" "$status" "$detail" >> "$OUT"
done
