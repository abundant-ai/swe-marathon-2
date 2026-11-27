FROM python:3.11-slim
# Same tools as the grading container (steps/*/tests/Dockerfile): Python, numpy, scipy and a C compiler with OpenMP.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libgomp1 make \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==1.26.4 scipy==1.13.1
WORKDIR /workspace
# MOPAC 23.2.5 source (openmopac/mopac, Apache-2.0, commit 5bbea09), vendored without git history. Removed: tests/, build/,
# all .out/.aux/.arc/.res and shipped example outputs. No MOPAC binary and no Fortran compiler in this image.
COPY mopac-src /workspace/mopac-src
RUN mkdir -p /workspace/solver /logs/verifier
