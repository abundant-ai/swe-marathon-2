FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends gfortran cmake make libopenblas-dev liblapack-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir numpy==1.26.4 scipy==1.13.1
COPY mopac-src /src/mopac
RUN cd /src/mopac && cmake -B /build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DTESTS=OFF >/tmp/cmake.log 2>&1 && cmake --build /build -j8 >/tmp/build.log 2>&1; tail -3 /tmp/build.log; ls /build | head -20
