# Duolingo Streak Agent

Keeps a Duolingo streak alive from a browser session. No Android, ADB,
emulator, Docker, Waydroid, or Cuttlefish is used.

The agent uses Microsoft's official `@playwright/mcp` server through the OpenAI
Agents SDK. That means the model receives real MCP browser tools in context,
including their names, descriptions, and schemas.

## Prerequisites

- Python 3.10+
- Node.js 18+ with `npx`
- Chromium installed on the machine (`/usr/bin/chromium` on Raspberry Pi OS)
- An OpenCode Go API key from https://opencode.ai/auth

## Setup

```bash
./setup.sh
cp .env.example .env
```

Fill `.env` with:

```bash
OPENCODE_GO_API_KEY=...
DUOLINGO_EMAIL=...
DUOLINGO_PASSWORD=...
```

Optional settings:

```bash
AGENT_MODEL=deepseek-v4-flash
VISION_MODEL=qwen3.5-plus
MAX_TURNS=150
MODEL_MAX_TOKENS=1200
VISION_MAX_TOKENS=500
MODEL_INCLUDE_USAGE=true
QWEN_ENABLE_THINKING=false
MCP_VISION=false
BROWSER_EXECUTABLE=/usr/bin/chromium
BROWSER_HEADLESS=true
BROWSER_USER_DATA_DIR=.browser-profile
DUOLINGO_URL=https://www.duolingo.com
DUOLINGO_ALLOWED_HOSTS=duolingo.com,.duolingo.com,d1vq87e9lcf771.cloudfront.net,d35aaqx5ub95lt.cloudfront.net,d2pur3iezf4d1j.cloudfront.net,d3kwyfyztuo0xs.cloudfront.net
```

## Run

```bash
./run.sh
```

For an MCP smoke test that starts the Playwright MCP server and lists available
browser tools without calling the model:

```bash
AGENT_DRY_RUN=1 ./run.sh
```

## How It Works

1. `agent.py` generates `mcp/playwright-mcp.generated.json` from `.env`.
2. The Agents SDK starts `npx --yes @playwright/mcp@latest --config ...` over stdio.
3. The agent receives Playwright MCP tools such as `browser_navigate`,
   `browser_snapshot`, `browser_click`, and `browser_fill_form`.
   Unsafe/file-transfer tools are filtered out before the model sees them.
4. Chromium is configured to look like Windows 11 Chrome with a Windows user
   agent, `navigator.platform`, `navigator.userAgentData`, language, hardware,
   `navigator.webdriver`, screen, and WebGL spoofing.
5. A Playwright route guard aborts browser requests whose host is not in
   `DUOLINGO_ALLOWED_HOSTS`. The MCP server's own `allowedOrigins` option is also
   set, but the route guard is the stricter fail-closed protection.
6. Browser profile data persists in `.browser-profile`.
7. A compact page helper, `window.__duolingoCompactView()`, is injected so the
   model can inspect Duolingo without repeatedly sending full YAML snapshots.
8. The main browser agent uses `AGENT_MODEL` for cheap text/tool control.
   If visual understanding is truly necessary, it can call
   `analyze_latest_screenshot_with_qwen`, which sends only the latest screenshot
   to `VISION_MODEL`.
9. MCP outputs are stored under `logs/`. MCP vision/image responses stay disabled
   by default; the separate Qwen vision fallback is used only on demand.

## Scheduling

Add this to `crontab -e` to run daily at 9 AM:

```cron
0 9 * * * cd /home/benedek/duolingo && ./run.sh >> logs/agent.log 2>&1
```

If you want to see the browser on the desktop, set `BROWSER_HEADLESS=false` in
`.env` and run it from a graphical session.
