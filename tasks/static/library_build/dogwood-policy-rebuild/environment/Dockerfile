# The working machine: Rust 1.100.0 with an offline crate registry, the 1.2.0 `dogwood` build
# installed execute-only, its guide and examples in /app/docs, and an empty directory for the new
# implementation.
ARG RUST_IMAGE=rust:1.100.0-slim-bookworm@sha256:bb875b0f8ce726053e259034848c471840e96bfe591fd52556178ae9a05e6126

# Dogwood 1.2.0 as released: the published dogwood-cli package (from tag commit 8ffd2106) with its
# published Cargo.lock, every dependency vendored from crates.io and checked against that lock,
# built for the image's own glibc target and linked statically. The digests of Dogwood's own
# source files, and of the build, are listed before its crates leave the registry, which must
# then hold exactly the crates of registry.txt.
FROM ${RUST_IMAGE} AS release
ARG CARGO_BUILD_JOBS=4
ADD --checksum=sha256:2390e687a9101ba29a7a949bef711c5d6ae5926dcdecd427d71d9424f3c211b0 \
    https://static.crates.io/crates/dogwood-cli/dogwood-cli-1.2.0.crate /tmp/dogwood-cli-1.2.0.crate
COPY registry.txt /opt/registry.txt
RUN set -eu; \
    tar -xzf /tmp/dogwood-cli-1.2.0.crate -C /opt --no-same-owner; \
    cd /opt/dogwood-cli-1.2.0; \
    cargo vendor --locked --versioned-dirs /opt/registry > /opt/vendor-source.toml; \
    mkdir -p .cargo; cp /opt/vendor-source.toml .cargo/config.toml; \
    triple=$(rustc -vV | sed -n 's/^host: //p'); \
    CARGO_PROFILE_RELEASE_DEBUG=0 CARGO_INCREMENTAL=0 RUSTFLAGS="-C target-feature=+crt-static" \
      cargo build --release --locked --offline --features experimental-arithmetic --target "$triple"; \
    cp "target/$triple/release/dogwood" /opt/dogwood-release; \
    if readelf -l /opt/dogwood-release | grep -q INTERP; then echo "the release build is not static" >&2; exit 1; fi; \
    rm -r target /usr/local/cargo/registry; \
    find /opt/dogwood-cli-1.2.0/src /opt/registry/dogwood-language-1.2.0 /opt/registry/dogwood-ops-1.2.0 \
         /opt/registry/dogwood-formatter-1.2.0 /opt/registry/dogwood-syntax-1.2.0 \
         -type f \( -name '*.rs' -o -name '*.pest' \) -exec sh -c 'for f; do \
           if [ "$(tr -d " \t\r\n" < "$f" | wc -c)" -ge 400 ]; then \
             echo "exact $(sha256sum < "$f" | cut -d" " -f1)"; \
             echo "squeezed $(tr -d " \t\r\n" < "$f" | sha256sum | cut -d" " -f1)"; \
           fi; done' sh {} + | sort -u > /opt/upstream-sources.txt; \
    echo "binary $(sha256sum < /opt/dogwood-release | cut -d' ' -f1) $(stat -c %s /opt/dogwood-release)" \
      >> /opt/upstream-sources.txt; \
    rm -r /opt/registry/dogwood-language-1.2.0 /opt/registry/dogwood-ops-1.2.0 \
          /opt/registry/dogwood-formatter-1.2.0 /opt/registry/dogwood-syntax-1.2.0; \
    ls /opt/registry | diff - /opt/registry.txt; \
    chmod -R a+rX /opt/registry

# Root runs programs by name from its PATH once the session is over (the hand-off, and the copy
# of the project and the logs), so no directory on that PATH, nothing in one and none of their
# parents may be writable by another user: the Rust image leaves its cargo and rustup trees
# writable by everyone, and they are closed here and checked. The user `dev` builds with its own
# CARGO_HOME and only reads the toolchain.
FROM ${RUST_IMAGE}
ENV CARGO_HOME=/home/dev/.cargo LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PATH=/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/* \
    && groupadd --system dogwood-run \
    && useradd --create-home --shell /bin/bash dev \
    && mkdir -p /home/dev/.cargo /app/dogwood-rebuild \
    && chown -R root:root /usr/local/cargo /usr/local/rustup \
    && chmod -R go-w /usr/local/cargo /usr/local/rustup
COPY --from=release /opt/registry /opt/cargo-registry
COPY cargo-config.toml /home/dev/.cargo/config.toml
COPY --from=release --chown=root:dogwood-run --chmod=2711 /opt/dogwood-release /usr/local/bin/dogwood
COPY docs/ /app/docs/
COPY handoff/ /usr/local/lib/dogwood-handoff/
RUN chown -R dev:dev /home/dev /app/dogwood-rebuild \
    && chown -R root:root /app/docs /usr/local/lib/dogwood-handoff && chmod -R a+rX,go-w /app/docs \
    && chmod 0700 /usr/local/lib/dogwood-handoff /usr/local/lib/dogwood-handoff/* \
    && bad=$(for d in $(echo "$PATH" | tr : ' '); do \
           find -L "$d" -maxdepth 1 \( ! -user root -o -perm -o+w -o \( -perm -g+w ! -group root \) \) -print; \
           p=$(readlink -f "$d"); while [ "$p" != / ]; do \
             find "$p" -maxdepth 0 \( ! -user root -o -perm -o+w -o \( -perm -g+w ! -group root \) \) -print; \
             p=$(dirname "$p"); done; \
         done) \
    && if [ -n "$bad" ]; then echo "writable by others on root's PATH: $bad" >&2; exit 1; fi
WORKDIR /app
