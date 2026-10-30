#!/bin/bash
# Stop whatever run-core.sh started.
cd /lab || exit 1
[ -f run/pids ] || exit 0
while read -r name pid; do
    [ -n "${pid:-}" ] && kill "$pid" 2>/dev/null && echo "stopped $name ($pid)"
done <run/pids
: >run/pids
