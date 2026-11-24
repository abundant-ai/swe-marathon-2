FROM python:3.12-slim-bookworm
ENV MUJOCO_GL=disable OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: -r /opt/requirements.txt \
    && useradd --uid 10001 --create-home --user-group candidate \
    && install -d -m 0700 /tests /logs/verifier
COPY *.py so101-rows.parquet SO101-ATTRIBUTION.md so101-headless.xml SO101-MODEL-LICENSE.txt test.sh /tests/
RUN chmod 0700 /tests/test.sh
WORKDIR /app
