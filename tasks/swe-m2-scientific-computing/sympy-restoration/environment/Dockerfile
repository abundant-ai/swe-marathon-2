# Agent image. The build context is environment/; packaging stages data/ and
# restore/lib/restorelib.py into it.
FROM ubuntu:24.04
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python-is-python3 ca-certificates curl git ripgrep xz-utils less procps \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml /opt/runtime-project/pyproject.toml
RUN uv pip install --system --break-system-packages --no-cache -r /opt/runtime-project/pyproject.toml
WORKDIR /app
COPY data/workspace.tar.gz /tmp/workspace.tar.gz
COPY restore /opt/restore
COPY data/units.json /opt/restore/units.json
RUN tar xzf /tmp/workspace.tar.gz -C /app && rm /tmp/workspace.tar.gz \
    && mkdir -p /opt/restore/skeleton /opt/restore/var/cand \
    && cp -a /app/sympy /app/pytest.ini /opt/restore/skeleton/ \
    && cp -a /opt/restore/skeleton/. /opt/restore/var/cand/ \
    && chmod -R a-w /opt/restore/skeleton /opt/restore/lib /opt/restore/units.json \
    && chmod -R a+rwX /opt/restore/var \
    && chmod 0755 /opt/restore/restore.py \
    && ln -s /opt/restore/restore.py /usr/local/bin/restore
COPY timer.sh /app/timer.sh
COPY ATTRIBUTION.txt LICENSE /app/
RUN chmod +x /app/timer.sh
