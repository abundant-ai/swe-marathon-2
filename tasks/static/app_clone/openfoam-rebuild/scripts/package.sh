#!/bin/bash
# Writes the runtime bundle that Oddish runs: the task without its development files, with
# common/reference/ in the agent image's build context, and for the reference solution the
# build script and OpenFOAM's source (the pinned tag without tutorials and doc) with
# hardening.patch applied, with the key that lets the verifier's copy check pass it.
# usage: scripts/package.sh <out dir>
set -euo pipefail
task=$(cd "$(dirname "$0")/.." && pwd)
out=$1
tag=OpenFOAM-v2606
commit=481094fdf34f11ed6d0d603ee59a858a0124236d
[ ! -e "$out" ] || { echo "$out exists" >&2; exit 1; }

mkdir -p "$out"
cp -R "$task/task.toml" "$task/instruction.md" "$task/environment" "$task/tests" "$task/solution" "$out/"
find "$out" -name __pycache__ -prune -exec rm -rf {} +
mkdir -p "$out/environment/reference" "$out/solution/reference"
cp "$task/common/reference/build.sh" "$task/common/reference/hardening.patch" "$out/environment/reference/"
cp "$task/common/reference/build.sh" "$out/solution/reference/"
# The reference solution's key (see tests/verifier/source.py): new for each bundle, its digest
# beside the verifier
python3 -c 'import secrets; print(secrets.token_hex(32))' > "$out/solution/reference.key"
shasum -a 256 "$out/solution/reference.key" | cut -d" " -f1 > "$out/tests/verifier/reference.sha256"

# git archive, not a checkout: a case-insensitive file system loses some of OpenFOAM's files
src="$task/experiment/upstream/openfoam.git"
[ -d "$src" ] || git clone --quiet --bare --depth 1 --branch "$tag" \
    https://gitlab.com/openfoam/core/openfoam.git "$src"
[ "$(git -C "$src" rev-parse "$tag^{commit}")" = "$commit" ] || { echo "$tag is not $commit" >&2; exit 1; }
work=$(mktemp -d)
git -C "$src" archive --format=tar --prefix=openfoam/ "$commit" -- . ':!tutorials' ':!doc' > "$work/src.tar"
python3 "$task/scripts/harden_archive.py" "$work/src.tar" "$task/common/reference/hardening.patch"
xz -T0 -9 < "$work/src.tar" > "$out/solution/openfoam-v2606-src.tar.xz"
rm -rf "$work"
echo "bundle: $out ($(du -sh "$out" | cut -f1))"
