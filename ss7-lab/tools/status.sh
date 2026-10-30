#!/bin/bash
# One-shot status of the lab.
cd /lab || exit 1
echo "== SCTP / GSUP / MGCP listeners =="
ss -ln --sctp 2>/dev/null
ss -lntu 2>/dev/null | grep -E '4222|2427|4239|4258|4254|4242'
echo
echo "== M3UA ASPs on OsmoSTP =="
printf 'enable\nshow cs7 instance 0 asp\n' | timeout 3 nc 127.0.0.1 4239 \
    | sed -n '/ASP Name/,$p' | head -8
echo
echo "== Subscriber =="
printf 'enable\nsubscriber imsi 001010123456789 show\n' | timeout 3 nc 127.0.0.1 4258 \
    | sed -n '/OsmoHLR#/,$p' | grep -vE '^OsmoHLR#?$' | head -12
echo
echo "== A-interface (BSC log) =="
grep -a "BSSMAP assocation is up" run/bsc.log | tail -1
