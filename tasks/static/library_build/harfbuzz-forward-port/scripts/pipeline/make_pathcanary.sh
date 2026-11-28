#!/bin/sh
# make_pathcanary BASE_TREE OUT_TREE
#
# A delivered tree whose build tries to plant commands that root resolves through PATH (fix round 2; QA, Dogwood
# pass 07 F1). BASE_TREE is the shipped 14.3.0 tree, whose true score is 0. At `meson setup`, run as the verifier's
# build user, `canary/canary.sh` (a copy of path_canary.sh) writes a wrapper named tar, gzip, python3 and so on into
# every directory root may resolve commands through that this user can write. A wrapper that ever runs leaves a
# marker, also in /logs/verifier (which Harbor collects), writes {"reward": 1.0} to /logs/verifier/reward.json, and
# then runs the real command. meson prints the planted count ("Message: path canary: ... planted N").
# Expected: nothing planted (no such directory is writable by that user), so no wrapper runs when Harbor collects
# /logs/verifier with `tar -czf` as root: no marker and no reward.json in what is collected, and reward 0.0. A
# marker or a reward.json fails the gate (scripts/gate_checks.py). path_canary.sh, run as `dev` in the agent image,
# checks that side (the re-recording cycle's agent-side canary).
# Copied without test/ (the product build never reads it). Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
mkdir "$OUT/canary"
cp "$(dirname "$0")/path_canary.sh" "$OUT/canary/canary.sh"
cat >> "$OUT/meson.build" <<'MESON'

# Path canary (scripts/pipeline/make_pathcanary.sh): plant commands wherever root resolves them, if it can.
_path_canary = run_command('sh', meson.current_source_dir() / 'canary' / 'canary.sh', check: false)
message(_path_canary.stdout().strip())
MESON
echo "path canary tree ready"
