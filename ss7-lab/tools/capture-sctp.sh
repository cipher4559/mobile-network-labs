#!/bin/bash
# Prove the A-interface is real SCTP/M3UA: bounce osmo-msc and capture on lo.
cd /lab || exit 1
mkdir -p run
timeout 14 tcpdump -i lo -p -nn -s0 -c 10 -w run/m3ua.pcap 'sctp' \
    >run/tcpdump.log 2>&1 &
DUMP=$!
sleep 1

OLD=$(awk '/^msc /{print $2}' run/pids | tail -1)
[ -n "${OLD:-}" ] && kill "$OLD" 2>/dev/null
sleep 1
setsid osmo-msc -c /lab/conf/osmo-msc.cfg >>run/msc.log 2>&1 &

wait "$DUMP" 2>/dev/null
echo "== captured SCTP (lo) =="
tcpdump -nn -r run/m3ua.pcap 2>/dev/null | head -20
echo
echo "== M3UA ASP state on the STP =="
printf 'enable\nshow cs7 instance 0 asp\n' | timeout 3 nc 127.0.0.1 4239 | sed -n '/ASP Name/,$p' | head -8
