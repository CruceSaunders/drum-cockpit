# Game Spec — "Rhythm Rush" (working title)

## One-line pitch

Falling notes in 5 lanes, drum the matching pad when a note hits the bottom, sync to a backing track, AI vibes on top.

## Inputs

| Pad | Lane | Game role |
|---|---|---|
| 1 | Lane 1 (left) | drum lane 1 |
| 2 | Lane 2 | drum lane 2 |
| 3 | Lane 3 (middle) | drum lane 3 |
| 4 | Lane 4 | drum lane 4 |
| 5 | Lane 5 (right) | drum lane 5 |
| 6 | — | mode switch (back to coding) — handled in drummer.py, not game |

In game mode, `drummer.py` sends keys **1–5** to the focused window when pads 1–5 are hit. The game listens for those keys.

## Visual layout

```
┌─────────────────────────────────────┐
│                                     │
│   ▒                                 │
│             ▒                       │
│                       ▒             │  ← notes spawn at top
│   ▒                                 │
│                 ▒                   │
│                                     │
│                                     │
│                                     │
├──┬──┬──┬──┬──┬──────────────────────│  ← "hit zone" at bottom
│ 1│ 2│ 3│ 4│ 5│  ← lane labels       │
└──┴──┴──┴──┴──┴──────────────────────┘
        score: 1240  combo: 12x
```

Notes spawn at top, fall straight down, must be hit when they enter the hit zone at the bottom of their lane.

## Sync model (the important math)

The audio is the master clock. Everything is measured against `audio.currentTime`.

For each note in the chart:
- `noteHitTime` — exact second of the audio when the note should be hit
- `spawnTime = noteHitTime - TRAVEL_TIME` — when to spawn the note off-screen (top)
- `TRAVEL_TIME` is a constant (e.g. 1.5 seconds) — how long a note takes to fall

At any frame:
- `now = audio.currentTime`
- For each active note: `y = ((now - spawnTime) / TRAVEL_TIME) * laneHeight`
- When `now >= noteHitTime`, the note is in the hit zone
- Hit window: ±100ms around `noteHitTime` for "good", ±50ms for "perfect", outside that = "miss"

This guarantees the note touches the hit zone at the exact moment the music's beat plays.

## Audio strategy (the part you asked about)

Two paths, going to support both:

### Path A — Procedural beats (default, works immediately)

We generate the 3 "songs" with Web Audio API synthesis. No MP3 files needed, no copyright concerns, perfect sync because we generate the audio AND the chart from the same data.

Each "song" is a tempo + pattern definition:
```js
{
  name: "Stack Trace",
  bpm: 80,
  pattern: [/* lanes per beat */],
  duration: 60s,
}
```

Three songs at increasing difficulty:
1. **"Stack Trace"** — 80 BPM, simple kick on every beat, notes mostly in lanes 1 + 3
2. **"Race Condition"** — 120 BPM, kick + snare alternating, notes spread across all 5 lanes
3. **"Heap Overflow"** — 160 BPM, syncopated, all lanes, occasional simultaneous double-notes

### Path B — Real MP3 files (stretch / polish)

User drops MP3s into `game/audio/` and a JSON chart into `game/charts/`. The game loads the MP3 and uses the chart. We can hand-author charts or auto-detect beats from the audio amplitude (Web Audio API peak detection).

**Path A ships first.** Path B is a stretch goal — drop in your favorite royalty-free tracks from Pixabay Music whenever and we'll add charts.

## Scoring

- **Perfect** (±50ms): 100 points, combo +1
- **Good** (±100ms): 50 points, combo +1
- **Miss** (>100ms late OR pad pressed with no note in zone): 0 points, combo reset

Final screen shows: score, accuracy %, longest combo, AI-generated quip about your performance.

## File structure

```
game/
├── index.html          # song select + game canvas
├── style.css           # all visuals
├── game.js             # game engine (loop, render, hit detection)
├── audio.js            # procedural beat synthesis (Path A)
├── songs.js            # song definitions
└── audio/              # MP3s for Path B (stretch)
    └── (empty for now)
```

## Build phases

1. **Engine** — HTML/canvas, 5 lanes, key listener for 1–5, hit zone, dummy notes hardcoded
2. **Sync** — Web Audio API context, master clock, scheduled note spawning
3. **Procedural audio** — drum synth (kick/snare/hihat) playing on each note's beat
4. **3 song definitions** — tempo, pattern, duration
5. **Song select screen** — pick one of 3 songs to play
6. **Scoring + game over** — score / combo / accuracy / quip
7. **Polish** — animations, hit flash, lane highlights, glow

Building Phase 1–4 now in one shot. 5–7 after we test.
