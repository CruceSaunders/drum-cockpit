/* ============================================================================
 * game.js — Rhythm Rush game engine
 *
 * Sync model: audio context's `currentTime` is the master clock. For each
 * note, we know exactly when it should be hit (song-time). The note's Y
 * position on screen is computed from that and the constant TRAVEL_TIME so
 * that the note hits the bottom of its lane at exactly the right moment.
 * ============================================================================
 */

// ---------- Tunable constants ------------------------------------------------

const TRAVEL_TIME    = 1.5;   // seconds for a note to fall top -> bottom
const LANE_COUNT     = 5;
const HIT_ZONE_HEIGHT = 80;   // px; bottom area where notes are hittable
const HIT_WINDOW_GOOD    = 0.12;  // ± seconds, "good"
const HIT_WINDOW_PERFECT = 0.06;  // ± seconds, "perfect"
const MISS_WINDOW        = 0.15;  // seconds late after which the note auto-misses

const QUIPS = {
    great: [
        "Claude is taking notes.",
        "git push --force on those drums.",
        "You shipped it.",
    ],
    ok: [
        "The CI passed but barely.",
        "Tests are flaky. Like your timing.",
        "Merged with 2/3 reviewers.",
    ],
    bad: [
        "You may have rebased onto the wrong branch.",
        "Did you commit straight to main again?",
        "The senior engineer would like a word.",
    ],
};

// ---------- Game state -------------------------------------------------------

const audio = new AudioEngine();
let canvas, ctx;
let song = null;
let notes = [];           // active notes: {beat, lane, hitTime, hit, judged}
let songDuration = 0;
let running = false;
let lastFrame = 0;

let score = 0;
let combo = 0;
let maxCombo = 0;
let perfectCount = 0;
let goodCount = 0;
let missCount = 0;

let laneFlash = [0, 0, 0, 0, 0]; // ms timer per lane for visual flash

// ---------- Setup ------------------------------------------------------------

function resizeCanvas() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
}

function setupCanvas() {
    canvas = document.getElementById("canvas");
    ctx = canvas.getContext("2d");
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
}

function laneX(lane) {
    // Lane 1..5 -> centered group of 5 columns, 90px wide each, centered horizontally
    const laneW = 90;
    const groupW = laneW * LANE_COUNT;
    const groupX = (canvas.width - groupW) / 2;
    return groupX + (lane - 1) * laneW + laneW / 2;
}

function laneRect() {
    const laneW = 90;
    const groupW = laneW * LANE_COUNT;
    return { x: (canvas.width - groupW) / 2, w: groupW, laneW };
}

// ---------- Note model -------------------------------------------------------

function loadSong(songIndex) {
    song = SONGS[songIndex];
    const beatSec = 60 / song.bpm;
    notes = song.chart.map(entry => ({
        beat: entry.beat,
        lane: entry.lane,
        hitTime: entry.beat * beatSec,
        hit: false,
        judged: false,
    }));
}

// ---------- Game loop --------------------------------------------------------

function startGame(songIndex) {
    loadSong(songIndex);
    score = 0;
    combo = 0;
    maxCombo = 0;
    perfectCount = 0;
    goodCount = 0;
    missCount = 0;
    laneFlash = [0, 0, 0, 0, 0];

    document.getElementById("score").textContent = "0";
    document.getElementById("combo").textContent = "0x";
    document.getElementById("song-title").textContent = song.name;

    show("game-screen");
    songDuration = audio.startSong(song);
    running = true;
    lastFrame = performance.now();
    requestAnimationFrame(frame);
}

function frame(now) {
    if (!running) return;
    const dt = now - lastFrame;
    lastFrame = now;

    update(dt);
    render();

    const t = audio.now();
    if (t > songDuration + TRAVEL_TIME + 1) {
        endGame();
        return;
    }
    requestAnimationFrame(frame);
}

function update(dt) {
    const t = audio.now();

    // Auto-miss notes that passed too far in the past
    for (const n of notes) {
        if (n.judged) continue;
        if (t - n.hitTime > MISS_WINDOW) {
            n.judged = true;
            n.hit = false;
            registerMiss();
        }
    }

    for (let i = 0; i < LANE_COUNT; i++) {
        if (laneFlash[i] > 0) laneFlash[i] -= dt;
    }
}

function render() {
    const t = audio.now();
    const W = canvas.width;
    const H = canvas.height;
    const { x: groupX, w: groupW, laneW } = laneRect();
    const hitZoneY = H - HIT_ZONE_HEIGHT - 60; // 60px gutter for lane labels

    // BG
    ctx.fillStyle = "#0a0a14";
    ctx.fillRect(0, 0, W, H);

    // Lane backgrounds
    for (let i = 0; i < LANE_COUNT; i++) {
        const lx = groupX + i * laneW;
        ctx.fillStyle = (i % 2 === 0) ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.04)";
        ctx.fillRect(lx, 0, laneW, H);

        // Lane flash
        if (laneFlash[i] > 0) {
            ctx.fillStyle = `rgba(106, 92, 255, ${0.25 * (laneFlash[i] / 150)})`;
            ctx.fillRect(lx, 0, laneW, H);
        }
    }

    // Hit zone line
    ctx.strokeStyle = "rgba(255,255,255,0.18)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(groupX, hitZoneY);
    ctx.lineTo(groupX + groupW, hitZoneY);
    ctx.stroke();

    // Hit zone glow
    const grad = ctx.createLinearGradient(0, hitZoneY, 0, hitZoneY + HIT_ZONE_HEIGHT);
    grad.addColorStop(0, "rgba(106, 92, 255, 0.30)");
    grad.addColorStop(1, "rgba(106, 92, 255, 0)");
    ctx.fillStyle = grad;
    ctx.fillRect(groupX, hitZoneY, groupW, HIT_ZONE_HEIGHT);

    // Notes
    for (const n of notes) {
        if (n.judged && n.hit) continue;  // hit & gone
        const dtToHit = n.hitTime - t;
        if (dtToHit > TRAVEL_TIME) continue;       // not spawned yet
        if (dtToHit < -MISS_WINDOW * 2) continue;  // way past, skip render

        // Y: maps [TRAVEL_TIME .. 0] -> [0 .. hitZoneY]
        const progress = 1 - (dtToHit / TRAVEL_TIME);
        const y = progress * hitZoneY;
        const cx = laneX(n.lane);

        const noteR = 32;

        // Glow
        ctx.fillStyle = `rgba(106, 92, 255, ${Math.min(0.45, progress * 0.5)})`;
        ctx.beginPath();
        ctx.arc(cx, y, noteR + 10, 0, Math.PI * 2);
        ctx.fill();

        // Core
        const noteGrad = ctx.createLinearGradient(cx - noteR, y, cx + noteR, y);
        noteGrad.addColorStop(0, "#5cdaff");
        noteGrad.addColorStop(1, "#6a5cff");
        ctx.fillStyle = noteGrad;
        ctx.beginPath();
        ctx.arc(cx, y, noteR, 0, Math.PI * 2);
        ctx.fill();

        // Lane number on note
        ctx.fillStyle = "rgba(255,255,255,0.95)";
        ctx.font = "bold 18px -apple-system, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(n.lane, cx, y);
    }
}

// ---------- Input handling ---------------------------------------------------

function handleHit(lane) {
    laneFlash[lane - 1] = 150;

    const t = audio.now();

    // Find the closest unjudged note in this lane
    let best = null;
    let bestDt = Infinity;
    for (const n of notes) {
        if (n.judged) continue;
        if (n.lane !== lane) continue;
        const dt = Math.abs(n.hitTime - t);
        if (dt < bestDt) { bestDt = dt; best = n; }
    }

    if (!best || bestDt > HIT_WINDOW_GOOD + 0.05) {
        // Too far from any note → counts as a "stray hit" — we don't penalize
        // since the missed note will auto-miss on its own.
        showJudgement("miss");
        return;
    }

    best.judged = true;
    best.hit = true;

    if (bestDt <= HIT_WINDOW_PERFECT) {
        score += 100; perfectCount++; combo++; audio.hit(true);
        showJudgement("perfect");
    } else if (bestDt <= HIT_WINDOW_GOOD) {
        score += 50; goodCount++; combo++; audio.hit(false);
        showJudgement("good");
    } else {
        registerMiss();
    }

    maxCombo = Math.max(maxCombo, combo);
    refreshHUD();
}

function registerMiss() {
    missCount++;
    combo = 0;
    showJudgement("miss");
    refreshHUD();
}

function refreshHUD() {
    document.getElementById("score").textContent = score.toLocaleString();
    document.getElementById("combo").textContent = combo + "x";
}

function showJudgement(kind) {
    const el = document.getElementById("judgement");
    el.textContent = kind.toUpperCase();
    el.className = "show " + kind;
    clearTimeout(showJudgement._t);
    showJudgement._t = setTimeout(() => {
        el.className = "";
    }, 350);
}

window.addEventListener("keydown", (e) => {
    if (!running) return;
    const n = parseInt(e.key, 10);
    if (n >= 1 && n <= 5) handleHit(n);
});

// ---------- Screen switching -------------------------------------------------

function show(screenId) {
    document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
    document.getElementById(screenId).classList.add("active");
}

function endGame() {
    running = false;
    audio.stop();

    const totalNotes = perfectCount + goodCount + missCount;
    const accuracy = totalNotes ? Math.round(((perfectCount + goodCount) / totalNotes) * 100) : 0;

    document.getElementById("result-score").textContent = score.toLocaleString();
    document.getElementById("result-accuracy").textContent = accuracy + "%";
    document.getElementById("result-combo").textContent = maxCombo + "x";
    document.getElementById("result-breakdown").textContent =
        `${perfectCount} / ${goodCount} / ${missCount}`;

    let bucket;
    if (accuracy >= 85) bucket = "great";
    else if (accuracy >= 50) bucket = "ok";
    else bucket = "bad";
    const qs = QUIPS[bucket];
    document.getElementById("result-quip").textContent =
        qs[Math.floor(Math.random() * qs.length)];

    show("result-screen");
}

// ---------- Wire up song select / play-again ---------------------------------

document.querySelectorAll(".song-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        const songIdx = parseInt(btn.dataset.song, 10);
        startGame(songIdx);
    });
});
document.getElementById("play-again").addEventListener("click", () => {
    show("song-select");
});

// ---------- Boot -------------------------------------------------------------

setupCanvas();
