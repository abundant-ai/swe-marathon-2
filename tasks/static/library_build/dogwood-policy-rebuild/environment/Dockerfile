# The working machine: Rust 1.100.0 with an offline crate registry, the 1.2.0 `dogwood` build
# installed execute-only, its guide and examples in /app/docs, and an empty directory for the new
# implementation.
ARG RUST_IMAGE=rust:1.100.0-slim-bookworm@sha256:bb875b0f8ce726053e259034848c471840e96bfe591fd52556178ae9a05e6126

# Dogwood 1.2.0 as released: the published dogwood-cli package (from tag commit 8ffd2106) with its
# published Cargo.lock, every dependency vendored from crates.io and checked against that lock,
# built for the image's own glibc target. The digests of Dogwood's own source files are listed
# before its crates leave the registry.
FROM ${RUST_IMAGE} AS release
ARG CARGO_BUILD_JOBS=4
ADD --checksum=sha256:2390e687a9101ba29a7a949bef711c5d6ae5926dcdecd427d71d9424f3c211b0 \
    https://static.crates.io/crates/dogwood-cli/dogwood-cli-1.2.0.crate /tmp/dogwood-cli-1.2.0.crate
RUN set -eu; \
    tar -xzf /tmp/dogwood-cli-1.2.0.crate -C /opt --no-same-owner; \
    cd /opt/dogwood-cli-1.2.0; \
    cargo vendor --locked --versioned-dirs /opt/registry > /opt/vendor-source.toml; \
    mkdir -p .cargo; cp /opt/vendor-source.toml .cargo/config.toml; \
    CARGO_PROFILE_RELEASE_DEBUG=0 CARGO_INCREMENTAL=0 \
      cargo build --release --locked --offline --features experimental-arithmetic; \
    cp target/release/dogwood /opt/dogwood-release; \
    rm -r target /usr/local/cargo/registry; \
    find /opt/dogwood-cli-1.2.0/src /opt/registry/dogwood-language-1.2.0 /opt/registry/dogwood-ops-1.2.0 \
         /opt/registry/dogwood-formatter-1.2.0 /opt/registry/dogwood-syntax-1.2.0 \
         -type f \( -name '*.rs' -o -name '*.pest' \) -exec sh -c 'for f; do \
           if [ "$(tr -d " \t\r\n" < "$f" | wc -c)" -ge 400 ]; then \
             echo "exact $(sha256sum < "$f" | cut -d" " -f1)"; \
             echo "squeezed $(tr -d " \t\r\n" < "$f" | sha256sum | cut -d" " -f1)"; \
           fi; done' sh {} + | sort -u > /opt/upstream-sources.txt; \
    rm -r /opt/registry/dogwood-language-1.2.0 /opt/registry/dogwood-ops-1.2.0 \
          /opt/registry/dogwood-formatter-1.2.0 /opt/registry/dogwood-syntax-1.2.0; \
    chmod -R a+rX /opt/registry

FROM ${RUST_IMAGE}
ENV CARGO_HOME=/home/dev/.cargo LANG=C.UTF-8 LC_ALL=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/* \
    && groupadd --system dogwood-run \
    && useradd --create-home --shell /bin/bash dev \
    && mkdir -p /home/dev/.cargo /app/dogwood-rebuild
COPY --from=release /opt/registry /opt/cargo-registry
COPY cargo-config.toml /home/dev/.cargo/config.toml
COPY --from=release --chown=root:dogwood-run --chmod=2711 /opt/dogwood-release /usr/local/bin/dogwood
COPY docs/ /app/docs/
COPY --chmod=0700 stop-user-processes /usr/local/sbin/stop-user-processes
RUN chown -R dev:dev /home/dev /app/dogwood-rebuild \
    && chown -R root:root /app/docs && chmod -R a+rX,go-w /app/docs
WORKDIR /app
