FROM python:3.12-slim-bookworm
ENV MUJOCO_GL=disable OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt \
    && useradd --uid 10001 --create-home --user-group candidate \
    && install -d -o candidate -g candidate /app
COPY resources/ /app/examples/
WORKDIR /app
