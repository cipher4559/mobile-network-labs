#!/bin/sh
set -e

ip tuntap add name ogstun mode tun 2>/dev/null || true
ip addr add 10.45.0.1/16 dev ogstun 2>/dev/null || true
ip -6 addr add cafe::1/64 dev ogstun 2>/dev/null || true
ip link set ogstun up

echo 1 > /proc/sys/net/ipv4/ip_forward 2>/dev/null || true
iptables -t nat -C POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE 2>/dev/null \
  || iptables -t nat -A POSTROUTING -s 10.45.0.0/16 ! -o ogstun -j MASQUERADE 2>/dev/null || true

echo "upf: ogstun ready, starting open5gs-upfd"
exec open5gs-upfd
