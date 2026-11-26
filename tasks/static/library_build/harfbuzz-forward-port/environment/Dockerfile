FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8
# The toolchain comes from the Ubuntu archive as it stood at one moment (snapshot.ubuntu.com), so every build of this
# image compiles with the same gcc as the product's build machines. The snapshot service covers amd64; other
# architectures use the live archive.
ARG UBUNTU_SNAPSHOT=20261126T000000Z
RUN apt-get update \
    && if [ "$(dpkg --print-architecture)" = amd64 ]; then \
         apt-get install -y --no-install-recommends ca-certificates \
         && rm -f /etc/apt/sources.list.d/ubuntu.sources \
         && for s in noble noble-updates noble-security; do \
              echo "deb https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT} $s main universe"; \
            done > /etc/apt/sources.list \
         && apt-get -o Acquire::Check-Valid-Until=false update; \
       fi \
    && apt-get install -y --no-install-recommends build-essential pkg-config ninja-build python3 python3-venv \
       python3-lxml ragel git ca-certificates curl xz-utils patch libglib2.0-dev less nano procps \
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
# The Unicode 18.0 data files upstream's table generators read (src/update-unicode-tables.make), the
# DerivedCoreProperties.txt they were generated with, and Microsoft's USE override files as upstream ships them.
RUN mkdir -p /tmp/u /app/docs/unicode/ms-use \
    && cd /tmp/u \
    && U=https://www.unicode.org/Public \
    && G=https://raw.githubusercontent.com/harfbuzz/harfbuzz/cdbe72ca8bf2c077e91ae10c4e428e1183d7d5ec/src/ms-use \
    && curl -fsSL -o UCD.zip $U/18.0.0/ucd/UCD.zip \
    && curl -fsSL -o ucd.nounihan.grouped.zip $U/18.0.0/ucdxml/ucd.nounihan.grouped.zip \
    && curl -fsSL -o DerivedCoreProperties.txt $U/17.0.0/ucd/DerivedCoreProperties.txt \
    && curl -fsSL -o emoji-data.txt $U/18.0.0/ucd/emoji/emoji-data.txt \
    && curl -fsSL -o emoji-test.txt $U/18.0.0/emoji/emoji-test.txt \
    && curl -fsSL -o license.txt https://www.unicode.org/license.txt \
    && curl -fsSL -o IndicSyllabicCategory-Additional.txt $G/IndicSyllabicCategory-Additional.txt \
    && curl -fsSL -o IndicPositionalCategory-Additional.txt $G/IndicPositionalCategory-Additional.txt \
    && printf '%s\n' \
       "7b3e555514060b92290d154f53655c5eb0fa62b16eb04c03434ff72d1a66a0d8  UCD.zip" \
       "552bef87e5bf69d0047048d1e5762d352ab817aecc1a35b955628e8f1a4707ee  ucd.nounihan.grouped.zip" \
       "24c7fed1195c482faaefd5c1e7eb821c5ee1fb6de07ecdbaa64b56a99da22c08  DerivedCoreProperties.txt" \
       "80d00f8e616a0ef27fd6b8de3b758c06383b5d917e2977709578e68baf733bf1  emoji-data.txt" \
       "8f3735cda1f92a779d78af67cf86066bb1f07143dc22f2ac29394d9bc57ab21a  emoji-test.txt" \
       "e7a93b009565cfce55919a381437ac4db883e9da2126fa28b91d12732bc53d96  license.txt" \
       "b9472e3e72d5fba8cb3f2e0578e73012aaae786db25779de0f1a5a5ab69b84a6  IndicSyllabicCategory-Additional.txt" \
       "2baa1c1efe5a5f108c304b1e27d0d97864c806764eb2b0a1bd91db80ae26b5b8  IndicPositionalCategory-Additional.txt" \
       | sha256sum -c --quiet - \
    && python3 -c "import zipfile; zipfile.ZipFile('UCD.zip').extractall('/app/docs/unicode', ['ArabicShaping.txt', 'Blocks.txt', 'IndicPositionalCategory.txt', 'IndicSyllabicCategory.txt', 'Scripts.txt', 'UnicodeData.txt'])" \
    && mv ucd.nounihan.grouped.zip DerivedCoreProperties.txt emoji-data.txt emoji-test.txt license.txt /app/docs/unicode/ \
    && mv IndicSyllabicCategory-Additional.txt IndicPositionalCategory-Additional.txt /app/docs/unicode/ms-use/ \
    && rm UCD.zip \
    && cd / && rmdir /tmp/u
COPY docs/ /app/docs/
COPY prune_tree.sh /opt/setup/prune_tree.sh
RUN curl -fsSL -o /tmp/harfbuzz-14.3.0.tar.xz \
       https://github.com/harfbuzz/harfbuzz/releases/download/14.3.0/harfbuzz-14.3.0.tar.xz \
    && echo "16070d77cfc4ba1f1e7327e83bf9b3f55898081cabdb94e56a33e04fc8874eae  /tmp/harfbuzz-14.3.0.tar.xz" \
       | sha256sum -c - \
    && mkdir -p /app/harfbuzz \
    && tar -xJf /tmp/harfbuzz-14.3.0.tar.xz -C /app/harfbuzz --strip-components=1 \
    && rm /tmp/harfbuzz-14.3.0.tar.xz \
    && sh /opt/setup/prune_tree.sh /app/harfbuzz \
    && rm /opt/setup/prune_tree.sh && rmdir /opt/setup \
    && useradd --create-home --shell /bin/bash dev \
    && git -C /app/harfbuzz init -q -b main \
    && git -C /app/harfbuzz -c user.name=product -c user.email=product@localhost add -A \
    && git -C /app/harfbuzz -c user.name=product -c user.email=product@localhost commit -q -m "HarfBuzz 14.3.0" \
    && chown -R dev:dev /app
WORKDIR /app
USER dev
