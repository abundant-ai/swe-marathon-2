FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && command -v cc \
    && rm -rf /var/lib/apt/lists/*

ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 MUJOCO_GL=disable
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt \
    && useradd --uid 10001 --create-home --user-group candidate \
    && install -d -m 0700 /tests /logs/verifier
COPY *.py test.sh /tests/
COPY public_cell/ /app/examples/cell/
RUN chmod 0700 /tests /tests/test.sh
WORKDIR /app
