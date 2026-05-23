"""
Duolingo Streak Agent — OpenAI Agents SDK edition
Uses minhalvp/android-mcp-server via MCPServerStdio.
The SDK handles the tool loop, message history, and MCP bridging automatically.
"""

import asyncio
import os
import subprocess
import time

from openai import AsyncOpenAI
from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

# ── Config ─────────────────────────────────────────────────────────────────────
OPENCODE_GO_API_KEY = os.environ["OPENCODE_GO_API_KEY"]
DUOLINGO_EMAIL      = os.environ["DUOLINGO_EMAIL"]
DUOLINGO_PASSWORD   = os.environ["DUOLINGO_PASSWORD"]

ADB_HOST   = os.environ.get("ADB_HOST", "localhost")
ADB_PORT   = os.environ.get("ADB_PORT", "5555")
ADB_TARGET = f"{ADB_HOST}:{ADB_PORT}"

MCP_SERVER_DIR = os.path.abspath(
    os.environ.get("MCP_SERVER_DIR", "./android-mcp-server")
)

MAX_TURNS = 40
# ──────────────────────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """
You are controlling a real Android phone to complete one Duolingo lesson.
You have NO memory of previous sessions — every run is completely independent.

═══ TOOLS ═══
- get_screenshot     → see the current screen (call this after every tap)
- get_uilayout       → list all clickable elements with exact centre coordinates
- execute_adb_shell_command(command) → run any ADB shell command
- get_packages       → check installed apps

═══ YOUR TASK (3 phases) ═══

PHASE 1 — ASSESS & LOGIN IF NEEDED
Call get_screenshot first. Look at what's on screen:
- Login / welcome screen → log in with the credentials below
- Duolingo home (owl, streak count, lesson map) → skip to Phase 2
- Loading / splash → wait and call get_screenshot again
Credentials (only if login screen is visible):
  email: {email}
  password: {password}
  To type: execute_adb_shell_command with "input text 'VALUE'"

PHASE 2 — REACH THE HOME SCREEN
Use get_uilayout to find the Home tab and tap it if not already there.
Dismiss any popup, modal, or "welcome back" overlay first.

PHASE 3 — COMPLETE ONE LESSON
Tap the first available (non-locked) lesson on the skill tree or the daily
challenge if highlighted. Use get_uilayout to get exact coordinates — prefer
this over guessing from screenshots. After each tap call get_screenshot to
confirm the result before the next action. Tap the green CONTINUE/CHECK/NEXT
button after each answer. When the XP/completion screen appears, stop.

═══ TAPPING ═══
execute_adb_shell_command with command = "input tap X Y"
Use coordinates from get_uilayout where possible — more reliable than vision.
"""


async def run_agent() -> bool:
    # 1. Connect ADB to Docker emulator
    subprocess.run(["adb", "connect", ADB_TARGET], capture_output=True)
    print(f"[ADB] Connected to {ADB_TARGET}")
    time.sleep(2)

    # 2. Launch Duolingo
    subprocess.run(
        ["adb", "-s", ADB_TARGET, "shell",
         "monkey", "-p", "com.duolingo",
         "-c", "android.intent.category.LAUNCHER", "1"],
        capture_output=True,
    )
    print("[Agent] Duolingo launched — waiting 4s...")
    time.sleep(4)

    # 3. OpenCode Go client — OpenAI-compatible endpoint
    #    OpenAIChatCompletionsModel is required for non-OpenAI providers;
    #    the default Responses model only works with OpenAI's own API.
    client = AsyncOpenAI(
        api_key=OPENCODE_GO_API_KEY,
        base_url="https://opencode.ai/zen/go/v1",
    )
    model = OpenAIChatCompletionsModel(
        # vision confirmed working — swap via AGENT_MODEL env var if needed
        model=os.environ.get("AGENT_MODEL", "kimi-k2.6"),
        openai_client=client,
    )

    # 4. Spin up the android-mcp-server via stdio
    #    cache_tools_list=True avoids re-fetching the tool list on every turn
    async with MCPServerStdio(
        params={
            "command": "uv",
            "args": ["--directory", MCP_SERVER_DIR, "run", "server.py"],
            "env": {**os.environ, "ANDROID_SERIAL": ADB_TARGET},
        },
        cache_tools_list=True,
    ) as mcp:

        agent = Agent(
            name="duolingo-streak",
            instructions=SYSTEM_PROMPT.format(
                email=DUOLINGO_EMAIL,
                password=DUOLINGO_PASSWORD,
            ),
            mcp_servers=[mcp],
            model=model,
        )

        # 5. Run — the SDK handles the tool loop, message history, everything.
        #    Fresh context every time: Runner.run() always starts a new thread.
        result = await Runner.run(
            agent,
            input="Start. Call get_screenshot to see the current state and begin.",
            max_turns=MAX_TURNS,
        )

        print(f"\n[Agent] ✅ Done — {result.final_output}")
        return True


if __name__ == "__main__":
    success = asyncio.run(run_agent())
    exit(0 if success else 1)
