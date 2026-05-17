/* ============================================================================
 * audio.js — procedural drum synthesis + master clock
 *
 * Uses Web Audio API to generate drum sounds (kick, snare, hihat) and schedule
 * them along the song's beat grid. The AudioContext's `currentTime` is the
 * master clock that the game loop uses for note-position math.
 * ============================================================================
 */

class AudioEngine {
    constructor() {
        this.ctx = null;
        this.startTime = 0;      // ctx.currentTime when playback began
        this.scheduled = [];     // scheduled audio events (for cleanup)
    }

    init() {
        if (!this.ctx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AC();
        }
        // Resume in case the browser suspended it before a user gesture
        if (this.ctx.state === "suspended") this.ctx.resume();
    }

    /** Current audio time, in seconds since `startSong()` was called. */
    now() {
        if (!this.ctx) return 0;
        return this.ctx.currentTime - this.startTime;
    }

    /** Synthesize a kick drum (low thump) at ctxTime. */
    kick(ctxTime, gain = 0.7) {
        const ctx = this.ctx;
        const osc = ctx.createOscillator();
        const env = ctx.createGain();
        osc.frequency.setValueAtTime(150, ctxTime);
        osc.frequency.exponentialRampToValueAtTime(40, ctxTime + 0.15);
        env.gain.setValueAtTime(gain, ctxTime);
        env.gain.exponentialRampToValueAtTime(0.001, ctxTime + 0.18);
        osc.connect(env).connect(ctx.destination);
        osc.start(ctxTime);
        osc.stop(ctxTime + 0.2);
    }

    /** Snare-ish (noise burst with bandpass). */
    snare(ctxTime, gain = 0.4) {
        const ctx = this.ctx;
        const buffer = ctx.createBuffer(1, ctx.sampleRate * 0.2, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        const bp = ctx.createBiquadFilter();
        bp.type = "bandpass";
        bp.frequency.value = 1800;
        const env = ctx.createGain();
        env.gain.setValueAtTime(gain, ctxTime);
        env.gain.exponentialRampToValueAtTime(0.001, ctxTime + 0.12);
        noise.connect(bp).connect(env).connect(ctx.destination);
        noise.start(ctxTime);
        noise.stop(ctxTime + 0.15);
    }

    /** Hi-hat (very brief noise burst with highpass). */
    hihat(ctxTime, gain = 0.18) {
        const ctx = this.ctx;
        const buffer = ctx.createBuffer(1, ctx.sampleRate * 0.05, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        const hp = ctx.createBiquadFilter();
        hp.type = "highpass";
        hp.frequency.value = 7000;
        const env = ctx.createGain();
        env.gain.setValueAtTime(gain, ctxTime);
        env.gain.exponentialRampToValueAtTime(0.001, ctxTime + 0.04);
        noise.connect(hp).connect(env).connect(ctx.destination);
        noise.start(ctxTime);
        noise.stop(ctxTime + 0.05);
    }

    /** Bass tone (sub bass / pluck) for melody. */
    bass(ctxTime, freq = 80, duration = 0.25, gain = 0.18) {
        const ctx = this.ctx;
        const osc = ctx.createOscillator();
        const env = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.value = freq;
        env.gain.setValueAtTime(gain, ctxTime);
        env.gain.exponentialRampToValueAtTime(0.001, ctxTime + duration);
        osc.connect(env).connect(ctx.destination);
        osc.start(ctxTime);
        osc.stop(ctxTime + duration + 0.02);
    }

    /** Hit sound when the user successfully hits a note. */
    hit(perfect = false) {
        if (!this.ctx) return;
        const t = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const env = this.ctx.createGain();
        osc.frequency.value = perfect ? 1200 : 800;
        env.gain.setValueAtTime(0.25, t);
        env.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
        osc.connect(env).connect(this.ctx.destination);
        osc.start(t);
        osc.stop(t + 0.1);
    }

    /**
     * Schedule the full backing track for a song.
     * Returns the song's duration in seconds.
     */
    startSong(song) {
        this.init();
        this.startTime = this.ctx.currentTime + 0.1; // tiny lead-in so first beat isn't clipped
        const beatSec = 60 / song.bpm;
        const totalBeats = song.duration;

        for (let b = 0; b < totalBeats; b++) {
            const t = this.startTime + b * beatSec;
            // Kick on every beat
            this.kick(t);
            // Snare on every other beat (offbeat)
            if (b % 2 === 1) this.snare(t);
            // Hihat on every half-beat
            this.hihat(t);
            this.hihat(t + beatSec * 0.5);
            // Light bassline (every 4 beats, alternating notes)
            if (b % 4 === 0) {
                const notes = [55, 73, 65, 82]; // A1, D2, C2, E2 — simple loop
                this.bass(t, notes[(b / 4) % notes.length], beatSec * 0.9, 0.15);
            }
        }

        return totalBeats * beatSec;
    }

    stop() {
        // Web Audio doesn't have a simple "stop all" — we just close & recreate
        if (this.ctx && this.ctx.state !== "closed") {
            this.ctx.close();
            this.ctx = null;
        }
    }
}
