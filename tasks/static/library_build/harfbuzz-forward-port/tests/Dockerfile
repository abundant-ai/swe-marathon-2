FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
# The same archive snapshot as the agent image, so a delivered tree compiles here with the same gcc it was built and
# tried with. The snapshot service covers amd64; other architectures use the live archive.
ARG UBUNTU_SNAPSHOT=20261126T000000Z
RUN apt-get update \
    && if [ "$(dpkg --print-architecture)" = amd64 ]; then \
         apt-get install -y --no-install-recommends ca-certificates \
         && rm -f /etc/apt/sources.list.d/ubuntu.sources \
         && for s in noble noble-updates noble-security; do \
              echo "deb https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT} $s main universe"; \
            done > /etc/apt/sources.list \
         && apt-get -o Acquire::Check-Valid-Until=false update; \
       fi \
    && apt-get install -y --no-install-recommends build-essential pkg-config ninja-build python3 python3-venv \
       ragel util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY wheels/ /opt/wheels/
RUN python3 -m venv /opt/py && /opt/py/bin/pip install --no-index --no-deps /opt/wheels/meson-*.whl \
    && dpkg-query -W -f '${Package}\t${Version}\t${Architecture}\n' > /opt/dpkg-versions.tsv \
    && useradd --system --create-home --shell /usr/sbin/nologin builder
COPY test.sh verify.py /tests/
COPY driver/ /tests/driver/
COPY inputs/ /tests/inputs/
COPY private/ /tests/private/
RUN chown -R root:root /tests && chmod 0711 /tests && chmod 0700 /tests/private /tests/test.sh \
    && chmod -R go-rwx /tests/private && chmod -R a+rX /tests/driver /tests/inputs \
    && mkdir -p /app /logs/verifier
WORKDIR /
