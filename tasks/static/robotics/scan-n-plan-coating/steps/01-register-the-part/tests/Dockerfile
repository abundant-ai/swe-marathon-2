FROM python:3.12-slim-bookworm

ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt \
    && useradd --uid 10001 --create-home --user-group candidate \
    && install -d -m 0700 /tests /logs/verifier
COPY verify.py registration_cases.py candidate.py test.sh /tests/
RUN chmod 0700 /tests /tests/test.sh
WORKDIR /app
