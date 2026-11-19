FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python-is-python3 nodejs golang-go ca-certificates procps util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /opt/py/requirements.txt
RUN python3 -m venv /opt/py \
    && /opt/py/bin/pip install --no-cache-dir --no-deps --require-hashes -r /opt/py/requirements.txt \
    && chmod -R a+rX /opt/py \
    && printf '#!/bin/sh\nexec /opt/py/bin/python "$@"\n' > /usr/local/bin/python3 \
    && cp /usr/local/bin/python3 /usr/local/bin/python && chmod 0755 /usr/local/bin/python3 /usr/local/bin/python \
    && echo /opt/py/lib/python3.12/site-packages > /usr/lib/python3/dist-packages/opt-py.pth \
    && setpriv --reuid nobody --regid nogroup --clear-groups sh -c 'cd / \
        && python3 -c "import fastapi, starlette, pydantic, sqlalchemy, uvicorn, httpx" && /usr/bin/python3 -c "import fastapi, uvicorn"'
COPY test.sh verify.py /tests/
COPY verifier/ /tests/verifier/
COPY private/ /tests/private/
RUN mkdir -p /app /logs/verifier /work \
    && chown -R root:root /tests && chmod -R go-rwx /tests && chmod 0700 /tests/test.sh
WORKDIR /
