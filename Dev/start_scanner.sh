#!/bin/bash
# 🦅🌍 YJCryptoSignal — Universal AI Scanner (Standalone)
set -e

cd /root/projects/YJCryptoSignal/Dev

# Clean up stale locks
rm -f /tmp/yjcryptosignal-scanner.lock

# Detect Python: prefer venv, fallback to system python3
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
else
    echo "ERROR: python3 not found" >&2
    exit 1
fi
echo "Using Python: $PYTHON"

# Exec scanner and redirect stdout/stderr to standard scanner.log
exec "$PYTHON" -u run_scanner.py >> /root/projects/YJCryptoSignal/Dev/logs/scanner.log 2>&1
