# Verifier image: the candidate's tools without OpenFOAM, the recorded tests, and the verifier.
# Build context: this folder.

# The tests, at a fixed revision of the dataset.
FROM python:3.13-slim AS tests
ARG DATASET=AdnanElAssadi/openfoam-rebuild-tests
ARG DATASET_REVISION=3468bf65180870b9b30fee43e4ac0187616e11d6
RUN pip install --no-cache-dir huggingface_hub==2.4.0 hf_xet==1.8.0 \
    && python -c "from huggingface_hub import snapshot_download; \
snapshot_download('$DATASET', repo_type='dataset', revision='$DATASET_REVISION', local_dir='/data/openfoam-tests')" \
    && rm -rf /data/openfoam-tests/.cache

# Same packages as the candidate's environment (environment/Dockerfile), so compile.sh builds the
# same way; OpenFOAM itself is not installed.
FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake python3 python-is-python3 golang-go rustc cargo \
        flex libfl-dev bison libcgal-dev zlib1g-dev libopenmpi-dev openmpi-bin libreadline-dev libncurses-dev \
        libscotch-dev libptscotch-dev libfftw3-dev libgmp-dev libmpfr-dev libmetis-dev \
        libboost-system-dev libboost-thread-dev \
        m4 perl bc gnuplot-nox unzip xz-utils bzip2 git ripgrep jq less procps ca-certificates \
        python3-numpy \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf bash /bin/sh \
    && useradd --uid 10001 --create-home dev \
    && mkdir -p /app/rebuild
COPY --from=tests /data/ /data/
COPY test.sh verify.py /tests/
COPY verifier/ /tests/verifier/
RUN chmod -R go-rwx /tests /data && chmod 700 /tests/test.sh
WORKDIR /app
