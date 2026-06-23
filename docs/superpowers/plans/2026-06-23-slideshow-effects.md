# On-Screen Experience v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 3×3 effect grid with a fullscreen slideshow that loops until the next doorbell ring, add a B&W distortion effect family + an animated burst flipbook, and render at display resolution via a streaming pipeline that stays feasible on the Pi 3B+.

**Architecture:** `effects.py` stays pure functions (burst → image). `effects_server.py` fetches the burst once, saves raw frames as static files, then renders effects one-at-a-time, pushing each to the viewer over SSE as it completes. `viewer.html` holds a playlist, crossfades through it on a loop, and animates the flipbook from the raw frames. Capture moves to ~1024×576 for fullscreen sharpness; a measurement spike validates timing before the full build.

**Tech Stack:** Python 3.11 (PIL/Pillow, numpy), Flask + SSE, vanilla JS in the viewer, MaixPy on the MaixCam.

**Spec:** `docs/superpowers/specs/2026-06-23-slideshow-effects-design.md`

**Testing note:** These are visual/image-processing changes. "Tests" here are smoke checks (effect returns an RGB image of expected size, doesn't throw), the Mac preview rig for visual confirmation, and on-Pi timing measurement — not failing-test-first TDD.

---

## Task 1: Measurement spike (FEASIBILITY GATE)

Validate per-effect render time at 1024px and burst fetch/decode at 1024×576 capture on the actual Pi **before** building the full roster. If the streaming timeline doesn't hold, adjust resolution/roster here.

**Files:**
- Create: `prototype/effects/spike_render.py`

- [ ] **Step 1: Write the spike script**

```python
#!/usr/bin/env python3
"""Feasibility spike: time each effect at a target render size + report burst fetch.

Run on the Pi:  python3 spike_render.py --host maixcam-288c.local --work 1024 --count 30
Run on the Mac with a local image dir: python3 spike_render.py --dir ./output/<session> --work 1024
"""
import argparse, io, time, zipfile, sys
import requests
from PIL import Image
import effects

EFFECTS = [
    ("slitscan_vertical", lambda f: effects.slitscan_vertical(f)[0]),
    ("echo_max",          lambda f: effects.echo_max(f)[0]),
    ("liquify",           lambda f: effects.liquify(f[len(f)//2])[0]),
    ("hockney_joiner",    lambda f: effects.hockney_joiner(f, rows=3, cols=3)[0]),
    ("warhol",            lambda f: effects.warhol(f)[0]),
    ("lichtenstein",      lambda f: effects.lichtenstein(f)[0]),
    ("mondrian",          lambda f: effects.mondrian(f)[0]),
]

def scale(img, work):
    w, h = img.size
    m = max(w, h)
    if m <= work: return img
    s = work / m
    return img.resize((round(w*s), round(h*s)), Image.LANCZOS)

def pull_burst(host, count):
    t0 = time.perf_counter()
    r = requests.get(f"http://{host}:8080/burst?count={count}", timeout=15)
    r.raise_for_status()
    fetch = (time.perf_counter()-t0)*1000
    frames = []
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for n in sorted(zf.namelist()):
            with zf.open(n) as fh:
                im = Image.open(fh); im.load(); frames.append(im.convert("RGB"))
    decode = (time.perf_counter()-t0)*1000 - fetch
    return frames, fetch, decode

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host"); ap.add_argument("--dir"); ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--work", type=int, default=1024)
    a = ap.parse_args()
    if a.host:
        frames, fetch, decode = pull_burst(a.host, a.count)
        print(f"burst: {len(frames)} frames, fetch {fetch:.0f}ms, decode {decode:.0f}ms")
    else:
        import glob, os
        paths = sorted(glob.glob(os.path.join(a.dir, "*.jpg")))[:a.count]
        frames = [Image.open(p).convert("RGB") for p in paths]
        print(f"loaded {len(frames)} frames from {a.dir}")
    frames = [scale(f, a.work) for f in frames]
    print(f"work size: {frames[0].size}")
    total = 0.0
    for name, fn in EFFECTS:
        t0 = time.perf_counter()
        img = fn(frames)
        ms = (time.perf_counter()-t0)*1000
        total += ms
        print(f"  {name:20s} {ms:7.0f}ms  -> {img.size}")
    print(f"TOTAL render (7 effects): {total:.0f}ms")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run on the Pi and capture numbers**

Deploy + run (MaixCam must be on; capture still at current res is fine for timing the render path):
```bash
scp prototype/effects/spike_render.py prototype/effects/effects.py imperfecta-pi:~/spike/
ssh imperfecta-pi 'cd ~/spike && python3 spike_render.py --host maixcam-288c.local --work 1024 --count 30'
```
Expected: per-effect ms (hockney is the outlier) + burst fetch/decode. Record them.

- [ ] **Step 3: Gate decision**

Confirm: first-image timeline = burst fetch+decode + slowest single effect ≲ ~6s, and total render of the full ~10 roster won't starve a 4s/slide loop. If it fails, drop `--work` to 800, reduce burst `--count`, or trim the roster — and note the chosen values in the spec before continuing.

- [ ] **Step 4: Commit**

```bash
git add prototype/effects/spike_render.py
git commit -m "Add render-timing spike for slideshow effects feasibility"
```

---

## Task 2: B&W treatment helper + new effects in `effects.py`

**Files:**
- Modify: `prototype/effects/effects.py`

- [ ] **Step 1: Add the shared B&W treatment helper**

Add after `_duotone` (around line 49):

```python
def _bw_treatment(img: Image.Image, grain: float = 0.10, seed: int | None = None) -> Image.Image:
    """Shared B&W-distortion-family look: grayscale → contrast stretch → film grain."""
    g = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    arr = np.asarray(g).astype(np.float32)
    if grain > 0:
        rng = np.random.default_rng(seed)
        arr = np.clip(arr + rng.normal(0.0, 255.0 * grain, arr.shape), 0, 255)
    return Image.fromarray(arr.astype(np.uint8)).convert("RGB")
```

- [ ] **Step 2: Add `slice_displacement`**

Add in a new "Slice displacement" section:

```python
# ─── Slice displacement ──────────────────────────────────────────────────────

@_timed
def slice_displacement(
    frames: list[Image.Image],
    n_bands: int = 16,
    max_shift_frac: float = 0.18,
    seed: int | None = None,
) -> Image.Image:
    """Cut the frame into vertical bands; offset each band vertically by a random
    amount → fractured, shuffled-strips look (the 'Dia 6' reference). B&W."""
    rng = random.Random(seed)
    src = _bw_treatment(_middle_frame(frames), seed=seed)
    arr = np.asarray(src)
    h, w, _ = arr.shape
    out = np.zeros_like(arr)
    band_w = max(1, w // n_bands)
    max_shift = int(h * max_shift_frac)
    for i in range(n_bands):
        x0 = i * band_w
        x1 = w if i == n_bands - 1 else (i + 1) * band_w
        shift = rng.randint(-max_shift, max_shift)
        out[:, x0:x1] = np.roll(arr[:, x0:x1], shift, axis=0)
    return Image.fromarray(out)
```

- [ ] **Step 3: Add `water_refraction`**

```python
# ─── Water refraction ────────────────────────────────────────────────────────

@_timed
def water_refraction(
    frames: list[Image.Image],
    amp: float = 12.0,
    freq: float = 6.0,
    seed: int | None = None,
) -> Image.Image:
    """Crossing-sine ripple displacement field warped through _numpy_remap →
    underwater refraction. B&W."""
    src = _bw_treatment(_middle_frame(frames), seed=seed)
    arr = np.asarray(src)
    h, w, _ = arr.shape
    ys, xs = np.indices((h, w), dtype=np.float32)
    src_x = xs + amp * np.sin(2 * np.pi * freq * ys / h + xs / w * 3.0)
    src_y = ys + amp * np.cos(2 * np.pi * freq * xs / w + ys / h * 3.0)
    return Image.fromarray(_numpy_remap(arr, src_x, src_y))
```

- [ ] **Step 4: Smoke-check on the Mac**

```bash
cd prototype/effects && python3 -c "
from PIL import Image; import effects
frames=[Image.new('RGB',(1024,576),(i*8%255,90,140)) for i in range(30)]
for fn in (effects.slice_displacement, effects.water_refraction):
    img,ms=fn(frames); assert img.size==(1024,576) and img.mode=='RGB', (fn.__name__, img.size, img.mode)
    print(f'{fn.__name__}: {ms:.0f}ms ok')
print('bw treatment:', effects._bw_treatment(frames[0]).mode)
"
```
Expected: both effects print `ok` with a timing; bw treatment prints `RGB`.

- [ ] **Step 5: Visual check via the preview rig (optional but recommended)**

Run `prototype/effects/preview_rig.py` per its header, capture a burst, and eyeball the two new effects + the B&W look before wiring them into the server.

- [ ] **Step 6: Commit**

```bash
git add prototype/effects/effects.py
git commit -m "Add slice_displacement, water_refraction, and shared B&W treatment effect"
```

---

## Task 3: Update the roster + apply B&W treatment in `effects_server.py`

Replace the grid palette with the v2 roster. Wrap the distortion-family effects in `_bw_treatment` and drop `slitscan_horizontal` + `time_grid` from the active list.

**Files:**
- Modify: `prototype/effects_server.py` (the `EFFECT_PALETTE` block, ~lines 41-80)

- [ ] **Step 1: Replace the palette + wrappers**

Replace the `_effect`/`_slit_v`…`_mond` helpers and `EFFECT_PALETTE` (lines ~44-80) with:

```python
import effects
_bw = effects._bw_treatment

def _slit_v(frames): return _bw(effects.slitscan_vertical(frames)[0])
def _emax(frames):   return _bw(effects.echo_max(frames)[0])
def _liq(frames):    return _bw(effects.liquify(frames[len(frames)//2], wave_amp=30, wave_freq=4, bulge=0.5, twirl_deg=45)[0])
def _hock(frames):   return _bw(effects.hockney_joiner(frames, rows=3, cols=3, rotation_max_deg=12, jitter_frac=0.12, border_px=10)[0])
def _slice(frames):  return effects.slice_displacement(frames)[0]      # B&W internally
def _water(frames):  return effects.water_refraction(frames)[0]        # B&W internally
def _warhol(frames): return effects.warhol(frames)[0]                  # color
def _licht(frames):  return effects.lichtenstein(frames)[0]            # color
def _mond(frames):   return effects.mondrian(frames)[0]                # color

# Order = loop order. "flipbook" is handled by the viewer, not rendered here.
EFFECT_PALETTE = [
    ("slitscan vertical",   _slit_v),
    ("slice displacement",  _slice),
    ("warhol",              _warhol),
    ("water refraction",    _water),
    ("echo",                _emax),
    ("lichtenstein",        _licht),
    ("liquify",             _liq),
    ("mondrian",            _mond),
    ("hockney",             _hock),
]
FLIPBOOK_KIND = "flipbook"   # viewer-rendered item, inserted into the playlist
```

- [ ] **Step 2: Smoke-check the palette renders**

```bash
ssh imperfecta-pi 'cd ~ && python3 -c "
import effects_server as s
from PIL import Image
frames=[Image.new(\"RGB\",(1024,576),(i*8%255,90,140)) for i in range(30)]
for name,fn in s.EFFECT_PALETTE:
    img=fn(frames); assert img.mode==\"RGB\"; print(name, img.size)
"' || echo "run after deploy in Task 6"
```
Expected: each effect name + size prints (run after the file is on the Pi).

- [ ] **Step 3: Commit**

```bash
git add prototype/effects_server.py
git commit -m "Swap grid palette for v2 slideshow roster (B&W family + color punctuation)"
```

---

## Task 4: Streaming render + SSE playlist + serve burst frames (`effects_server.py`)

Replace `render_grid`/grid `/trigger` with: save raw burst frames as static files, push `playlist-start` (with flipbook frame URLs), then render each effect and push an `append` event as it finishes.

**Files:**
- Modify: `prototype/effects_server.py` (`render_grid`, `_pull_burst`, `/trigger`, config)

- [ ] **Step 1: Config — work res + frame dir**

In the config block, change `WORK_MAX_DIM` default to `1024` (or the spike-chosen value) and add:

```python
WORK_MAX_DIM = int(os.environ.get("WORK_MAX_DIM", "1024"))
SLIDE_COUNT = len(EFFECT_PALETTE)  # stills; flipbook added on top
# Ephemeral render outputs live in RAM (tmpfs), NOT on the SD card. They're regenerated
# every ring, so writing ~24 JPEGs/ring to the card all day would just wear it out (the
# first card already died) and fight the go-live read-only filesystem. /dev/shm is
# RAM-backed and present by default on Pi OS. viewer.html stays in STATIC_DIR (deployed,
# not per-ring).
RENDER_DIR = os.environ.get("RENDER_DIR", "/dev/shm/imperfecta")
FRAMES_DIR = os.path.join(RENDER_DIR, "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)
```

- [ ] **Step 2: Save burst frames for the flipbook**

Add a helper near `_pull_burst`:

```python
def _save_burst_frames(frames: list[Image.Image], stride: int = 2) -> list[str]:
    """Write a decimated copy of the burst to static/frames/ for the flipbook.
    Returns the URL list (cache-busted). stride=2 → ~15 frames from 30."""
    import glob
    for old in glob.glob(os.path.join(FRAMES_DIR, "*.jpg")):
        os.remove(old)
    urls = []
    token = str(int(time.time() * 1000))
    for i, f in enumerate(frames[::stride]):
        name = f"f{i:03d}.jpg"
        f.save(os.path.join(FRAMES_DIR, name), "JPEG", quality=82)
        urls.append(f"/static/frames/{name}?t={token}")
    return urls
```
(Note: `STATIC_DIR` is Flask's `static_folder`; add a route to serve `frames/` — see Step 4.)

- [ ] **Step 3: Replace `/trigger` with the streaming render**

Replace the whole `trigger()` function with:

```python
@app.route("/trigger", methods=["POST"])
def trigger():
    if not _trigger_lock.acquire(blocking=False):
        return jsonify({"error": "busy"}), 429
    try:
        overall = time.perf_counter()
        print(f"\n[{time.strftime('%H:%M:%S')}] trigger received")
        try:
            frames = _pull_burst()           # already downscales to WORK_MAX_DIM
        except Exception as e:
            print(f"  burst failed: {e}")
            return jsonify({"error": "burst", "detail": str(e)}), 502
        if not frames:
            return jsonify({"error": "empty burst"}), 502

        # Flipbook frames (decimated) + new-playlist signal. Viewer keeps showing the
        # current loop until the first still arrives — no black gap.
        flip_urls = _save_burst_frames(frames)
        _push_sse("playlist-start", {"flipbook": flip_urls, "kind": FLIPBOOK_KIND})

        # Render stills one at a time; push each as it completes.
        for i, (name, fn) in enumerate(EFFECT_PALETTE):
            try:
                t0 = time.perf_counter()
                img = fn(frames)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                path = os.path.join(RENDER_DIR, f"latest_{i}.jpg")
                img.save(path, "JPEG", quality=85)
                ms = (time.perf_counter() - t0) * 1000
                token = str(int(time.time() * 1000))
                _push_sse("append", {"index": i, "url": f"/latest_{i}.jpg?t={token}",
                                     "kind": "still", "name": name})
                print(f"  {name}: {ms:.0f}ms")
            except Exception as e:
                print(f"  effect {name} failed, skipping: {e}")

        total = (time.perf_counter() - overall) * 1000
        print(f"  done: {len(EFFECT_PALETTE)} stills, total {total:.0f}ms")
        return jsonify({"ok": True, "stills": len(EFFECT_PALETTE), "total_ms": round(total, 1)})
    finally:
        _trigger_lock.release()
```

- [ ] **Step 4: Add the `latest_<i>.jpg` + frames routes**

Add routes (the single `latest.jpg` route can stay for back-compat or be removed):

```python
@app.route("/latest_<int:i>.jpg")
def latest_n(i):
    p = os.path.join(RENDER_DIR, f"latest_{i}.jpg")
    return send_from_directory(RENDER_DIR, f"latest_{i}.jpg") if os.path.exists(p) else ("no image", 404)

@app.route("/static/frames/<path:name>")
def frame(name):
    return send_from_directory(FRAMES_DIR, name)
```

- [ ] **Step 5: Delete the now-unused `render_grid` and grid constants**

Remove `render_grid`, `GRID_ROWS`, `GRID_COLS`. Keep `_pull_burst`, `_scale_to_work`, `_push_sse`, SSE `/events`.

- [ ] **Step 6: Commit**

```bash
git add prototype/effects_server.py
git commit -m "Stream effects as an SSE playlist; serve burst frames for the flipbook"
```

---

## Task 5: Viewer playlist loop + flipbook (`static/viewer.html`)

Replace the single-image swap logic with a playlist that crossfades on a loop and animates the flipbook. Preserve the existing self-heal.

**Files:**
- Modify: `prototype/static/viewer.html` (the `<script>` block)

- [ ] **Step 1: Replace the script with the playlist engine**

Replace everything between `<script>` and `</script>` with:

```javascript
const a = document.getElementById('a');
const b = document.getElementById('b');
const status = document.getElementById('status');
let front = a, back = b;

const SLIDE_MS = 4000;        // dwell per still
const FADE_MS = 600;          // matches CSS transition
const FLIP_FPS = 4;           // flipbook playback rate
const FLIP_LOOPS = 2;         // ping-pong passes before advancing

let active = [];              // playlist currently looping: [{kind,url|frames}]
let building = null;          // playlist being assembled from a new capture
let idx = 0;
let timer = null;

function showStill(url) {
  back.onload = () => {
    back.classList.add('visible');
    front.classList.remove('visible');
    [front, back] = [back, front];
  };
  back.src = url;
}

function preload(urls) { urls.forEach(u => { const im = new Image(); im.src = u; }); }

async function playFlipbook(frames) {
  // Ping-pong through the frames on the front layer, then resolve.
  back.classList.remove('visible');
  const seq = frames.concat(frames.slice(1, -1).reverse());
  const order = [].concat(...Array(FLIP_LOOPS).fill(seq));
  for (const url of order) {
    front.src = url;
    front.classList.add('visible');
    await new Promise(r => setTimeout(r, 1000 / FLIP_FPS));
  }
}

async function step() {
  if (!active.length) { timer = setTimeout(step, 500); return; }
  const item = active[idx % active.length];
  idx++;
  if (item.kind === 'flipbook') {
    await playFlipbook(item.frames);
    timer = setTimeout(step, 200);
  } else {
    showStill(item.url);
    timer = setTimeout(step, SLIDE_MS + FADE_MS);
  }
}

function connect() {
  const es = new EventSource('/events');
  es.onopen = () => { everConnected = true; status.classList.add('live'); };
  es.onerror = () => {
    status.classList.remove('live');
    if (es.readyState === EventSource.CLOSED) setTimeout(() => location.reload(), 3000);
  };
  es.addEventListener('playlist-start', (e) => {
    const d = JSON.parse(e.data);
    // Start assembling a new playlist; keep looping the current one until ready.
    building = [];
    if (d.flipbook && d.flipbook.length) {
      preload(d.flipbook);
      building.push({ kind: 'flipbook', frames: d.flipbook });
    }
  });
  es.addEventListener('append', (e) => {
    const d = JSON.parse(e.data);
    if (!building) building = [];
    preload([d.url]);
    building.push({ kind: 'still', url: d.url });
    // Hand over once the new playlist has a couple items (no black gap).
    if (building.length >= 2) { active = building; idx = 0; building = building; }
  });
}

let everConnected = false;
connect();
setTimeout(() => { if (!everConnected) location.reload(); }, 20000);
step();
```

- [ ] **Step 2: Sanity-check locally (optional)**

Open `viewer.html` against a mock SSE if convenient, or rely on the on-Pi test in Task 6. Confirm no JS console errors on load (status dot present).

- [ ] **Step 3: Commit**

```bash
git add prototype/static/viewer.html
git commit -m "Viewer: playlist loop + flipbook playback (replaces single-image swap)"
```

---

## Task 6: Capture-res bump, deploy, and tune on the Pi

**Files:**
- Modify: `maixcam/face_capture/face_capture_multi_server.py` (`CAPTURE_WIDTH/HEIGHT`)

- [ ] **Step 1: Bump MaixCam capture to the spike-chosen res (default 1024×576)**

In `face_capture_multi_server.py`:
```python
CAPTURE_WIDTH = 1024
CAPTURE_HEIGHT = 576
```

- [ ] **Step 2: Deploy MaixCam (via the Pi jump host) + reboot**

```bash
scp -J imperfecta-pi -i ~/.ssh/id_imperfecta \
  maixcam/face_capture/face_capture_multi_server.py \
  root@10.40.141.1:/maixapp/apps/face_capture_server/main.py
ssh -J imperfecta-pi -i ~/.ssh/id_imperfecta root@10.40.141.1 'reboot'
# wait ~45s, then confirm: capture size is 1024x576
ssh imperfecta-pi 'curl -s http://maixcam-288c.local:8080/photo -o /tmp/m.jpg && python3 -c "from PIL import Image;print(Image.open(\"/tmp/m.jpg\").size)"'
```
Expected: `(1024, 576)`.

- [ ] **Step 3: Deploy Pi side + restart effects server**

```bash
cd prototype && ./deploy.sh
```
(`deploy.sh` ships `effects_server.py`, `effects/effects.py`, `static/viewer.html` and restarts the service.)

- [ ] **Step 4: Fire a trigger and verify the streaming playlist**

```bash
ssh imperfecta-pi 'curl -s -X POST http://localhost:5050/trigger' | python3 -m json.tool
ssh imperfecta-pi 'ls -la ~/static/latest_*.jpg ~/static/frames/ | head'
```
Expected: `{"ok": true, "stills": 9, ...}`; `latest_0..8.jpg` and `frames/f*.jpg` exist.

- [ ] **Step 5: Visual check on the gallery display + grim screenshot**

```bash
ssh imperfecta-pi 'WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 grim /tmp/s.png'
scp imperfecta-pi:/tmp/s.png /tmp/s.png   # then view
```
Confirm: fullscreen effect crossfading and looping; flipbook plays the burst as motion; B&W family reads cohesively beside the color effects. Tune `SLIDE_MS`, `FLIP_FPS`, effect params as needed (viewer edits need no MaixCam reboot).

- [ ] **Step 6: Regression — cold boot still works**

```bash
ssh imperfecta-pi '~/shutdown'   # power-cycle, then watch the screen
```
Expected: boots straight into the experience (black loading page → looping slideshow), no desktop, no blank.

- [ ] **Step 7: One-time legacy cleanup + confirm tmpfs render dir**

The retired `bg_removal` pipeline accumulated face captures under `~/static/`. List first,
then remove the legacy artifacts (leave `viewer.html` and the new tmpfs render dir alone):
```bash
# Inspect what's there before deleting anything
ssh imperfecta-pi 'ls -la ~/static/ ~/static/captures 2>/dev/null; du -sh ~/static 2>/dev/null'
# Remove legacy accumulated captures (adjust to what the listing shows)
ssh imperfecta-pi 'rm -rf ~/static/captures ~/static/faces 2>/dev/null; rm -f ~/static/latest.jpg'
# Confirm render outputs are in RAM (tmpfs), not on the card
ssh imperfecta-pi 'df -h /dev/shm; ls -la /dev/shm/imperfecta/ /dev/shm/imperfecta/frames/ | head'
```
Expected: `/dev/shm/imperfecta/` holds `latest_*.jpg` + `frames/`; `~/static/` holds only
`viewer.html`. No accumulating capture files anywhere.

- [ ] **Step 8: Commit**

```bash
git add maixcam/face_capture/face_capture_multi_server.py
git commit -m "Bump MaixCam capture to 1024x576 for fullscreen slideshow sharpness"
```

---

## Verification (whole feature)
- Spike numbers recorded; streaming first-image lands ≈ when the 5s WLED ring ends.
- Ring → fullscreen effects crossfade and loop until the next ring; no black idle.
- Flipbook plays the burst back as motion.
- B&W distortion family reads cohesively next to warhol/lichtenstein/mondrian.
- Sustained CPU ≈ 0 between rings; `vcgencmd get_throttled` = 0x0.
- **Storage:** render outputs in `/dev/shm` (RAM), not the SD card; footprint constant
  across many rings (no accumulation); legacy captures removed. `/dev/shm/imperfecta` is
  recreated on service start (`os.makedirs` at import), so it survives reboots/RAM clears.
- Cold-boot regression passes.
