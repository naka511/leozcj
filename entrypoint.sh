#!/bin/bash
set -e

rm -f /tmp/.X99-lock

Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp &
XVFB_PID=$!

sleep 1
echo "Xvfb started (DISPLAY=:99, PID=$XVFB_PID)"

exec "$@"
