#!/bin/sh
# make_slow BASE_TREE OUT_TREE [SETUP_SECONDS [BUILD_SECONDS]]
#
# A delivered tree whose build outlasts the verifier's one deadline (1,800 s from its start, tests/verify.py): its
# meson.build sleeps SETUP_SECONDS at `meson setup` (default 600, inside the setup step's own 900 s) and a build
# target sleeps BUILD_SECONDS more at `ninja` (default 1500). BASE_TREE is the reference tree, so that only the
# time decides. Expected: setup exits 0 after about 600 s; the build step is stopped at what is left of the deadline
# (about 1,195 s); no case program is compiled and no batch runs; every case fails; reward.txt 0.0 is written at
# about 1,800-1,850 s, well inside the verifier's 2,400 s.
# Copied without test/ (the product build never reads it). Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
SETUP=${3:-600}
BUILD=${4:-1500}
for n in "$SETUP" "$BUILD"; do
  case $n in
    '' | *[!0-9]*) echo "make_slow: seconds must be whole numbers, not '$n'" >&2; exit 2 ;;
  esac
done
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
cat >> "$OUT/meson.build" <<MESON

# Slow-build probe (scripts/pipeline/make_slow.sh): $SETUP s at setup, $BUILD s more at build.
run_command('sleep', '$SETUP', check: false)
custom_target('slow-build',
  output: 'slow-build.stamp',
  command: ['sh', '-c', 'sleep $BUILD && : > "\$1"', 'sh', '@OUTPUT@'],
  build_by_default: true,
)
MESON
echo "slow tree: setup sleeps ${SETUP}s, build ${BUILD}s"
