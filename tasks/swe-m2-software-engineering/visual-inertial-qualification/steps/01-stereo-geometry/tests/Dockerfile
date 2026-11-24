FROM python:3.12-slim-bookworm
COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt \
    && useradd --uid 10001 --create-home --user-group candidate \
    && install -d -m 0700 /tests /logs/verifier
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MUJOCO_GL=disable
COPY *.py test.sh /tests/
COPY fixture/ /tests/fixture/
RUN chmod 0700 /tests/test.sh
WORKDIR /app
