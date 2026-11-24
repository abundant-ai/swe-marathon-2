FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates g++ libeigen3-dev python3 python3-venv \
    && python3 -m venv /opt/fleet-tools \
    && /opt/fleet-tools/bin/pip install --no-cache-dir --only-binary=:all: uv==0.7.13 \
    && ln -s /opt/fleet-tools/bin/python /usr/local/bin/python \
    && ln -s /opt/fleet-tools/bin/uv /usr/local/bin/uv \
    && useradd --uid 10001 --create-home --user-group candidate \
    && install -d -o candidate -g candidate /app /app/fleet_recovery \
    && rm -rf /var/lib/apt/lists/*
COPY native-rmf /tmp/native-rmf
RUN cd /tmp/native-rmf && sha256sum -c SHA256SUMS \
    && mkdir -p /opt/fleet-rmf \
    && for package in *.deb; do dpkg-deb -x "$package" /opt/fleet-rmf; done
COPY example /app/example
RUN sh /app/example/rmf/build_rmf_native.sh /usr/local/bin/rmf-native
WORKDIR /app
