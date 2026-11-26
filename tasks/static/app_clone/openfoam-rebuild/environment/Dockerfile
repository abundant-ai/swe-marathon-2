# Stage 1 builds OpenFOAM from source. Stage 2 gets only the programs, libraries,
# run-time data and tutorials. Build context: this folder plus reference/.
FROM ubuntu:26.04 AS openfoam
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential flex libfl-dev bison cmake zlib1g-dev \
        libboost-system-dev libboost-thread-dev libopenmpi-dev openmpi-bin \
        libreadline-dev libncurses-dev libscotch-dev libptscotch-dev libfftw3-dev \
        libcgal-dev libgmp-dev libmpfr-dev libmetis-dev ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf bash /bin/sh
ARG OPENFOAM_TAG=OpenFOAM-v2606
ARG OPENFOAM_COMMIT=481094fdf34f11ed6d0d603ee59a858a0124236d
# The clone is shallow, its .git is deleted, and only build products leave this stage.
# provenance-okay
RUN git clone --quiet --depth 1 --branch "$OPENFOAM_TAG" https://gitlab.com/openfoam/core/openfoam.git /src \
    && test "$(git -C /src rev-parse HEAD)" = "$OPENFOAM_COMMIT" \
    && rm -rf /src/.git
COPY reference/ /reference/
ARG JOBS=8
RUN bash /reference/build.sh /src /opt/openfoam "$JOBS" \
    && cp -a /src/tutorials /opt/tutorials
RUN cp -a /src/META-INFO /opt/openfoam/META-INFO

FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake python3 python-is-python3 golang-go rustc cargo \
        flex libfl-dev bison libcgal-dev zlib1g-dev libopenmpi-dev openmpi-bin libreadline-dev libncurses-dev \
        libscotch-dev libptscotch-dev libfftw3-dev libgmp-dev libmpfr-dev libmetis-dev \
        libboost-system-dev libboost-thread-dev \
        m4 perl bc gnuplot-nox unzip xz-utils bzip2 git ripgrep jq less procps ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf bash /bin/sh
COPY --from=openfoam /opt/openfoam /opt/openfoam
COPY --from=openfoam /opt/tutorials /app/tutorials
# Programs can be run but not read: setgid group openfoam, mode 2711; libraries readable by
# that group only. Setgid programs ignore LD_LIBRARY_PATH, so the libraries go through ldconfig,
# with lib/dummy stand-ins for libraries not built (KaHIP). In the hardened build (hardening.patch)
# the programs open for reading only files the user may read, and load libraries only by name.
# The run-time data in etc and the scripts in bin are readable.
RUN groupadd --system openfoam && useradd --uid 10001 --create-home dev \
    && O=/opt/openfoam/platforms/$(cat /opt/openfoam/WM_OPTIONS) \
    && chown -R root:openfoam "$O" \
    && find "$O/bin" -type f -exec chmod 2711 {} + \
    && find "$O/lib" -type d -exec chmod 0750 {} + \
    && find "$O/lib" -type f -exec chmod 0640 {} + \
    && chmod 0755 "$O" "$O/bin" \
    && mkdir "$O/lib/stubs" \
    && for f in "$O"/lib/dummy/*.so; do n=$(basename "$f"); \
           [ -e "$O/lib/$n" ] || [ -e "$O/lib/sys-openmpi/$n" ] || ln -s "../dummy/$n" "$O/lib/stubs/$n"; done \
    && chown -h root:openfoam "$O/lib/stubs" "$O"/lib/stubs/* && chmod 0750 "$O/lib/stubs" \
    && printf '%s\n' "$O/lib/sys-openmpi" "$O/lib" "$O/lib/stubs" > /etc/ld.so.conf.d/openfoam.conf \
    && ldconfig \
    && ln -s /app/tutorials /opt/openfoam/tutorials \
    && ln -s "$(cat /opt/openfoam/WM_OPTIONS)" /opt/openfoam/platforms/current \
    && printf '%s\n' '_args=("$@"); set --; source /opt/openfoam/etc/bashrc; set -- "${_args[@]}"; unset _args' \
           > /etc/openfoam-env.sh \
    && echo 'source /etc/openfoam-env.sh' > /etc/profile.d/openfoam.sh \
    && echo 'source /etc/openfoam-env.sh' >> /etc/bash.bashrc \
    && mkdir -p /app/rebuild && chown -R dev:dev /app
# The published v2606 documentation, read-only.
COPY docs/ /app/docs/
# Time left of the agent's 12 hours: `bash /app/timer.sh`.
COPY timer.sh /app/timer.sh
# OpenFOAM's environment in every shell (openfoam-env.sh hides the script's arguments, which
# etc/bashrc would otherwise read as settings files). PMIX_MCA_psec=none: otherwise mpirun
# rejects the setgid programs because their group differs from the user's.
ENV WM_PROJECT_DIR=/opt/openfoam FOAM_TUTORIALS=/app/tutorials PMIX_MCA_psec=none \
    BASH_ENV=/etc/openfoam-env.sh \
    PATH=/opt/openfoam/platforms/current/bin:/opt/openfoam/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /app
# As the agent's user: the programs neither read the libraries nor load a library of the user's.
COPY check_hardening.sh /tmp/check_hardening.sh
RUN setpriv --reuid=dev --regid=dev --init-groups env HOME=/home/dev bash /tmp/check_hardening.sh \
    && rm /tmp/check_hardening.sh
USER dev
