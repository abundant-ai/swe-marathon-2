#!/bin/sh
# run_cases BUILD_DIR DRIVER CASES OUT
#
# Run one driver of one build over a case file. A driver the build could not compile (a probe of a function the
# release does not have) answers "!nobuild" for every case, which is that release's output for those cases.
# Runs inside the pipeline image only.
set -u
B=$1
D=$2
C=$3
O=$4
if [ -x "$B/$D" ]; then
  timeout 1800 "$B/$D" < "$C" > "$O"
else
  awk -F'\t' '{print $1 "\t!nobuild"}' "$C" > "$O"
fi
