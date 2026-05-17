"""
drum_visual_test.py — visual tester for drum-pad-via-ESP32 input.

Listens to the ESP32 over USB serial. When the firmware sends "PAD N",
the corresponding colored box flashes on screen.

Usage:
    ./run.sh --drum-test
  or
    .venv/bin/python3 drum_visual_test.py
"""

import sys
import time
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

# A distinct color for each pad (1-indexed access via PAD_COLORS[n-1])
PAD_COLORS = [
    "#ff4444",  # pad 1 — red
    "#ff8800",  # pad 2 — orange
    "#ffdd00",  # pad 3 — yellow
    "#33cc33",  # pad 4 — green
    "#00bbcc",  # pad 5 — cyan
    "#3366ff",  # pad 6 — blue
    "#aa44dd",  # pad 7 — purple
    "#ff44aa",  # pad 8 — pink
]

FLASH_MS = 200  # how long a pad stays lit after being hit


# --- App ---------------------------------------------------------------------

class DrumTester:
    def __init__(self, root):
        self.root = root
        self.root.title("Drum Cockpit — Pad Tester")
        self.root.geometry("960x340")
        self.root.configure(bg="#1a1a1a")

        title = tk.Label(root, text="Hit your drums!", font=("Helvetica", 18, "bold"),
                         bg="#1a1a1a", fg="white")
        title.pack(pady=(15, 5))

        self.status = tk.Label(root, text=f"Connecting to {SERIAL_PORT}…",
                               font=("Helvetica", 11), bg="#1a1a1a", fg="gray")
        self.status.pack()

        box_frame = tk.Frame(root, bg="#1a1a1a")
        box_frame.pack(pady=20)

        self.counts = [0] * PAD_COUNT
        self.boxes = []
        for i in range(PAD_COUNT):
            n = i + 1
            frame = tk.Frame(box_frame, width=100, height=140, bg="#333",
                             highlightthickness=2, highlightbackground="#555")
            frame.grid(row=0, column=i, padx=6)
            frame.pack_propagate(False)
            label = tk.Label(frame, text=f"Pad {n}", bg="#333", fg="white",
                             font=("Helvetica", 16, "bold"))
            label.pack(expand=True)
            count_label = tk.Label(frame, text="0 hits", bg="#333", fg="#aaa",
                                   font=("Helvetica", 11))
            count_label.pack(pady=(0, 8))
            self.boxes.append({
                "frame": frame, "label": label, "count": count_label
            })

        # Last hit info — useful for figuring out which physical pad maps to which number
        self.last_hit = tk.Label(root, text="Waiting for first hit…",
                                 font=("Helvetica", 13), bg="#1a1a1a", fg="white")
        self.last_hit.pack(pady=(0, 10))

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
            text=f"Connected: {SERIAL_PORT} — hit the pads!", fg="#66ff66"))

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
                    # Other serial messages (e.g. "drum_reader ready")
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
        self.last_hit.config(text=f"Last hit: Pad {pad_num}  (total hits: {self.counts[idx]})")

        color = PAD_COLORS[idx]
        box = self.boxes[idx]
        box["frame"].config(bg=color, highlightbackground=color)
        box["label"].config(bg=color)
        box["count"].config(bg=color, fg="white", text=f"{self.counts[idx]} hits")

        self.root.after(FLASH_MS, lambda: self.unflash(idx))

    def unflash(self, idx):
        box = self.boxes[idx]
        box["frame"].config(bg="#333", highlightbackground="#555")
        box["label"].config(bg="#333")
        box["count"].config(bg="#333", fg="#aaa")


def main():
    root = tk.Tk()
    DrumTester(root)
    root.mainloop()


if __name__ == "__main__":
    main()
