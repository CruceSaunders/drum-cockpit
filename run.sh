#!/bin/bash
# run.sh — set up venv (first run) and execute drummer.py with any args
# Usage:
#   ./run.sh                    # normal mode (needs drum kit)
#   ./run.sh --sound-test       # sound test — no drum, no permissions needed
#   ./run.sh --test-keys        # full test panel with watchdog + actions
#   ./run.sh --calibrate        # identify pad MIDI note numbers

set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Setting up Python virtual environment (first time, ~30 sec)..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet mido python-rtmidi pynput
    echo "Done. Running drummer.py..."
    echo
fi

.venv/bin/python3 drummer.py "$@"
