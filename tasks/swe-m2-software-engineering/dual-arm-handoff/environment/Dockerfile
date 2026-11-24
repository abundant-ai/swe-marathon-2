FROM python:3.12-slim-bookworm

ENV MUJOCO_GL=disable OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt \
    && useradd --uid 10001 --create-home --user-group candidate \
    && install -d -o candidate -g candidate /app /app/dual_arm
COPY resources/ /app/examples/
WORKDIR /app
