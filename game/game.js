/* ============================================================================
 * game.js — Rhythm Rush game engine
 *
 * Sync model: audio context's `currentTime` is the master clock. For each
 * note, we know exactly when it should be hit (song-time). The note's Y
 * position on screen is computed from that and the constant TRAVEL_TIME so
 * that the note hits the bottom of its lane at exactly the right moment.
 *
 * Inputs:
 *   Drums 1-5 = lane hits in-game (5 lanes total)
 *   Drum 5    = on song-select & result screens: menu navigation
 *               (single tap = cycle, double tap = select / back)
 *   Drum 6    = mode switch back to coding (handled in drummer.py, not here)
 *
 * The screen-state check in the keydown listener routes drum 5 differently
 * depending on what's visible: nav on menus, lane-hit during gameplay.
 * ============================================================================
 */

// ---------- Tunable constants ------------------------------------------------

const TRAVEL_TIME    = 1.5;   // seconds for a note to fall top -> bottom
const LANE_COUNT     = 5;
const LANE_WIDTH     = 110;   // must match .lane-label width in style.css
const HIT_ZONE_HEIGHT = 80;
const HIT_WINDOW_GOOD    = 0.12;  // ± seconds, "good"
const HIT_WINDOW_PERFECT = 0.06;  // ± seconds, "perfect"
const MISS_WINDOW        = 0.15;  // seconds late after which the note auto-misses
const DOUBLE_TAP_WINDOW  = 400;   // ms — double-tap drum 5 to select song

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
let notes = [];
let songDuration = 0;
let running = false;
let lastFrame = 0;

let score = 0;
let combo = 0;
let maxCombo = 0;
let perfectCount = 0;
let goodCount = 0;
let missCount = 0;

let laneFlash = new Array(LANE_COUNT).fill(0);

// Song-select navigation state
let selectedSongIndex = 0;
let lastSelectTapTime = 0;

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
    const laneW = LANE_WIDTH;
    const groupW = laneW * LANE_COUNT;
    const groupX = (canvas.width - groupW) / 2;
    return groupX + (lane - 1) * laneW + laneW / 2;
}

function laneRect() {
    const laneW = LANE_WIDTH;
    const groupW = laneW * LANE_COUNT;
    return { x: (canvas.width - groupW) / 2, w: groupW, laneW };
}

// ---------- Note model -------------------------------------------------------

function loadSong(songIndex) {
    song = SONGS[songIndex];
    const beatSec = 60 / song.bpm;
    notes = song.chart
        .filter(entry => entry.lane >= 1 && entry.lane <= LANE_COUNT)
        .map(entry => ({
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
    laneFlash = new Array(LANE_COUNT).fill(0);

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
    const hitZoneY = H - HIT_ZONE_HEIGHT - 60;

    // BG
    ctx.fillStyle = "#0a0a14";
    ctx.fillRect(0, 0, W, H);

    // Lane backgrounds
    for (let i = 0; i < LANE_COUNT; i++) {
        const lx = groupX + i * laneW;
        ctx.fillStyle = (i % 2 === 0) ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.04)";
        ctx.fillRect(lx, 0, laneW, H);

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

    const grad = ctx.createLinearGradient(0, hitZoneY, 0, hitZoneY + HIT_ZONE_HEIGHT);
    grad.addColorStop(0, "rgba(106, 92, 255, 0.30)");
    grad.addColorStop(1, "rgba(106, 92, 255, 0)");
    ctx.fillStyle = grad;
    ctx.fillRect(groupX, hitZoneY, groupW, HIT_ZONE_HEIGHT);

    // Notes
    for (const n of notes) {
        if (n.judged && n.hit) continue;
        const dtToHit = n.hitTime - t;
        if (dtToHit > TRAVEL_TIME) continue;
        if (dtToHit < -MISS_WINDOW * 2) continue;

        const progress = 1 - (dtToHit / TRAVEL_TIME);
        const y = progress * hitZoneY;
        const cx = laneX(n.lane);

        const noteR = 36;

        // Glow
        ctx.fillStyle = `rgba(106, 92, 255, ${Math.min(0.45, progress * 0.5)})`;
        ctx.beginPath();
        ctx.arc(cx, y, noteR + 10, 0, Math.PI * 2);
        ctx.fill();

        const noteGrad = ctx.createLinearGradient(cx - noteR, y, cx + noteR, y);
        noteGrad.addColorStop(0, "#5cdaff");
        noteGrad.addColorStop(1, "#6a5cff");
        ctx.fillStyle = noteGrad;
        ctx.beginPath();
        ctx.arc(cx, y, noteR, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "rgba(255,255,255,0.95)";
        ctx.font = "bold 20px -apple-system, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(n.lane, cx, y);
    }
}

// ---------- In-game hit handling ---------------------------------------------

function handleHit(lane) {
    laneFlash[lane - 1] = 150;

    const t = audio.now();

    let best = null;
    let bestDt = Infinity;
    for (const n of notes) {
        if (n.judged) continue;
        if (n.lane !== lane) continue;
        const dt = Math.abs(n.hitTime - t);
        if (dt < bestDt) { bestDt = dt; best = n; }
    }

    if (!best || bestDt > HIT_WINDOW_GOOD + 0.05) {
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

// ---------- Song-select navigation (drum 5) ----------------------------------

function highlightSelectedSong() {
    document.querySelectorAll(".song-btn").forEach((btn, i) => {
        btn.classList.toggle("selected", i === selectedSongIndex);
    });
}

function handleSongSelectKey5() {
    const now = performance.now();
    if (now - lastSelectTapTime < DOUBLE_TAP_WINDOW) {
        // Second tap of double-tap → select current
        lastSelectTapTime = 0;
        startGame(selectedSongIndex);
    } else {
        // Single tap → cycle to next song
        selectedSongIndex = (selectedSongIndex + 1) % SONGS.length;
        highlightSelectedSong();
        lastSelectTapTime = now;
    }
}

function handleResultScreenKey5() {
    // Just go back to song select on result screen
    show("song-select");
}

// ---------- Screen switching -------------------------------------------------

function show(screenId) {
    document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
    document.getElementById(screenId).classList.add("active");
    // Re-grab focus when changing screens so drums reach the page
    try { document.body.focus(); } catch (e) {}
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

// ---------- Global key listener ----------------------------------------------

function flashLastKey(keyStr) {
    const el = document.getElementById("last-key");
    if (!el) return;
    el.textContent = keyStr;
    el.classList.remove("flash");
    void el.offsetWidth; // restart CSS animation
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 200);
}

window.addEventListener("keydown", (e) => {
    // Always show the indicator so you can verify drums are reaching the page
    if (e.key >= "1" && e.key <= "9") flashLastKey(e.key);

    if (document.getElementById("song-select").classList.contains("active")) {
        if (e.key === "5") {
            handleSongSelectKey5();
            return;
        }
    } else if (document.getElementById("result-screen").classList.contains("active")) {
        if (e.key === "5") {
            handleResultScreenKey5();
            return;
        }
    } else if (running) {
        // In-game: drums 1-4 hit lanes 1-4
        const n = parseInt(e.key, 10);
        if (n >= 1 && n <= LANE_COUNT) handleHit(n);
    }
});

// ---------- Wire up mouse fallbacks for song select and play-again -----------

document.querySelectorAll(".song-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        const songIdx = parseInt(btn.dataset.song, 10);
        selectedSongIndex = songIdx;
        highlightSelectedSong();
        startGame(songIdx);
    });
});
document.getElementById("play-again").addEventListener("click", () => {
    show("song-select");
});

// ---------- Boot -------------------------------------------------------------

setupCanvas();
highlightSelectedSong();
// Try to grab keyboard focus right away
window.addEventListener("load", () => { try { document.body.focus(); } catch (e) {} });
try { document.body.focus(); } catch (e) {}
