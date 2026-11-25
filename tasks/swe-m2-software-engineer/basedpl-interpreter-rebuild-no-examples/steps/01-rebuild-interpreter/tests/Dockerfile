FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8 AS program
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY original/ /original/
RUN python3 /original/mark.py /original/bpl.xz /original/build.txt /original/marker /opt/bpl/bpl \
    && bash /original/smoke.sh /opt/bpl/bpl
COPY verifier/runcases.py verifier/recorder.py verifier/recording.py verifier/derivations.py verifier/functions.json /record/
COPY private/cases.json /record/cases.json
RUN cp /original/marker /record/marker \
    && python3 /record/recorder.py record /opt/bpl/bpl /record/cases.json /record/expected.json --keep /record/kept.json --report /record/timing.json \
    && python3 /record/derivations.py /opt/bpl/bpl /record/kept.json /record/expected.json /record/functions.json /record/derived.json \
    && python3 /record/recording.py /record/cases.json /record/kept.json /record/expected.json /record/timing.json /record/recording.json \
       --derived /record/derived.json --build /opt/bpl/build.txt

FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python-is-python3 golang-go rustc cargo gcc g++ make cmake libc6-dev ca-certificates procps util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY test.sh verify.py /tests/
COPY verifier/ /tests/verifier/
COPY --from=program /record/kept.json /tests/private/cases.json
COPY --from=program /record/expected.json /tests/private/expected.json
COPY --from=program /record/recording.json /tests/private/recording.json
COPY --from=program /record/derived.json /tests/private/derived.json
COPY --from=program /record/marker /tests/private/marker
RUN mkdir -p /app /logs/verifier \
    && chown -R root:root /tests && chmod -R go-rwx /tests && chmod 0700 /tests/test.sh
WORKDIR /
