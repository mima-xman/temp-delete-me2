#!/bin/bash

set -e

echo "=========================================="
echo "GitHub Account Generator - Docker Startup"
echo "=========================================="
echo ""

# Start Tor in background
echo "Starting Tor..."
tor &

# Wait for Tor ports to open
echo "Waiting for Tor ports to open..."

MAX_WAIT=60
WAIT_COUNT=0

while ! nc -z 127.0.0.1 9151 2>/dev/null; do
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo "ERROR: Tor control port not available after ${MAX_WAIT} seconds"
        exit 1
    fi
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    
    # Print progress every 10 seconds
    if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
        echo "Still waiting for Tor... (${WAIT_COUNT}/${MAX_WAIT} sec)"
    fi
done

echo "Tor SOCKS port: $TOR_PORT"
echo "Tor Control port: $TOR_CONTROL_PORT"
echo ""
echo "Tor ports ready, starting GitHub Generator..."
echo "=========================================="
echo ""

# Start Xvfb for headless browser support (virtual display)
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# Run the GitHub generator script
exec python -u github_generator.py
