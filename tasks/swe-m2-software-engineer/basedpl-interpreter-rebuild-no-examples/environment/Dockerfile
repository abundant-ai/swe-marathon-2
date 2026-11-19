FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8 AS program
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY original/ /original/
RUN python3 /original/mark.py /original/bpl.xz /original/build.txt /original/marker /opt/bpl/bpl \
    && bash /original/smoke.sh /opt/bpl/bpl

FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python-is-python3 golang-go rustc cargo gcc g++ make cmake libc6-dev ca-certificates curl git ripgrep jq xz-utils less procps util-linux \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home dev && groupadd --system bpl
COPY --from=program /opt/bpl/bpl /opt/bpl/bpl
COPY --from=program /original/smoke.sh /tmp/bpl-smoke.sh
COPY docs/ /app/docs/
COPY provision-scratch reclaim-scratch session-timer /usr/local/sbin/
RUN ln -s /opt/bpl/bpl /usr/local/bin/bpl \
    && mkdir -p /app/rebuild \
    && chown -R root:root /app && chmod -R a+rX,go-w /app/docs \
    && chmod 1777 /app && chmod 0777 /app/rebuild \
    && chmod 0755 /opt/bpl && chown root:bpl /opt/bpl/bpl && chmod 2711 /opt/bpl/bpl \
    && chown root:root /usr/local/sbin/provision-scratch /usr/local/sbin/reclaim-scratch /usr/local/sbin/session-timer \
    && chmod 0700 /usr/local/sbin/provision-scratch /usr/local/sbin/reclaim-scratch /usr/local/sbin/session-timer \
    && chmod 0644 /tmp/bpl-smoke.sh \
    && setpriv --reuid dev --regid dev --clear-groups env HOME=/tmp bash /tmp/bpl-smoke.sh /opt/bpl/bpl \
    && rm -f /tmp/bpl-smoke.sh
WORKDIR /app
