#!/bin/sh
# make_oracle OUT_PATCH
#
# The reference change: from our shipped tree (14.3.0, pruned as environment/prune_tree.sh prunes it) to 15.2.0's
# library: 15.2.0's src/ and top-level meson.build (with the same speed-measurement wiring removed). Everything else in
# the tree stays as shipped. Like any change of ours, it keeps the tree's own version (meson.build's project version,
# from which the build writes src/hb-version.h, stays 14.3.0) and leaves out the unit-test programs 15.x adds, which
# only a -Dtests=enabled build compiles and no note needs. tests/verify.py treats a tree with either as a copied 15.x
# release. Runs inside the pipeline image only.
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

# The tree's own version: the project() call's version line, and src/hb-version.h as shipped.
ours=$(sed -n "3s/^  version: '\([0-9][0-9.]*\)',\$/\1/p" "$W/a/meson.build")
theirs=$(sed -n "3s/^  version: '\([0-9][0-9.]*\)',\$/\1/p" "$W/b/meson.build")
if [ -z "$ours" ] || [ -z "$theirs" ]; then
  echo "make_oracle: no project version on line 3 of meson.build" >&2
  exit 1
fi
sed -i "3s/^  version: '$theirs',\$/  version: '$ours',/" "$W/b/meson.build"
cp "$W/a/src/hb-version.h" "$W/b/src/hb-version.h"
if ! grep -q "^  version: '$ours',\$" "$W/b/meson.build" \
  || ! grep -q "^#define HB_VERSION_STRING \"$ours\"\$" "$W/b/src/hb-version.h"; then
  echo "make_oracle: the version was not kept at $ours" >&2
  exit 1
fi

# The unit-test programs 15.x adds. Only the `if get_option('tests').enabled()` blocks of src/meson.build name
# them; if any other part of the build did, leaving them out would break it, so that stops here.
outside="$W/outside-tests.txt"
awk "/^if get_option\('tests'\)\.enabled\(\)\$/ {skip = 1; next} skip && /^endif\$/ {skip = 0; next} !skip" \
  "$W/b/src/meson.build" > "$outside"
find "$W/b" -name meson.build ! -path "$W/b/src/meson.build" -exec cat {} + >> "$outside"
left_out=0
for f in $(cd "$W/t/src" && ls test-*.cc); do
  [ -e "$W/a/src/$f" ] && continue
  if grep -q -F "'$f'" "$outside"; then
    echo "make_oracle: src/$f is built outside the test programs" >&2
    exit 1
  fi
  rm "$W/b/src/$f"
  left_out=$((left_out + 1))
done
rm "$outside"

cd "$W"
diff -ruN a b > "$OUT" || [ $? -eq 1 ]
echo "oracle patch: $(grep -c '^diff ' "$OUT") files, $(wc -c < "$OUT") bytes; version $ours kept, $left_out 15.x test programs left out"
