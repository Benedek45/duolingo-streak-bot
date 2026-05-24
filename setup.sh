#!/usr/bin/env bash
# setup.sh — one-time setup for the Duolingo agent
set -euo pipefail

echo "=== 1. Checking Chromium ==="
if ! command -v chromium >/dev/null 2>&1; then
  echo "Chromium is required. Install it with: sudo apt install chromium"
  exit 1
fi

echo "=== 2. Checking Node/npx for Playwright MCP ==="
if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required for @playwright/mcp. Install Node.js 18+ and npm."
  exit 1
fi

echo "=== 3. Installing Python deps ==="
pip install -r requirements.txt --break-system-packages

echo "=== 4. Checking Playwright MCP ==="
npx --yes @playwright/mcp@latest --version >/dev/null

echo ""
echo "Done. Next steps:"
echo "  1. cp .env.example .env && fill in your keys"
echo "  2. AGENT_DRY_RUN=1 ./run.sh"
echo "  3. ./run.sh"
