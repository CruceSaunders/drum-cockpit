/* ============================================================================
 * songs.js — song definitions (4 lanes: drums 1-4)
 *
 * A "song" is a tempo + a sequence of (beat, lane) tuples. The audio engine
 * synthesizes the backing track at the given BPM. The chart says which lane
 * a note appears in on each beat (or fraction of a beat).
 *
 * Lane numbers are 1-4 (matching drum pads 1-4). Drum 5 = menu navigation.
 *
 * Chart entries: { beat: <number>, lane: <1-4> }
 *   beat 0 = the first beat. beat 0.5 = half a beat later. etc.
 * ============================================================================
 */

const SONGS = [
    {
        name: "Stack Trace",
        bpm: 80,
        duration: 32, // beats — at 80 BPM that's 24 sec
        // Easy: mostly center lanes, predictable
        chart: [
            { beat: 0,  lane: 2 },
            { beat: 2,  lane: 3 },
            { beat: 4,  lane: 1 },
            { beat: 6,  lane: 4 },
            { beat: 8,  lane: 2 },
            { beat: 10, lane: 3 },
            { beat: 12, lane: 2 },
            { beat: 14, lane: 4 },
            { beat: 16, lane: 3 },
            { beat: 17, lane: 3 },
            { beat: 18, lane: 1 },
            { beat: 19, lane: 4 },
            { beat: 20, lane: 2 },
            { beat: 22, lane: 3 },
            { beat: 24, lane: 4 },
            { beat: 26, lane: 2 },
            { beat: 28, lane: 1 },
            { beat: 29, lane: 3 },
            { beat: 30, lane: 4 },
        ],
    },
    {
        name: "Race Condition",
        bpm: 120,
        duration: 64, // at 120 BPM that's 32 sec
        // Medium: alternating, all 4 lanes
        chart: [
            { beat: 0,   lane: 1 },
            { beat: 1,   lane: 3 },
            { beat: 2,   lane: 4 },
            { beat: 3,   lane: 3 },
            { beat: 4,   lane: 2 },
            { beat: 5,   lane: 4 },
            { beat: 6,   lane: 1 },
            { beat: 7,   lane: 4 },
            { beat: 8,   lane: 3 },
            { beat: 8.5, lane: 3 },
            { beat: 9,   lane: 2 },
            { beat: 10,  lane: 4 },
            { beat: 11,  lane: 2 },
            { beat: 12,  lane: 1 },
            { beat: 13,  lane: 4 },
            { beat: 14,  lane: 3 },
            { beat: 15,  lane: 1 },
            { beat: 16,  lane: 4 },
            { beat: 17,  lane: 4 },
            { beat: 18,  lane: 3 },
            { beat: 19,  lane: 2 },
            { beat: 20,  lane: 1 },
            { beat: 21,  lane: 3 },
            { beat: 22,  lane: 4 },
            { beat: 23,  lane: 3 },
            { beat: 24,  lane: 4 },
            { beat: 25,  lane: 2 },
            { beat: 26,  lane: 1 },
            { beat: 27,  lane: 4 },
            { beat: 28,  lane: 3 },
            { beat: 29,  lane: 4 },
            { beat: 30,  lane: 2 },
            { beat: 31,  lane: 1 },
            { beat: 32,  lane: 4 },
            { beat: 33,  lane: 4 },
            { beat: 34,  lane: 3 },
            { beat: 35,  lane: 2 },
            { beat: 36,  lane: 1 },
            { beat: 38,  lane: 3 },
            { beat: 40,  lane: 4 },
            { beat: 41,  lane: 4 },
            { beat: 42,  lane: 3 },
            { beat: 43,  lane: 2 },
            { beat: 44,  lane: 1 },
            { beat: 46,  lane: 4 },
            { beat: 48,  lane: 1 },
            { beat: 48.5,lane: 4 },
            { beat: 50,  lane: 3 },
            { beat: 52,  lane: 2 },
            { beat: 54,  lane: 4 },
            { beat: 56,  lane: 1 },
            { beat: 57,  lane: 4 },
            { beat: 58,  lane: 3 },
            { beat: 60,  lane: 4 },
            { beat: 62,  lane: 2 },
        ],
    },
    {
        name: "Heap Overflow",
        bpm: 160,
        duration: 96, // at 160 BPM that's 36 sec
        // Hard: syncopated, fast, occasional half-beats and doubles
        chart: (() => {
            const c = [];
            const lanes = [1, 2, 3, 4];
            let seed = 7;
            const rng = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
            let lastDoubleLane = -1;
            for (let b = 0; b < 96; b += 0.5) {
                if (rng() < 0.7) {
                    c.push({ beat: b, lane: lanes[Math.floor(rng() * 4)] });
                }
                // Occasional double — same beat, different lane (different pad)
                if (rng() < 0.06) {
                    let other = lanes[Math.floor(rng() * 4)];
                    while (c.length && other === c[c.length - 1].lane) {
                        other = lanes[Math.floor(rng() * 4)];
                    }
                    c.push({ beat: b, lane: other });
                }
            }
            return c;
        })(),
    },
];
