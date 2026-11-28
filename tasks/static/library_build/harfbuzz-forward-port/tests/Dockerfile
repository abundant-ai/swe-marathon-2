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
# verify.py builds and runs the delivered tree under fresh numeric ids for each run (process limits count per uid on
# the host). This user, with a fixed uid of its own, is the fallback where those ids cannot be used.
RUN python3 -m venv /opt/py && /opt/py/bin/pip install --no-index --no-deps /opt/wheels/meson-*.whl \
    && dpkg-query -W -f '${Package}\t${Version}\t${Architecture}\n' > /opt/dpkg-versions.tsv \
    && useradd --system --uid 61423 --user-group --create-home --shell /usr/sbin/nologin builder
# sweep_check.py reads the post-session sweep's mark and record; verify.py loads it by this path.
COPY test.sh verify.py sweep_check.py /tests/
COPY driver/ /tests/driver/
COPY inputs/ /tests/inputs/
COPY private/ /tests/private/
RUN chown -R root:root /tests && chmod 0711 /tests \
    && chmod 0700 /tests/private /tests/test.sh /tests/verify.py /tests/sweep_check.py \
    && chmod -R go-rwx /tests/private && chmod -R a+rX /tests/driver /tests/inputs \
    && mkdir -p /app /logs/verifier && chown root:root /logs/verifier && chmod 0755 /logs/verifier
WORKDIR /
