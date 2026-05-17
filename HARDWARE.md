# Hardware State — Pad Mapping (Authoritative)

**Last verified: 2026-05-17**

This file is the **authoritative source of truth** for which drum pads are connected, working, dead, or coupled. Any code or config that maps actions to pads MUST respect this file.

> ⚠️ **For future AI assistants / future Cruce:**
> **DO NOT assign actions to dead pads or to both halves of a coupled pair.** Use only the pad numbers listed under "Working logical inputs" below.

---

## Setup

- **Microcontroller:** ESP32-C3 SuperMini, mounted on breadboard
- **USB-C** at breadboard row 1 (orientation reference)
- **GND** at breadboard hole `g2` (right side, row 2)
- All drum pad ground signals share the **black wire** → `g2`
- Each drum pad's signal wire goes to a unique GPIO on the ESP32 (`INPUT_PULLUP`); when the pad is hit, the wire is pulled to GND
- Firmware: `firmware/drum_reader/drum_reader.ino` — prints `PAD N\n` over USB serial on each hit

---

## Full pad table

| Hardware Pad # | Wire color | GPIO | Breadboard hole | Status |
|:---:|---|:---:|:---:|---|
| **1** | Grey       | 5 | c1 | ✅ **working** |
| **2** | Red        | 6 | c2 | ✅ **working** |
| **3** | Purple     | 7 | c3 | ✅ **working** |
| **4** | Green      | 4 | h4 | ❌ **DEAD — never fires. Do not assign.** |
| **5** | Blue       | 3 | h5 | ✅ **working** |
| **6** | Tap-Yellow | 2 | h6 | ✅ **working** |
| **7** | Brown      | 1 | h7 | ⚠️ **coupled with Pad 8** (same physical pad — always fire together) |
| **8** | White      | 0 | h8 | ⚠️ **coupled with Pad 7 — treat as duplicate, ignore in CONFIG** |

---

## Working logical inputs — **6 total**

These are the only pad numbers that should appear in `drummer.py` CONFIG's `actions` dict or `mode_switch_pad`:

```
ACTIVE_PADS = [1, 2, 3, 5, 6, 7]
```

- **Pad 8** is the secondary of the coupled pair → ignore (do not map to anything; will fire whenever Pad 7 fires)
- **Pad 4** is dead → ignore

---

## Verification log

| Date | Method | Result |
|---|---|---|
| 2026-05-17 | Background serial listener (`/tmp/drum_listener.py`); user tapped 6 pads in sequence | Pads 1, 3, 2, 5, 6 fired cleanly; 6th tap produced PAD 7 + PAD 8 simultaneously |
| 2026-05-17 | 5 consecutive taps on the coupled pad | 5× PAD 7 and 5× PAD 8, all at identical timestamps → 100% coupling confirmed |

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

- `drummer.py` → `CONFIG["actions"]`, `CONFIG["mode_switch_pad"]` must use only ACTIVE_PADS
- `drum_visual_test.py` → `PAD_INFO` dict shows wire/GPIO/breadboard per pad
- `firmware/drum_reader/drum_reader.ino` → `PAD_PINS` array must match wiring above
