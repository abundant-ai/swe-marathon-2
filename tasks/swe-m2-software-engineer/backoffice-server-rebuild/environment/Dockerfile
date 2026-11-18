FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python-is-python3 nodejs golang-go ca-certificates curl git ripgrep jq xz-utils less procps util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /opt/py/requirements.txt
RUN python3 -m venv /opt/py \
    && /opt/py/bin/pip install --no-cache-dir --no-deps --require-hashes -r /opt/py/requirements.txt \
    && chmod -R a+rX /opt/py \
    && ln -sf /opt/py/bin/python /usr/local/bin/python3 && ln -sf /opt/py/bin/python /usr/local/bin/python
RUN useradd --uid 10001 --create-home candidate && useradd --uid 10002 --system --no-create-home stockwell
COPY sealed/ /opt/stockwell/app/
COPY client/ /app/client/
COPY samples/ /app/samples/
COPY start-sealed-server /usr/local/sbin/start-sealed-server
COPY entrypoint.sh /usr/local/sbin/entrypoint.sh
RUN mkdir -p /app/server /opt/stockwell/client /opt/stockwell/data \
    && cp -a /app/client/dist/. /opt/stockwell/client/ \
    && /opt/py/bin/python -m compileall -q -b /opt/stockwell/app && find /opt/stockwell/app -name '*.py' -delete \
    && chown -R stockwell:stockwell /opt/stockwell && chmod -R go-rwx /opt/stockwell \
    && chown -R candidate:candidate /app && chown root:root /app /app/server && chmod 1777 /app && chmod 0777 /app/server \
    && git config --system --add safe.directory '*' \
    && chmod 0700 /usr/local/sbin/start-sealed-server /usr/local/sbin/entrypoint.sh
WORKDIR /app
ENTRYPOINT ["/usr/local/sbin/entrypoint.sh"]
CMD ["sleep", "infinity"]
