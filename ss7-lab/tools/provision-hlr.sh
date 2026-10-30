#!/bin/bash
# Idempotently provision the lab subscriber into OsmoHLR (via VTY).
set -u
cd /lab || exit 1
IMSI=${IMSI:-001010123456789}
K=${K:-465B5CE8B199B49FAA5F0A2EE238A6BC}
OPC=${OPC:-E8ED2A9CDFB6DFC9E1E6B4B0A5C1D9E2}
MSISDN=${MSISDN:-15551234567}

for _ in $(seq 1 30); do
    nc -z 127.0.0.1 4258 2>/dev/null && break
    sleep 0.3
done

{
    printf 'enable\n'
    printf 'subscriber imsi %s create\n' "$IMSI"
    printf 'subscriber imsi %s update aud3g milenage k %s opc %s\n' "$IMSI" "$K" "$OPC"
    printf 'subscriber imsi %s update aud2g comp128v1 k %s\n' "$IMSI" "$K"
    printf 'subscriber imsi %s update msisdn %s\n' "$IMSI" "$MSISDN"
    printf 'subscriber imsi %s show\n' "$IMSI"
} | timeout 8 nc 127.0.0.1 4258 | sed -n '/OsmoHLR#/,$p'
