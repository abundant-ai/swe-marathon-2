FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8 AS program
ENV DEBIAN_FRONTEND=noninteractive
# For reproducibility over time, build with --build-arg APT_SNAPSHOT=YYYYMMDDTHHMMSSZ to pin the
# Ubuntu archive to one snapshot.ubuntu.com date; empty uses the base image's current archive.
ARG APT_SNAPSHOT=
RUN if [ -n "$APT_SNAPSHOT" ]; then \
        sed -i "s|http://archive.ubuntu.com/ubuntu|https://snapshot.ubuntu.com/ubuntu/$APT_SNAPSHOT|g; \
                s|http://security.ubuntu.com/ubuntu|https://snapshot.ubuntu.com/ubuntu/$APT_SNAPSHOT|g" \
            /etc/apt/sources.list /etc/apt/sources.list.d/* 2>/dev/null || true; fi \
    && apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY original/ /original/
RUN python3 -I /original/install.py /original/carve.tar.gz /original/build.txt /opt/carve/carve
COPY verifier/runcases.py verifier/recorder.py verifier/recording.py /record/
COPY private/cases.json /record/cases.json
COPY private/probes.json /record/probes.json
# Record the answers and the probes; where original/kept_ids.txt names a sha256, the kept ids must
# hash to it.
RUN python3 /record/recorder.py record /opt/carve/carve /record/cases.json /record/expected.json \
        --keep /record/kept.json --report /record/timing.json \
        --probes /record/probes.json --probes-out /record/probes_expected.json \
        --expect-kept-ids "$(cat /original/kept_ids.txt 2>/dev/null)" \
    && python3 /record/recording.py /record/cases.json /record/kept.json /record/expected.json /record/timing.json /record/recording.json \
       --build /original/build.txt

FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
ARG APT_SNAPSHOT=
RUN if [ -n "$APT_SNAPSHOT" ]; then \
        sed -i "s|http://archive.ubuntu.com/ubuntu|https://snapshot.ubuntu.com/ubuntu/$APT_SNAPSHOT|g; \
                s|http://security.ubuntu.com/ubuntu|https://snapshot.ubuntu.com/ubuntu/$APT_SNAPSHOT|g" \
            /etc/apt/sources.list /etc/apt/sources.list.d/* 2>/dev/null || true; fi \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python-is-python3 golang-go rustc cargo gcc libc6-dev ca-certificates procps util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY test.sh verify.py /tests/
COPY verifier/ /tests/verifier/
COPY --from=program /record/kept.json /tests/private/cases.json
COPY --from=program /record/expected.json /tests/private/expected.json
COPY --from=program /record/probes.json /tests/private/probes.json
COPY --from=program /record/probes_expected.json /tests/private/probes_expected.json
COPY --from=program /record/recording.json /tests/private/recording.json
RUN mkdir -p /app /logs/verifier \
    && chown -R root:root /tests && chmod -R go-rwx /tests && chmod 0700 /tests/test.sh
WORKDIR /
