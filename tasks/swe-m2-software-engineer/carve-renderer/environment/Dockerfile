FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python-is-python3 golang-go rustc cargo gcc libc6-dev \
        ca-certificates curl git ripgrep jq xz-utils less procps util-linux \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home dev
COPY spec/ /app/spec/
COPY docs/ /app/docs/
COPY prepare-delivery /usr/local/sbin/prepare-delivery
RUN mkdir -p /app/rebuild \
    && chown -R root:root /app && chmod -R a+rX,go-w /app/spec /app/docs \
    && chmod 1777 /app && chmod 0777 /app/rebuild \
    && chmod 0700 /usr/local/sbin/prepare-delivery
WORKDIR /app
