# Drum Cockpit

A drum-controlled control surface for AI-assisted coding. Built for the Stasis Hardware Hackathon.

## What it does

A 9-pad electronic drum kit (KVONE) becomes a multi-mode input device for vibe coding:

- **Coding mode** — drum pads trigger AI tools (Wispr Flow dictation, terminal shortcuts, Enter, Ctrl+C, etc.)
- **Game mode** — drum pads control a small browser game you play while AI is generating

**Signature mechanic:** while Wispr Flow is dictating, you have to keep drumming. Stop for 2 seconds → dictation cuts off mid-sentence. (Warning beep at 1.5s.)

## Architecture

```
   Drum kit (USB MIDI)
        ↓
   drummer.py  (Python)
        ↓
   keystrokes  /  app focus  /  game inputs
```

One Python file does everything. No microcontroller, no firmware, no wiring.

## Quick start

```bash
# Install dependencies
pip3 install mido python-rtmidi pynput

# Grant Terminal Accessibility permissions:
# System Settings → Privacy & Security → Accessibility → add Terminal

# Test without a drum (opens a tkinter panel)
python3 drummer.py --test-keys

# When drum is plugged in, calibrate which pad sends which MIDI note
python3 drummer.py --calibrate

# Run normally
python3 drummer.py
```

See [SETUP.md](SETUP.md) for full setup instructions.

## How to extend

All settings live in `CONFIG` at the top of `drummer.py`:

- Add a mode → append to `CONFIG["modes"]` + add entry in `CONFIG["actions"]`
- Add an action → write a function, register in `ACTION_HANDLERS`, map a pad to it
- Rebind a pad → edit one line in `CONFIG["actions"]`
- Tune watchdog timing → change `wispr_watchdog_seconds`

## Tech stack

| Layer | Tech |
|---|---|
| OS | macOS |
| Hardware | KVONE Drum Pads (USB MIDI, 9 pads) |
| Input | Python 3 + `mido` |
| Output | Python 3 + `pynput` (keystrokes), AppleScript (app focus) |
| Test panel | Python 3 + `tkinter` |
| Game (when built) | HTML5 + vanilla JS in Chrome |
| Terminal | iTerm2 + Claude Code CLI |
| Voice | Wispr Flow |

## Hardware state

The authoritative pad mapping (which pads work, which are dead, which are coupled) lives in **[HARDWARE.md](HARDWARE.md)**. Any code that assigns actions to pads must respect that file. Updated whenever the wiring changes.

## Status

Built during the Stasis Hardware Hackathon 2026. Working code, evolving daily. Project docs and ideation live in a separate Obsidian vault.
