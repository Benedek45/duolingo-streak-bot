#!/usr/bin/env bash
# Run the Duolingo agent once, randomly during the 8-9 AM hour.

set -euo pipefail

cd /home/benedek/duolingo
mkdir -p logs

sleep "$(( RANDOM % 3600 ))"

# Run like a normal visible desktop browser when the Pi desktop session is active.
export BROWSER_HEADLESS=false
export DISPLAY=${DISPLAY:-:0}
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/1000}
export XAUTHORITY=${XAUTHORITY:-/home/benedek/.Xauthority}

./run.sh
