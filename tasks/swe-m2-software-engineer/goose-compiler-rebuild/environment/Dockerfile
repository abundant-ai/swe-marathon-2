FROM ubuntu:24.04 AS program
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake python3 ca-certificates git && rm -rf /var/lib/apt/lists/*
COPY upstream/ /src/
COPY hardening/ /hardening/
RUN sh /hardening/apply.sh /src \
    && mkdir -p /opt/goose /usr/local/share/goose && cp -a /src/stdlib /usr/local/share/goose/stdlib \
    && sh /hardening/build.sh /src /build 4 \
    && cp /build/goose /opt/goose/goose && cp -a /build/tcclib /opt/goose/tcclib \
    && bash /hardening/smoke.sh /opt/goose/goose

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python-is-python3 golang-go rustc cargo gcc g++ make cmake libc6-dev ca-certificates curl git ripgrep jq xz-utils less procps util-linux sudo \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home dev && groupadd --system goose
COPY --from=program /opt/goose /opt/goose
COPY --from=program /usr/local/share/goose /usr/local/share/goose
COPY docs/ /app/docs/
COPY run_examples.py examples.json /app/examples/
RUN ln -s /opt/goose/goose /usr/local/bin/goose \
    && python3 /app/examples/run_examples.py record /opt/goose/goose /app/examples/examples.json /app/examples/outputs.json --keep /app/examples/examples.json \
    && rm -rf /tmp/goose-case /tmp/.goose /root/.goose \
    && mkdir -p /app/rebuild && chown -R dev:dev /app \
    && chmod -R a+rX /usr/local/share/goose /opt/goose/tcclib && chmod 0755 /opt/goose \
    && chown root:goose /opt/goose/goose && chmod 2711 /opt/goose/goose
WORKDIR /app
