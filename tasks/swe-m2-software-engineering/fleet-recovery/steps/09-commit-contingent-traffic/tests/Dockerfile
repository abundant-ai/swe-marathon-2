FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ libeigen3-dev python3 \
    && useradd --uid 10001 --create-home --user-group candidate \
    && install -d -m 0700 /tests /logs/verifier \
    && rm -rf /var/lib/apt/lists/*
COPY native-rmf /tmp/native-rmf
RUN cd /tmp/native-rmf && sha256sum -c SHA256SUMS \
    && mkdir -p /opt/fleet-rmf \
    && for package in *.deb; do dpkg-deb -x "$package" /opt/fleet-rmf; done
COPY *.py test.sh /tests/
COPY rmf_native.cpp build_rmf_native.sh traffic_smoke.cpp /tests/
RUN sh /tests/build_rmf_native.sh /usr/local/bin/rmf-native \
    && g++ -std=c++17 -O2 -I/opt/fleet-rmf/opt/ros/jazzy/include -I/usr/include/eigen3 \
       /tests/traffic_smoke.cpp -L/opt/fleet-rmf/opt/ros/jazzy/lib/x86_64-linux-gnu \
       -L/opt/fleet-rmf/opt/ros/jazzy/lib -Wl,-rpath-link,/opt/fleet-rmf/usr/lib/x86_64-linux-gnu \
       -Wl,--disable-new-dtags,-rpath,/opt/fleet-rmf/opt/ros/jazzy/lib/x86_64-linux-gnu:/opt/fleet-rmf/opt/ros/jazzy/lib:/opt/fleet-rmf/usr/lib/x86_64-linux-gnu \
       -lrmf_traffic -lrmf_utils -o /usr/local/bin/rmf-schedule-proof \
    && chmod 0700 /tests/test.sh \
    && /usr/local/bin/rmf-schedule-proof
WORKDIR /app
