FROM ubuntu:24.04
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python-is-python3 ca-certificates procps util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY runtime/pyproject.toml /opt/runtime-project/pyproject.toml
RUN uv pip install --system --break-system-packages --no-cache -r /opt/runtime-project/pyproject.toml
COPY test.sh verify.py /tests/
COPY verifier/ /tests/verifier/
COPY private/ /tests/private/
RUN mkdir -p /app /logs/verifier /work /opt/grader/skeleton \
    && tar xzf /tests/private/skeleton.tar.gz -C /opt/grader/skeleton \
    && rm /tests/private/skeleton.tar.gz \
    && chown -R root:root /tests /opt/grader && chmod -R go-rwx /tests /opt/grader \
    && chmod 0700 /tests/test.sh
WORKDIR /
