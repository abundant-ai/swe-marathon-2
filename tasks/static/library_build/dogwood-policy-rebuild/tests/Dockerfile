# The separate image that builds and checks the delivered project. It holds the same Rust
# toolchain and crate registry as the working machine, python3, the grader, the private cases,
# and their expected results, recorded while this image is built. No dogwood build is left in it.
ARG RUST_IMAGE=rust:1.100.0-slim-bookworm@sha256:bb875b0f8ce726053e259034848c471840e96bfe591fd52556178ae9a05e6126

# Dogwood 1.2.0 as released: the published dogwood-cli package (from tag commit 8ffd2106) with its
# published Cargo.lock, every dependency vendored from crates.io and checked against that lock.
# The working machine's Dockerfile has the same stage, so both images carry the same build.
FROM ${RUST_IMAGE} AS release
ARG TARGETARCH
ADD --checksum=sha256:2390e687a9101ba29a7a949bef711c5d6ae5926dcdecd427d71d9424f3c211b0 \
    https://static.crates.io/crates/dogwood-cli/dogwood-cli-1.2.0.crate /tmp/dogwood-cli-1.2.0.crate
RUN set -eu; \
    case "$TARGETARCH" in \
      amd64) T=x86_64-unknown-linux-musl ;; \
      arm64) T=aarch64-unknown-linux-musl ;; \
      *) echo "unsupported architecture $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    rustup target add "$T"; \
    tar -xzf /tmp/dogwood-cli-1.2.0.crate -C /opt --no-same-owner; \
    cd /opt/dogwood-cli-1.2.0; \
    cargo vendor --locked --versioned-dirs /opt/vendor > /opt/vendor-source.toml; \
    mkdir -p .cargo; cp /opt/vendor-source.toml .cargo/config.toml; \
    CARGO_PROFILE_RELEASE_DEBUG=0 CARGO_INCREMENTAL=0 \
      cargo build --release --locked --offline --features experimental-arithmetic --target "$T"; \
    cp "target/$T/release/dogwood" /opt/dogwood-release; \
    mkdir /opt/registry; cp -R /opt/vendor/. /opt/registry/; \
    rm -r /opt/registry/dogwood-language-1.2.0 /opt/registry/dogwood-ops-1.2.0 \
          /opt/registry/dogwood-formatter-1.2.0 /opt/registry/dogwood-syntax-1.2.0

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
RUN mkdir -p /app /logs/verifier \
    && chown -R root:root /tests /opt/verifier \
    && chmod -R go-rwx /tests \
    && chmod -R a+rX /opt/verifier \
    && chmod 0700 /tests/test.sh
WORKDIR /
