#!/bin/sh
# hb_build SRC OUT [PATCHES] [JOBS] [RAGEL]
#
# Build one HarfBuzz tree with the product's build command and link the case driver against it.
#   SRC      a release tarball (.tar.xz) or a directory holding a tree (copied, never modified)
#   OUT      output directory: lib/libharfbuzz.a, include/harfbuzz/, hbdrv, build.json, logs
#   PATCHES  a directory of *.patch files reverse-applied newest first (the name order), or "" for none
#   JOBS     ninja parallelism (default 4)
#   RAGEL    "on" (default) or "off" (hide ragel so meson keeps the shipped machines)
# The driver source is read from /drv/hbdrv.c. Runs inside the pipeline image only.
set -eu
SRC=$1
OUT=$2
PATCHES=${3:-}
JOBS=${4:-4}
RAGEL=${5:-on}

W=$(mktemp -d /tmp/hbtree.XXXXXX)
if [ -d "$SRC" ]; then
  cp -a "$SRC/." "$W/"
else
  tar -xJf "$SRC" -C "$W" --strip-components=1
fi
mkdir -p "$OUT"
rm -f "$OUT/skipped.txt"
cd "$W"

applied=0
if [ -n "$PATCHES" ]; then
  # Upstream commits (*.patch) are reverted newest first; mutations of our own (*.fwd.patch) are then applied.
  # HB_TOLERANT=1 (the all-units revert): a patch that does not revert cleanly is skipped and listed.
  for p in $(ls -r "$PATCHES"/*.patch 2>/dev/null | grep -v '[.]fwd[.]patch$'); do
    if [ "${HB_TOLERANT:-}" = 1 ] && ! patch -R -p1 -s --dry-run -r - < "$p" > /dev/null 2>&1; then
      basename "$p" >> "$OUT/skipped.txt"
      continue
    fi
    patch -R -p1 -s --no-backup-if-mismatch -r - < "$p" > "$OUT/patch.log" 2>&1 || {
      echo "{\"status\": \"revert-failed\", \"patch\": \"$(basename "$p")\"}" > "$OUT/build.json"
      exit 3
    }
    applied=$((applied + 1))
  done
  for p in $(ls "$PATCHES"/*.fwd.patch 2>/dev/null); do
    patch -p1 -s --no-backup-if-mismatch -r - < "$p" > "$OUT/patch.log" 2>&1 || {
      echo "{\"status\": \"apply-failed\", \"patch\": \"$(basename "$p")\"}" > "$OUT/build.json"
      exit 3
    }
    applied=$((applied + 1))
  done
fi

if [ "$RAGEL" = off ] && [ -x /usr/bin/ragel ]; then
  mv /usr/bin/ragel /usr/bin/ragel.off
fi

t0=$(date +%s)
meson setup build --buildtype=release --wrap-mode=nodownload -Ddefault_library=static \
  -Dglib=disabled -Dgobject=disabled -Dcairo=disabled -Dchafa=disabled -Dicu=disabled \
  -Dfreetype=disabled -Dpng=disabled -Dzlib=disabled -Dgraphite2=disabled \
  -Draster=disabled -Dvector=disabled -Dgpu=disabled -Dsubset=disabled \
  -Dtests=disabled -Dintrospection=disabled -Ddocs=disabled -Dutilities=disabled ${MESON_EXTRA:-} \
  > "$OUT/setup.log" 2>&1 || { echo '{"status": "setup-failed"}' > "$OUT/build.json"; exit 4; }
t1=$(date +%s)
ninja -C build -j "$JOBS" > "$OUT/ninja.log" 2>&1 || { echo '{"status": "build-failed"}' > "$OUT/build.json"; exit 5; }
t2=$(date +%s)

mkdir -p "$OUT/lib" "$OUT/include/harfbuzz"
cp build/src/libharfbuzz.a "$OUT/lib/"
cp src/hb*.h "$OUT/include/harfbuzz/"
cp build/src/hb*.h "$OUT/include/harfbuzz/" 2>/dev/null || true
cc -O2 -c -I"$OUT/include/harfbuzz" -o "$W/hbdrv.o" /drv/hbdrv.c
c++ -o "$OUT/hbdrv" "$W/hbdrv.o" "$OUT/lib/libharfbuzz.a" -lm
if [ -f /drv/hbprops.c ]; then
  cc -O2 -c -I"$OUT/include/harfbuzz" -o "$W/hbprops.o" /drv/hbprops.c
  c++ -o "$OUT/hbprops" "$W/hbprops.o" "$OUT/lib/libharfbuzz.a" -lm
fi
# The API drivers. A probe of a function this tree does not have fails to compile; it is then simply absent.
for d in hbapi hbmeta hbapi33 hbapi48 hbapi49 hbapi51; do
  [ -f "/drv/$d.c" ] || continue
  rm -f "$OUT/$d"
  { cc -O2 -Werror=implicit-function-declaration -c -I"$OUT/include/harfbuzz" -o "$W/$d.o" "/drv/$d.c" \
    && c++ -o "$OUT/$d" "$W/$d.o" "$OUT/lib/libharfbuzz.a" -lm; } > "$OUT/$d.compile.log" 2>&1 || rm -f "$OUT/$d"
done
regen=$(grep -c "machine.hh with a custom command" "$OUT/ninja.log" || true)
peak=$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo 0)
printf '{"status": "ok", "setup_s": %s, "build_s": %s, "jobs": %s, "ragel": "%s", "ragel_steps": %s, "reverted_patches": %s, "mem_peak_bytes": %s}\n' \
  "$((t1 - t0))" "$((t2 - t1))" "$JOBS" "$RAGEL" "$regen" "$applied" "$peak" > "$OUT/build.json"
# The tree stays in the container's /tmp, which goes away with the container (run with --rm).
