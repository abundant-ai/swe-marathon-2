# The separate image that builds and checks the delivered project. It holds the same Rust
# toolchain and crate registry as the working machine, python3, the grader, the private cases,
# their expected results, recorded while this image is built, and the digests of Dogwood's own
# source files. No dogwood build is left in it.
ARG RUST_IMAGE=rust:1.100.0-slim-bookworm@sha256:bb875b0f8ce726053e259034848c471840e96bfe591fd52556178ae9a05e6126

# Dogwood 1.2.0 as released: the published dogwood-cli package (from tag commit 8ffd2106) with its
# published Cargo.lock, every dependency vendored from crates.io and checked against that lock,
# built for the image's own glibc target. The digests of Dogwood's own source files are listed
# before its crates leave the registry.
# The working machine's Dockerfile has the same stage, so both images carry the same build.
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

# Expected results: every private case run three times through the release build, the way the
# grader runs it; a case without a single answer stops the build.
FROM ${RUST_IMAGE} AS record
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
COPY --from=release /opt/dogwood-release /opt/dogwood-release
COPY verifier/ /record/verifier/
COPY record.py /record/record.py
COPY private/cases.jsonl /record/private/cases.jsonl
COPY private/bundles/ /record/private/bundles/
RUN python3 -I -B /record/record.py /opt/dogwood-release /record/private /record/gold.jsonl

FROM ${RUST_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 LANG=C.UTF-8 LC_ALL=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --shell /usr/sbin/nologin builder
COPY --from=release /opt/registry /opt/verifier/registry
COPY cargo-config.toml /opt/verifier/cargo-config.toml
COPY test.sh verify.py /tests/
COPY verifier/ /tests/verifier/
COPY private/cases.jsonl /tests/private/cases.jsonl
COPY private/bundles/ /tests/private/bundles/
COPY --from=record /record/gold.jsonl /tests/private/gold.jsonl
COPY --from=release /opt/upstream-sources.txt /tests/upstream-sources.txt
RUN mkdir -p /app /logs/verifier \
    && chown -R root:root /tests \
    && chmod -R go-rwx /tests \
    && chmod 0700 /tests/test.sh
WORKDIR /
