#!/bin/bash
# Detection exercise: baseline, burst, sweep - all on loopback.
# Run from the host (ss7-lab/), with the lab up (./up.sh):
#   ./tools/detect-demo.sh
set -e
cd "$(dirname "$0")/.."

AUDIT=run/hlr_audit.jsonl
BL=run/baseline.json

dc()  { docker compose exec -T core "$@"; }
step(){ printf '\n\033[1m== %s\033[0m\n' "$*"; }

mkdir -p run
if ! dc bash -c 'nc -z 127.0.0.1 3899' 2>/dev/null; then
    echo "-- mock HLR not running, starting it"
    dc bash -c 'nohup python3 -u tools/hlr_mock.py >run/hlr_mock.log 2>&1 &'
    sleep 1
fi

step "Phase 1 - quiet baseline: one legitimate dialogue (4 ops, 1 IMSI)"
rm -f "$AUDIT" "$BL"
dc python3 tools/map_client.py --quiet >/dev/null
sleep 1
dc python3 tools/query_monitor.py --once --save-baseline "$BL"

step "Phase 2 - burst: the same four ops x6 against one IMSI"
dc python3 tools/map_client.py --quiet --repeat 6 >/dev/null
dc python3 tools/query_monitor.py --once --baseline-file "$BL" || true

step "Phase 3 - sweep: 10 IMSIs from one source (phase 2 burst is still in the window)"
dc python3 tools/map_client.py --quiet --sweep 10 >/dev/null
dc python3 tools/query_monitor.py --once --baseline-file "$BL" || true

step "done"
echo "audit log: ss7-lab/$AUDIT   baseline: ss7-lab/$BL"
echo "live tail: docker compose exec -T core python3 tools/query_monitor.py --follow --baseline-file $BL"
