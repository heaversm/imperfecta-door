"""Mac-side sandbox for previewing the Imperfecta effects.

Run it, open http://localhost:8000, hit CAPTURE. Webcam grabs a ~2 sec burst,
all effects render with multiple parameter variants, results display in a grid
with per-effect timings.

  pip install -r requirements.txt
  python preview_rig.py

First run will trigger macOS camera permission prompt — grant Terminal access.
"""

from __future__ import annotations

import threading
import time
import webbrowser
from pathlib import Path

import os
import sys

import cv2
from flask import Flask, jsonify, render_template_string, send_from_directory
from PIL import Image

# palette.py lives in prototype/ (the parent of this effects/ dir).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import effects   # noqa: E402  (path set above)
import palette    # noqa: E402  (the shared roster — same effects the gallery loop uses)
import experimental_palette   # noqa: E402  (preview-only experimental roster; not deployed)

# ─── Config ────────────────────────────────────────────────────────────────
BURST_FRAMES = 30        # how many frames per capture
BURST_DURATION = 2.0     # target wall-clock seconds for the burst
CAMERA_INDEX = 0         # 0 = default Mac webcam
CAPTURE_WIDTH = 1280     # request from camera (camera picks closest supported)
CAPTURE_HEIGHT = 720
PORT = 8000

# Clip prototypes — render a few cheap effects across the burst so the SUBJECT MOVES
# (real temporal animation, not a pan on a still). Preview-only; lets us compare a
# stop-motion vs a smoother playback before committing on the Pi. Each is a pure
# frames->Image effect rendered on one burst frame at a time with a fixed seed, so the
# random structure stays put and only the subject animates.
CLIP_EFFECTS = [
    ("thermal map",  effects.thermal_map),
    ("block mosaic", effects.block_mosaic),
    ("mirror smear", effects.mirror_smear),
]
CLIP_FRAMES = 16         # frames rendered across the burst per clip effect
CLIP_SEED = 7            # fixed per-clip seed → stable structure, moving subject
# ───────────────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
_cap_lock = threading.Lock()
_cap = None


def init_camera():
    """Open the webcam once at startup and warm it up."""
    global _cap
    _cap = cv2.VideoCapture(CAMERA_INDEX)
    if not _cap.isOpened():
        raise RuntimeError(
            f"Could not open webcam {CAMERA_INDEX}. "
            "On macOS check System Settings → Privacy & Security → Camera."
        )
    _cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
    _cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
    # First few frames are often black or auto-exposing — discard them
    for _ in range(5):
        _cap.read()
    actual_w = int(_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Webcam ready: {actual_w}x{actual_h}")


def capture_burst(n: int = BURST_FRAMES) -> list[Image.Image]:
    """Grab N frames from the webcam, return as PIL Images (RGB)."""
    frames = []
    interval = BURST_DURATION / n
    with _cap_lock:
        t_next = time.perf_counter()
        for _ in range(n):
            ret, bgr = _cap.read()
            if not ret:
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(rgb))
            # Sleep until next slot (rough pacing — camera FPS may cap us anyway)
            t_next += interval
            sleep = t_next - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)
    return frames


def run_all_effects(frames: list[Image.Image]) -> list[dict]:
    """Render the shared roster (palette.py) so preview matches the gallery exactly.
    Stills render from the whole burst; living effects are previewed as a single still."""
    results = []
    middle = [frames[len(frames) // 2]]

    def timed(label, fn, *args):
        t0 = time.perf_counter()
        img = fn(*args)
        results.append({"name": label, "image": img, "ms": (time.perf_counter() - t0) * 1000})

    for name, fn in palette.STILL_PALETTE:
        timed(name, fn, frames)
    for name, fn in palette.ANIM_PALETTE:
        timed(name, fn, middle, 0)   # living effects: preview the middle frame as a still
    for name, fn in experimental_palette.EXPERIMENTAL_PALETTE:
        timed(name, fn, frames)      # experimental (preview-only) effects
    return results


@app.route("/")
def viewer():
    return render_template_string(VIEWER_HTML)


@app.route("/capture", methods=["POST"])
def capture():
    timestamp = int(time.time())
    session_dir = OUTPUT_DIR / str(timestamp)
    session_dir.mkdir(exist_ok=True)

    t0 = time.perf_counter()
    frames = capture_burst()
    capture_ms = (time.perf_counter() - t0) * 1000

    # Save the middle source frame too — handy for re-running effects offline
    middle_idx = len(frames) // 2
    frames[middle_idx].save(session_dir / "_source_middle.jpg", quality=85)

    results = run_all_effects(frames)

    payload = []
    for r in results:
        filename = f"{r['name'].replace(' ', '_').replace('(', '').replace(')', '')}.jpg"
        r["image"].save(session_dir / filename, quality=88)
        payload.append({
            "name": r["name"],
            "url": f"/output/{timestamp}/{filename}",
            "ms": round(r["ms"], 1),
        })

    # Render clip prototypes: each effect across CLIP_FRAMES evenly-sampled burst frames.
    clips = []
    n = len(frames)
    if n >= 2:
        sample = [round(i * (n - 1) / (CLIP_FRAMES - 1)) for i in range(CLIP_FRAMES)]
        for name, fn in CLIP_EFFECTS:
            urls = []
            for j, fi in enumerate(sample):
                res = fn([frames[fi]], seed=CLIP_SEED)
                img = res[0] if isinstance(res, tuple) else res   # @_timed -> (img, ms)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                fname = f"clip_{name.replace(' ', '_')}_{j:02d}.jpg"
                img.save(session_dir / fname, quality=85)
                urls.append(f"/output/{timestamp}/{fname}")
            clips.append({"name": name, "frames": urls})

    return jsonify({
        "session": timestamp,
        "capture_ms": round(capture_ms, 1),
        "n_frames": len(frames),
        "results": payload,
        "clips": clips,
        "source_url": f"/output/{timestamp}/_source_middle.jpg",
    })


@app.route("/output/<session>/<filename>")
def serve_output(session, filename):
    return send_from_directory(OUTPUT_DIR / session, filename)


VIEWER_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Imperfecta — effects preview</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: #111;
    color: #eee;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    padding: 24px;
  }
  header {
    display: flex; align-items: center; gap: 16px;
    margin-bottom: 24px;
  }
  h1 { font-size: 20px; margin: 0; font-weight: 500; }
  button {
    background: #c33; color: white; border: 0;
    padding: 12px 24px; font-size: 16px; border-radius: 6px;
    cursor: pointer; font-weight: 600;
  }
  button:hover { background: #e44; }
  button:disabled { background: #555; cursor: wait; }
  #status { color: #888; font-size: 14px; }
  #grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 16px;
  }
  .tile {
    background: #1a1a1a;
    border-radius: 6px;
    overflow: hidden;
    cursor: zoom-in;
  }
  .tile img {
    width: 100%; display: block; aspect-ratio: 16/9; object-fit: cover;
    background: #000;
  }
  .tile .meta {
    padding: 8px 12px;
    display: flex; justify-content: space-between;
    font-size: 13px;
  }
  .tile .ms { color: #6c6; font-variant-numeric: tabular-nums; }
  .tile .ms.slow { color: #e94; }
  .tile .ms.veryslow { color: #f55; }
  .source-tile { border: 1px solid #444; }
  .source-tile .name { color: #aaa; font-style: italic; }
  /* Lightbox */
  #lightbox {
    position: fixed; inset: 0; background: rgba(0,0,0,0.95);
    display: none; align-items: center; justify-content: center;
    cursor: zoom-out; z-index: 100;
  }
  #lightbox.open { display: flex; }
  #lightbox img { max-width: 95vw; max-height: 95vh; }
</style>
</head>
<body>
<header>
  <button id="capture">CAPTURE</button>
  <h1>Imperfecta — effects preview</h1>
  <span id="status">idle</span>
</header>
<div id="grid"></div>
<div id="lightbox"><img id="lightbox-img"></div>

<script>
const btn = document.getElementById('capture');
const status = document.getElementById('status');
const grid = document.getElementById('grid');
const lb = document.getElementById('lightbox');
const lbImg = document.getElementById('lightbox-img');

lb.addEventListener('click', () => lb.classList.remove('open'));

async function capture() {
  btn.disabled = true;
  status.textContent = 'capturing…';
  const t0 = performance.now();
  try {
    const res = await fetch('/capture', { method: 'POST' });
    const data = await res.json();
    const totalMs = (performance.now() - t0).toFixed(0);
    status.textContent = `session ${data.session} · ${data.n_frames} frames · capture ${data.capture_ms.toFixed(0)}ms · total ${totalMs}ms`;
    render(data);
  } catch (e) {
    status.textContent = 'error: ' + e.message;
  } finally {
    btn.disabled = false;
  }
}

let clipTimers = [];   // playback intervals for clip tiles — cleared on each re-render

function render(data) {
  clipTimers.forEach(clearInterval); clipTimers = [];
  grid.innerHTML = '';
  // Source frame first
  grid.appendChild(makeTile({
    name: 'Source (middle frame)',
    url: data.source_url,
    ms: null,
  }, true));
  for (const r of data.results) {
    grid.appendChild(makeTile(r, false));
  }
  // Clip prototypes: two tiles per effect — stop-motion (every other frame, slow) vs
  // smooth (all frames, faster) — so the subject actually moves. Compare the two looks.
  for (const c of (data.clips || [])) {
    const stop = c.frames.filter((_, k) => k % 2 === 0);   // half the frames
    grid.appendChild(makeClipTile(c.name + ' — stop-motion', stop, 6));
    grid.appendChild(makeClipTile(c.name + ' — smooth', c.frames, 12));
  }
}

function makeClipTile(label, frames, fps) {
  const tile = document.createElement('div');
  tile.className = 'tile';
  const img = document.createElement('img');
  img.src = frames[0];
  frames.forEach(u => { const p = new Image(); p.src = u; });   // preload for smooth playback
  let i = 0;
  clipTimers.push(setInterval(() => { i = (i + 1) % frames.length; img.src = frames[i]; }, 1000 / fps));
  img.addEventListener('click', () => { lbImg.src = img.src; lb.classList.add('open'); });
  const meta = document.createElement('div');
  meta.className = 'meta';
  const name = document.createElement('span');
  name.className = 'name';
  name.textContent = label;
  meta.appendChild(name);
  const tag = document.createElement('span');
  tag.className = 'ms';
  tag.textContent = fps + ' fps';
  meta.appendChild(tag);
  tile.appendChild(img);
  tile.appendChild(meta);
  return tile;
}

function makeTile(r, isSource) {
  const tile = document.createElement('div');
  tile.className = 'tile' + (isSource ? ' source-tile' : '');
  const img = document.createElement('img');
  img.src = r.url;
  img.loading = 'lazy';
  img.addEventListener('click', () => {
    lbImg.src = r.url;
    lb.classList.add('open');
  });
  const meta = document.createElement('div');
  meta.className = 'meta';
  const name = document.createElement('span');
  name.className = 'name';
  name.textContent = r.name;
  meta.appendChild(name);
  if (r.ms != null) {
    const ms = document.createElement('span');
    ms.className = 'ms' + (r.ms > 1500 ? ' veryslow' : r.ms > 800 ? ' slow' : '');
    ms.textContent = r.ms.toFixed(0) + ' ms';
    meta.appendChild(ms);
  }
  tile.appendChild(img);
  tile.appendChild(meta);
  return tile;
}

btn.addEventListener('click', capture);
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !btn.disabled) capture();
  if (e.key === 'Escape') lb.classList.remove('open');
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    init_camera()
    url = f"http://localhost:{PORT}"
    print(f"Preview rig running at {url}")
    print("Press CAPTURE in the browser (or hit Enter while focused there).")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
