# Agent image.
FROM ubuntu:24.04
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python-is-python3 ca-certificates curl git ripgrep xz-utils less procps util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml /opt/runtime-project/pyproject.toml
RUN uv pip install --system --break-system-packages --no-cache -r /opt/runtime-project/pyproject.toml
RUN useradd --uid 10001 --create-home dev
WORKDIR /app
COPY data/workspace.tar.gz /tmp/workspace.tar.gz
COPY restore /opt/restore
COPY data/units.json /opt/restore/units.json
COPY fsmaint-reserve fsmaint-netcheck fsmaint-sweep /usr/local/lib/fsmaint/
COPY data/fsmaint.key /usr/local/lib/fsmaint/key
RUN tar xzf /tmp/workspace.tar.gz -C /app && rm /tmp/workspace.tar.gz \
    && mkdir -p /opt/restore/skeleton /opt/restore/var/cand \
    && cp -a /app/sympy /app/pytest.ini /opt/restore/skeleton/ \
    && cp -a /opt/restore/skeleton/. /opt/restore/var/cand/ \
    && chown -R root:root /app /opt/restore \
    && chmod -R a-w /opt/restore/skeleton /opt/restore/lib /opt/restore/units.json \
    && chmod -R a+rwX /opt/restore/var \
    && chmod 0755 /opt/restore/restore.py \
    && ln -s /opt/restore/restore.py /usr/local/bin/restore \
    && chown -R dev:dev /app/sympy && chown root:root /app/sympy && chmod 0777 /app/sympy \
    && touch /app/PROGRESS.md && chown dev:dev /app/PROGRESS.md \
    && chmod 1777 /app \
    && chown -R root:root /usr/local/lib/fsmaint \
    && chmod 0700 /usr/local/lib/fsmaint /usr/local/lib/fsmaint/fsmaint-reserve /usr/local/lib/fsmaint/fsmaint-netcheck \
        /usr/local/lib/fsmaint/fsmaint-sweep \
    && chmod 0600 /usr/local/lib/fsmaint/key
COPY timer.sh /app/timer.sh
COPY ATTRIBUTION.txt LICENSE /app/
RUN chmod 0755 /app/timer.sh && chmod 0644 /app/ATTRIBUTION.txt /app/LICENSE
