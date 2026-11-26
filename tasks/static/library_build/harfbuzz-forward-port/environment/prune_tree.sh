#!/bin/sh
# Turn the upstream 14.3.0 release tree into our shipped tree: drop the speed-measurement programs, CI files and
# upstream's contribution policy, and the build wiring that pointed at them. The library itself is untouched.
# Usage: prune_tree.sh TREE
set -eu
cd "$1"
rm -r perf .github .ci
rm .codecov.yml CODE_OF_AI_CONDUCT.md subprojects/google-benchmark.wrap test/vector/README.md
sed -i '/^- `perf\/`: benchmarks\.$/d' AGENTS.md
sed -i "/^option('benchmark', type: 'feature', value: 'disabled',$/,+1d" meson_options.txt
sed -i "/^if not get_option('benchmark').disabled()$/,/^endif$/d" meson.build
sed -i "/'Benchmark': get_option('benchmark').enabled(),/d" meson.build
sed -i "s/exclude_suites: \['google-benchmark'\],//" meson.build
sed -i '/^\/benchmark-\*$/d' subprojects/.gitignore
if grep -r -I -i -l "benchmark" --exclude=NEWS . ; then
  echo "prune_tree: benchmark still mentioned outside NEWS" >&2
fi
