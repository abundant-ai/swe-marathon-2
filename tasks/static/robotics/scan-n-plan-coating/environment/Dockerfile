FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && command -v cc \
    && rm -rf /var/lib/apt/lists/*

ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt \
    && useradd --uid 10001 --create-home --user-group candidate \
    && install -d -o candidate -g candidate /app /app/coating_app
COPY resources/ /app/examples/
WORKDIR /app
