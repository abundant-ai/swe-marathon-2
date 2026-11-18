FROM ubuntu:24.04 AS program
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake python3 ca-certificates git && rm -rf /var/lib/apt/lists/*
COPY upstream/ /src/
COPY hardening/ /hardening/
RUN sh /hardening/apply.sh /src \
    && cmake -S /src -B /build -DCMAKE_BUILD_TYPE=Release -DGOOSE_VERSION=745901f -DGOOSE_STDLIB_PATH=/usr/local/share/goose/stdlib \
    && cmake --build /build --target goose -j 4 \
    && test -f /build/tcclib/include/tccdefs.h \
    && mkdir -p /opt/goose /usr/local/share/goose \
    && cp /build/goose /opt/goose/goose && cp -a /build/tcclib /opt/goose/tcclib && cp -a /src/stdlib /usr/local/share/goose/stdlib \
    && bash /hardening/smoke.sh /opt/goose/goose
COPY verifier/runcases.py /record/runcases.py
COPY private/cases.json /record/cases.json
RUN python3 /record/runcases.py record /opt/goose/goose /record/cases.json /record/expected.json --keep /record/kept.json

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python-is-python3 golang-go rustc cargo gcc g++ make cmake libc6-dev ca-certificates procps util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY --from=program /usr/local/share/goose /usr/local/share/goose
COPY test.sh verify.py /tests/
COPY verifier/ /tests/verifier/
COPY --from=program /record/kept.json /tests/private/cases.json
COPY --from=program /record/expected.json /tests/private/expected.json
RUN mkdir -p /app /logs/verifier && chmod -R a+rX /usr/local/share/goose \
    && chown -R root:root /tests && chmod -R go-rwx /tests && chmod 0700 /tests/test.sh
WORKDIR /
