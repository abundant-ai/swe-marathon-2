FROM 022499036267.dkr.ecr.us-east-1.amazonaws.com/unreal-engine/base/linux@sha256:d654ad8859754d9c51b74ea0ea915316881dff64e617eb47fbaac34539746a8d

USER root
RUN set -eu; \
    if ! command -v python3 >/dev/null 2>&1; then \
        apt-get update; \
        apt-get install -y --no-install-recommends python3; \
        rm -rf /var/lib/apt/lists/*; \
    fi; \
    if ! id -u ue >/dev/null 2>&1; then \
        useradd --create-home --shell /bin/bash ue; \
    fi; \
    owner="ue:$(id -gn ue)"; \
    install -d -m 0755 /opt/unreal/Epic/UnrealEngine/Intermediate/Build /opt/unreal/Epic/UnrealBuildTool; \
    chown "$owner" /opt/unreal/Engine; \
    for directory in Epic Engine/Intermediate Engine/Programs/UnrealBuildTool Engine/Saved Engine/DerivedDataCache; do \
        install -d -m 0755 "/opt/unreal/$directory"; \
        chown -R "$owner" "/opt/unreal/$directory"; \
    done

COPY build_smoke.py test.sh two_client_smoke.py /tests/
RUN chmod 0755 /tests/test.sh
USER ue
