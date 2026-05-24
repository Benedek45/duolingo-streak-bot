#!/usr/bin/env bash
# run.sh — load env vars and run the browser Duolingo agent
# Usage: ./run.sh
# Cron (daily at 9am): 0 9 * * * cd /path/to/duolingo-agent && ./run.sh >> logs/agent.log 2>&1

set -euo pipefail

# Load .env without overwriting one-off command-line overrides.
if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [ -z "${!key+x}" ]; then
      export "$key=$value"
    fi
  done < .env
fi

mkdir -p logs

python3 agent.py
STATUS=$?

if [ $STATUS -eq 0 ]; then
  echo "[run.sh] Streak saved — $(date)"
else
  echo "[run.sh] Agent failed — $(date)"
fi

exit $STATUS
