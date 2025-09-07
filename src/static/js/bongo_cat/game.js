// static/js/bongo_cat/game.js
(() => {
  // ========================================================================
  // GLOBAL DOM + CONFIG
  // ========================================================================
  const root = document.getElementById("bongo-root");
  if (!root) return;

  const scoreEl = document.getElementById("score");
  const tapBtn  = document.getElementById("tap-btn");
  const toLb    = document.getElementById("to-leaderboard");

  const syncUrl        = root.dataset.syncUrl;
  const leaderboardUrl = root.dataset.leaderboardUrl;
  const initialScore   = Number(root.dataset.initialScore || 0);

  // ========================================================================
  // ANTI-SPAM + COUNTERS (state and helpers)
  // ========================================================================
  const MIN_INTERVAL_MS = 1;   // cooldown between counted taps (tune as desired)
  let lastIncAt = 0;
  let baseTotal = initialScore; // server-confirmed total
  let localDelta = 0;           // buffered increments not yet sent

  // Render current total (server base + local buffer)
  function render() {
    if (scoreEl) scoreEl.textContent = String(baseTotal + localDelta);
  }

  // Increment once, respecting cooldown
  function tryIncrement() {
    const now = performance.now();
    if (now - lastIncAt < MIN_INTERVAL_MS) return; // cooldown
    lastIncAt = now;
    localDelta += 1;
    render();
  }

  // ========================================================================
  // VISUAL STATE (button image: left/right/both)
  // ========================================================================
  function clearPressed() {
    if (!tapBtn) return;
    tapBtn.classList.remove("pressed-left", "pressed-right", "pressed-both");
  }
  function setPressed(kind) {
    if (!tapBtn) return;
    clearPressed();
    if (kind === "left")  tapBtn.classList.add("pressed-left");
    if (kind === "right") tapBtn.classList.add("pressed-right");
    if (kind === "both")  tapBtn.classList.add("pressed-both");
  }

  // ========================================================================
  // EVENT LISTENERS (pointer + keyboard)
  // ========================================================================

  // ----- Pointer must click the image → always BOTH -----
  if (tapBtn) {
    tapBtn.addEventListener("pointerdown", () => setPressed("both"));
    tapBtn.addEventListener("pointerup", (e) => {
      if (e.button !== 0) { clearPressed(); return; }
      tryIncrement();
      clearPressed();
    });
    tapBtn.addEventListener("pointercancel", clearPressed);
    tapBtn.addEventListener("pointerleave",  clearPressed);
    tapBtn.addEventListener("contextmenu", (e) => e.preventDefault()); // avoid weird states

    // Preload pressed images to avoid first-press flicker
    try {
      ["BongoBoth.png", "BongoLeft.png", "BongoRight.png"].forEach(n => {
        const img = new Image(); img.src = `/static/img/bongo_cat/${n}`;
      });
    } catch {}
  }

  // ----- Keyboard global (Space/Enter/letters/digits), except when typing -----
  function isTypingTarget(el) {
    if (!el) return false;
    const tag = (el.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || el.isContentEditable;
  }
  function isAlphaNum(e) {
    if (!e.key || e.key.length !== 1) return false;
    return /[a-z0-9]/i.test(e.key);
  }
  function isScoringKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return false; // don't hijack shortcuts
    return e.code === "Space" || e.code === "Enter" || isAlphaNum(e);
  }

  // Map key code → left/right/both
  const LEFT_CODES = new Set([
    "Digit1","Digit2","Digit3","Digit4","Digit5",
    "KeyQ","KeyW","KeyE","KeyR","KeyT",
    "KeyA","KeyS","KeyD","KeyF","KeyG",
    "KeyZ","KeyX","KeyC","KeyV","KeyB",
    "Numpad1","Numpad2","Numpad3","Numpad4", "Numpad5",
  ]);
  const RIGHT_CODES = new Set([
    "Digit6","Digit7","Digit8","Digit9","Digit0",
    "KeyY","KeyU","KeyI","KeyO","KeyP",
    "KeyH","KeyJ","KeyK","KeyL",
    "KeyN","KeyM","Comma","Period","Slash",
    "Numpad6","Numpad7","Numpad8","Numpad9", "Numpad0",
  ]);
  function keySide(e) {
    if (e.code === "Space" || e.code === "Enter") return "both";
    if (LEFT_CODES.has(e.code))  return "left";
    if (RIGHT_CODES.has(e.code)) return "right";
    if (/[a-z0-9]/i.test(e.key)) return "right"; // conservative fallback
    return null;
  }

  // Keydown = show pressed visual; Keyup = count + clear visual.
  document.addEventListener("keydown", (e) => {
    if (e.repeat) return;
    if (!isScoringKey(e)) return;
    if (isTypingTarget(e.target)) return;

    const side = keySide(e);
    if (!side) return;
    setPressed(side);
    if (e.code === "Space") e.preventDefault(); // stop page scroll
  });

  document.addEventListener("keyup", (e) => {
    if (!isScoringKey(e)) return;
    if (isTypingTarget(e.target)) return;

    tryIncrement();
    clearPressed();
    if (e.code === "Space") e.preventDefault();
  });

  // ========================================================================
  // BACKEND SYNC (batch JSON to avoid server load)
  // ========================================================================
  async function flush() {
    if (localDelta === 0) return;
    const delta = localDelta;
    localDelta = 0; // optimistic reset

    try {
      const res = await fetch(syncUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ delta }) // -> Flask request.get_json()
      });
      if (!res.ok) throw new Error("sync failed");
      const data = await res.json();
      if (typeof data.total === "number") baseTotal = data.total;
      else localDelta += delta; // restore on bad payload
    } catch {
      localDelta += delta;       // restore on failure
    } finally {
      render();
    }
  }

  // Periodic sync
  const timer = setInterval(flush, 10000);

  // Flush before navigating to leaderboard
  if (toLb) {
    toLb.addEventListener("click", async (e) => {
      e.preventDefault();
      await flush();
      window.location.href = leaderboardUrl;
    });
  }

  // Flush when tab hidden
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });

  // Last-chance beacon on unload (non-blocking)
  window.addEventListener("beforeunload", () => {
    if (localDelta === 0) return;
    try {
      const blob = new Blob([JSON.stringify({ delta: localDelta })], { type: "application/json" });
      navigator.sendBeacon(syncUrl, blob);
    } catch {}
  });

  // Initial paint
  render();
})();
