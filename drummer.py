"""
drummer.py — Drum-controlled vibe coder cockpit.

Reads drum pad hits from the ESP32 over USB serial (firmware in
firmware/drum_reader/). Dispatches actions based on current mode.

  Pad 7 (the coupled pad) cycles modes.
  Coding mode → iTerm2 focused; pads do AI / shell shortcuts.
  Game mode   → Chrome focused on game/index.html; pads send digit keystrokes.

Usage:
    python3 drummer.py              # normal serial mode (default)
    python3 drummer.py --calibrate  # MIDI calibration (legacy)
    python3 drummer.py --sound-test # tkinter sound test
    python3 drummer.py --test-keys  # tkinter full action test panel
    python3 drummer.py --midi       # legacy USB MIDI input mode

EVERY tunable setting lives in CONFIG. EVERY action is in ACTION_HANDLERS.
Modes are entries in CONFIG["modes"] (mode-switch pad cycles through them).
"""

import os
import sys
import time
import threading
import subprocess

try:
    from pynput.keyboard import Controller, Key
except ImportError:
    print("pynput not installed. Run: pip install pynput")
    sys.exit(1)

# mido is imported lazily inside the MIDI-using functions so --sound-test and
# --test-keys keep working even if python-rtmidi has install/runtime issues.


# ============================================================================
# CONFIG — every tunable setting lives here
#
# ⚠️ HARDWARE CONSTRAINTS — see HARDWARE.md for the authoritative pad map.
# Pad numbers below match the PHYSICAL drum layout (1–6).
#   Active pads:  1, 2, 3, 4, 5, 6
#   Pad 6 is a coupled hardware pair — both halves report as PAD 6 (Python
#   debounces the duplicate event).
#   Firmware also emits "PAD 99" for the dead GPIO 4 if it ever fires (ignored).
# ============================================================================

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    # ---- Serial input (ESP32 over USB) ----
    "serial_port": "/dev/cu.usbmodem1101",
    "serial_baud": 115200,

    # ---- Legacy MIDI device (only used with --midi mode) ----
    "midi_device_name_contains": "",

    # ---- Watchdog timing ----
    "wispr_watchdog_seconds": 2.0,
    "wispr_warning_seconds": 0.5,

    # ---- Wispr Flow hotkeys (must match what's set in Wispr's Settings) ----
    # Cruce's setup:
    #   Start dictation = Fn + Space
    #   Stop  dictation = Fn (tap alone)
    # The action toggles between these two based on state.
    # Fn requires Quartz (CGEvent), not pynput. See send_fn / send_fn_space below.
    "wispr_hotkey_start": "fn_space",  # symbolic; handled by action_wispr_toggle
    "wispr_hotkey_stop":  "fn",

    # ---- Modes (mode-switch pad cycles through this list, looping) ----
    "modes": ["coding", "game"],

    # ---- Hardware pad availability (DO NOT change without re-verifying) ----
    "active_pads":  ["pad_1", "pad_2", "pad_3", "pad_4", "pad_5", "pad_6"],
    "ignored_pads": ["pad_99"],  # GPIO 4 (dead drum) emits this if it ever fires

    # ---- Cross-pad debounce (ms) ----
    # Same pad fired again within this window is treated as a bounce and dropped.
    # Firmware-side cross-pin debounce already deduplicates the pad 6 coupled
    # pair (GPIOs 0+1 → both emit PAD 6 but firmware suppresses the second).
    # Python-side debounce is just a safety net + handles stick bounce for all pads.
    "pad_debounce_ms": {
        "default": 80,    # covers stick bounce, allows fast rhythm play
    },

    # ---- Mode-switch crosstalk suppression ----
    # If pad 6 (mode switch) fires within this many ms of any OTHER pad hit,
    # assume it's vibration cross-talk from hitting another drum hard, and
    # ignore it. Real intentional mode switches are tapped on their own.
    "mode_switch_crosstalk_window_ms": 200,

    # ---- Which pad cycles modes? Must be in active_pads. ----
    "mode_switch_pad": "pad_6",

    # ---- Pad → action mapping per mode ----
    # Action name must exist in ACTION_HANDLERS below.
    # mode_switch_pad (pad_6) is handled separately, not in this dict.
    "actions": {
        "coding": {
            "pad_1": "iterm_smart_split",  # new pane/tab in iTerm, layout-aware
            "pad_2": "iterm_navigate",     # cycle pane→tab→window in iTerm
            "pad_3": "close_pane",         # Cmd+W (close current pane/tab)
            "pad_4": "enter",              # submit prompt
            "pad_5": "wispr_toggle",       # Fn+Space on, Fn off
            # pad_6 = mode switch (handled separately)
        },
        "game": {
            "pad_1": "game_input_1",   # sends key "1" → lane 1
            "pad_2": "game_input_2",   # sends key "2" → lane 2
            "pad_3": "game_input_3",   # sends key "3" → lane 3
            "pad_4": "game_input_4",   # sends key "4" → lane 4
            "pad_5": "game_input_5",   # sends key "5" → menu nav OR lane 5
            # pad_6 = mode switch (handled separately)
        },
    },

    # ---- Smart-split threshold ----
    # If `columns > rows * SPLIT_ASPECT_FACTOR`, the pane is "wider than tall in
    # pixels" (cells are ~2x taller than wide), so we split vertically. Tune up
    # to bias toward horizontal splits, down to bias toward vertical.
    "iterm_split_aspect_factor": 2.0,

    # ---- Smart-split limit ----
    # If current tab already has this many sessions, open a new tab instead of splitting.
    "iterm_max_sessions_per_tab": 4,

    # ---- Per-mode focus target (macOS app name) ----
    "mode_focus_app": {
        "coding": "iTerm",            # change to "Terminal" if using built-in
        "game":   "Google Chrome",
    },

    # ---- Game ----
    "game_url": f"file://{_PROJECT_DIR}/game/index.html",
    "game_url_match": "drum-cockpit/game",  # substring used to find existing tab

    # ---- MIDI test-key mapping (legacy --test-keys mode) ----
    "test_key_to_pad": {
        "1": "pad_1", "2": "pad_2", "3": "pad_3",
        "4": "pad_4", "5": "pad_5", "6": "pad_6",
        "7": "pad_7", "8": "pad_8",
    },

    # ---- Sound file for the watchdog warning beep ----
    "warning_sound_path": "/System/Library/Sounds/Tink.aiff",

    # ---- Sound test mode files (--sound-test) ----
    "sound_test_files": {
        "pad_1": "/System/Library/Sounds/Tink.aiff",
        "pad_2": "/System/Library/Sounds/Pop.aiff",
        "pad_3": "/System/Library/Sounds/Ping.aiff",
        "pad_4": "/System/Library/Sounds/Glass.aiff",
        "pad_5": "/System/Library/Sounds/Funk.aiff",
        "pad_6": "/System/Library/Sounds/Hero.aiff",
        "pad_7": "/System/Library/Sounds/Bottle.aiff",
        "pad_8": "/System/Library/Sounds/Morse.aiff",
        "pad_9": "/System/Library/Sounds/Submarine.aiff",
    },
}


# ============================================================================
# State
# ============================================================================

state = {
    "current_mode_index": 0,
    "wispr_active": False,
    "last_hit_time": 0.0,
    "warning_played": False,
    "last_pad_hit_at": {},        # pad_name -> last hit time (used for debounce)
    "last_non_mode_hit_at": 0.0,  # last time a non-mode pad fired (crosstalk check)
}

keyboard = Controller()


# ============================================================================
# Helpers
# ============================================================================

def current_mode() -> str:
    return CONFIG["modes"][state["current_mode_index"]]


def press_combo(keys):
    for k in keys:
        keyboard.press(k)
    for k in reversed(keys):
        keyboard.release(k)


def tap_key(key):
    keyboard.press(key)
    keyboard.release(key)


def play_warning_sound():
    subprocess.run(["afplay", CONFIG["warning_sound_path"]], capture_output=True)


# ----- macOS Fn-key support (via Quartz CGEvent) ----------------------------
# pynput can't reliably send the Fn modifier on macOS — it doesn't set the
# secondary-Fn flag on the CGEvent it posts. So we build the events directly.
# Virtual key codes: Fn = 63, Space = 49.

def _send_fn_event(key_down: bool, vk: int = 63):
    from Quartz import (
        CGEventCreateKeyboardEvent, CGEventPost, CGEventSetFlags,
        kCGHIDEventTap, kCGEventFlagMaskSecondaryFn,
    )
    event = CGEventCreateKeyboardEvent(None, vk, key_down)
    if key_down:
        CGEventSetFlags(event, kCGEventFlagMaskSecondaryFn)
    CGEventPost(kCGHIDEventTap, event)


def send_fn():
    """Tap the Fn key (down + up)."""
    _send_fn_event(True)
    time.sleep(0.02)
    _send_fn_event(False)


def send_fn_space():
    """Hold Fn, tap Space, release Fn."""
    from Quartz import (
        CGEventCreateKeyboardEvent, CGEventPost, CGEventSetFlags,
        kCGHIDEventTap, kCGEventFlagMaskSecondaryFn,
    )
    SPACE_VK = 49

    # Fn down
    _send_fn_event(True)
    time.sleep(0.02)

    # Space down (with Fn flag still asserted)
    e = CGEventCreateKeyboardEvent(None, SPACE_VK, True)
    CGEventSetFlags(e, kCGEventFlagMaskSecondaryFn)
    CGEventPost(kCGHIDEventTap, e)
    time.sleep(0.02)

    # Space up (still with Fn flag)
    e = CGEventCreateKeyboardEvent(None, SPACE_VK, False)
    CGEventSetFlags(e, kCGEventFlagMaskSecondaryFn)
    CGEventPost(kCGHIDEventTap, e)
    time.sleep(0.02)

    # Fn up
    _send_fn_event(False)


def focus_app(app_name: str):
    """Bring a Mac app to the front. No-op if AppleScript fails."""
    subprocess.run(
        ["osascript", "-e", f'tell application "{app_name}" to activate'],
        capture_output=True,
    )


def focus_game_window():
    """Find Chrome window/tab with our game URL, focus it, AND click into
    the page content area so the URL bar doesn't keep keyboard focus."""
    app = CONFIG["mode_focus_app"].get("game", "Google Chrome")
    match = CONFIG["game_url_match"]
    url = CONFIG["game_url"]

    script = f'''
    tell application "{app}"
        activate
        set found to false
        try
            repeat with w in windows
                set i to 0
                repeat with t in tabs of w
                    set i to i + 1
                    if URL of t contains "{match}" then
                        set active tab index of w to i
                        set index of w to 1
                        set found to true
                        exit repeat
                    end if
                end repeat
                if found then exit repeat
            end repeat
        end try
        if not found then
            open location "{url}"
        end if
    end tell

    delay 0.2

    -- Click into the page content so keystrokes reach the page, not the URL bar.
    -- Position: horizontal center, ~130px below the top of the window
    -- (past Chrome's title/tab/toolbar, into the page body).
    tell application "System Events"
        tell process "{app}"
            try
                set winPos to position of front window
                set winSize to size of front window
                set cx to (item 1 of winPos) + (item 1 of winSize) / 2
                set cy to (item 2 of winPos) + 130
                click at {{cx, cy}}
            end try
        end tell
    end tell
    '''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def focus_for_mode(mode: str):
    """Auto-focus the right window when entering a mode."""
    if mode == "game":
        focus_game_window()
    else:
        app = CONFIG.get("mode_focus_app", {}).get(mode)
        if app:
            focus_app(app)


def cycle_mode():
    state["current_mode_index"] = (state["current_mode_index"] + 1) % len(CONFIG["modes"])
    new_mode = current_mode()
    print(f"[mode] now in: {new_mode}")
    focus_for_mode(new_mode)


# ============================================================================
# Action handlers
# ============================================================================

def action_wispr_toggle():
    """Pad 5 = Wispr START. When already active, just keep alive (no stop).
    To stop Wispr, simply stop drumming — the watchdog will cut it off."""
    if state["wispr_active"]:
        # Already running — pad 5 hit just refreshes watchdog (handled by handle_pad_hit).
        # Don't send Fn here (that would stop Wispr unexpectedly).
        print("[wispr] still on (drum-keep-alive)")
    else:
        print("[wispr] starting  (sending Fn+Space)")
        send_fn_space()
        state["wispr_active"] = True
        state["last_hit_time"] = time.time()
        state["warning_played"] = False


def action_enter():
    print("[enter]")
    tap_key(Key.enter)


def action_game_toggle():
    """Show the game window (open if needed) without switching the mode."""
    print("[game] focus game window")
    focus_game_window()


def action_tmux_new_tab():
    print("[iterm] new tab")
    press_combo([Key.cmd, "t"])


def action_tmux_next_tab():
    print("[iterm] next tab")
    press_combo([Key.cmd, "]"])


def action_tmux_prev_tab():
    print("[iterm] prev tab")
    press_combo([Key.cmd, "["])


def action_cancel():
    print("[ctrl-c] cancel")
    press_combo([Key.ctrl, "c"])


def action_shift_tab():
    """Claude Code: toggle auto-accept mode."""
    print("[shift+tab]")
    press_combo([Key.shift, Key.tab])


def action_close_pane():
    """Close current iTerm pane/tab (Cmd+W)."""
    print("[cmd+w] close pane")
    press_combo([Key.cmd, "w"])


def action_iterm_navigate():
    """Cycle to next pane/tab/window in iTerm2 — whichever level has >1 item."""
    script = '''
    tell application "iTerm2"
        try
            set paneCount to count of (every session of current tab of current window)
        on error
            set paneCount to 0
        end try
        try
            set tabCount to count of (every tab of current window)
        on error
            set tabCount to 0
        end try
        try
            set winCount to count of (every window)
        on error
            set winCount to 0
        end try
    end tell
    if paneCount > 1 then
        return "pane"
    else if tabCount > 1 then
        return "tab"
    else if winCount > 1 then
        return "window"
    else
        return "none"
    end if
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=2,
        )
        decision = result.stdout.strip()
    except Exception as e:
        print(f"[iterm-nav] AppleScript failed: {e}")
        decision = "pane"  # safe default

    print(f"[iterm-nav] cycling: {decision}")
    if decision == "pane":
        press_combo([Key.cmd, "]"])
    elif decision == "tab":
        press_combo([Key.cmd, Key.shift, "]"])
    elif decision == "window":
        press_combo([Key.cmd, "`"])
    # "none" → do nothing


def action_iterm_smart_split():
    """Open a new pane (smart direction) or new tab if pane count >= limit."""
    script = '''
    tell application "iTerm2"
        try
            set paneCount to count of (every session of current tab of current window)
            set c to columns of current session of current window
            set r to rows of current session of current window
        on error
            return "fallback,0,0"
        end try
    end tell
    return (paneCount as string) & "," & (c as string) & "," & (r as string)
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=2,
        )
        parts = result.stdout.strip().split(",")
        pane_count = int(parts[0]) if parts[0].isdigit() else 1
        cols = int(parts[1]) if parts[1].isdigit() else 0
        rows = int(parts[2]) if parts[2].isdigit() else 0
    except Exception as e:
        print(f"[iterm-split] AppleScript failed: {e} — defaulting to Cmd+D")
        press_combo([Key.cmd, "d"])
        return

    max_per_tab = CONFIG.get("iterm_max_sessions_per_tab", 4)
    aspect = CONFIG.get("iterm_split_aspect_factor", 2.0)

    if pane_count >= max_per_tab:
        print(f"[iterm-split] {pane_count} panes already — opening new tab")
        press_combo([Key.cmd, "t"])
    elif rows > 0 and cols > rows * aspect:
        print(f"[iterm-split] {cols}x{rows} → wider than tall → split vertical")
        press_combo([Key.cmd, "d"])
    else:
        print(f"[iterm-split] {cols}x{rows} → taller than wide → split horizontal")
        press_combo([Key.cmd, Key.shift, "d"])


def action_noop():
    pass


def make_game_input(n: int):
    def handler():
        print(f"[game] input {n}")
        tap_key(str(n))
    return handler


ACTION_HANDLERS = {
    "wispr_toggle":       action_wispr_toggle,
    "enter":              action_enter,
    "game_toggle":        action_game_toggle,
    "shift_tab":          action_shift_tab,
    "close_pane":         action_close_pane,
    "iterm_navigate":     action_iterm_navigate,
    "iterm_smart_split":  action_iterm_smart_split,
    "tmux_new_tab":       action_tmux_new_tab,
    "tmux_next_tab":      action_tmux_next_tab,
    "tmux_prev_tab":      action_tmux_prev_tab,
    "cancel":             action_cancel,
    "noop":               action_noop,
}
for i in range(1, 9):
    ACTION_HANDLERS[f"game_input_{i}"] = make_game_input(i)


# ============================================================================
# Watchdog: cut off Wispr if no drum hits within timeout
# ============================================================================

def watchdog_loop():
    while True:
        time.sleep(0.05)
        if not state["wispr_active"]:
            continue
        elapsed = time.time() - state["last_hit_time"]
        timeout = CONFIG["wispr_watchdog_seconds"]
        warning_at = timeout - CONFIG["wispr_warning_seconds"]

        if elapsed >= warning_at and not state["warning_played"]:
            play_warning_sound()
            state["warning_played"] = True

        if elapsed >= timeout:
            print("[wispr] WATCHDOG cutoff — stopped drumming")
            send_fn()  # Wispr stop hotkey
            state["wispr_active"] = False
            state["warning_played"] = False


# ============================================================================
# Central pad-hit dispatcher (shared by all input sources)
# ============================================================================

def handle_pad_hit(pad_name: str, velocity: int):
    now = time.time()

    # Silently drop ignored pads (e.g. dead GPIO printing PAD 99)
    if pad_name in CONFIG.get("ignored_pads", []):
        return

    # Debounce same pad fired again within window (stick bounce + coupled pair).
    # CONFIG["pad_debounce_ms"] can be an int (uniform) or a dict (per-pad).
    debounce_cfg = CONFIG.get("pad_debounce_ms", 100)
    if isinstance(debounce_cfg, dict):
        debounce_ms = debounce_cfg.get(pad_name, debounce_cfg.get("default", 100))
    else:
        debounce_ms = debounce_cfg
    last = state["last_pad_hit_at"].get(pad_name, 0)
    if (now - last) * 1000 < debounce_ms:
        return
    state["last_pad_hit_at"][pad_name] = now

    # Refresh Wispr watchdog (any hit counts as drumming)
    state["last_hit_time"] = now
    state["warning_played"] = False

    print(f"[hit] {pad_name} (vel={velocity}) — mode: {current_mode()}")

    if pad_name == CONFIG["mode_switch_pad"]:
        # Crosstalk filter: if any non-mode drum was hit very recently,
        # this pad-6 event is almost certainly vibration from a real drum
        # hit (especially during fast game play). Suppress it.
        ct_window_ms = CONFIG.get("mode_switch_crosstalk_window_ms", 200)
        elapsed_since_other = (now - state["last_non_mode_hit_at"]) * 1000
        if elapsed_since_other < ct_window_ms:
            print(f"  [mode-switch ignored] only {elapsed_since_other:.0f}ms since last other drum (crosstalk)")
            return
        cycle_mode()
        return

    # This was a non-mode pad — record it so a later pad 6 within the
    # crosstalk window gets filtered as vibration.
    state["last_non_mode_hit_at"] = now

    action_map = CONFIG["actions"].get(current_mode(), {})
    action_name = action_map.get(pad_name)
    if not action_name:
        print(f"  (no action mapped for {pad_name} in {current_mode()} mode)")
        return
    handler = ACTION_HANDLERS.get(action_name)
    if not handler:
        print(f"  (no handler registered for action: {action_name})")
        return
    handler()


# ============================================================================
# Serial mode — read drum hits from ESP32 (the default)
# ============================================================================

def run_serial_mode():
    try:
        import serial
    except ImportError:
        print("pyserial not installed. Run: pip install pyserial")
        sys.exit(1)

    port = CONFIG["serial_port"]
    baud = CONFIG["serial_baud"]

    try:
        ser = serial.Serial(port, baud, timeout=0.2)
    except Exception as e:
        print(f"Failed to open {port}: {e}")
        print("Is the ESP32 plugged in? Is another process holding the port?")
        return

    threading.Thread(target=watchdog_loop, daemon=True).start()

    print(f"Connected to {port} @ {baud} baud.")
    print(f"Active pads: {CONFIG['active_pads']}  (ignored: {CONFIG['ignored_pads']})")
    print(f"Mode-switch pad: {CONFIG['mode_switch_pad']}")
    print(f"Starting in mode: {current_mode()}.  Hit drum pads. Ctrl+C to quit.\n")

    # Focus the right app for the starting mode
    focus_for_mode(current_mode())

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("PAD "):
                try:
                    n = int(line.split()[1])
                    handle_pad_hit(f"pad_{n}", 100)
                except (IndexError, ValueError):
                    pass
            else:
                # boot messages, heartbeats, etc.
                print(f"[esp32] {line}")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"serial error: {e}")
            break


# ============================================================================
# Legacy MIDI input (only when --midi flag is given)
# ============================================================================

def find_midi_input():
    import mido  # lazy: only loaded when MIDI is actually used
    devices = mido.get_input_names()
    if not devices:
        print("No MIDI input devices found.")
        return None
    name_filter = CONFIG["midi_device_name_contains"].lower().strip()
    if name_filter:
        for d in devices:
            if name_filter in d.lower():
                print(f"Using MIDI device: {d}")
                return d
        print(f"No device matching '{name_filter}'. Available: {devices}")
        return None
    print(f"Using first MIDI device: {devices[0]}")
    return devices[0]


def run_midi_mode():
    import mido  # lazy
    device_name = find_midi_input()
    if not device_name:
        return

    threading.Thread(target=watchdog_loop, daemon=True).start()
    print(f"Mode: {current_mode()}. Hit a pad. Ctrl+C to quit.\n")

    # No MIDI-pad mapping table here — would need re-introduction if revived
    with mido.open_input(device_name) as port:
        for msg in port:
            if msg.type == "note_on" and msg.velocity > 0:
                print(f"[midi] note {msg.note} vel {msg.velocity} (mapping not implemented in serial-first build)")


def run_calibration():
    import mido  # lazy
    device_name = find_midi_input()
    if not device_name:
        return
    print("\n=== MIDI CALIBRATION (legacy) ===")
    print("Hit each pad. The MIDI note number prints below. Ctrl+C when done.\n")
    seen = {}
    with mido.open_input(device_name) as port:
        for msg in port:
            if msg.type != "note_on" or msg.velocity == 0:
                continue
            if msg.note not in seen:
                seen[msg.note] = 0
                print(f"  NEW PAD — MIDI note {msg.note} (vel {msg.velocity})")
            seen[msg.note] += 1


# ============================================================================
# Sound test (no permissions / hardware needed)
# ============================================================================

def run_sound_test():
    import tkinter as tk

    root = tk.Tk()
    root.title("Drum Cockpit — Sound Test")
    root.geometry("560x440")
    root.attributes("-topmost", True)

    tk.Label(root, text="Sound Test", font=("Helvetica", 18, "bold")).pack(pady=(15, 5))
    tk.Label(root,
             text="Click a pad OR press 1-9 (while focused). Each pad plays a different sound.",
             font=("Helvetica", 11), fg="gray").pack()
    last = tk.Label(root, text="Waiting…", font=("Helvetica", 13))
    last.pack(pady=10)

    def play_for(pad_name):
        sound_file = CONFIG["sound_test_files"].get(pad_name)
        if not sound_file:
            return
        sound_name = sound_file.split("/")[-1].replace(".aiff", "")
        last.config(text=f"✓ {pad_name} → {sound_name}")
        print(f"[sound-test] {pad_name} → {sound_name}")
        subprocess.Popen(["afplay", sound_file])

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    for i in range(9):
        n = i + 1
        pad = f"pad_{n}"
        sf = CONFIG["sound_test_files"].get(pad, "")
        sn = sf.split("/")[-1].replace(".aiff", "") if sf else "?"
        tk.Button(btn_frame, text=f"Pad {n}\n[{n}]\n{sn}", width=10, height=4,
                  command=lambda p=pad: play_for(p)).grid(row=i // 3, column=i % 3, padx=4, pady=4)

    def on_key(event):
        pad = CONFIG["test_key_to_pad"].get(event.char)
        if pad:
            play_for(pad)
    root.bind("<Key>", on_key)

    print("Sound test running. Close window or Ctrl+C to quit.\n")
    root.mainloop()


# ============================================================================
# Full action test panel (--test-keys)
# ============================================================================

def run_test_mode():
    """Tkinter panel that simulates pad hits via mouse click or keys 1-9."""
    import tkinter as tk

    threading.Thread(target=watchdog_loop, daemon=True).start()

    root = tk.Tk()
    root.title("Drum Cockpit — Test Panel")
    root.geometry("520x460")
    root.attributes("-topmost", True)

    mode_label = tk.Label(root, text="", font=("Helvetica", 20, "bold"))
    mode_label.pack(pady=(15, 5))
    tk.Label(root, text="Click a pad button OR press 1-9 (while focused).",
             font=("Helvetica", 11), fg="gray").pack()
    wispr_label = tk.Label(root, text="", font=("Helvetica", 12))
    wispr_label.pack(pady=(8, 0))
    timer_label = tk.Label(root, text="", font=("Helvetica", 10), fg="gray")
    timer_label.pack(pady=(0, 8))

    def refresh_status():
        mode_label.config(text=f"Mode: {current_mode().upper()}")
        if state["wispr_active"]:
            elapsed = time.time() - state["last_hit_time"]
            remaining = CONFIG["wispr_watchdog_seconds"] - elapsed
            wispr_label.config(text="Wispr: ACTIVE", fg="green")
            timer_label.config(text=f"watchdog cutoff in {max(0, remaining):.1f}s")
        else:
            wispr_label.config(text="Wispr: idle", fg="gray")
            timer_label.config(text="")
        root.after(50, refresh_status)
    refresh_status()

    def fire(pad_name):
        handle_pad_hit(pad_name, 100)

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    for i in range(9):
        n = i + 1
        pad = f"pad_{n}"
        is_mode = (pad == CONFIG["mode_switch_pad"])
        is_dead = pad in CONFIG.get("ignored_pads", [])
        label = f"Pad {n}\n[{n}]"
        if is_mode:
            label += "\n(MODE)"
        if is_dead:
            label += "\n(IGNORED)"
        bg = "#ffd966" if is_mode else ("#666" if is_dead else None)
        tk.Button(btn_frame, text=label, width=10, height=4,
                  command=lambda p=pad: fire(p),
                  bg=bg, activebackground=bg
                  ).grid(row=i // 3, column=i % 3, padx=4, pady=4)

    def on_key(event):
        pad = CONFIG["test_key_to_pad"].get(event.char)
        if pad:
            fire(pad)
    root.bind("<Key>", on_key)

    print("Test panel running. Close window or Ctrl+C to quit.\n")
    root.mainloop()


# ============================================================================
# Entry point
# ============================================================================

def main():
    if "--calibrate" in sys.argv:
        run_calibration()
        return
    if "--sound-test" in sys.argv:
        run_sound_test()
        return
    if "--test-keys" in sys.argv or "--test" in sys.argv:
        run_test_mode()
        return
    if "--midi" in sys.argv:
        run_midi_mode()
        return
    # Default: serial input from ESP32
    run_serial_mode()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye.")
