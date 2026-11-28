# syntax=docker/dockerfile:1
# Verifier image: the toolchain and the same offline registry as the agent image; no original build.
# The private cases and their recorded outputs are root-only.
FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8 AS base
ARG SNAPSHOT=20261126T000000Z
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8 TZ=UTC
RUN set -e; apt-get update; apt-get install -y --no-install-recommends ca-certificates; \
    arch="$(dpkg --print-architecture)"; \
    if [ "$arch" = amd64 ]; then \
      sed -i -E "s#http://[a-z.]*ubuntu\.com/ubuntu/?#https://snapshot.ubuntu.com/ubuntu/${SNAPSHOT}/#g" /etc/apt/sources.list.d/ubuntu.sources; \
    fi; \
    apt-get -o Acquire::Check-Valid-Until=false update; \
    apt-get install -y --no-install-recommends \
        git=1:2.43.0-1ubuntu7.4 build-essential pkg-config python3 xz-utils curl util-linux procps; \
    apt-get clean; rm -r /var/lib/apt/lists; mkdir -p /var/lib/apt/lists/partial
RUN set -e; arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) t=x86_64; rc=f1d0b1dec81dab6f523cd098507763487b0d4bd7fd2c87582f154128719be03b; cg=7e29ce07d7c6e92d1826870575ba27d57fff6cb3e754aa57d99099cb88fab35d; st=4591b6486594ded52ecd6135db95bf9355bbd3ca7a380888b141528bbcf9a5d4 ;; \
      arm64) t=aarch64; rc=fcbfa5b8a0cb28f0c4edfb6dda6910ee910993db31f05258613f5cd5b851263a; cg=d07ee80eb6ba3c5845c554ac88086e1ff5d63f83d99c3c09cb32504cbedd6844; st=c73f62fbe5d837f9807ed9e0076575dd8d3475c79af2b30e3570d328e6713f8f ;; \
      *) echo "unsupported architecture $arch"; exit 1 ;; \
    esac; \
    for pair in "rustc $rc" "cargo $cg" "rust-std $st"; do \
      set -- $pair; f="$1-1.100.0-$t-unknown-linux-gnu"; \
      curl -fsSL -o "/tmp/$f.tar.xz" "https://static.rust-lang.org/dist/2026-11-12/$f.tar.xz"; \
      echo "$2  /tmp/$f.tar.xz" | sha256sum -c -; \
      tar -xJf "/tmp/$f.tar.xz" -C /tmp; "/tmp/$f/install.sh" --prefix=/usr/local --disable-ldconfig > /dev/null; \
      rm -r "/tmp/$f" "/tmp/$f.tar.xz"; \
    done; \
    rustc --version; cargo --version; git --version

FROM base AS registry
COPY registry/ /seed/
RUN set -e; cd /seed; cargo vendor --locked -q /opt/cargo-vendor > /dev/null; rm -r /root/.cargo/registry

FROM base
COPY --from=registry /opt/cargo-vendor /opt/cargo-vendor
COPY cargo-config.toml /usr/local/share/offline-registry/config.toml
COPY test.sh verify.py delivery_manifest.py upstream-digests.txt /tests/
COPY private/ /tests/private/
RUN set -e; chmod -R a+rX /opt/cargo-vendor /usr/local/share/offline-registry; \
    chown -R root:root /tests; chmod 0700 /tests/private; chmod 0600 /tests/private/*; chmod 0755 /tests/test.sh; \
    chmod 0644 /tests/verify.py /tests/delivery_manifest.py /tests/upstream-digests.txt
# Harbor runs tar, gzip and su as root through the image's PATH: nothing on it may be writable by
# anyone but root.
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN set -e; for d in $(echo "$PATH" | tr ':' ' '); do \
      if [ -d "$d" ] && [ ! -L "$d" ]; then chmod -R go-w "$d"; fi; \
    done; \
    bad=$(for d in $(echo "$PATH" | tr ':' ' '); do \
      if [ -d "$d" ] && [ ! -L "$d" ]; then find "$d" -maxdepth 1 ! -type l \( ! -user root -o -perm -0020 -o -perm -0002 \); fi; \
    done); \
    if [ -n "$bad" ]; then echo "on PATH and writable by others: $bad"; exit 1; fi
WORKDIR /
