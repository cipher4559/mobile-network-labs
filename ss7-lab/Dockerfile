FROM debian:12-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      osmo-stp osmo-hlr osmo-msc osmo-bsc osmo-mgw \
      python3 python3-pip iproute2 tcpdump procps netcat-openbsd less \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages --no-cache-dir pycrate==0.8.1
WORKDIR /lab
