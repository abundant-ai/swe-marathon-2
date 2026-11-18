FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python-is-python3 nodejs golang-go ca-certificates procps util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /opt/py/requirements.txt
RUN python3 -m venv /opt/py \
    && /opt/py/bin/pip install --no-cache-dir --no-deps --require-hashes -r /opt/py/requirements.txt \
    && chmod -R a+rX /opt/py \
    && ln -sf /opt/py/bin/python /usr/local/bin/python3 && ln -sf /opt/py/bin/python /usr/local/bin/python
COPY test.sh verify.py /tests/
COPY verifier/ /tests/verifier/
COPY private/ /tests/private/
RUN mkdir -p /app /logs/verifier /work \
    && chown -R root:root /tests && chmod -R go-rwx /tests && chmod 0700 /tests/test.sh
WORKDIR /
