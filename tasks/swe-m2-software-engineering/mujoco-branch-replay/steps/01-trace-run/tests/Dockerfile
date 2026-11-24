FROM python:3.12-slim-bookworm

ENV MUJOCO_GL=disable
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt

RUN useradd --uid 10001 --create-home --user-group candidate \
    && install -d -m 0700 /tests /logs/verifier
COPY *.py test.sh /tests/
RUN chmod 0700 /tests/test.sh
WORKDIR /app
