# syntax=docker/dockerfile:1
# Agent image: the original 0.7.1 built from its pinned tag and installed execute-only; the offline
# registry of the crates the driver is built on; the specification. Network is used at build only.
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

FROM base AS original
# The v0.7.1 tag (commit 527ccb37a951) as a source archive, checked by its sha256; no history.
RUN set -e; curl -fsSL --proto '=https' -o /tmp/weave.tar.gz \
# provenance-okay
        https://github.com/Ataraxy-Labs/weave/archive/refs/tags/v0.7.1.tar.gz; \
    echo "2c3c913b1b2ae8c2c90ec152211a5818828714f142436c32df6b21391ad9cc35  /tmp/weave.tar.gz" | sha256sum -c -; \
    mkdir /src; tar -xzf /tmp/weave.tar.gz -C /src --strip-components=1; rm /tmp/weave.tar.gz; \
    cd /src; CARGO_BUILD_JOBS=4 cargo build --release --locked -q -p weave-driver; \
    strip target/release/weave-driver; cp target/release/weave-driver /weave-driver; \
    rm -r target /root/.cargo/registry

FROM base AS registry
COPY registry/ /seed/
RUN set -e; cd /seed; cargo vendor --locked -q /opt/cargo-vendor > /dev/null; rm -r /root/.cargo/registry

FROM base
COPY --from=original /weave-driver /usr/local/bin/weave-driver
COPY --from=original /src/LICENSE-MIT /src/LICENSE-APACHE /app/docs/
COPY --from=registry /opt/cargo-vendor /opt/cargo-vendor
COPY cargo-config.toml /app/.cargo/config.toml
COPY docs/ /app/docs/
RUN set -e; groupadd --system weaveorig; chown root:weaveorig /usr/local/bin/weave-driver; \
    chmod 2711 /usr/local/bin/weave-driver; useradd --create-home dev; \
    mkdir -p /app/driver; chown dev:dev /app/driver; chmod -R a+rX /app/docs /app/.cargo /opt/cargo-vendor
WORKDIR /app
