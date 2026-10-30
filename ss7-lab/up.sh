#!/bin/bash
# Bring up the loopback SS7/Osmocom core and run both lab stages.
set -e
cd "$(dirname "$0")"

docker compose up -d --build
echo "-- waiting for VTY/GSUP..."
for _ in $(seq 1 40); do
    docker compose exec -T core nc -z 127.0.0.1 4258 2>/dev/null && break
    sleep 0.5
done

echo "-- provisioning subscriber"
docker compose exec -T core ./tools/provision-hlr.sh

echo "-- Stage B: MAP over TCAP (mock HLR + client)"
docker compose exec -T core bash -c \
    'nohup python3 -u tools/hlr_mock.py >run/hlr_mock.log 2>&1 &'
sleep 1
docker compose exec -T core python3 tools/map_client.py

echo
echo "-- live state"
docker compose exec -T core bash -c 'ss -ln --sctp 2>/dev/null; ss -lntu | grep -E "2905|4222|2427"'
