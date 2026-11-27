FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==2.2.6 pillow==11.3.0 && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.7.1+cpu
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
RUN useradd -m -u 10001 dev
COPY public/ /app/work/
RUN chown -R dev:dev /app/work
WORKDIR /app/work
