FROM python:3.12-slim-bookworm

RUN useradd --uid 10001 --create-home --user-group candidate \
    && install -d -o candidate -g candidate /app /app/workcell
COPY resources/ /app/examples/
WORKDIR /app
