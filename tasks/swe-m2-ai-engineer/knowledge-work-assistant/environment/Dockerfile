FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash git ripgrep ca-certificates curl nodejs npm procps jq tar gzip unzip build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock /opt/runtime-project/
RUN UV_PROJECT_ENVIRONMENT=/opt/runtime uv sync --project /opt/runtime-project --frozen --no-dev
COPY resources/ /opt/resources/
RUN /opt/runtime/bin/python /opt/resources/prepare_model.py
COPY data/corpus.jsonl data/manifest.json data/HERB_LICENSE.txt data/NOTICE.txt /data/
RUN useradd --uid 10001 --create-home candidate && mkdir -p /app \
    && chmod -R a+rX /opt/resources /opt/models /data && chown candidate:candidate /app
ENV PATH="/app:/opt/runtime/bin:${PATH}"
ENV PYTHONPATH="/opt/resources"
ENV HF_HUB_OFFLINE="1" TRANSFORMERS_OFFLINE="1" HF_HUB_DISABLE_TELEMETRY="1"
WORKDIR /app
