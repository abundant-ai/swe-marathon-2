#!/bin/sh
# make_oracle OUT_PATCH
#
# The reference change: from our shipped tree (14.3.0, pruned as environment/prune_tree.sh prunes it) to 15.2.0's
# library: 15.2.0's src/ and top-level meson.build (with the same speed-measurement wiring removed). Everything else in
# the tree stays as shipped. Runs inside the pipeline image only.
set -eu
OUT=$1
W=$(mktemp -d /tmp/oracle.XXXXXX)
mkdir -p "$W/a" "$W/b" "$W/t"
tar -xJf /dl/harfbuzz/harfbuzz-14.3.0.tar.xz -C "$W/a" --strip-components=1
sh /env/prune_tree.sh "$W/a" > /dev/null
cp -a "$W/a/." "$W/b/"
rm -r "$W/b/src"
tar -xJf /dl/harfbuzz/harfbuzz-15.2.0.tar.xz -C "$W/t" --strip-components=1
cp -a "$W/t/src" "$W/b/src"
cp "$W/t/meson.build" "$W/b/meson.build"
sed -i "/^if not get_option('benchmark').disabled()$/,/^endif$/d" "$W/b/meson.build"
sed -i "/'Benchmark': get_option('benchmark').enabled(),/d" "$W/b/meson.build"
sed -i "s/exclude_suites: \['google-benchmark'\],//" "$W/b/meson.build"
if grep -n "benchmark" "$W/b/meson.build"; then
  echo "make_oracle: benchmark wiring left in meson.build" >&2
  exit 1
fi
cd "$W"
diff -ruN a b > "$OUT" || [ $? -eq 1 ]
echo "oracle patch: $(grep -c '^diff ' "$OUT") files, $(wc -c < "$OUT") bytes"
