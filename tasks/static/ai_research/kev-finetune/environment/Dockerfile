FROM python:3.13-slim-bookworm@sha256:f0fa218d5b06f9b9235024fa061cde2cb141f726de52134471053d2d9b5324a3

COPY --from=ghcr.io/astral-sh/uv:0.9.7@sha256:ba4857bf2a068e9bc0e64eed8563b065908a4cd6bfb66b531a9c424c8e25e142 /uv /uvx /usr/local/bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git jq less procps vim-tiny \
    && rm -rf /var/lib/apt/lists/*

ENV KEV_COMMIT=556167b5b151152cb4101629e25d883e9ead5094 \
    QWEN_BASE_REVISION=dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68 \
    KEV_08B_REVISION=bf75a6a8848ea6960ff2ed108d9ed44c2941174f \
    HF_HOME=/opt/hf \
    UV_PROJECT_ENVIRONMENT=/opt/kev/.venv \
    UV_PYTHON=/usr/local/bin/python3.13 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

COPY kev-files.txt /tmp/kev-files.txt
# provenance-okay
RUN git clone --quiet --filter=blob:none --no-checkout https://github.com/jaredpalmer/kev.git /tmp/kev-src \
    && cd /tmp/kev-src && git checkout --quiet "$KEV_COMMIT" -- $(grep -v '^#' /tmp/kev-files.txt) \
    && mkdir -p /opt/kev \
    && for p in $(grep -v '^#' /tmp/kev-files.txt); do mkdir -p "/opt/kev/$(dirname "$p")" && cp -R "$p" "/opt/kev/$p"; done \
    && rm -f /opt/kev/kev/study_v3.py /opt/kev/kev/transfer_v9.py \
    && cd / && rm -rf /tmp/kev-src /tmp/kev-files.txt

RUN cd /opt/kev && uv sync --frozen --no-dev \
    && uv pip install --python /opt/kev/.venv/bin/python --no-cache flash-linear-attention==0.5.2 triton==3.7.1 \
    && uv pip install --python /opt/kev/.venv/bin/python --no-cache --no-deps \
        "https://github.com/Dao-AILab/causal-conv1d/releases/download/v1.7.0/causal_conv1d-1.7.0%2Bcu12torch2.8cxx11abiTRUE-cp313-cp313-linux_x86_64.whl" \
    && /opt/kev/.venv/bin/python -c "from importlib.metadata import version as v; got = {p: v(p) for p in ('torch', 'triton', 'flash-linear-attention', 'causal-conv1d')}; print(got); \
assert got['torch'].startswith('2.8.0') and got['triton'] == '3.7.1' and got['flash-linear-attention'] == '0.5.2'" \
    && uv pip install --python /opt/kev/.venv/bin/python --no-cache anthropic==2.14.0 \
    && rm -rf /root/.cache/uv

RUN /opt/kev/.venv/bin/python -c "import os; from huggingface_hub import snapshot_download as get; \
get('Qwen/Qwen3.5-0.8B-Base', revision=os.environ['QWEN_BASE_REVISION']); \
get('jaredpalmer/kev-0.8b', revision=os.environ['KEV_08B_REVISION'], local_dir='/opt/models/kev-0.8b', \
    allow_patterns=['adapter_config.json', 'adapter_model.safetensors', 'head.pt', 'training_config.json', 'provenance.json', 'README.md'])" \
    && rm -rf /opt/models/kev-0.8b/.cache \
    && chmod -R a+rX,a-w /opt/hf /opt/models

COPY resources/ /opt/task/
RUN chmod -R a+rX,a-w /opt/task

RUN useradd --uid 10001 --user-group --create-home --shell /bin/bash candidate \
    && chown -R candidate:candidate /opt/kev \
    && mkdir -p /app /scratch && chown candidate:candidate /app /scratch

ENV PATH="/opt/kev/.venv/bin:${PATH}" \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
WORKDIR /app
