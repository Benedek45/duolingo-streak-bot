#!/usr/bin/env bash
# run.sh — load env vars and run the Duolingo agent
# Usage: ./run.sh
# Cron (daily at 9am): 0 9 * * * cd /path/to/duolingo-agent && ./run.sh >> logs/agent.log 2>&1

set -euo pipefail

# Load .env
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Wait for emulator to be healthy before running (useful on cold start)
echo "[run.sh] Waiting for emulator ADB..."
for i in $(seq 1 20); do
  if adb -s "${ADB_HOST:-localhost}:${ADB_PORT:-5555}" get-state 2>/dev/null | grep -q "device"; then
    echo "[run.sh] Emulator ready."
    break
  fi
  echo "[run.sh] Not ready yet ($i/20)..."
  sleep 10
done

python3 agent.py
STATUS=$?

if [ $STATUS -eq 0 ]; then
  echo "[run.sh] ✅ Streak saved — $(date)"
else
  echo "[run.sh] ❌ Agent failed — $(date)"
fi

exit $STATUS
