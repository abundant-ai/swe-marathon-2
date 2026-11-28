# syntax=docker/dockerfile:1
# Spike builder: pinned base, apt pinned through the Ubuntu snapshot archive (ca-certificates first,
# from the default archive, so the snapshot's HTTPS can be reached), git pinned, Rust 1.100.0 from
# checksummed archives (bind-mounted from the download cache, never copied into a layer).
FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ARG SNAPSHOT=20261126T000000Z
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8 TZ=UTC
RUN set -e; apt-get update; apt-get install -y --no-install-recommends ca-certificates; \
    arch="$(dpkg --print-architecture)"; \
    if [ "$arch" = amd64 ]; then \
      sed -i -E "s#http://[a-z.]*ubuntu\.com/ubuntu/?#https://snapshot.ubuntu.com/ubuntu/${SNAPSHOT}/#g" /etc/apt/sources.list.d/ubuntu.sources; \
    fi; \
    grep '^URIs' /etc/apt/sources.list.d/ubuntu.sources; \
    apt-get -o Acquire::Check-Valid-Until=false update; \
    apt-get install -y --no-install-recommends \
        git=1:2.43.0-1ubuntu7.4 build-essential pkg-config python3 xz-utils util-linux; \
    dpkg-query -W -f '${Package}=${Version}\n' > /etc/apt-installed.txt; \
    apt-get clean; rm -r /var/lib/apt/lists; mkdir -p /var/lib/apt/lists/partial
RUN --mount=type=bind,from=rustdist,target=/dist \
    set -e; arch="$(uname -m)"; \
    for c in rustc cargo rust-std; do \
      mkdir /tmp/r; tar -xJf "/dist/${c}-1.100.0-${arch}-unknown-linux-gnu.tar.xz" -C /tmp/r; \
      "/tmp/r/${c}-1.100.0-${arch}-unknown-linux-gnu/install.sh" --prefix=/usr/local --disable-ldconfig > /dev/null; \
      rm -r /tmp/r; \
    done; \
    rustc --version; cargo --version; git --version
