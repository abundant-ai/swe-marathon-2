# Build-host image for the HarfBuzz forward-port pipeline: the product toolchain from the pinned base image
# and checksummed wheels. Every HarfBuzz tree (the four releases, the per-unit reverts, the mutants) is built
# from pinned, checksummed tarballs by `hb_build` inside bounded `docker run` containers of this image.
# Development tooling: never shipped, never copied into the agent or verifier image.
FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config ninja-build python3 python3-venv \
       ragel git ca-certificates xz-utils patch \
    && rm -rf /var/lib/apt/lists/*
COPY wheels/ /opt/wheels/
COPY SHA256SUMS /opt/SHA256SUMS
RUN cd /opt && sha256sum -c --ignore-missing --strict SHA256SUMS \
    && python3 -m venv /opt/py \
    && /opt/py/bin/pip install --no-index --no-deps /opt/wheels/*.whl \
    && dpkg-query -W -f '${Package}\t${Version}\t${Architecture}\n' > /opt/dpkg-versions.tsv \
    && /opt/py/bin/pip freeze > /opt/pip-versions.txt
ENV PATH=/opt/py/bin:$PATH
COPY hb_build.sh /usr/local/bin/hb_build
LABEL org.abundant.task=harfbuzz-forward-port
