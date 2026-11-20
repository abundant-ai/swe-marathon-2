FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python-is-python3 nodejs golang-go ca-certificates curl git ripgrep jq xz-utils less procps util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /opt/py/requirements.txt
RUN python3 -m venv /opt/py \
    && /opt/py/bin/pip install --no-cache-dir --no-deps --require-hashes -r /opt/py/requirements.txt \
    && chmod -R a+rX /opt/py \
    && printf '#!/bin/sh\nexec /opt/py/bin/python "$@"\n' > /usr/local/bin/python3 \
    && cp /usr/local/bin/python3 /usr/local/bin/python && chmod 0755 /usr/local/bin/python3 /usr/local/bin/python \
    && echo /opt/py/lib/python3.12/site-packages > /usr/lib/python3/dist-packages/opt-py.pth
RUN useradd --uid 10001 --create-home dev && useradd --uid 10002 --system --no-create-home stockwell \
    && for user in dev nobody; do \
        setpriv --reuid "$user" --regid "$(id -g "$user")" --clear-groups sh -c 'cd / \
            && python3 -c "import fastapi, starlette, pydantic, sqlalchemy, uvicorn, httpx" \
            && /usr/bin/python3 -c "import fastapi, uvicorn" && python3 -m pip --version >/dev/null' || exit 1; \
    done
COPY sealed/ /opt/stockwell/app/
COPY client/ /app/client/
COPY samples/ /app/samples/
COPY stockwell.env /usr/local/lib/stockwell/stockwell.env
COPY start-sealed-server /usr/local/sbin/start-sealed-server
COPY sealed-supervisor /usr/local/sbin/sealed-supervisor
COPY prepare-delivery /usr/local/sbin/prepare-delivery
COPY precap-watchdog /usr/local/sbin/precap-watchdog
COPY entrypoint.sh /usr/local/sbin/entrypoint.sh
RUN mkdir -p /app/server /opt/stockwell/data \
    && test -z "$(find /opt/stockwell/app -name '*.py' -print -quit)" \
    && chown -R stockwell:stockwell /opt/stockwell && chmod -R go-rwx /opt/stockwell \
    && chown -R dev:dev /app && chown root:root /app /app/server && chmod 1777 /app && chmod 0777 /app/server \
    && git config --system --add safe.directory '*' \
    && chmod 0600 /usr/local/lib/stockwell/stockwell.env \
    && chmod 0700 /usr/local/sbin/start-sealed-server /usr/local/sbin/sealed-supervisor /usr/local/sbin/entrypoint.sh \
        /usr/local/sbin/prepare-delivery /usr/local/sbin/precap-watchdog
WORKDIR /app
ENTRYPOINT ["/usr/local/sbin/entrypoint.sh"]
CMD ["sleep", "infinity"]
