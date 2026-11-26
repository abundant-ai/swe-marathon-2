FROM python:3.13-slim-bookworm@sha256:f0fa218d5b06f9b9235024fa061cde2cb141f726de52134471053d2d9b5324a3

COPY --from=ghcr.io/astral-sh/uv:0.9.7@sha256:ba4857bf2a068e9bc0e64eed8563b065908a4cd6bfb66b531a9c424c8e25e142 /uv /uvx /usr/local/bin/

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git procps \
    && rm -rf /var/lib/apt/lists/*

ENV KEV_COMMIT=556167b5b151152cb4101629e25d883e9ead5094 \
    QWEN_BASE_REVISION=dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68 \
    KEV_08B_REVISION=bf75a6a8848ea6960ff2ed108d9ed44c2941174f \
    HF_HOME=/opt/hf \
    UV_PROJECT_ENVIRONMENT=/opt/kev/.venv \
    UV_PYTHON=/usr/local/bin/python3.13 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

# provenance-okay
RUN git clone --quiet --filter=blob:none --no-checkout https://github.com/jaredpalmer/kev.git /tmp/kev-src \
    && cd /tmp/kev-src \
    && paths="kev pyproject.toml uv.lock LICENSE README.md \
              evals/v4/transfer-v4/manifest.json evals/v4/transfer-v4/development.jsonl evals/v4/transfer-v4/test.jsonl \
              evals/v7/decision-v7/manifest.json evals/v7/decision-v7/test.jsonl" \
    && git checkout --quiet "$KEV_COMMIT" -- $paths \
    && for p in $paths; do mkdir -p "/opt/kev/$(dirname "$p")" && cp -R "$p" "/opt/kev/$p"; done \
    && cd / && rm -rf /tmp/kev-src

RUN cd /opt/kev && uv sync --frozen --no-dev \
    && uv pip install --python /opt/kev/.venv/bin/python --no-cache flash-linear-attention==0.5.2 triton==3.7.1 \
    && uv pip install --python /opt/kev/.venv/bin/python --no-cache --no-deps \
        "https://github.com/Dao-AILab/causal-conv1d/releases/download/v1.7.0/causal_conv1d-1.7.0%2Bcu12torch2.8cxx11abiTRUE-cp313-cp313-linux_x86_64.whl" \
    && /opt/kev/.venv/bin/python -c "from importlib.metadata import version as v; got = {p: v(p) for p in ('torch', 'triton', 'flash-linear-attention', 'causal-conv1d')}; print(got); \
assert got['torch'].startswith('2.8.0') and got['triton'] == '3.7.1' and got['flash-linear-attention'] == '0.5.2'" \
    && rm -rf /root/.cache/uv

RUN /opt/kev/.venv/bin/python -c "import os; from huggingface_hub import snapshot_download as get; \
get('Qwen/Qwen3.5-0.8B-Base', revision=os.environ['QWEN_BASE_REVISION']); \
get('jaredpalmer/kev-0.8b', revision=os.environ['KEV_08B_REVISION'], local_dir='/opt/models/kev-0.8b', \
    allow_patterns=['adapter_config.json', 'adapter_model.safetensors', 'head.pt'])" \
    && rm -rf /opt/models/kev-0.8b/.cache && chmod -R a+rX,a-w /opt/models \
    && cd /opt/kev && /opt/kev/.venv/bin/python -c "from kev.suite import load_split; \
[load_split(p, s, allow_test=True) for p, s in [('evals/v4/transfer-v4', 'test'), ('evals/v4/transfer-v4', 'development'), ('evals/v7/decision-v7', 'test')]]" \
    && chmod -R a+rX,a-w /opt/hf /opt/kev

RUN useradd --uid 10021 --user-group --no-create-home --shell /usr/sbin/nologin kevgrader

COPY test.sh verify.py grader.py /tests/
RUN chown -R root:root /tests && chmod 0755 /tests && chmod 0700 /tests/test.sh /tests/verify.py && chmod 0644 /tests/grader.py
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
WORKDIR /tests
