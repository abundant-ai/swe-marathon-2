#!/usr/bin/env bash
set -euo pipefail

if ! id -u ue >/dev/null 2>&1; then
    /usr/sbin/useradd --create-home --shell /bin/bash ue
fi

engine=/opt/unreal
owner="ue:$(id -gn ue)"
install -d -m 0755 "$engine/Epic/UnrealEngine/Intermediate/Build" "$engine/Epic/UnrealBuildTool"
chown "$owner" "$engine/Engine"
for cache in Epic Engine/Intermediate Engine/Programs/UnrealBuildTool Engine/Saved Engine/DerivedDataCache; do
    install -d -m 0755 "$engine/$cache"
    chown -R "$owner" "$engine/$cache"
done

if /usr/sbin/runuser -u ue -- test -w /logs/verifier; then
    printf '%s\n' 'The build user has write access to the verifier output.' >&2
    exit 1
fi

if ! output=$(/usr/sbin/runuser -u ue -- "$engine/Engine/Build/BatchFiles/RunUAT.sh" -List); then
    printf '%s\n' "$output"
    exit 1
fi
printf '%s\n' "$output"
grep -Eq '^[[:space:]]*BuildCookRun[[:space:]]*$' <<<"$output"
