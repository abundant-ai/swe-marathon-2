# The separate image that builds and checks the delivered project. It holds the same Rust
# toolchain and crate registry as the working machine, python3, the grader, the private cases,
# their expected results, recorded while this image is built, and the digests of Dogwood's own
# source files and of the release build. No dogwood build is left in it.
ARG RUST_IMAGE=rust:1.100.0-slim-bookworm@sha256:bb875b0f8ce726053e259034848c471840e96bfe591fd52556178ae9a05e6126

# Dogwood 1.2.0 as released: the published dogwood-cli package (from tag commit 8ffd2106) with its
# published Cargo.lock, every dependency vendored from crates.io and checked against that lock,
# built for the image's own glibc target and linked statically. The digests of Dogwood's own
# source files, and of the build, are listed before its crates leave the registry, which must
# then hold exactly the crates of registry.txt.
# The working machine's Dockerfile has the same stage, so both images carry the same build.
FROM ${RUST_IMAGE} AS release
ARG CARGO_BUILD_JOBS=4
ADD --checksum=sha256:2390e687a9101ba29a7a949bef711c5d6ae5926dcdecd427d71d9424f3c211b0 \
    https://static.crates.io/crates/dogwood-cli/dogwood-cli-1.2.0.crate /tmp/dogwood-cli-1.2.0.crate
COPY registry.txt /opt/registry.txt
RUN set -eu; \
    tar -xzf /tmp/dogwood-cli-1.2.0.crate -C /opt --no-same-owner; \
    cd /opt/dogwood-cli-1.2.0; \
    cargo vendor --locked --versioned-dirs /opt/registry > /opt/vendor-source.toml; \
    rm -r /usr/local/cargo/registry; \
    mkdir -p .cargo; cp /opt/vendor-source.toml .cargo/config.toml; \
    triple=$(rustc -vV | sed -n 's/^host: //p'); \
    CARGO_PROFILE_RELEASE_DEBUG=0 CARGO_INCREMENTAL=0 RUSTFLAGS="-C target-feature=+crt-static" \
      cargo build --release --locked --offline --features experimental-arithmetic --target "$triple"; \
    cp "target/$triple/release/dogwood" /opt/dogwood-release; \
    if readelf -l /opt/dogwood-release | grep -q INTERP; then echo "the release build is not static" >&2; exit 1; fi; \
    rm -rf target /usr/local/cargo/registry; \
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

# Expected results: every private case run three times through the release build, the way the
# grader runs it; a case without a single answer stops the build. The program is named `dogwood`,
# as a delivered build is installed, because its usage text names the file it was started as.
FROM ${RUST_IMAGE} AS record
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
COPY --from=release /opt/dogwood-release /opt/release/dogwood
COPY verifier/ /record/verifier/
COPY record.py /record/record.py
COPY private/cases.jsonl /record/private/cases.jsonl
COPY private/bundles/ /record/private/bundles/
RUN python3 -I -B /record/record.py /opt/release/dogwood /record/private /record/gold.jsonl \
      /record/gold-meta.json

# The grading machine. Root runs programs by name from its PATH while the grader works and after
# it (Harbor packs the grader's output folder with `tar`), so no directory on that PATH, nothing
# in one and none of their parents may be writable by another user: the Rust image leaves
# /usr/local/cargo, its bin directory and the `rustup` program its entries link to writable by
# everyone, and they are closed here and checked. (The toolchain below /usr/local/rustup stays as
# the Rust image ships it: root runs nothing from there, and the grader removes whatever the
# build and the runs leave on the machine.) Python and Perl run for root only (the grader is
# root's; the build and the runs are not). Python and the registry come first, as in the working
# image.
FROM ${RUST_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
COPY --from=release /opt/registry /opt/cargo-registry
ENV PYTHONDONTWRITEBYTECODE=1 LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    PATH=/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN useradd --system --create-home --shell /usr/sbin/nologin builder \
    && chmod go-w /usr/local/cargo /usr/local/cargo/bin /usr/local/cargo/bin/rustup \
    && chmod 0700 "$(readlink -f /usr/bin/python3)" /usr/bin/perl /usr/bin/perl5.* \
    && bad=$(for d in $(echo "$PATH" | tr : ' '); do \
           find -L "$d" -maxdepth 1 \( ! -user root -o -perm -o+w -o \( -perm -g+w ! -group root \) \) -print; \
           p=$(readlink -f "$d"); while [ "$p" != / ]; do \
             find "$p" -maxdepth 0 \( ! -user root -o -perm -o+w -o \( -perm -g+w ! -group root \) \) -print; \
             p=$(dirname "$p"); done; \
         done) \
    && if [ -n "$bad" ]; then echo "writable by others on root's PATH: $bad" >&2; exit 1; fi
COPY cargo-config.toml /opt/verifier/cargo-config.toml
COPY test.sh verify.py /tests/
COPY verifier/ /tests/verifier/
COPY private/cases.jsonl /tests/private/cases.jsonl
COPY private/bundles/ /tests/private/bundles/
COPY --from=record /record/gold.jsonl /record/gold-meta.json /tests/private/
COPY --from=release /opt/upstream-sources.txt /tests/upstream-sources.txt
RUN mkdir -p /app /logs/verifier \
    && chown -R root:root /tests \
    && chmod -R go-rwx /tests \
    && chmod 0700 /tests/test.sh
WORKDIR /
