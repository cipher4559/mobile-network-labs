#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

docker compose up -d mongo
for _ in $(seq 1 30); do
  st=$(docker inspect -f '{{.State.Health.Status}}' 5glab-mongo 2>/dev/null || echo none)
  [ "$st" = healthy ] && break
  sleep 2
done

docker compose up -d nrf scp ausf udr udm pcf nssf bsf amf smf upf
sleep 15

./provision.sh

docker compose up -d gnb
sleep 5
docker compose up -d ue
sleep 8

docker compose ps --format 'table {{.Name}}\t{{.Status}}'
