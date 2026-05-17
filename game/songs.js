/* ============================================================================
 * songs.js — song definitions (5 lanes: drums 1-5)
 *
 * A "song" is a tempo + a sequence of (beat, lane) tuples. The audio engine
 * synthesizes the backing track at the given BPM. The chart says which lane
 * a note appears in on each beat (or fraction of a beat).
 *
 * Lane numbers are 1-5 (matching drum pads 1-5). Drum 5 is dual-purpose:
 *   - On menu screens: navigates (single tap cycle, double tap select)
 *   - In-game: hits lane 5
 *
 * Chart entries: { beat: <number>, lane: <1-5> }
 * ============================================================================
 */

const SONGS = [
    {
        name: "Stack Trace",
        bpm: 80,
        duration: 32,
        chart: [
            { beat: 0,  lane: 3 },
            { beat: 2,  lane: 3 },
            { beat: 4,  lane: 1 },
            { beat: 6,  lane: 5 },
            { beat: 8,  lane: 3 },
            { beat: 10, lane: 3 },
            { beat: 12, lane: 2 },
            { beat: 14, lane: 4 },
            { beat: 16, lane: 3 },
            { beat: 17, lane: 3 },
            { beat: 18, lane: 1 },
            { beat: 19, lane: 5 },
            { beat: 20, lane: 3 },
            { beat: 22, lane: 2 },
            { beat: 24, lane: 4 },
            { beat: 26, lane: 3 },
            { beat: 28, lane: 1 },
            { beat: 29, lane: 3 },
            { beat: 30, lane: 5 },
        ],
    },
    {
        name: "Race Condition",
        bpm: 120,
        duration: 64,
        chart: [
            { beat: 0,   lane: 1 },
            { beat: 1,   lane: 3 },
            { beat: 2,   lane: 5 },
            { beat: 3,   lane: 3 },
            { beat: 4,   lane: 2 },
            { beat: 5,   lane: 4 },
            { beat: 6,   lane: 1 },
            { beat: 7,   lane: 5 },
            { beat: 8,   lane: 3 },
            { beat: 8.5, lane: 3 },
            { beat: 9,   lane: 2 },
            { beat: 10,  lane: 4 },
            { beat: 11,  lane: 2 },
            { beat: 12,  lane: 1 },
            { beat: 13,  lane: 5 },
            { beat: 14,  lane: 3 },
            { beat: 15,  lane: 1 },
            { beat: 16,  lane: 5 },
            { beat: 17,  lane: 4 },
            { beat: 18,  lane: 3 },
            { beat: 19,  lane: 2 },
            { beat: 20,  lane: 1 },
            { beat: 21,  lane: 3 },
            { beat: 22,  lane: 5 },
            { beat: 23,  lane: 3 },
            { beat: 24,  lane: 4 },
            { beat: 25,  lane: 2 },
            { beat: 26,  lane: 1 },
            { beat: 27,  lane: 5 },
            { beat: 28,  lane: 3 },
            { beat: 29,  lane: 4 },
            { beat: 30,  lane: 2 },
            { beat: 31,  lane: 1 },
            { beat: 32,  lane: 5 },
            { beat: 33,  lane: 4 },
            { beat: 34,  lane: 3 },
            { beat: 35,  lane: 2 },
            { beat: 36,  lane: 1 },
            { beat: 38,  lane: 3 },
            { beat: 40,  lane: 5 },
            { beat: 41,  lane: 4 },
            { beat: 42,  lane: 3 },
            { beat: 43,  lane: 2 },
            { beat: 44,  lane: 1 },
            { beat: 46,  lane: 5 },
            { beat: 48,  lane: 1 },
            { beat: 48.5,lane: 5 },
            { beat: 50,  lane: 3 },
            { beat: 52,  lane: 2 },
            { beat: 54,  lane: 4 },
            { beat: 56,  lane: 1 },
            { beat: 57,  lane: 5 },
            { beat: 58,  lane: 3 },
            { beat: 60,  lane: 4 },
            { beat: 62,  lane: 2 },
        ],
    },
    {
        name: "Heap Overflow",
        bpm: 160,
        duration: 96,
        chart: (() => {
            const c = [];
            const lanes = [1, 2, 3, 4, 5];
            let seed = 7;
            const rng = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
            for (let b = 0; b < 96; b += 0.5) {
                if (rng() < 0.7) {
                    c.push({ beat: b, lane: lanes[Math.floor(rng() * 5)] });
                }
                if (rng() < 0.06) {
                    let other = lanes[Math.floor(rng() * 5)];
                    while (c.length && other === c[c.length - 1].lane) {
                        other = lanes[Math.floor(rng() * 5)];
                    }
                    c.push({ beat: b, lane: other });
                }
            }
            return c;
        })(),
    },
];
