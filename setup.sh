#!/usr/bin/env bash
# setup.sh — one-time setup for the Duolingo agent
set -euo pipefail

echo "=== 1. Cloning android-mcp-server ==="
if [ ! -d "android-mcp-server" ]; then
  git clone https://github.com/minhalvp/android-mcp-server.git
else
  echo "  Already cloned, skipping."
fi

echo "=== 2. Installing MCP server Python deps ==="
cd android-mcp-server
uv python install 3.11
uv sync
cd ..

echo "=== 3. Writing android-mcp-server/config.yaml ==="
cat > android-mcp-server/config.yaml << 'YAML'
device:
  name: "localhost:5555"
YAML

echo "=== 4. Installing agent Python deps ==="
pip install openai-agents --break-system-packages

echo ""
echo "Done. Next steps:"
echo "  1. cp .env.example .env && fill in your keys"
echo "  2. docker compose up -d"
echo "  3. Open http://localhost:6080, install Duolingo, log in once"
echo "  4. ./run.sh"
