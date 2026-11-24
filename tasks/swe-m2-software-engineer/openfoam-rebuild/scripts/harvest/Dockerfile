# Agent image plus numpy, for harvesting.
# usage: docker build -t ofrebuild:harvest -f scripts/harvest/Dockerfile scripts/harvest
FROM ofrebuild:agent
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-numpy \
    && rm -rf /var/lib/apt/lists/*
USER dev
