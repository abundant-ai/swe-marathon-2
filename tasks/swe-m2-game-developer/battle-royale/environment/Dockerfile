FROM 022499036267.dkr.ecr.us-east-1.amazonaws.com/unreal-engine/base/linux@sha256:d654ad8859754d9c51b74ea0ea915316881dff64e617eb47fbaac34539746a8d

USER root
RUN set -eu; \
    if ! id -u agent >/dev/null 2>&1; then \
        useradd --create-home --shell /bin/bash agent; \
    fi; \
    group="$(id -gn agent)"; \
    install -d -m 0755 -o agent -g "$group" /app; \
    install -d -m 0755 /opt/unreal/Epic/UnrealEngine/Intermediate/Build /opt/unreal/Epic/UnrealBuildTool; \
    chown "agent:$group" /opt/unreal/Engine; \
    for directory in Epic Engine/Intermediate Engine/Programs/UnrealBuildTool Engine/Saved Engine/DerivedDataCache; do \
        install -d -m 0755 "/opt/unreal/$directory"; \
        chown -R "agent:$group" "/opt/unreal/$directory"; \
    done; \
    test -x /opt/unreal/Engine/Build/BatchFiles/RunUAT.sh
WORKDIR /app
