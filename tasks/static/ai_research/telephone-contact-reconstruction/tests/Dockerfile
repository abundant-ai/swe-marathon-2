FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev util-linux ffmpeg ca-certificates git curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==2.2.6 pillow==11.3.0 scipy==1.15.3
ENV OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd -M --uid 12037 --shell /usr/sbin/nologin meshworker
COPY test.sh verify.py test_reconstruction.py worker_bootstrap.py fixture-digests.json /tests/
COPY private/ /tests/private/
COPY private/public-observations/ /app/work/
RUN chmod 700 /tests /tests/test.sh
WORKDIR /app/work
