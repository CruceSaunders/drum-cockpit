#!/bin/bash
# run.sh — set up venv (first run) and execute the right script
# Usage:
#   ./run.sh --drum-test        # visual tester for the ESP32+drum hardware (USB serial)
#   ./run.sh --sound-test       # tkinter panel, each pad plays a unique sound
#   ./run.sh --test-keys        # full test panel with watchdog + actions
#   ./run.sh --calibrate        # identify pad MIDI note numbers (drum kit's MIDI mode)
#   ./run.sh                    # normal mode

set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Setting up Python virtual environment (first time, ~30 sec)..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet pynput pyserial pyobjc-framework-Quartz
    # mido/python-rtmidi are optional — only needed if using the kit's MIDI output.
    # They sometimes have install/runtime issues, so we don't fail on them.
    .venv/bin/pip install --quiet mido python-rtmidi 2>/dev/null || \
        echo "(Note: mido/python-rtmidi install issue — that's ok, we're using ESP32 path)"
    echo "Done."
    echo
fi

# Route --drum-test to the standalone visual tester
if [ "$1" = "--drum-test" ]; then
    .venv/bin/python3 drum_visual_test.py
else
    .venv/bin/python3 drummer.py "$@"
fi
