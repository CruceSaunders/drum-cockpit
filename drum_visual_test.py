"""
drum_visual_test.py — visual tester for drum-pad-via-ESP32 input.

Listens to the ESP32 over USB serial. When the firmware sends "PAD N",
the corresponding colored box flashes on screen + hit count increments.

Also shows the wire color / GPIO / breadboard position for each pad so you
can spot wiring mistakes when a pad doesn't register.

Click "Print active pads" to dump the list of pads that have registered
hits — useful for figuring out which pads are alive and which are dead.

Usage:
    ./run.sh --drum-test
  or
    .venv/bin/python3 drum_visual_test.py
"""

import sys
import threading
import tkinter as tk

try:
    import serial
except ImportError:
    print("pyserial not installed. Run: pip install pyserial")
    sys.exit(1)


# --- Tunable -----------------------------------------------------------------

SERIAL_PORT = "/dev/cu.usbmodem1101"
BAUD = 115200
PAD_COUNT = 8
FLASH_MS = 200

# Per-pad wiring info (matches firmware/drum_reader/drum_reader.ino)
PAD_INFO = {
    1: {"color": "Grey",       "gpio": 5, "bb": "c1"},
    2: {"color": "Red",        "gpio": 6, "bb": "c2"},
    3: {"color": "Purple",     "gpio": 7, "bb": "c3"},
    4: {"color": "Green",      "gpio": 4, "bb": "h4"},
    5: {"color": "Blue",       "gpio": 3, "bb": "h5"},
    6: {"color": "Tap-Yellow", "gpio": 2, "bb": "h6"},
    7: {"color": "Brown",      "gpio": 1, "bb": "h7"},
    8: {"color": "White",      "gpio": 0, "bb": "h8"},
}

# Distinct color per pad (1-indexed -> PAD_FLASH_COLORS[n-1])
PAD_FLASH_COLORS = [
    "#ff4444", "#ff8800", "#ffdd00", "#33cc33",
    "#00bbcc", "#3366ff", "#aa44dd", "#ff44aa",
]


# --- App ---------------------------------------------------------------------

class DrumTester:
    def __init__(self, root):
        self.root = root
        self.root.title("Drum Cockpit — Pad Tester")
        self.root.geometry("1080x440")
        self.root.configure(bg="#1a1a1a")

        title = tk.Label(root, text="Hit your drums",
                         font=("Helvetica", 18, "bold"),
                         bg="#1a1a1a", fg="white")
        title.pack(pady=(15, 5))

        self.status = tk.Label(root, text=f"Connecting to {SERIAL_PORT}…",
                               font=("Helvetica", 11), bg="#1a1a1a", fg="gray")
        self.status.pack()

        # 8 pad boxes
        box_frame = tk.Frame(root, bg="#1a1a1a")
        box_frame.pack(pady=15)

        self.counts = [0] * PAD_COUNT
        self.boxes = []
        for i in range(PAD_COUNT):
            n = i + 1
            info = PAD_INFO[n]
            frame = tk.Frame(box_frame, width=120, height=180, bg="#333",
                             highlightthickness=2, highlightbackground="#555")
            frame.grid(row=0, column=i, padx=5)
            frame.pack_propagate(False)

            label = tk.Label(frame, text=f"Pad {n}", bg="#333", fg="white",
                             font=("Helvetica", 16, "bold"))
            label.pack(pady=(10, 0))

            count_label = tk.Label(frame, text="0 hits", bg="#333", fg="#aaa",
                                   font=("Helvetica", 11))
            count_label.pack()

            info_label = tk.Label(
                frame,
                text=f"{info['color']}\nGPIO {info['gpio']}\nhole {info['bb']}",
                bg="#333", fg="#888", font=("Helvetica", 9),
                justify="center",
            )
            info_label.pack(pady=(8, 5))

            self.boxes.append({
                "frame": frame, "label": label,
                "count": count_label, "info": info_label,
            })

        # Last hit
        self.last_hit = tk.Label(root, text="Waiting for first hit…",
                                 font=("Helvetica", 13),
                                 bg="#1a1a1a", fg="white")
        self.last_hit.pack(pady=(0, 10))

        # Buttons
        btn_frame = tk.Frame(root, bg="#1a1a1a")
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Print active pads (to terminal)",
                  command=self.print_active, padx=12, pady=4).grid(row=0, column=0, padx=8)
        tk.Button(btn_frame, text="Reset counts",
                  command=self.reset_counts, padx=12, pady=4).grid(row=0, column=1, padx=8)

        # Background serial reader
        self.running = True
        threading.Thread(target=self.serial_loop, daemon=True).start()

    def serial_loop(self):
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
        except Exception as e:
            self.root.after(0, lambda: self.status.config(
                text=f"ERROR opening {SERIAL_PORT}: {e}", fg="#ff6666"))
            return

        self.root.after(0, lambda: self.status.config(
            text=f"Connected: {SERIAL_PORT} — hit the pads.", fg="#66ff66"))

        while self.running:
            try:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                if line.startswith("PAD "):
                    try:
                        n = int(line.split()[1])
                        self.root.after(0, lambda p=n: self.handle_hit(p))
                    except (IndexError, ValueError):
                        pass
                else:
                    print(f"[esp32] {line}")
                    self.root.after(0, lambda l=line: self.last_hit.config(
                        text=f"ESP32: {l}"))
            except Exception as e:
                print(f"serial error: {e}")
                break

    def handle_hit(self, pad_num):
        idx = pad_num - 1
        if idx < 0 or idx >= PAD_COUNT:
            self.last_hit.config(text=f"Unknown pad number: {pad_num}")
            return
        self.counts[idx] += 1
        self.last_hit.config(
            text=f"Last hit: Pad {pad_num}  ·  total: {self.counts[idx]}"
        )

        color = PAD_FLASH_COLORS[idx]
        box = self.boxes[idx]
        box["frame"].config(bg=color, highlightbackground=color)
        box["label"].config(bg=color)
        box["count"].config(bg=color, fg="white",
                            text=f"{self.counts[idx]} hits")
        box["info"].config(bg=color, fg="white")

        self.root.after(FLASH_MS, lambda: self.unflash(idx))

    def unflash(self, idx):
        box = self.boxes[idx]
        box["frame"].config(bg="#333", highlightbackground="#555")
        box["label"].config(bg="#333")
        box["count"].config(bg="#333", fg="#aaa")
        box["info"].config(bg="#333", fg="#888")

    def print_active(self):
        active = [i + 1 for i in range(PAD_COUNT) if self.counts[i] > 0]
        dead = [i + 1 for i in range(PAD_COUNT) if self.counts[i] == 0]
        print("\n=== ACTIVE PADS ===")
        print(f"  active pads ({len(active)}):  {active}")
        print(f"  dead   pads ({len(dead)}):  {dead}")
        for n in dead:
            info = PAD_INFO[n]
            print(f"    Pad {n} dead — wire: {info['color']}, GPIO {info['gpio']}, hole {info['bb']}")
        print()

    def reset_counts(self):
        self.counts = [0] * PAD_COUNT
        for box in self.boxes:
            box["count"].config(text="0 hits")
        self.last_hit.config(text="Counts reset. Hit pads again.")


def main():
    root = tk.Tk()
    DrumTester(root)
    root.mainloop()


if __name__ == "__main__":
    main()
