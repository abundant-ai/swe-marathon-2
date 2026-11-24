FROM python:3.12-slim-bookworm
RUN useradd --uid 10001 --create-home --user-group candidate     && install -d -o candidate -g candidate /app /app/barn_qualification     && python3 -m pip install --no-cache-dir --only-binary=:all: uv==0.7.13
COPY example /app/example
WORKDIR /app
