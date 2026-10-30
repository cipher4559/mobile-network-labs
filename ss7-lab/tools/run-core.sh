#!/bin/bash
# Start the loopback Osmocom core: STP, HLR, MGW, MSC and (best effort) BSC.
set -u
cd /lab || exit 1
mkdir -p run
: > run/pids

start() {
    local name=$1; shift
    "$@" >"run/$name.log" 2>&1 &
    echo "$name $!" >>run/pids
    printf '%-4s pid %s\n' "$name" "$!"
}

start stp osmo-stp -c /lab/conf/osmo-stp.cfg
start hlr osmo-hlr -c /lab/conf/osmo-hlr.cfg
start mgw osmo-mgw -c /lab/conf/osmo-mgw.cfg
sleep 1
start msc osmo-msc -c /lab/conf/osmo-msc.cfg

# osmo-bsc: ship default radio config, add SCCP + A-interface peer
cp /etc/osmocom/osmo-bsc.cfg run/osmo-bsc.cfg
cat >>run/osmo-bsc.cfg <<'EOF'
cs7 instance 0
 point-code 0.23.4
 asp asp-clnt-bsc-0 2905 0 m3ua
  remote-ip 127.0.0.1
 as as-bsc-0 m3ua
  asp asp-clnt-bsc-0
  routing-key 0 0.23.4
msc 0
 mgw remote-ip 127.0.0.1
 mgw remote-port 2427
 asp-protocol m3ua
EOF
start bsc osmo-bsc -c /lab/run/osmo-bsc.cfg

sleep 2
echo
echo "== listening sockets =="
ss -lntu 2>/dev/null | grep -E '2905|4222|2427|4239|4258|4254|4243|4242'
echo
for f in run/stp.log run/hlr.log run/mgw.log run/msc.log run/bsc.log; do
    echo "== $f"
    tail -4 "$f"
done
