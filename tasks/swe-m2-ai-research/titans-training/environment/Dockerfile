# CUDA development tools support Titans' compiled memory and attention kernels.
FROM nvidia/cuda:12.9.1-devel-ubuntu24.04
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-dev python3-venv bash git ripgrep ca-certificates curl \
    nodejs npm procps jq tar gzip unzip build-essential libnuma1 \
    && rm -rf /var/lib/apt/lists/*

# Fetch public source at build time; starting the agent needs no GitHub credentials.
ARG TITANS_REV=2260f95668a4c3d40fd6050292a1d2f74d8f5a5c
ENV GIT_TERMINAL_PROMPT=0
RUN git init /app/titans \
    && git -C /app/titans remote add origin https://github.com/abundant-ai/titans.git \
    && git -C /app/titans fetch --depth=1 origin "${TITANS_REV}" \
    && git -C /app/titans checkout -b codex/titans-training FETCH_HEAD \
    && test "$(git -C /app/titans rev-parse HEAD)" = "${TITANS_REV}"

# Install the editable checkout and its locked GPU and development dependencies.
ENV UV_PROJECT_ENVIRONMENT=/opt/titans-venv
ENV PATH="/opt/titans-venv/bin:${PATH}"
RUN uv sync --project /app/titans --frozen --extra gpu --no-cache \
    && python -c 'from pathlib import Path; import titans; assert Path(titans.__file__).resolve().is_relative_to(Path("/app/titans"))'

RUN useradd --uid 10001 --create-home candidate \
    && chown -R candidate:candidate /app /opt/titans-venv
USER candidate
WORKDIR /app/titans
CMD ["bash"]
