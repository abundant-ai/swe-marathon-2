#!/bin/sh
# Turn the upstream 14.3.0 release tree into our shipped tree: drop the speed-measurement programs, CI files,
# upstream's contribution policies, and the build wiring that pointed at them. The library itself is untouched.
# Usage: prune_tree.sh TREE
set -eu
cd "$1"
rm -r perf .github .ci
rm .codecov.yml CODE_OF_AI_CONDUCT.md CLAUDE.md AGENTS.md subprojects/google-benchmark.wrap test/vector/README.md
# The Windows cross-build notes and the profiling pointer refer to the removed CI and speed-measurement files.
rm README.mingw.md
sed -i '/^## Profiling$/,$d' TESTING.md
# The threaded shaping test reads its fonts and texts from the removed speed-measurement folder by default.
rm test/threads/hb-shape-threads.cc
sed -i "/^test('shape_threads', executable('hb-shape-threads', 'hb-shape-threads.cc',$/,/^)$/d" test/threads/meson.build
if grep -q "shape_threads\|perf/" test/threads/meson.build; then
  echo "prune_tree: the threaded shaping test is still wired in" >&2
  exit 1
fi
sed -i "/^option('benchmark', type: 'feature', value: 'disabled',$/,+1d" meson_options.txt
sed -i "/^if not get_option('benchmark').disabled()$/,/^endif$/d" meson.build
sed -i "/'Benchmark': get_option('benchmark').enabled(),/d" meson.build
sed -i "s/exclude_suites: \['google-benchmark'\],//" meson.build
sed -i '/^\/benchmark-\*$/d' subprojects/.gitignore
if grep -r -I -i -l "benchmark" --exclude=NEWS . ; then
  echo "prune_tree: benchmark still mentioned outside NEWS" >&2
fi
