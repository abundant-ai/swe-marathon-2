FROM python:3.12-slim-bookworm
RUN useradd --uid 10001 --create-home --user-group candidate     && install -d -m 0700 /tests /logs/verifier
COPY *.py test.sh /tests/
RUN chmod 0700 /tests/test.sh
WORKDIR /app
