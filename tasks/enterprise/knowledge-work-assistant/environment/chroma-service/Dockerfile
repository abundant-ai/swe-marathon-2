# A CPU-only service image; neither the GPU runtime nor candidate files enter it.
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
WORKDIR /opt/chroma-service
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache
COPY orange_chroma/ ./orange_chroma/
RUN useradd --uid 10002 --no-create-home chroma && mkdir -p /var/lib/orange-chroma \
    && chown chroma:chroma /var/lib/orange-chroma
USER 10002:10002
ENV ANONYMIZED_TELEMETRY=False
# Only the capped ASGI application listens; no direct Chroma port is exposed.
CMD [".venv/bin/uvicorn", "orange_chroma.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "32", "--timeout-keep-alive", "5"]
