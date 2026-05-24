"""
test_model.py — sanity check for OpenCode Go models
Tests: API key auth, text response, image/vision support

Usage:
  python test_model.py                         # tests deepseek-v4-flash (default)
  python test_model.py qwen3.6-plus
  python test_model.py kimi-k2.6 qwen3.6-plus deepseek-v4-flash
  python test_model.py --all
  python test_model.py --debug qwen3.6-plus    # show full raw API response
"""

import base64, json, os, struct, sys, zlib
import requests

CHAT_URL = "https://opencode.ai/zen/go/v1/chat/completions"
MSG_URL  = "https://opencode.ai/zen/go/v1/messages"

# MiniMax uses Anthropic messages format, everything else uses OpenAI chat completions
ANTHROPIC_FORMAT = {"minimax-m2.5", "minimax-m2.7"}

ALL_MODELS = [
    "kimi-k2.5", "kimi-k2.6",
    "glm-5", "glm-5.1",
    "minimax-m2.5", "minimax-m2.7",
    "mimo-v2.5", "mimo-v2.5-pro",
    "qwen3.5-plus", "qwen3.6-plus",
    "deepseek-v4-pro", "deepseek-v4-flash",
]


# ── Valid 32x32 solid red PNG (RGB, no alpha) ──────────────────────────────────
def _make_red_png_b64() -> str:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    w = h = 32
    # Color type 2 = RGB, 8 bits per channel → 3 bytes per pixel
    # Each row: 1 filter byte (0x00) + w*3 pixel bytes
    row  = b"\x00" + b"\xFF\x00\x00" * w   # filter=None, pure red pixels
    raw  = row * h
    png  = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode()

IMAGE_B64  = _make_red_png_b64()
IMAGE_URL  = f"data:image/png;base64,{IMAGE_B64}"


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _post(url, api_key, body, extra_headers=None, timeout=30):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    r = requests.post(url, headers=headers, json=body, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = {"_raw": r.text}
    return r.status_code, data


def post_openai(api_key, model, messages, timeout=30):
    return _post(CHAT_URL, api_key,
                 {"model": model, "max_tokens": 128, "messages": messages},
                 timeout=timeout)


def post_anthropic(api_key, model, messages, timeout=30):
    # Convert OpenAI-style content blocks → Anthropic format
    converted = []
    for m in messages:
        role    = m["role"]
        content = m["content"]
        if isinstance(content, str):
            converted.append({"role": role, "content": content})
        else:
            parts = []
            for block in content:
                if block["type"] == "image_url":
                    b64 = block["image_url"]["url"].split(",", 1)[1]
                    parts.append({"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": b64
                    }})
                elif block["type"] == "text":
                    parts.append({"type": "text", "text": block["text"]})
            converted.append({"role": role, "content": parts})

    return _post(MSG_URL, api_key,
                 {"model": model, "max_tokens": 128, "messages": converted},
                 extra_headers={"anthropic-version": "2023-06-01"},
                 timeout=timeout)


def extract_reply(data, anthropic=False):
    if anthropic:
        return data["content"][0]["text"].strip()
    return data["choices"][0]["message"]["content"].strip()


# ── Per-model test ─────────────────────────────────────────────────────────────

def test_model(api_key, model, debug=False):
    use_anthropic = model in ANTHROPIC_FORMAT
    post    = post_anthropic if use_anthropic else post_openai
    extract = lambda d: extract_reply(d, anthropic=use_anthropic)
    result  = {"model": model, "text": False, "vision": False,
               "vision_reply": None, "error": None}

    # ── 1. Text ────────────────────────────────────────────────────────────────
    status, data = post(api_key, model,
                        [{"role": "user", "content": "Reply with the single word PONG."}])
    if debug:
        print(f"\n  [text] status={status}")
        print(f"  [text] response=\n{json.dumps(data, indent=2)}")

    if status == 401:
        result["error"] = "API key rejected (401)"
        return result
    if status == 404:
        result["error"] = "Model not found (404)"
        return result
    if status != 200:
        result["error"] = f"HTTP {status}: {str(data)[:200]}"
        return result

    try:
        result["text"] = bool(extract(data))
    except Exception as e:
        result["error"] = f"Unexpected text response shape: {e} | {str(data)[:200]}"
        return result

    # ── 2. Vision ──────────────────────────────────────────────────────────────
    vision_msg = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": IMAGE_URL}},
        {"type": "text",
         "text": "This image is a single solid colour. What colour is it? Reply with one word."},
    ]}]

    status, data = post(api_key, model, vision_msg, timeout=40)
    if debug:
        print(f"\n  [vision] status={status}")
        print(f"  [vision] response=\n{json.dumps(data, indent=2)}")

    if status == 200:
        try:
            reply = extract(data).lower()
            result["vision_reply"] = reply
            colour_words = {"red", "crimson", "scarlet", "maroon", "rouge"}
            result["vision"] = any(w in reply for w in colour_words)
        except Exception:
            result["vision"] = False
    else:
        if debug:
            print(f"  [vision] non-200: {str(data)[:300]}")

    return result


# ── Runner ─────────────────────────────────────────────────────────────────────

PASS = "✅"; FAIL = "❌"

def run(models, api_key, debug=False):
    print(f"\nOpenCode Go model tester")
    print(f"Chat endpoint : {CHAT_URL}")
    print(f"Msg  endpoint : {MSG_URL}  (MiniMax only)")
    print(f"Models        : {', '.join(models)}")
    print("-" * 60)

    vision_capable = []

    for model in models:
        print(f"\n{model}  ({'anthropic fmt' if model in ANTHROPIC_FORMAT else 'openai fmt'})")
        r = test_model(api_key, model, debug=debug)

        if r["error"]:
            print(f"  {FAIL} {r['error']}")
            continue

        print(f"  {PASS if r['text']   else FAIL} Text / API key")
        if r["vision"]:
            print(f"  {PASS} Vision  (model said: '{r['vision_reply']}')")
            vision_capable.append(model)
        else:
            reply_hint = f"  model said: '{r['vision_reply']}'" if r["vision_reply"] else ""
            print(f"  {FAIL} Vision{reply_hint}")

    print("\n" + "-" * 60)
    if vision_capable:
        print(f"Vision-capable: {', '.join(vision_capable)}")
        print(f"\nRecommended for agent.py: {vision_capable[0]}")
    else:
        print("No vision support confirmed on OpenCode Go.")
        print("Alternatives with vision + cheap pricing:")
        print("  Moonshot AI  — api.moonshot.ai/v1        model: kimi-k2.6")
        print("  Google       — generativelanguage...      model: gemini-2.5-flash")


if __name__ == "__main__":
    api_key = os.environ.get("OPENCODE_GO_API_KEY", "")
    if not api_key:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            for line in open(env_path):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "OPENCODE_GO_API_KEY":
                        api_key = v.strip()

    if not api_key:
        print("Error: OPENCODE_GO_API_KEY not set. Export it or add it to .env")
        sys.exit(1)

    args     = sys.argv[1:]
    debug    = "--debug" in args
    args     = [a for a in args if a != "--debug"]
    models   = ALL_MODELS if "--all" in args else (args or ["deepseek-v4-flash"])

    run(models, api_key, debug=debug)
