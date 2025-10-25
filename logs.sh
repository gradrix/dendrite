#!/bin/bash

#!/usr/bin/env bash
set -euo pipefail
PREFIX="${1:-center-agent}"   # usage: ./follow.sh [prefix]

trap 'echo; echo "Bye!"; exit 0' INT TERM

while :; do
  name="$(docker ps --filter "name=^$PREFIX" --format '{{.Names}}' | head -n1)"
  if [ -n "$name" ]; then
    echo "Attaching to logs of: $name"
    # Show only new lines by default; change TAIL_LINES to e.g. 100 if you want last 100 lines
    docker logs -f "$name" || true
    echo "Logs ended for $name (container stopped or restarted)."
  else
    echo "No running containers matching ^$PREFIX. Retrying..."
    sleep 5
  fi
  # Loop continues and will re-check until a new matching container appears
done

