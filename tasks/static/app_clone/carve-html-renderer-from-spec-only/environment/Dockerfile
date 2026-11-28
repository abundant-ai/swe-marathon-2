FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
# For reproducibility over time, build with --build-arg APT_SNAPSHOT=YYYYMMDDTHHMMSSZ to pin the
# Ubuntu archive to one snapshot.ubuntu.com date; empty uses the base image's current archive.
ARG APT_SNAPSHOT=
RUN if [ -n "$APT_SNAPSHOT" ]; then \
        sed -i "s|http://archive.ubuntu.com/ubuntu|https://snapshot.ubuntu.com/ubuntu/$APT_SNAPSHOT|g; \
                s|http://security.ubuntu.com/ubuntu|https://snapshot.ubuntu.com/ubuntu/$APT_SNAPSHOT|g" \
            /etc/apt/sources.list /etc/apt/sources.list.d/* 2>/dev/null || true; fi \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python-is-python3 golang-go rustc cargo gcc libc6-dev \
        ca-certificates curl git ripgrep jq xz-utils less procps util-linux \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home dev
COPY spec/ /app/spec/
COPY docs/ /app/docs/
COPY fsmaint-reserve fsmaint-sweep /usr/local/lib/fsmaint/
RUN mkdir -p /app/rebuild \
    && chown -R root:root /app && chmod -R a+rX,go-w /app/spec /app/docs \
    && chmod 1777 /app && chmod 0777 /app/rebuild \
    && chown -R root:root /usr/local/lib/fsmaint && chmod 0700 /usr/local/lib/fsmaint /usr/local/lib/fsmaint/*
WORKDIR /app
