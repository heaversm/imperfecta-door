# Melt Gallery Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the friend's WebGL melt + cutout-mosaic experience as a feature-flagged display mode that runs alongside the current `viewer.html` effects loop, triggered by the real RF doorbell, without removing any existing functionality.

**Architecture:** Reuse the friend's standalone Node server (`facecapture/container/server.mjs` in `STORAGE_DIR` mode — local disk + offline `@imgly` background removal + `/ws` feed). Add a `POST /api/ring` endpoint that broadcasts a `ring` message over the existing `/ws`; the page runs its existing `capture()` on it. `orchestrator.py` gets a display-mode switch: in `melt` mode it POSTs `/api/ring` instead of `/trigger`. A single `~/display_mode` file on the Pi drives both the orchestrator's routing and which URL the kiosk opens. The effects pipeline (`effects_server.py`, `viewer.html`, MaixCam) is never modified and stays the default.

**Tech Stack:** Node 20 (Hono, `@imgly/background-removal-node`, `sharp`, `ws`), WebGL, Python 3 (`orchestrator.py`), systemd, Chromium kiosk on Raspberry Pi OS 64-bit (labwc/Wayland).

**Note on testing:** Per project convention, this plan uses **verification-driven** steps (run the real thing, observe behavior, curl endpoints) rather than failing-unit-test-first. Each task ends with a concrete check and a commit.

---

## File Structure

- `facecapture/container/server.mjs` — **modify.** Add `POST /api/ring` + a `broadcastRing()` that sends `{type:'ring'}` over the existing `/ws` (standalone mode only).
- `facecapture/container/public/index.html` — **modify.** Handle a `ring` WebSocket message by calling the existing `capture()`. Add an optional FPS overlay gated by `?fps=1`.
- `facecapture/container/test-ring.mjs` — **create.** Small Node script: connect to `/ws`, POST `/api/ring`, assert a `ring` message arrives.
- `prototype/facecapture.service` — **create.** systemd unit running the standalone server on the Pi (port 8090, `STORAGE_DIR` set).
- `prototype/orchestrator.py` — **modify.** Add `FACECAPTURE_PORT`, a display-mode reader, and route the doorbell trigger to `/api/ring` in melt mode.
- `prototype/kiosk_loading.html` — **modify.** Choose the target/health URL from a `?mode=` query param.
- `prototype/kiosk_autostart.sh` — **modify.** Read `~/display_mode`, pass it as `?mode=`, add the camera auto-grant flag.
- `prototype/deploy.sh` — **modify.** Add a step to sync the facecapture source to the Pi and restart `facecapture.service`.

---

## Phase 1 — App additions (develop + verify on the Mac)

### Task 1: Add `POST /api/ring` + `broadcastRing()` to the standalone server

**Files:**
- Modify: `facecapture/container/server.mjs`

- [ ] **Step 1: Declare a top-level `broadcastRing` alongside `broadcast`**

In `server.mjs`, find (line ~62):

```js
// ---------------- standalone mode: storage + API + live feed ----------------
let broadcast = () => {};
```

Replace with:

```js
// ---------------- standalone mode: storage + API + live feed ----------------
let broadcast = () => {};
// Doorbell "ring" push over the same /ws the feed uses. Assigned in the wss block
// below (standalone mode only); a no-op until then so a stray call can't throw.
let broadcastRing = () => {};
```

- [ ] **Step 2: Register the `/api/ring` route inside the `if (STORAGE_DIR)` block**

Find the end of the `POST /api/capture` handler and the `GET /files/...` route inside `if (STORAGE_DIR) {`. Immediately after the `/api/heads` route (line ~90), add:

```js
  // Doorbell trigger: the Pi orchestrator POSTs this on an RF burst. It just
  // fans a "ring" out to every connected page over the existing /ws — the page
  // runs the same capture() the on-screen button does. No body needed.
  app.post("/api/ring", (c) => {
    broadcastRing();
    return c.json({ ok: true });
  });
```

- [ ] **Step 3: Assign `broadcastRing` in the WebSocket block**

Find the `broadcast = (manifest) => {...}` assignment near the end (line ~228, inside the second `if (STORAGE_DIR)` block). Immediately after that assignment, add:

```js
  broadcastRing = () => {
    const msg = JSON.stringify({ type: "ring" });
    for (const client of wss.clients) {
      if (client.readyState === 1) client.send(msg);
    }
  };
```

- [ ] **Step 4: Start the standalone server locally and verify the endpoint responds**

Run (from `facecapture/container/`, deps already installed here on the Mac):

```bash
cd facecapture/container
npm install
STORAGE_DIR=/tmp/facecapture-data PORT=8090 node server.mjs
```

Expected console: `facecapture standalone server on :8090` and, shortly after, `model pre-warmed`.

In a second terminal:

```bash
curl -s -X POST http://localhost:8090/api/ring
```

Expected: `{"ok":true}`

- [ ] **Step 5: Commit**

```bash
git add facecapture/container/server.mjs
git commit -m "feat(facecapture): add /api/ring -> /ws ring broadcast (standalone mode)"
```

---

### Task 2: Handle the `ring` message in the page (call `capture()`)

**Files:**
- Modify: `facecapture/container/public/index.html`

- [ ] **Step 1: Extend the WebSocket `onmessage` handler**

Find (line ~329):

```js
				ws.onmessage = (e) => {
					try {
						const msg = JSON.parse(e.data)
						if (msg.type === 'feed' && Array.isArray(msg.heads)) {
							applyFeed(msg.heads)
						}
					} catch (err) {
						console.error('ws message', err)
					}
				}
```

Replace with:

```js
				ws.onmessage = (e) => {
					try {
						const msg = JSON.parse(e.data)
						if (msg.type === 'feed' && Array.isArray(msg.heads)) {
							applyFeed(msg.heads)
						} else if (msg.type === 'ring') {
							// Real doorbell rang — same path as the on-screen button.
							// Dormant in the tablet demo (no ring messages arrive there).
							capture()
						}
					} catch (err) {
						console.error('ws message', err)
					}
				}
```

- [ ] **Step 2: Verify the button still works (demo unchanged) and the ring path fires**

With the server from Task 1 still running (`STORAGE_DIR=/tmp/facecapture-data PORT=8090 node server.mjs`), open `http://localhost:8090/` in Chrome, grant camera access.

- Click **Ring Doorbell** → the frame should freeze, flash, and dissolve into particles; a cutout should appear in the collage. (Confirms the demo path is intact.)
- Then from a terminal: `curl -s -X POST http://localhost:8090/api/ring` → the melt should fire **without** clicking the button. (Confirms the doorbell path.)

- [ ] **Step 3: Commit**

```bash
git add facecapture/container/public/index.html
git commit -m "feat(facecapture): trigger capture() on a /ws ring message"
```

---

### Task 3: Add an automated ring-path test script

**Files:**
- Create: `facecapture/container/test-ring.mjs`

- [ ] **Step 1: Write the test script**

Create `facecapture/container/test-ring.mjs`:

```js
// Verifies the doorbell path end to end at the transport level:
// connect to /ws, POST /api/ring, assert a {type:'ring'} message arrives.
// Run against a live standalone server:
//   STORAGE_DIR=/tmp/facecapture-data PORT=8090 node server.mjs   (in one shell)
//   node test-ring.mjs                                            (in another)
import WebSocket from "ws";

const PORT = Number(process.env.PORT) || 8090;
const ws = new WebSocket(`ws://localhost:${PORT}/ws`);

const timer = setTimeout(() => {
  console.error("FAIL: no ring message within 5s");
  process.exit(1);
}, 5000);

ws.on("open", async () => {
  const res = await fetch(`http://localhost:${PORT}/api/ring`, { method: "POST" });
  if (!res.ok) {
    console.error(`FAIL: /api/ring returned ${res.status}`);
    process.exit(1);
  }
});

ws.on("message", (data) => {
  const msg = JSON.parse(data.toString());
  if (msg.type === "ring") {
    clearTimeout(timer);
    console.log("PASS: received ring over /ws");
    process.exit(0);
  }
});

ws.on("error", (err) => {
  console.error("FAIL: ws error", err.message);
  process.exit(1);
});
```

- [ ] **Step 2: Run it against the running server**

With the standalone server running (from Task 1), run:

```bash
cd facecapture/container
node test-ring.mjs
```

Expected: `PASS: received ring over /ws` and exit code 0.

- [ ] **Step 3: Commit**

```bash
git add facecapture/container/test-ring.mjs
git commit -m "test(facecapture): assert /api/ring fans out over /ws"
```

---

## Phase 2 — Pi runtime (get the app running on the Pi, offline, and measure perf)

### Task 4: Install Node + facecapture deps on the Pi and warm the offline model

**Files:** none (Pi setup). Assumes Raspberry Pi OS **64-bit** (required for `onnxruntime-node`/`sharp` arm64 prebuilds) and SSH alias `imperfecta-pi`.

- [ ] **Step 1: Confirm Node 20+ on the Pi (install if missing)**

```bash
ssh imperfecta-pi 'node --version || echo NONE'
```

If missing or older than v20, install NodeSource Node 20:

```bash
ssh -t imperfecta-pi 'curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs'
```

Expected: `node --version` prints `v20.x` or newer.

- [ ] **Step 2: Copy the facecapture source to the Pi (source only, no node_modules)**

Native modules must be built/installed **on the Pi** (arm64), so never copy the Mac's `node_modules`.

```bash
rsync -av --exclude node_modules --exclude .next \
  /Users/mheavers/Desktop/imperfecta/_project/facecapture/container/ \
  imperfecta-pi:~/facecapture/container/
```

- [ ] **Step 3: Install deps on the Pi**

```bash
ssh imperfecta-pi 'cd ~/facecapture/container && npm install --omit=dev'
```

Expected: completes without native-build errors (`sharp`, `onnxruntime-node` pull arm64 prebuilds). This can take several minutes on a Pi 3B+.

- [ ] **Step 4: Warm the offline background-removal model (needs network ONCE)**

`@imgly` caches model assets to disk on first use; after this the venue can be offline. With the Pi online, run the server briefly:

```bash
ssh imperfecta-pi 'cd ~/facecapture/container && STORAGE_DIR=$HOME/facecapture-data PORT=8090 timeout 90 node server.mjs'
```

Expected console: `facecapture standalone server on :8090` then `model pre-warmed`. If `model pre-warmed` prints, the model is cached. (The `timeout 90` stops it after warm-up.)

- [ ] **Step 5: Verify the endpoints on the Pi**

Start the server again and, from the Pi, curl it:

```bash
ssh imperfecta-pi 'cd ~/facecapture/container && STORAGE_DIR=$HOME/facecapture-data PORT=8090 node server.mjs &
  sleep 8; curl -s http://127.0.0.1:8090/api/health; curl -s -X POST http://127.0.0.1:8090/api/ring; kill %1'
```

Expected: `{"ok":true}` from `/api/health` and `{"ok":true}` from `/api/ring`.

- [ ] **Step 6: Commit** (nothing to commit — Pi setup only). Record completion in the task tracker.

---

### Task 5: Add a systemd service for the standalone server

**Files:**
- Create: `prototype/facecapture.service`

- [ ] **Step 1: Write the unit file**

Create `prototype/facecapture.service`:

```ini
[Unit]
Description=Imperfecta facecapture (melt gallery mode)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=imperfecta
WorkingDirectory=/home/imperfecta/facecapture/container
Environment=STORAGE_DIR=/home/imperfecta/facecapture-data
Environment=PORT=8090
Environment=IMPERFECTA_INSTALL=1
ExecStart=/usr/bin/node server.mjs
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Install and start it on the Pi**

```bash
scp prototype/facecapture.service imperfecta-pi:~/
ssh -t imperfecta-pi 'sudo mv ~/facecapture.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now facecapture'
```

- [ ] **Step 3: Verify the service is active and serving**

```bash
ssh imperfecta-pi 'systemctl is-active facecapture && curl -s http://127.0.0.1:8090/api/health'
```

Expected: `active` and `{"ok":true}`.

- [ ] **Step 4: Commit**

```bash
git add prototype/facecapture.service
git commit -m "feat(pi): systemd unit for the facecapture standalone server"
```

---

### Task 6: Measure the melt's FPS on the Pi (validation gate)

**Files:**
- Modify: `facecapture/container/public/index.html`

- [ ] **Step 1: Add an optional FPS overlay to the melt loop**

In `index.html`, find the `tick` function inside the `fx` module (line ~501):

```js
						const t0 = performance.now()
						const tick = () => {
							gl.uniform1f(loc.time, (performance.now() - t0) / 1000)
							gl.clearColor(0, 0, 0, 0)
							gl.clear(gl.COLOR_BUFFER_BIT)
							gl.drawArrays(gl.POINTS, 0, count)
							raf = requestAnimationFrame(tick)
						}
						tick()
```

Replace with:

```js
						const t0 = performance.now()
						// Optional FPS overlay for perf validation on the Pi: add ?fps=1
						const showFps = new URLSearchParams(location.search).has('fps')
						let fpsEl = null
						if (showFps) {
							fpsEl = document.createElement('div')
							fpsEl.style.cssText =
								'position:fixed;top:6px;left:6px;z-index:2000;color:#0f0;' +
								'font:14px monospace;background:rgba(0,0,0,.6);padding:4px 8px'
							document.body.appendChild(fpsEl)
						}
						let frames = 0
						let lastReport = t0
						const tick = () => {
							const now = performance.now()
							gl.uniform1f(loc.time, (now - t0) / 1000)
							gl.clearColor(0, 0, 0, 0)
							gl.clear(gl.COLOR_BUFFER_BIT)
							gl.drawArrays(gl.POINTS, 0, count)
							frames++
							if (fpsEl && now - lastReport >= 500) {
								fpsEl.textContent =
									(frames / ((now - lastReport) / 1000)).toFixed(0) + ' fps'
								frames = 0
								lastReport = now
							}
							raf = requestAnimationFrame(tick)
						}
						tick()
```

- [ ] **Step 2: Deploy the updated page to the Pi**

```bash
rsync -av /Users/mheavers/Desktop/imperfecta/_project/facecapture/container/public/ \
  imperfecta-pi:~/facecapture/container/public/
ssh -t imperfecta-pi 'sudo systemctl restart facecapture'
```

- [ ] **Step 3: Measure on the Pi's actual screen**

On the Pi's display (or VNC), open Chromium at `http://127.0.0.1:8090/?fps=1`, then trigger a ring:

```bash
ssh imperfecta-pi 'curl -s -X POST http://127.0.0.1:8090/api/ring'
```

Watch the green FPS counter during the ~4.7s dissolve. **Record the number.**

- Acceptance: **sustained ≥ 24 fps** during the dissolve reads as smooth enough.
- If below that: reduce particle density — in `index.html` find `const GRID = 420` (line ~436) and step it down (e.g. `320`, then `260`), redeploy, and re-measure until it passes. Note the final `GRID` value in the commit message.

- [ ] **Step 4: Commit**

```bash
git add facecapture/container/public/index.html
git commit -m "feat(facecapture): optional ?fps overlay; tune GRID for Pi 3B+ (<final value>)"
```

---

## Phase 3 — Wiring + mode switch

### Task 7: Route the doorbell trigger by display mode in the orchestrator

**Files:**
- Modify: `prototype/orchestrator.py`

- [ ] **Step 1: Add the facecapture port + a display-mode reader to the config block**

In `orchestrator.py`, find (line ~52):

```python
BG_SERVER_IP = "127.0.0.1"     # bg_removal_server.py runs locally on Pi
BG_SERVER_PORT = 5050
```

Replace with:

```python
BG_SERVER_IP = "127.0.0.1"     # effects/bg server runs locally on Pi
BG_SERVER_PORT = 5050
FACECAPTURE_PORT = 8090        # facecapture standalone server (melt gallery mode)

def read_display_mode() -> str:
    """Which display experience is live: 'effects' (viewer.html slideshow, default)
    or 'melt' (facecapture app). Read from ~/display_mode so the mode can be flipped
    without editing code; falls back to the DISPLAY_MODE env var, then 'effects'.
    Read per-trigger (cheap) so a mode change takes effect on the next ring."""
    try:
        with open(os.path.expanduser("~/display_mode")) as f:
            mode = f.read().strip()
            if mode in ("effects", "melt"):
                return mode
    except OSError:
        pass
    return os.environ.get("DISPLAY_MODE", "effects")
```

- [ ] **Step 2: Branch the trigger in `handle_button_press`**

Find (line ~208):

```python
    # Kick the local effects server
    try:
        resp = requests.post(
            f"http://{BG_SERVER_IP}:{BG_SERVER_PORT}/trigger",
            timeout=15.0,
        )
        if resp.ok:
            data = resp.json()
            print(f"  effects: {data.get('effect')} "
                  f"({data.get('effect_ms', 0):.0f}ms render, "
                  f"{data.get('total_ms', 0):.0f}ms total)")
        else:
            print(f"  effects HTTP {resp.status_code}: {resp.text[:200]}")
    except requests.RequestException as exc:
        print(f"  effects trigger failed: {exc}")
```

Replace with:

```python
    # Kick whichever display is live. 'melt' → ring the facecapture app; 'effects'
    # → the existing render pipeline. WLED fires the same either way (above).
    mode = read_display_mode()
    if mode == "melt":
        url = f"http://{BG_SERVER_IP}:{FACECAPTURE_PORT}/api/ring"
    else:
        url = f"http://{BG_SERVER_IP}:{BG_SERVER_PORT}/trigger"
    try:
        resp = requests.post(url, timeout=15.0)
        if resp.ok:
            print(f"  [{mode}] trigger ok")
        else:
            print(f"  [{mode}] trigger HTTP {resp.status_code}: {resp.text[:200]}")
    except requests.RequestException as exc:
        print(f"  [{mode}] trigger failed: {exc}")
```

- [ ] **Step 3: Verify mode routing locally (dev mode, no GPIO)**

`orchestrator.py` runs in dev mode off-Pi (it prints the no-GPIO warning). Confirm the reader picks up the file. From the repo root on the Mac:

```bash
python3 - <<'PY'
import os, importlib.util
os.environ.pop("DISPLAY_MODE", None)
spec = importlib.util.spec_from_file_location("orch", "prototype/orchestrator.py")
# Only load the config helpers; avoid running main().
PY
echo "melt" > ~/display_mode
python3 -c "import sys; sys.path.insert(0,'prototype'); import orchestrator; print(orchestrator.read_display_mode())"
rm ~/display_mode
python3 -c "import sys; sys.path.insert(0,'prototype'); import orchestrator; print(orchestrator.read_display_mode())"
```

Expected: first prints `melt`, second prints `effects`. (If importing `orchestrator` executes hardware setup, guard by confirming it prints the "gpiod not available — dev mode" warning and still returns; it does not call `main()` on import.)

- [ ] **Step 4: Commit**

```bash
git add prototype/orchestrator.py
git commit -m "feat(orchestrator): route doorbell to /api/ring in melt mode (~/display_mode)"
```

---

### Task 8: Make the kiosk mode-aware + auto-grant the camera

**Files:**
- Modify: `prototype/kiosk_loading.html`
- Modify: `prototype/kiosk_autostart.sh`

- [ ] **Step 1: Make the loading page target the right server per `?mode=`**

In `kiosk_loading.html`, find (line ~17):

```js
const TARGET = 'http://localhost:5050/';
function check() {
  fetch('http://localhost:5050/health', { mode: 'no-cors', cache: 'no-store' })
    .then(() => { window.location.replace(TARGET); })
    .catch(() => { setTimeout(check, 1000); });
}
check();
```

Replace with:

```js
// Mode is passed by kiosk_autostart.sh as ?mode=effects|melt (default effects).
// 'melt' points at the facecapture app (:8090); 'effects' at the viewer (:5050).
const MODE = new URLSearchParams(location.search).get('mode') || 'effects';
const CFG = MODE === 'melt'
  ? { health: 'http://localhost:8090/api/health', target: 'http://localhost:8090/' }
  : { health: 'http://localhost:5050/health',     target: 'http://localhost:5050/' };
function check() {
  fetch(CFG.health, { mode: 'no-cors', cache: 'no-store' })
    .then(() => { window.location.replace(CFG.target); })
    .catch(() => { setTimeout(check, 1000); });
}
check();
```

- [ ] **Step 2: Read the mode + auto-grant camera in the autostart script**

In `kiosk_autostart.sh`, find (line ~22):

```sh
chromium \
  --kiosk \
  --password-store=basic \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  --incognito \
  --allow-file-access-from-files \
  "file:///home/imperfecta/kiosk_loading.html" &
```

Replace with:

```sh
# Which experience to show. 'effects' (default) = viewer.html slideshow;
# 'melt' = the facecapture app. Flip with:  echo melt > ~/display_mode  (then relaunch).
MODE="$(cat /home/imperfecta/display_mode 2>/dev/null || echo effects)"

# --use-fake-ui-for-media-stream auto-accepts the getUserMedia camera prompt using
# the REAL default device (the C920) — needed for the melt mode's live preview in a
# headless kiosk. Harmless in effects mode (no getUserMedia there).
chromium \
  --kiosk \
  --password-store=basic \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  --incognito \
  --allow-file-access-from-files \
  --use-fake-ui-for-media-stream \
  "file:///home/imperfecta/kiosk_loading.html?mode=${MODE}" &
```

- [ ] **Step 3: Deploy the two kiosk files and verify effects mode is unchanged**

```bash
scp prototype/kiosk_loading.html imperfecta-pi:~/
scp prototype/kiosk_autostart.sh imperfecta-pi:~/.config/labwc/autostart
ssh imperfecta-pi 'cat ~/display_mode 2>/dev/null || echo "(no file → effects default)"'
```

Reboot the Pi (or relaunch the session). With no `~/display_mode` file, the kiosk must come up on the **existing effects viewer** exactly as before (regression check).

```bash
ssh -t imperfecta-pi 'sudo reboot'
```

Expected after boot: the normal effects viewer appears; the current effects doorbell flow is unaffected.

- [ ] **Step 4: Commit**

```bash
git add prototype/kiosk_loading.html prototype/kiosk_autostart.sh
git commit -m "feat(kiosk): mode-aware target (?mode) + camera auto-grant for melt"
```

---

### Task 9: Add a facecapture deploy step

**Files:**
- Modify: `prototype/deploy.sh`

- [ ] **Step 1: Add a facecapture sync + restart to the deploy script**

In `deploy.sh`, find (line ~14):

```bash
ssh -t "$PI_HOST" "sudo systemctl restart bg_removal orchestrator"
ssh "$PI_HOST" "systemctl is-active bg_removal orchestrator"
```

Replace with:

```bash
# Sync the facecapture app source (NOT node_modules — native arm64 modules are built
# on the Pi via `npm install` during setup, see the plan's Task 4).
rsync -av --exclude node_modules --exclude .next \
  "$SRC/../facecapture/container/" "$PI_HOST":~/facecapture/container/

ssh -t "$PI_HOST" "sudo systemctl restart bg_removal orchestrator facecapture"
ssh "$PI_HOST" "systemctl is-active bg_removal orchestrator facecapture"
```

- [ ] **Step 2: Run the deploy and verify all three services are active**

```bash
cd prototype && ./deploy.sh
```

Expected: rsync completes, and `systemctl is-active` prints `active` for `bg_removal`, `orchestrator`, and `facecapture`.

- [ ] **Step 3: Commit**

```bash
git add prototype/deploy.sh
git commit -m "feat(deploy): sync facecapture source and restart its service"
```

---

### Task 10: End-to-end doorbell test on the Pi in melt mode

**Files:** none (integration verification).

- [ ] **Step 1: Switch the Pi to melt mode and relaunch the kiosk**

```bash
ssh imperfecta-pi 'echo melt > ~/display_mode'
ssh -t imperfecta-pi 'sudo reboot'
```

Expected after boot: Chromium opens the facecapture melt app (live C920 preview at top, empty/existing collage below). Camera preview should be live (auto-granted).

- [ ] **Step 2: Fire a simulated ring and confirm the full chain**

From the Mac:

```bash
ssh imperfecta-pi 'curl -s -X POST http://127.0.0.1:8090/api/ring'
```

Expected on the Pi screen: the preview freezes, flashes, dissolves into particles, and a new background-removed cutout pops into the collage. (This exercises `/api/ring → /ws → capture() → /api/capture → offline bg-removal → feed`.)

- [ ] **Step 3: Fire the REAL doorbell and confirm the orchestrator routes it**

Press the physical Avantek doorbell. Watch the orchestrator log:

```bash
ssh imperfecta-pi 'journalctl -u orchestrator -f -n 20'
```

Expected: a line `[melt] trigger ok`, and the melt fires on screen. WLED ring should also animate (unchanged behavior).

- [ ] **Step 4: Confirm the fallback still works**

Switch back and verify the effects mode is fully intact:

```bash
ssh imperfecta-pi 'echo effects > ~/display_mode'
ssh -t imperfecta-pi 'sudo reboot'
```

Press the doorbell → the original effects slideshow flow should run (`[effects] trigger ok` in the log). This proves the two modes coexist and nothing was removed.

- [ ] **Step 5: Decide the default and record the result**

Leave `~/display_mode` set to whichever mode is chosen as the live default (melt once validated, or effects until you're ready). Note the measured melt FPS (Task 6) and the final default in the task tracker / a follow-up note. No code commit required for this task.

---

## Self-Review Notes

- **Spec coverage:** additive melt mode (Tasks 1–3, 5), offline bg-removal warm (Task 4 Step 4), doorbell trigger via `/api/ring → /ws → capture()` (Tasks 1, 2, 7, 10), install/kiosk behavior + camera auto-grant (Task 8), kiosk mode switch without touching `viewer.html`/`effects_server.py` (Tasks 7, 8), MaixCam/effects preserved as fallback (Task 10 Step 4), Pi FPS validation gate (Task 6). All spec sections map to a task.
- **Deviation from spec (intentional, simpler):** the spec described an `IMPERFECTA_INSTALL` client flag; the client now handles `ring` unconditionally (harmless — dormant without ring messages), so no client flag is needed. `IMPERFECTA_INSTALL=1` is still set in the service env for future kiosk cosmetics but gates nothing yet (YAGNI). The single `~/display_mode` file is the real switch.
- **Names are consistent across tasks:** `broadcastRing`, `/api/ring`, `{type:'ring'}`, `read_display_mode`, `FACECAPTURE_PORT=8090`, `~/display_mode` values `effects|melt`.
