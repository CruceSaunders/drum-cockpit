"""
drummer.py — Drum-controlled vibe coder cockpit

Reads MIDI from a drum kit (or keyboard in test mode) and dispatches actions
based on the current mode. The signature mechanic: while Wispr Flow dictation
is active, the script watches for drum hits. If no hit within
`wispr_watchdog_seconds`, it sends Wispr's hotkey again (toggling it off,
cutting the user off mid-sentence).

Usage:
    python3 drummer.py                # normal mode (requires drum kit plugged in)
    python3 drummer.py --calibrate    # identify each pad's MIDI note number
    python3 drummer.py --test-keys    # open tkinter test panel (no drum needed)

Required packages:
    pip3 install mido python-rtmidi pynput

EVERY tunable variable lives in CONFIG at the top.
EVERY action is a function registered in ACTION_HANDLERS.
EVERY mode is just an entry in CONFIG["modes"] + CONFIG["actions"].
"""

import sys
import time
import threading
import subprocess

try:
    from pynput.keyboard import Controller, Key
except ImportError:
    print("pynput not installed. Install with: pip install pynput")
    sys.exit(1)

# mido (MIDI reader) is imported lazily inside the MIDI-using functions.
# This way --sound-test and --test-keys keep working even if python-rtmidi
# has install/runtime issues on this machine.


# ============================================================================
# CONFIG — every tunable setting lives here
#
# ⚠️ HARDWARE CONSTRAINTS — see HARDWARE.md for the authoritative pad map.
#   Active pads (only these): 1, 2, 3, 5, 6, 7
#   DEAD pad (never fires):   4
#   COUPLED pair (treat as 1): 7 + 8  (fire together; assign actions to 7 only,
#                                       leave 8 unmapped so it's silently ignored)
# Do not assign actions to pad 4 or pad 8.
# ============================================================================

CONFIG = {
    # ---- MIDI device selection ----
    # Substring match (case-insensitive). Leave empty to use first device found.
    "midi_device_name_contains": "",  # e.g. "KVONE" or "drum"

    # ---- Watchdog timing ----
    "wispr_watchdog_seconds": 2.0,   # cut off Wispr after this long with no hits
    "wispr_warning_seconds": 0.5,    # beep this long before cutoff (warning)

    # ---- Wispr Flow hotkey ----
    # MUST match the hotkey configured in Wispr Flow's settings.
    # Same hotkey starts AND stops Wispr (toggle).
    "wispr_hotkey": [Key.cmd, Key.shift, "9"],

    # ---- Modes (cycled by the mode-switch pad, loops back to start) ----
    "modes": ["coding", "game"],

    # ---- Pad → MIDI note number mapping ----
    # PLACEHOLDER values. Run --calibrate with the drum kit plugged in,
    # then update these with the real numbers from your kit.
    "pad_notes": {
        "pad_1": 36,
        "pad_2": 38,
        "pad_3": 43,
        "pad_4": 47,
        "pad_5": 50,
        "pad_6": 42,
        "pad_7": 46,
        "pad_8": 49,
        "pad_9": 57,
    },

    # ---- Which pad cycles modes? ----
    # Same pad in every mode. Hitting it cycles to the next mode in
    # CONFIG["modes"], looping back to the start.
    "mode_switch_pad": "pad_9",

    # ---- Pad → action mapping per mode ----
    # Each mode maps pad_name → action_name (must exist in ACTION_HANDLERS).
    # The mode_switch_pad is handled specially — don't list it here.
    "actions": {
        "coding": {
            "pad_1": "wispr_toggle",      # start/stop Wispr dictation
            "pad_2": "enter",             # send Enter key
            "pad_3": "game_toggle",       # focus the game window
            "pad_4": "tmux_new_tab",      # iTerm2: Cmd+T
            "pad_5": "tmux_next_tab",     # iTerm2: Cmd+]
            "pad_6": "tmux_prev_tab",     # iTerm2: Cmd+[
            "pad_7": "cancel",            # Ctrl+C
            "pad_8": "noop",              # reserved
            # pad_9 = mode switch
        },
        "game": {
            "pad_1": "game_input_1",
            "pad_2": "game_input_2",
            "pad_3": "game_input_3",
            "pad_4": "game_input_4",
            "pad_5": "game_input_5",
            "pad_6": "game_input_6",
            "pad_7": "game_input_7",
            "pad_8": "game_input_8",
            # pad_9 = mode switch
        },
    },

    # ---- Auto-focus an app when switching to each mode ----
    # macOS app name (the name that shows in the dock).
    # Leave a mode out to skip auto-focus for it.
    "mode_focus_app": {
        "coding": "iTerm",            # or "Terminal" if using built-in
        "game":   "Google Chrome",
    },

    # ---- Test mode: keyboard digit → pad name ----
    # Used when running with --test-keys. Lets you simulate drum hits
    # without the kit plugged in.
    "test_key_to_pad": {
        "1": "pad_1", "2": "pad_2", "3": "pad_3",
        "4": "pad_4", "5": "pad_5", "6": "pad_6",
        "7": "pad_7", "8": "pad_8", "9": "pad_9",
    },

    # ---- Sound file for the watchdog warning beep ----
    "warning_sound_path": "/System/Library/Sounds/Tink.aiff",

    # ---- Sound test mode: each pad plays a unique macOS system sound ----
    # Used with --sound-test to verify keys/buttons are detected. No
    # Accessibility permission, no Wispr, no MIDI — pure detection check.
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
# State (managed by the script — don't edit directly)
# ============================================================================

state = {
    "current_mode_index": 0,
    "wispr_active": False,
    "last_hit_time": 0.0,
    "warning_played": False,
}

keyboard = Controller()


# ============================================================================
# Helpers
# ============================================================================

def current_mode() -> str:
    return CONFIG["modes"][state["current_mode_index"]]


def note_to_pad(note: int):
    for pad_name, n in CONFIG["pad_notes"].items():
        if n == note:
            return pad_name
    return None


def cycle_mode():
    state["current_mode_index"] = (state["current_mode_index"] + 1) % len(CONFIG["modes"])
    new_mode = current_mode()
    print(f"[mode] now in: {new_mode}")
    # Auto-focus the app for this mode (if configured)
    target_app = CONFIG.get("mode_focus_app", {}).get(new_mode)
    if target_app:
        subprocess.run(
            ["osascript", "-e", f'tell application "{target_app}" to activate'],
            capture_output=True
        )


def press_combo(keys):
    """Press multiple keys simultaneously, then release in reverse order."""
    for k in keys:
        keyboard.press(k)
    for k in reversed(keys):
        keyboard.release(k)


def tap_key(key):
    keyboard.press(key)
    keyboard.release(key)


def play_warning_sound():
    subprocess.run(["afplay", CONFIG["warning_sound_path"]], capture_output=True)


# ============================================================================
# Action handlers
# ============================================================================

def action_wispr_toggle():
    if state["wispr_active"]:
        print("[wispr] stopping (manual toggle)")
        press_combo(CONFIG["wispr_hotkey"])
        state["wispr_active"] = False
    else:
        print("[wispr] starting")
        press_combo(CONFIG["wispr_hotkey"])
        state["wispr_active"] = True
        state["last_hit_time"] = time.time()
        state["warning_played"] = False


def action_enter():
    print("[enter]")
    tap_key(Key.enter)


def action_game_toggle():
    """Focus / open the game window (Chrome)."""
    print("[game] toggle/focus")
    target_app = CONFIG.get("mode_focus_app", {}).get("game", "Google Chrome")
    subprocess.run(
        ["osascript", "-e", f'tell application "{target_app}" to activate'],
        capture_output=True
    )


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


def action_noop():
    pass


def make_game_input(n: int):
    """Factory: returns a handler that sends digit key `n` (game input)."""
    def handler():
        print(f"[game] input {n}")
        tap_key(str(n))
        # TODO: when game uses SSE/WebSocket instead of keystrokes,
        # replace tap_key with a message-send to the game.
    return handler


ACTION_HANDLERS = {
    "wispr_toggle":  action_wispr_toggle,
    "enter":         action_enter,
    "game_toggle":   action_game_toggle,
    "tmux_new_tab":  action_tmux_new_tab,
    "tmux_next_tab": action_tmux_next_tab,
    "tmux_prev_tab": action_tmux_prev_tab,
    "cancel":        action_cancel,
    "noop":          action_noop,
}
# Auto-register game inputs 1-8
for i in range(1, 9):
    ACTION_HANDLERS[f"game_input_{i}"] = make_game_input(i)


# ============================================================================
# Watchdog: cut off Wispr if no drum hits within timeout
# ============================================================================

def watchdog_loop():
    while True:
        time.sleep(0.05)  # 20 Hz check
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
            press_combo(CONFIG["wispr_hotkey"])
            state["wispr_active"] = False
            state["warning_played"] = False


# ============================================================================
# Pad hit handler (shared by all input sources: MIDI, test panel, test keyboard)
# ============================================================================

def handle_pad_hit(pad_name: str, velocity: int):
    print(f"[hit] {pad_name} (vel={velocity}) — mode: {current_mode()}")

    # Any hit refreshes the watchdog (keeps Wispr alive)
    state["last_hit_time"] = time.time()
    state["warning_played"] = False

    # Mode-switch pad always cycles modes, regardless of current mode
    if pad_name == CONFIG["mode_switch_pad"]:
        cycle_mode()
        return

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
# Normal mode: read MIDI from drum kit
# ============================================================================

def find_midi_input():
    import mido  # lazy: only loaded when MIDI is actually used
    devices = mido.get_input_names()
    if not devices:
        print("No MIDI input devices found. Is the drum kit plugged in?")
        return None
    name_filter = CONFIG["midi_device_name_contains"].lower().strip()
    if name_filter:
        for d in devices:
            if name_filter in d.lower():
                print(f"Using MIDI device: {d}")
                return d
        print(f"No device matching '{name_filter}'. Available:")
        for d in devices:
            print(f"  - {d}")
        return None
    print(f"Using first MIDI device: {devices[0]}")
    return devices[0]


def run_midi_mode():
    import mido  # lazy: only loaded when MIDI is actually used
    device_name = find_midi_input()
    if not device_name:
        return

    threading.Thread(target=watchdog_loop, daemon=True).start()

    print(f"Mode: {current_mode()}. Hit a pad. Ctrl+C to quit.\n")
    with mido.open_input(device_name) as port:
        for msg in port:
            # Some kits send note_on velocity=0 as note_off
            if msg.type == "note_on" and msg.velocity > 0:
                pad = note_to_pad(msg.note)
                if pad is None:
                    print(f"[unknown note: {msg.note}] (consider adding to pad_notes)")
                    continue
                handle_pad_hit(pad, msg.velocity)


# ============================================================================
# Calibration mode: identify which pad sends which MIDI note number
# ============================================================================

def run_calibration():
    import mido  # lazy: only loaded when MIDI is actually used
    device_name = find_midi_input()
    if not device_name:
        return
    print("\n=== CALIBRATION MODE ===")
    print("Hit each pad. The MIDI note number prints below.")
    print("Write down: physical pad → note number.")
    print("Then update CONFIG['pad_notes'] in drummer.py.")
    print("Ctrl+C when done.\n")

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
# Test mode: tkinter panel that simulates pad hits (no drum required)
# ============================================================================

def run_test_mode():
    """Opens a tkinter window with 9 pad buttons + keyboard 1-9 bindings.
    Lets you exercise the full action pipeline without a drum kit."""
    import tkinter as tk

    threading.Thread(target=watchdog_loop, daemon=True).start()

    root = tk.Tk()
    root.title("Drum Cockpit — Test Panel")
    root.geometry("520x460")
    root.attributes("-topmost", True)

    mode_label = tk.Label(root, text="", font=("Helvetica", 20, "bold"))
    mode_label.pack(pady=(15, 5))

    instruct = tk.Label(
        root,
        text="Click a pad button OR press 1-9 (while this window is focused).",
        font=("Helvetica", 11),
        fg="gray",
    )
    instruct.pack()

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
        label = f"Pad {n}\n[{n}]"
        if is_mode:
            label += "\n(MODE)"
        bg = "#ffd966" if is_mode else None
        btn = tk.Button(
            btn_frame, text=label, width=10, height=4,
            command=lambda p=pad: fire(p),
            bg=bg, activebackground=bg,
        )
        btn.grid(row=i // 3, column=i % 3, padx=4, pady=4)

    def on_key(event):
        pad = CONFIG["test_key_to_pad"].get(event.char)
        if pad:
            fire(pad)
    root.bind("<Key>", on_key)

    print("Test panel running. Close window or Ctrl+C to quit.\n")
    root.mainloop()


# ============================================================================
# Sound test mode: confirm key detection (no permissions / Wispr / MIDI needed)
# ============================================================================

def run_sound_test():
    """Plays a unique sound per pad. No actions, no modes, no permissions.
    Just confirms that the script detects keys and clicks correctly."""
    import tkinter as tk

    root = tk.Tk()
    root.title("Drum Cockpit — Sound Test")
    root.geometry("560x440")
    root.attributes("-topmost", True)

    title = tk.Label(root, text="Sound Test", font=("Helvetica", 18, "bold"))
    title.pack(pady=(15, 5))

    instruct = tk.Label(
        root,
        text="Click a pad OR press 1-9 (while this window is focused).\nEach pad plays a different sound.",
        font=("Helvetica", 11), fg="gray",
    )
    instruct.pack()

    last_label = tk.Label(root, text="Waiting…", font=("Helvetica", 13))
    last_label.pack(pady=10)

    def play_for(pad_name):
        sound_file = CONFIG["sound_test_files"].get(pad_name)
        if not sound_file:
            print(f"  no sound mapped for {pad_name}")
            return
        sound_name = sound_file.split("/")[-1].replace(".aiff", "")
        last_label.config(text=f"✓ {pad_name} → {sound_name}")
        print(f"[sound-test] {pad_name} → {sound_name}")
        subprocess.Popen(["afplay", sound_file])  # non-blocking

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    for i in range(9):
        n = i + 1
        pad = f"pad_{n}"
        sound_file = CONFIG["sound_test_files"].get(pad, "")
        sound_name = sound_file.split("/")[-1].replace(".aiff", "") if sound_file else "?"
        btn = tk.Button(
            btn_frame,
            text=f"Pad {n}\n[{n}]\n{sound_name}",
            width=10, height=4,
            command=lambda p=pad: play_for(p),
        )
        btn.grid(row=i // 3, column=i % 3, padx=4, pady=4)

    def on_key(event):
        pad = CONFIG["test_key_to_pad"].get(event.char)
        if pad:
            play_for(pad)
    root.bind("<Key>", on_key)

    print("Sound test running. Press 1-9 or click buttons. Close window or Ctrl+C to quit.\n")
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
    run_midi_mode()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye.")
