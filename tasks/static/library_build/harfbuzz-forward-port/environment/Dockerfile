FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config ninja-build python3 python3-venv \
       ragel git ca-certificates curl xz-utils patch libglib2.0-dev less nano procps python3-lxml \
    && rm -rf /var/lib/apt/lists/*
RUN printf '%s\n' \
       "fonttools==4.69.1 --hash=sha256:20e9dfac71694d9eeae48bb53c877bdf43b914794d69a769940728a1929cc835" \
       "packtab==1.9.0 --hash=sha256:5641d7505ea726c21501101af32f21908180db84eae0f04e3b70a5cb40fd10a1" \
       "meson==1.12.1 --hash=sha256:930bc7542cbd9f57009e182fd014eba48cf1a0180a7b9006d2d32d8f168d8b02" \
       > /tmp/requirements.txt \
    && python3 -m venv --system-site-packages /opt/py \
    && /opt/py/bin/pip install --no-cache-dir --no-deps --only-binary=:all: --require-hashes -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt
ENV PATH=/opt/py/bin:$PATH
COPY prune_tree.sh /opt/setup/prune_tree.sh
RUN curl -fsSL -o /tmp/harfbuzz-14.3.0.tar.xz \
       https://github.com/harfbuzz/harfbuzz/releases/download/14.3.0/harfbuzz-14.3.0.tar.xz \
    && echo "16070d77cfc4ba1f1e7327e83bf9b3f55898081cabdb94e56a33e04fc8874eae  /tmp/harfbuzz-14.3.0.tar.xz" \
       | sha256sum -c - \
    && mkdir -p /app/harfbuzz /app/docs/unicode /app/docs/specs \
    && tar -xJf /tmp/harfbuzz-14.3.0.tar.xz -C /app/harfbuzz --strip-components=1 \
    && rm /tmp/harfbuzz-14.3.0.tar.xz \
    && sh /opt/setup/prune_tree.sh /app/harfbuzz \
    && useradd --create-home --shell /bin/bash dev \
    && git -C /app/harfbuzz init -q -b main \
    && git -C /app/harfbuzz -c user.name=product -c user.email=product@localhost add -A \
    && git -C /app/harfbuzz -c user.name=product -c user.email=product@localhost commit -q -m "HarfBuzz 14.3.0" \
    && chown -R dev:dev /app
WORKDIR /app
USER dev
