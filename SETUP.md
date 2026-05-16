# Setup

Full install and run instructions for `drummer.py`.

## One-time setup

### 1. Python 3

```bash
python3 --version    # should print 3.x.x
```

If missing: install from [python.org](https://www.python.org/downloads/) or `brew install python3`.

### 2. Install dependencies

```bash
pip3 install mido python-rtmidi pynput
```

What these do:
- **`mido`** — reads MIDI events from the drum kit
- **`python-rtmidi`** — the MIDI driver backend `mido` uses
- **`pynput`** — simulates keystrokes (Wispr hotkey, Enter, etc.)

### 3. Grant Accessibility permissions

Required for `pynput` to send keystrokes:

- **System Settings** → **Privacy & Security** → **Accessibility**
- Click **+** → add **Terminal** (or **iTerm2** if you use that)
- Toggle the permission **on**

Without this, the script reads inputs but can't type anything.

### 4. Configure Wispr Flow's hotkey

- Open Wispr Flow → Settings → Hotkey
- Set to something unique like `Cmd+Shift+9`
- Confirm `CONFIG["wispr_hotkey"]` in `drummer.py` matches (defaults to `[Key.cmd, Key.shift, "9"]`)

## Running the script

### Test mode (no drum needed)

```bash
python3 drummer.py --test-keys
```

Opens a small floating window with 9 buttons (Pad 1 – Pad 9). Click them with mouse OR press 1-9 on keyboard while the window is focused. Exercises the full action pipeline without needing the drum kit.

### Calibrate (when drum is first plugged in)

```bash
python3 drummer.py --calibrate
```

Hit each pad once. The script prints the MIDI note number each pad sends. Write down which physical pad sends which number, then update `CONFIG["pad_notes"]` in `drummer.py`. Ctrl+C when done.

### Normal mode

```bash
python3 drummer.py
```

The script listens for drum hits and dispatches actions based on the current mode. Ctrl+C to quit.

## Daily reference — `CONFIG` settings

All tunable settings live at the top of `drummer.py`:

| Setting | Default | What it controls |
|---|---|---|
| `midi_device_name_contains` | `""` | Filter to pick the right MIDI device by name substring |
| `wispr_watchdog_seconds` | `2.0` | Cut-off time when no drumming during dictation |
| `wispr_warning_seconds` | `0.5` | Warning beep this long before cutoff |
| `wispr_hotkey` | `[Cmd, Shift, "9"]` | Must match the hotkey set in Wispr Flow |
| `modes` | `["coding", "game"]` | List of modes; cycle pad rotates through them |
| `pad_notes` | (placeholders) | Pad name → MIDI note number (set during calibration) |
| `mode_switch_pad` | `"pad_9"` | Which pad cycles modes |
| `actions` | (see file) | Pad → action mapping per mode |
| `mode_focus_app` | (see file) | macOS app to auto-focus when entering each mode |
| `test_key_to_pad` | (`"1"`→`"pad_1"`, etc.) | Keyboard mapping for test mode |
| `warning_sound_path` | system Tink sound | Sound file for watchdog warning |

## How to extend

**Add a mode:**
1. Append to `CONFIG["modes"]` (e.g. `["coding", "game", "presentation"]`)
2. Add a matching entry in `CONFIG["actions"]` for the new mode
3. Optionally add an entry in `CONFIG["mode_focus_app"]`

The mode-switch pad will automatically cycle through it.

**Add an action:**
1. Write a function (e.g. `def action_open_safari(): ...`)
2. Register it in `ACTION_HANDLERS` (e.g. `"open_safari": action_open_safari`)
3. Map a pad to it in `CONFIG["actions"]`

**Rebind a pad:** edit one line in `CONFIG["actions"]`.

## Troubleshooting

| Symptom | Try |
|---|---|
| `No MIDI input devices found` | Drum kit not plugged in, USB-C is charge-only, or wrong cable |
| Pad hits not registering | Run `--calibrate`; some kits send `note_on velocity=0` (handled) |
| Wispr not toggling | Check Wispr hotkey config matches `CONFIG["wispr_hotkey"]`; Terminal needs Accessibility permission |
| Watchdog cuts off too fast/slow | Adjust `wispr_watchdog_seconds` |
| Wrong MIDI device selected | Set `midi_device_name_contains` to a substring of the kit's name |
| Test panel grabs key 1-9 even when I want to type | Click somewhere else first (test panel only captures keys when it's focused) |
| Mode-switch doesn't focus the right app | Verify `mode_focus_app` matches the exact app name in macOS |
