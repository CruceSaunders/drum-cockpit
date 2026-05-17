# Hardware State — Pad Mapping (Authoritative)

**Last verified: 2026-05-17 (after physical-pad renumbering)**

This file is the **authoritative source of truth** for which drum pads are connected, working, dead, or coupled. Any code or config that maps actions to pads MUST respect this file.

> ⚠️ **For future AI assistants / future Cruce:**
> Pad numbers in `drummer.py` and `firmware/drum_reader/` use the **physical drum layout numbering** (the way Cruce numbers the pads on the actual kit, 1–6). They do **not** match the GPIO order on the ESP32. Always cross-reference this table before assigning actions.

---

## Setup

- **Microcontroller:** ESP32-C3 SuperMini, mounted on breadboard
- **USB-C** at breadboard row 1 (orientation reference)
- **GND** at breadboard hole `g2` — all drum pad ground signals share the **black wire** → `g2`
- Each drum pad's signal wire goes to a unique GPIO (`INPUT_PULLUP`); when the pad is hit, the wire is pulled to GND
- Firmware: `firmware/drum_reader/drum_reader.ino` — prints `PAD N\n` over USB serial on each hit, where N is the **physical pad number** (not the GPIO)
- Cross-pad debounce (e.g. the coupled GPIO 0+1 pair both reporting PAD 6) is handled Python-side in `drummer.py`

---

## Pad table — physical layout

| **Physical pad #** | Wire color | GPIO | Breadboard hole | Status |
|:---:|---|:---:|:---:|---|
| **1** | Grey       | 5 | c1 | ✅ **working** |
| **2** | Purple     | 7 | c3 | ✅ **working** |
| **3** | Red        | 6 | c2 | ✅ **working** |
| **4** | Blue       | 3 | h5 | ✅ **working** — currently bound to Wispr toggle |
| **5** | Tap-Yellow | 2 | h6 | ✅ **working** |
| **6** | Brown + White | 1 + 0 | h7 + h8 | ✅ **working** (coupled pair; mode-switch pad) |

### Unmapped GPIOs

| GPIO | Wire | Hole | Status | Firmware prints |
|:---:|---|:---:|---|:---:|
| 4 | Green | h4 | ❌ DEAD (never fires) | `PAD 99` if anything were to trigger it |

---

## Active pads — `[1, 2, 3, 4, 5, 6]`

All 6 physical pads register. Pad 6 is a coupled hardware pair (Brown and White wires fire simultaneously); the firmware reports both as `PAD 6` and Python debounces the duplicate event within 100ms.

---

## Verification log

| Date | Method | Result |
|---|---|---|
| 2026-05-17 | Background serial listener (`/tmp/drum_listener.py`); user tapped 6 pads in physical order | Hits arrived as PAD 1, 3, 2, 5 (×2), 6, 7+8 → confirmed mapping. Firmware was then renumbered so physical = printed. |
| 2026-05-17 | Stick bounce observed | Some pads double-trigger within ~60ms; Python-side 100ms debounce per pad covers it. |

---

## How to re-verify (if hardware changes)

If wires are reseated, the kit is reconnected, or the ESP32 is re-flashed, redo the test:

```bash
cd ~/Desktop/drum-cockpit
./run.sh --drum-test
# OR background-log method:
.venv/bin/python3 /tmp/drum_listener.py &
# tap each pad, then:
cat /tmp/drum_test_log.txt
pkill -f drum_listener.py
```

Then **update this file** with new results and the verification date.

---

## Code hooks that depend on this file

- `drummer.py` → `CONFIG["active_pads"]`, `CONFIG["mode_switch_pad"]`, `CONFIG["actions"]` use **physical** pad numbers
- `drum_visual_test.py` → `PAD_INFO` dict shows wire/GPIO/breadboard per physical pad
- `firmware/drum_reader/drum_reader.ino` → `PAD_NUMBERS[]` array maps GPIO index → physical pad number (this is what makes it all work)
