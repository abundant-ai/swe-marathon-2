#!/usr/bin/env bash
set -euo pipefail

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project="$solution_dir/project"
submission="/workspace/submission"

test -s "$project/BattleRoyale.uproject"
test -d "$project/Source/BattleRoyale"

if [[ ! -e "$submission" && ! -L "$submission" ]]; then
    # Publish the complete project at once so an interrupted copy can be retried.
    staging="$(mktemp -d /workspace/.basin-submission.XXXXXXXX)"
    trap 'rm -rf -- "$staging"' EXIT
    cp -a -- "$project/." "$staging/"
    chmod 0755 -- "$staging"
    if ! publish_error="$(mv -nT -- "$staging" "$submission" 2>&1)" &&
        [[ ! -e "$submission" && ! -L "$submission" ]]; then
        printf '%s\n' "$publish_error" >&2
        exit 1
    fi
fi

if [[ -L "$submission" || ! -d "$submission" ]] ||
    ! diff -qr --no-dereference -- "$project" "$submission" >/dev/null; then
    printf 'Existing submission differs from the Oracle project at %s.\n' "$submission" >&2
    exit 1
fi
