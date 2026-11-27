FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates util-linux && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==2.2.6 pillow==11.3.0 && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.7.1+cpu
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --system --uid 10002 coreworker
COPY public/ /opt/core50/
COPY test.sh verify.py test_stream.py test_training.py execution.py training_replay.py label_replay.py /tests/
COPY private/ /tests/private/
RUN chmod 700 /tests /tests/test.sh && find /usr /var /opt /home -xdev -type d -perm -0002 -exec chmod o-w {} +
WORKDIR /app/work
