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
  for d in hbapi hbmeta hbapi48 hbapi49 hbapi51; do
    [ -f "/drv/$d.c" ] || continue
    rm -f "$OUT/$d"
    { cc -O2 -Werror=implicit-function-declaration -c -I"$OUT/include/harfbuzz" -o "$T/$d.o" "/drv/$d.c" \
      && c++ -o "$OUT/$d" "$T/$d.o" "$OUT/lib/libharfbuzz.a" -lm; } > "$OUT/$d.compile.log" 2>&1 || rm -f "$OUT/$d"
  done
  echo "relinked $OUT"
done
