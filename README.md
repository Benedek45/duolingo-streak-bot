# Duolingo Streak Agent

Keeps your Duolingo streak alive by running a daily lesson inside a
Dockerised Android emulator, controlled by Kimi K2.5 (vision + tool-use)
via the OpenCode Go API.

```
┌─────────────┐   cron / CI   ┌──────────────┐   ADB tap   ┌───────────────────┐
│  run.sh     │ ────────────► │  agent.py    │ ──────────► │ Docker Android    │
│  (daily)    │               │  (Python)    │ ◄────────── │ (budtmo image)    │
└─────────────┘               │              │  screenshot │                   │
                               │  calls Kimi  │             │  Duolingo app     │
                               │  K2.5 API    │             └───────────────────┘
                               └──────────────┘
```

---

## Prerequisites

- Docker + Docker Compose
- Python 3.10+
- `adb` on your host machine (`brew install android-platform-tools` or `apt install adb`)
- An OpenCode Go subscription → API key from https://opencode.ai/auth

---

## Setup

### 1. Clone & configure

```bash
git clone <this-repo>
cd duolingo-agent
cp .env.example .env
# Edit .env — add your OpenCode Go key and Duolingo credentials
```

### 2. Start the Android emulator

```bash
docker compose up -d
```

The first boot takes **2-3 minutes**. Watch it boot at http://localhost:6080
(noVNC browser UI — no extra software needed).

### 3. Install Duolingo & log in (one-time)

```bash
# Wait until healthy
docker compose ps   # should show "healthy"

# Connect ADB
adb connect localhost:5555

# Option A: sideload APK (download from APKPure/APKMirror and put in ./apks/)
adb install apks/duolingo.apk

# Option B: install from Play Store via the noVNC browser UI at localhost:6080
# (PICO GAPPS are pre-installed in the budtmo image)
```

Log in to Duolingo **manually once** via the noVNC UI.
The `android-data` Docker volume persists your session — you won't need to log in again.

### 4. Install Python deps

```bash
pip install requests
```

### 5. Test a run

```bash
chmod +x run.sh
./run.sh
```

You should see the agent taking screenshots and tapping through a lesson.

---

## Scheduling (daily cron)

```bash
crontab -e
```

Add (runs at 9 AM every day):

```
0 9 * * * cd /path/to/duolingo-agent && ./run.sh >> logs/agent.log 2>&1
```

Or use GitHub Actions with a `schedule` trigger if you run this in CI.

---

## How it works

1. `run.sh` loads `.env` and waits for ADB to be ready.
2. `agent.py` connects to the emulator, launches Duolingo via `adb shell monkey`.
3. In a loop (max 40 turns):
   - Takes a screenshot via `adb screencap`
   - Sends it to Kimi K2.5 as a base64 image with "what to do next?"
   - Kimi replies with `{"action": "tap", "x": 540, "y": 1200, "reason": "..."}` or `{"action": "done"}`
   - Agent executes the tap with ±6px jitter and 0.4–1.1s random delay
4. Exits with code 0 on success, 1 on failure.

---

## Notes

- **Streak freeze safety**: if the agent fails (network issue, unexpected screen),
  it exits with code 1. You can set up a notification on failure so you can do it manually.
- **CAPTCHA**: Kimi K2.5 handles simple image CAPTCHAs. If Duolingo serves a hard
  CAPTCHA, the agent may fail — this is rare for the mobile app.
- **KVM**: The `budtmo/docker-android` image uses KVM for hardware acceleration.
  Make sure KVM is available on your host (`ls /dev/kvm`). On most Linux hosts this
  works out of the box. On a VPS, check that nested virtualisation is enabled.
- **No KVM fallback**: If KVM isn't available, replace the image with
  `budtmo/docker-android:emulator_14.0_noKVM` (slower but works anywhere).
