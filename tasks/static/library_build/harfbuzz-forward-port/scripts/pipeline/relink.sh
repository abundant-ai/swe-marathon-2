#!/bin/sh
# relink OUT...
#
# Recompile the case driver (and hbprops) against the library and headers each build saved in OUT, after a driver
# change, without rebuilding HarfBuzz. Same compiler commands as hb_build.sh. Runs inside the pipeline image only.
set -eu
T=$(mktemp -d /tmp/relink.XXXXXX)
for OUT in "$@"; do
  [ -f "$OUT/lib/libharfbuzz.a" ] || continue
  cc -O2 -c -I"$OUT/include/harfbuzz" -o "$T/hbdrv.o" /drv/hbdrv.c
  c++ -o "$OUT/hbdrv" "$T/hbdrv.o" "$OUT/lib/libharfbuzz.a" -lm
  if [ -f /drv/hbprops.c ]; then
    cc -O2 -c -I"$OUT/include/harfbuzz" -o "$T/hbprops.o" /drv/hbprops.c
    c++ -o "$OUT/hbprops" "$T/hbprops.o" "$OUT/lib/libharfbuzz.a" -lm
  fi
  echo "relinked $OUT"
done
