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
cd "$W"

applied=0
if [ -n "$PATCHES" ]; then
  for p in $(ls -r "$PATCHES"/*.patch); do
    patch -R -p1 -s --no-backup-if-mismatch -r - < "$p" > "$OUT/patch.log" 2>&1 || {
      echo "{\"status\": \"revert-failed\", \"patch\": \"$(basename "$p")\"}" > "$OUT/build.json"
      exit 3
    }
    applied=$((applied + 1))
  done
fi

if [ "$RAGEL" = off ] && [ -x /usr/bin/ragel ]; then
  mv /usr/bin/ragel /usr/bin/ragel.off
fi

t0=$(date +%s)
meson setup build --buildtype=release -Ddefault_library=static \
  -Dglib=disabled -Dgobject=disabled -Dcairo=disabled -Dchafa=disabled -Dicu=disabled \
  -Dfreetype=disabled -Dpng=disabled -Dzlib=disabled -Dgraphite2=disabled \
  -Draster=disabled -Dvector=disabled -Dgpu=disabled -Dsubset=disabled \
  -Dtests=disabled -Dintrospection=disabled -Ddocs=disabled -Dutilities=disabled \
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
regen=$(grep -c "gen-ragel-artifacts" "$OUT/ninja.log" || true)
peak=$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo 0)
printf '{"status": "ok", "setup_s": %s, "build_s": %s, "jobs": %s, "ragel": "%s", "ragel_steps": %s, "reverted_patches": %s, "mem_peak_bytes": %s}\n' \
  "$((t1 - t0))" "$((t2 - t1))" "$JOBS" "$RAGEL" "$regen" "$applied" "$peak" > "$OUT/build.json"
# The tree stays in the container's /tmp, which goes away with the container (run with --rm).
