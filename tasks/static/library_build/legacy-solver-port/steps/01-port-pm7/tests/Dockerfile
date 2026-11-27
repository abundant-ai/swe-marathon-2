# Verifier image. Build context: this folder as staged by scripts/package_task.py (adds verify_core.py and private/).
FROM python:3.11-slim
RUN pip install --no-cache-dir numpy==1.26.4 scipy==1.13.1 \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin candidate \
    && install -d -m 0700 /tests /logs/verifier
COPY test.sh verify.py verify_core.py /tests/
COPY private/ /tests/private/
RUN chmod -R go-rwx /tests && chmod 0700 /tests/test.sh
WORKDIR /workspace
