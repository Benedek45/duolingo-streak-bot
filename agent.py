"""
Duolingo Streak Agent - Playwright MCP edition.

The Python code runs the OpenAI Agents SDK and gives the model Microsoft's
official Playwright MCP server as its browser tool provider.
"""

import asyncio
import base64
import json
import mimetypes
import os
import shutil
from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from openai.resources.chat.completions import AsyncCompletions
from agents import Agent, ModelSettings, Runner, function_tool
from agents.mcp import MCPServerStdio
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent, RunItemStreamEvent


ROOT = Path(__file__).resolve().parent
MCP_DIR = ROOT / "mcp"
LOG_DIR = ROOT / "logs"
CONFIG_PATH = MCP_DIR / "playwright-mcp.generated.json"


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def find_browser() -> str:
    configured = os.environ.get("BROWSER_EXECUTABLE")
    if configured:
        return configured
    for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome executable found. Install Chromium or set BROWSER_EXECUTABLE.")


load_dotenv()

OPENCODE_GO_API_KEY = os.environ["OPENCODE_GO_API_KEY"]
DUOLINGO_EMAIL = os.environ["DUOLINGO_EMAIL"]
DUOLINGO_PASSWORD = os.environ["DUOLINGO_PASSWORD"]

DUOLINGO_URL = os.environ.get("DUOLINGO_URL", "https://www.duolingo.com")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "deepseek-v4-flash")
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen3.5-plus")
MAX_TURNS = int(os.environ.get("MAX_TURNS", "150"))
MODEL_MAX_TOKENS = int(os.environ.get("MODEL_MAX_TOKENS", "1200"))
VISION_MAX_TOKENS = int(os.environ.get("VISION_MAX_TOKENS", "500"))
API_RETRIES = int(os.environ.get("API_RETRIES", "5"))
API_RETRY_DELAY = float(os.environ.get("API_RETRY_DELAY", "3"))
MODEL_INCLUDE_USAGE = env_bool("MODEL_INCLUDE_USAGE", True)
QWEN_ENABLE_THINKING = env_bool("QWEN_ENABLE_THINKING", False)
DRY_RUN = env_bool("AGENT_DRY_RUN", False)

WINDOW_WIDTH = int(os.environ.get("BROWSER_WIDTH", "1366"))
WINDOW_HEIGHT = int(os.environ.get("BROWSER_HEIGHT", "768"))
CHROME_MAJOR = os.environ.get("BROWSER_CHROME_MAJOR", "136")
WINDOWS_CHROME_UA = os.environ.get(
    "BROWSER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/{CHROME_MAJOR}.0.0.0 Safari/537.36",
)
HEADLESS = env_bool(
    "BROWSER_HEADLESS",
    not bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
)
USER_DATA_DIR = Path(os.environ.get("BROWSER_USER_DATA_DIR", ROOT / ".browser-profile"))
MCP_VISION = env_bool("MCP_VISION", False)

# Add extra hosts with DUOLINGO_ALLOWED_HOSTS if Duolingo introduces a new CDN/auth
# host. Host entries may be exact names, suffixes prefixed by a dot, or "*" to
# allow all normal http/https web requests.
DEFAULT_ALLOWED_HOSTS = [
    "duolingo.com",
    ".duolingo.com",
    "d1vq87e9lcf771.cloudfront.net",
    "d35aaqx5ub95lt.cloudfront.net",
    "d2pur3iezf4d1j.cloudfront.net",
    "d3kwyfyztuo0xs.cloudfront.net",
]
ALLOWED_HOSTS = [
    host.strip().lower()
    for host in os.environ.get("DUOLINGO_ALLOWED_HOSTS", ",".join(DEFAULT_ALLOWED_HOSTS)).split(",")
    if host.strip()
]
ALLOW_ALL_WEB = "*" in ALLOWED_HOSTS

BLOCKED_MCP_TOOLS = {
    "browser_run_code_unsafe",
    "browser_file_upload",
    "browser_drop",
}


SYSTEM_PROMPT = """
You control Duolingo in a desktop Chrome browser through the Playwright MCP tools.
Complete any one Duolingo daily task, quest, practice, story, or lesson to keep
the streak alive, then stop. It does not matter which task you choose; if there
are multiple options, pick the first/easiest actionable one and continue. It is
OK if the task was already completed before; repeat a completed lesson/practice
if that is the fastest available option.

The available browser tools are provided by MCP. Use the browser_* tools directly:
navigate, snapshot, click, type, press key, wait, screenshot, and related tools.
Prefer accessibility snapshots and exact element refs over coordinate clicks.

Cost and context rules:
- Keep messages short. Do not narrate obvious steps.
- Prefer browser_evaluate with `() => window.__duolingoCompactView()` to inspect
  the page. It returns compact visible text and actionable controls.
- Do not call browser_snapshot after every click. Full snapshots are expensive.
  Use browser_snapshot only when compact view is insufficient or a ref is stale.
- Do not take screenshots unless there is a CAPTCHA/security challenge or the
  page cannot be understood from compact text.
- If visual understanding is truly necessary, call browser_take_screenshot first,
  then call analyze_latest_screenshot_with_qwen with one short question. This is
  expensive; use it only as a fallback.

Batching:
- Batch simple deterministic actions when the answer/action sequence is already
  clear, especially tapping multiple word-bank tokens in order or pressing
  Continue/Check after an answer is complete.
- For known word-bank sequences, prefer one browser_evaluate call that clicks
  all known token selectors in order, then click Check/Continue. Example: click
  token A, token B, token C in one evaluate call instead of three separate
  browser_click calls.
- Use a fresh compact view before deciding the batch; use a snapshot only if the
  compact view is insufficient. Do not batch across unknown page transitions or
  across a state that needs feedback from Duolingo.
- If one item in a batch might be missing or ambiguous, stop batching and use
  single tool calls with a new snapshot.
- After you submit an answer and Duolingo shows correct-answer feedback, the
  browser may automatically click TOVÁBB after a short random delay. Do not spend
  a separate model turn clicking TOVÁBB from correct-answer feedback; wait briefly
  and inspect the next question instead. Still handle lesson-complete/reward
  screens yourself.

Important environment constraints:
- The browser is configured to look like Chrome on Windows 11.
- Browser network requests may be broad/permissive when `DUOLINGO_ALLOWED_HOSTS=*`
  is configured so reCAPTCHA and external auth scripts can load. Still do not
  browse unrelated sites except auth/CAPTCHA resources required by Duolingo.
- If a required Duolingo/auth asset is blocked, report the blocked host.

Credentials, only if the account is logged out:
- email: {email}
- password: {password}

Login rules:
- Prefer reusing an existing logged-in browser session. Only enter credentials if
  Duolingo clearly shows the logged-out/login form.
- During login, do not use browser_fill_form for credentials. Simulate normal
  typing with browser_evaluate and the injected helper:
  `async () => await window.__duolingoHumanType("selector", "value")`.
- Type the email first, pause/check briefly, then type the password.
- Before clicking the final login/submit button, call browser_take_screenshot,
  then call analyze_latest_screenshot_with_qwen with a short question asking
  whether this is the normal login form, which visible submit button should be
  clicked, and whether there is an overlay/hidden alternate button or account
  creation mode. Use that answer to choose the button.
- If Duolingo says the account does not exist or the login UI is ambiguous, stop
  and report the exact visible message instead of repeatedly retrying.

Task flow:
1. Navigate to {url}.
2. If logged out, log in with the credentials above.
3. Dismiss cookie banners, notification prompts, modals, ads, or free-trial popups.
4. Reach the learning/home path and start any visible unlocked or completed
   skill-path node, daily task, quest, practice, story, or normal lesson. Do not
   spend time deciding between tasks. Repeating an already completed lesson is
   allowed and preferred over searching.
5. Answer prompts using the page content. Continue/check/next until an XP,
   streak, daily-task-complete, or lesson-complete screen appears.
6. Stop immediately once one task or lesson is complete.

Task selection rules:
- Try at most 3 start attempts total.
- Find the task in the TANULÁS section (`/learn`). Do not use the left/sidebar
  GYAKORLÁS menu item because that opens Practice Hub and is usually not useful.
  This is different from the GYAKORLÁS: +5 PONT button/link inside a TANULÁS
  skill-path popup; that one is useful and should be clicked when visible because
  it starts a repeatable lesson/practice task.
- First try the first visible unlocked/completed skill-path lesson node on /learn.
- If that does not open a task within 10 seconds, try the first visible story or
  practice node.
- If that also fails, use Practice Hub or Quests and click the first actionable
  task, including tasks already done before.
- Do not loop between pages looking for a better task. After 3 failed start
  attempts, stop and report what failed.

Return success only after one task or lesson is complete. If there is a CAPTCHA,
security challenge, payment wall, or blocked-host issue, stop and explain the reason.
""".strip()


def redact(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(to_plain_data(value), default=str)
    replacements = {
        OPENCODE_GO_API_KEY: "<opencode-api-key>",
        DUOLINGO_PASSWORD: "<duolingo-password>",
        DUOLINGO_EMAIL: "<duolingo-email>",
    }
    for secret, label in replacements.items():
        if secret:
            text = text.replace(secret, label)
    return text


def to_plain_data(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_unset=True)
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_data(item) for item in value]
    return value


def short_text(value: object, limit: int = 2400) -> str:
    text = redact(value)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... <truncated {len(text) - limit} chars>"


def raw_attr(value: object, *names: str) -> object | None:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return None


def tool_call_summary(item: object) -> str:
    raw = raw_attr(item, "raw_item") or item
    name = raw_attr(item, "tool_name") or raw_attr(raw, "name") or raw_attr(raw, "tool_name")
    title = raw_attr(item, "title") or raw_attr(raw, "title")
    arguments = raw_attr(raw, "arguments", "input")
    label = name or title or type(raw).__name__
    if arguments is None:
        return str(label)
    return f"{label} {short_text(arguments, 1200)}"


async def print_streamed_events(result) -> None:
    print("[Agent] Streaming model output and browser tool activity. Hidden chain-of-thought is not exposed.")
    last_usage = None
    model_text_buffer = ""
    secret_tail = max((len(secret) for secret in [OPENCODE_GO_API_KEY, DUOLINGO_PASSWORD, DUOLINGO_EMAIL] if secret), default=0) + 16

    def flush_model_text(force: bool = False) -> None:
        nonlocal model_text_buffer
        if not model_text_buffer:
            return
        keep = 0 if force else secret_tail
        if len(model_text_buffer) <= keep:
            return
        printable = model_text_buffer[:-keep] if keep else model_text_buffer
        model_text_buffer = model_text_buffer[-keep:] if keep else ""
        print(redact(printable), end="", flush=True)

    async for event in result.stream_events():
        if isinstance(event, RawResponsesStreamEvent):
            usage = getattr(event.data, "usage", None)
            if usage is not None and usage != last_usage:
                last_usage = usage
                flush_model_text(force=True)
                print(f"\n[Usage] {short_text(usage, 1000)}", flush=True)
            delta = getattr(event.data, "delta", None)
            if isinstance(delta, str) and delta:
                model_text_buffer += delta
                flush_model_text()
            continue

        flush_model_text(force=True)

        if isinstance(event, AgentUpdatedStreamEvent):
            print(f"\n[Agent] switched to {event.new_agent.name}", flush=True)
            continue

        if not isinstance(event, RunItemStreamEvent):
            continue

        if event.name == "tool_called":
            print(f"\n[Tool call] {tool_call_summary(event.item)}", flush=True)
        elif event.name == "tool_output":
            output = raw_attr(event.item, "output")
            print(f"\n[Tool output] {short_text(output)}", flush=True)
        elif event.name == "mcp_list_tools":
            print("\n[MCP] listed browser tools", flush=True)
        elif event.name == "reasoning_item_created":
            print("\n[Reasoning] hidden by the model/API; showing actions and final output instead", flush=True)
        elif event.name == "message_output_created":
            print("\n[Message]", flush=True)

    flush_model_text(force=True)


def allowed_origins() -> list[str]:
    if ALLOW_ALL_WEB:
        return []
    origins = {"https://duolingo.com", "https://www.duolingo.com"}
    for host in ALLOWED_HOSTS:
        if host.startswith("."):
            continue
        origins.add(f"https://{host}")
    return sorted(origins)


def write_mcp_config() -> None:
    MCP_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    browser_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--disable-infobars",
        f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
        "--lang=en-US",
    ]

    config = {
        "browser": {
            "browserName": "chromium",
            "userDataDir": str(USER_DATA_DIR),
            "launchOptions": {
                "headless": HEADLESS,
                "executablePath": find_browser(),
                "args": browser_args,
            },
            "contextOptions": {
                "userAgent": WINDOWS_CHROME_UA,
                "locale": "en-US",
                "timezoneId": os.environ.get("BROWSER_TIMEZONE", "America/New_York"),
                "viewport": {"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                "screen": {"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                "colorScheme": "light",
            },
            "initScript": [
                str(MCP_DIR / "windows-chrome-spoof.js"),
                str(MCP_DIR / "duolingo-compact-view.js"),
                str(MCP_DIR / "duolingo-human-type.js"),
                str(MCP_DIR / "duolingo-auto-continue.js"),
            ],
            "initPage": [str(MCP_DIR / "duolingo-network-guard.ts")],
        },
        "capabilities": ["core"] + (["vision"] if MCP_VISION else []),
        "outputDir": str(LOG_DIR),
        "timeouts": {"action": 10000, "navigation": 90000},
    }
    if not ALLOW_ALL_WEB:
        config["network"] = {"allowedOrigins": allowed_origins()}
    if MCP_VISION:
        config["imageResponses"] = "allow"
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")


def model_settings() -> ModelSettings:
    extra_body = {}
    if AGENT_MODEL.startswith("qwen"):
        # Qwen hybrid-thinking models can spend many hidden reasoning tokens.
        # Keep this off for browser automation unless explicitly enabled.
        extra_body["enable_thinking"] = QWEN_ENABLE_THINKING
    return ModelSettings(
        max_tokens=MODEL_MAX_TOKENS,
        include_usage=MODEL_INCLUDE_USAGE,
        parallel_tool_calls=False,
        extra_body=extra_body or None,
    )


def is_empty_assistant_message(message: dict) -> bool:
    if message.get("role") != "assistant" or message.get("tool_calls"):
        return False
    content = message.get("content")
    return content is None or content == "" or content == []


def plain_tool_content(content: object) -> object:
    if not isinstance(content, list):
        return content
    text_parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text_parts.append(str(item.get("text", "")))
        else:
            text_parts.append(json.dumps(item, default=str))
    return "\n".join(part for part in text_parts if part)


def sanitize_deepseek_messages(messages: list[dict]) -> list[dict]:
    sanitized = []
    for message in messages:
        if is_empty_assistant_message(message):
            continue
        if message.get("role") == "tool" and isinstance(message.get("content"), list):
            message = {**message, "content": plain_tool_content(message["content"])}
        sanitized.append(message)
    return sanitized


def should_retry_api_error(error: Exception) -> bool:
    if isinstance(error, (APIConnectionError, APITimeoutError)):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code == 429 or error.status_code >= 500
    return False


def install_deepseek_compat() -> None:
    if getattr(AsyncCompletions.create, "_duolingo_deepseek_compat", False):
        return
    original_create = AsyncCompletions.create

    async def create_with_deepseek_compat(self, *args, **kwargs):
        model = str(kwargs.get("model") or "")
        if model.startswith("deepseek") and isinstance(kwargs.get("messages"), list):
            kwargs = {**kwargs, "messages": sanitize_deepseek_messages(kwargs["messages"])}
        last_error = None
        for attempt in range(1, API_RETRIES + 1):
            try:
                return await original_create(self, *args, **kwargs)
            except Exception as error:
                last_error = error
                if attempt >= API_RETRIES or not should_retry_api_error(error):
                    raise
                status = getattr(error, "status_code", type(error).__name__)
                delay = API_RETRY_DELAY * attempt
                print(f"\n[API retry] {model or 'model'} failed with {status}; retry {attempt}/{API_RETRIES - 1} in {delay:.1f}s", flush=True)
                await asyncio.sleep(delay)
        raise last_error

    create_with_deepseek_compat._duolingo_deepseek_compat = True
    AsyncCompletions.create = create_with_deepseek_compat


def latest_screenshot() -> Path | None:
    candidates = []
    for pattern in ("*.png", "*.jpg", "*.jpeg", "**/*.png", "**/*.jpg", "**/*.jpeg"):
        candidates.extend(LOG_DIR.glob(pattern))
    files = [path for path in candidates if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


@function_tool
async def analyze_latest_screenshot_with_qwen(question: str) -> str:
    """Analyze the latest browser screenshot with the Qwen vision model.

    Use only after calling browser_take_screenshot and only when DOM text or
    accessibility snapshots are not enough, such as CAPTCHA or image-only tasks.

    Args:
        question: Short, specific question about the screenshot.
    """
    image_path = latest_screenshot()
    if image_path is None:
        return "No screenshot file was found. Call browser_take_screenshot first, then retry this tool."

    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    client = AsyncOpenAI(api_key=OPENCODE_GO_API_KEY, base_url="https://opencode.ai/zen/go/v1")
    request = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Answer this Duolingo browser screenshot question concisely. "
                            "Do not describe irrelevant UI. Question: " + question
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}",
                            "detail": "low",
                        },
                    },
                ],
            }
        ],
        "max_tokens": VISION_MAX_TOKENS,
    }
    if VISION_MODEL.startswith("qwen"):
        request["extra_body"] = {"enable_thinking": False}
    response = await client.chat.completions.create(**request)
    answer = response.choices[0].message.content or ""
    return f"Qwen vision answer from {image_path.name}: {answer.strip()}"


def mcp_params() -> dict:
    return {
        "command": "npx",
        "args": ["--yes", "@playwright/mcp@latest", "--config", str(CONFIG_PATH)],
        "env": {
            **os.environ,
            "CHROME_MAJOR": CHROME_MAJOR,
            "BROWSER_USER_AGENT": WINDOWS_CHROME_UA,
            "BROWSER_WIDTH": str(WINDOW_WIDTH),
            "BROWSER_HEIGHT": str(WINDOW_HEIGHT),
            "DUOLINGO_ALLOWED_HOSTS": ",".join(ALLOWED_HOSTS),
        },
    }


def cleanup_mcp_artifacts() -> None:
    # MCP snapshots can include login form values. Keep the main transcript only.
    for pattern in ["page-*.yml", "console-*.log", "page-*.png"]:
        for path in LOG_DIR.glob(pattern):
            try:
                path.unlink()
            except OSError:
                pass


async def dry_run() -> bool:
    write_mcp_config()
    async with MCPServerStdio(
        params=mcp_params(),
        cache_tools_list=True,
        client_session_timeout_seconds=90,
        tool_filter={"blocked_tool_names": sorted(BLOCKED_MCP_TOOLS)},
    ) as mcp:
        tools = await mcp.list_tools()
        print("[MCP] Playwright MCP started")
        print(f"[MCP] config: {CONFIG_PATH}")
        print(f"[MCP] allowed hosts: {', '.join(ALLOWED_HOSTS)}")
        print(f"[MCP] tools ({len(tools)}):")
        for tool in tools:
            print(f"  - {tool.name}")
    return True


async def run_agent() -> bool:
    write_mcp_config()
    if DRY_RUN:
        return await dry_run()

    install_deepseek_compat()
    client = AsyncOpenAI(api_key=OPENCODE_GO_API_KEY, base_url="https://opencode.ai/zen/go/v1")
    model = OpenAIChatCompletionsModel(model=AGENT_MODEL, openai_client=client)

    try:
        async with MCPServerStdio(
            params=mcp_params(),
            cache_tools_list=True,
            client_session_timeout_seconds=90,
            tool_filter={"blocked_tool_names": sorted(BLOCKED_MCP_TOOLS)},
        ) as mcp:
            agent = Agent(
                name="duolingo-browser-streak",
                instructions=SYSTEM_PROMPT.format(
                    email=DUOLINGO_EMAIL,
                    password=DUOLINGO_PASSWORD,
                    url=DUOLINGO_URL,
                ),
                tools=[analyze_latest_screenshot_with_qwen],
                mcp_servers=[mcp],
                model=model,
                model_settings=model_settings(),
            )
            result = Runner.run_streamed(
                agent,
                input="Start now. Navigate to Duolingo, complete any available daily task or lesson, then stop.",
                max_turns=MAX_TURNS,
            )
            await print_streamed_events(result)
            print(f"\n[Agent] {redact(result.final_output)}")
            return True
    finally:
        cleanup_mcp_artifacts()


if __name__ == "__main__":
    success = asyncio.run(run_agent())
    raise SystemExit(0 if success else 1)
