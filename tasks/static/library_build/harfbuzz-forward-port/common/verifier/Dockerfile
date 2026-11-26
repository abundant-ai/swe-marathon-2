FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config ninja-build python3 python3-venv \
       ragel util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY wheels/ /opt/wheels/
RUN python3 -m venv /opt/py && /opt/py/bin/pip install --no-index --no-deps /opt/wheels/meson-*.whl \
    && useradd --system --create-home --shell /usr/sbin/nologin builder
COPY test.sh verify.py /tests/
COPY driver/ /tests/driver/
COPY inputs/ /tests/inputs/
COPY private/ /tests/private/
RUN chown -R root:root /tests && chmod 0711 /tests && chmod 0700 /tests/private /tests/test.sh \
    && chmod -R go-rwx /tests/private && chmod -R a+rX /tests/driver /tests/inputs \
    && mkdir -p /app /logs/verifier
WORKDIR /
