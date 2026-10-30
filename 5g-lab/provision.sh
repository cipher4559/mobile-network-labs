#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

IMSI="${IMSI:-999700000000001}"
KEY="${KEY:-465B5CE8B199B49FAA5F0A2EE238A6BC}"
OPC="${OPC:-E8ED2A9CDFB6DFC9E1E6B4B0A5C1D9E2}"

docker compose cp ./open5gs-dbctl mongo:/tmp/open5gs-dbctl
docker compose exec -T mongo mongosh --quiet --eval "db.getSiblingDB('open5gs').subscribers.deleteOne({imsi:'$IMSI'})" >/dev/null
docker compose exec -T mongo bash /tmp/open5gs-dbctl --db_uri=mongodb://localhost/open5gs add "$IMSI" "$KEY" "$OPC"
docker compose exec -T mongo mongosh --quiet --eval "db.getSiblingDB('open5gs').subscribers.updateOne({imsi:'$IMSI'},{\$set:{'slice.0.sd':'000001'}})" >/dev/null
echo "provisioned IMSI $IMSI"
