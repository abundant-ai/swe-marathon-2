FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8 AS program
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake python3 ca-certificates git && rm -rf /var/lib/apt/lists/*
COPY upstream/ /src/
COPY hardening/ /hardening/
RUN sh /hardening/apply.sh /src \
    && mkdir -p /opt/goose /usr/local/share/goose && cp -a /src/stdlib /usr/local/share/goose/stdlib \
    && sh /hardening/build.sh /src /build 4 \
    && cp /build/goose /opt/goose/goose && cp -a /build/tcclib /opt/goose/tcclib \
    && bash /hardening/smoke.sh /opt/goose/goose
COPY run_examples.py /record/runcases.py
COPY recorder.py examples.json /record/
RUN python3 /record/recorder.py record /opt/goose/goose /record/examples.json /record/outputs.json \
        --keep /record/kept.json --renumber E

FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python-is-python3 golang-go rustc cargo gcc g++ make cmake libc6-dev ca-certificates curl git ripgrep jq xz-utils less procps util-linux sudo \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home dev && groupadd --system goose
COPY --from=program /opt/goose /opt/goose
COPY --from=program /usr/local/share/goose /usr/local/share/goose
COPY docs/ /app/docs/
COPY run_examples.py /app/examples/
COPY --from=program /record/kept.json /app/examples/examples.json
COPY --from=program /record/outputs.json /app/examples/outputs.json
RUN ln -s /opt/goose/goose /usr/local/bin/goose \
    && mkdir -p /app/rebuild && chown -R dev:dev /app \
    && chown root:root /app /app/rebuild && chmod 1777 /app && chmod 0777 /app/rebuild \
    && chmod -R a+rX /usr/local/share/goose /opt/goose/tcclib && chmod 0755 /opt/goose \
    && chown root:goose /opt/goose/goose && chmod 2711 /opt/goose/goose
WORKDIR /app
