"""Effects server (replaces bg_removal_server.py).

Runs on the Pi. On `POST /trigger`:
  1. Pulls the burst from the MaixCam, saves a decimated copy as flipbook frames.
  2. Pushes a `playlist-start` SSE event, then stream-renders each effect in the
     roster, pushing an `append` event (with its image URL) as each completes.
  3. The viewer loops/crossfades through the playlist until the next ring.

Render outputs live in RAM (RENDER_DIR, tmpfs) — not the SD card. No accumulation,
no Replicate, no internet dependency. Same `effects.py` module runs here and on the
Mac preview rig.
"""

from __future__ import annotations

import io
import json
import os
import queue
import random
import threading
import time
import zipfile

import requests
from flask import Flask, Response, jsonify, send_from_directory
from PIL import Image

import effects

# ── Config ──────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 5050
MAIXCAM_HOST = os.environ.get("MAIXCAM_HOST", "maixcam-288c.local")
MAIXCAM_PORT = int(os.environ.get("MAIXCAM_PORT", "8080"))
BURST_COUNT = int(os.environ.get("BURST_COUNT", "30"))
# Each effect is shown fullscreen, so render at ~display res. The spike (2026-06-23)
# confirmed ~1024px is feasible on the Pi 3B+ when streamed (see the design spec).
WORK_MAX_DIM = int(os.environ.get("WORK_MAX_DIM", "1024"))

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# Per-ring render outputs live in RAM (tmpfs), NOT the SD card — regenerated every ring,
# so writing them to the card would just wear it out and fight the go-live read-only
# filesystem. /dev/shm is RAM-backed and present by default on Pi OS. Override with
# RENDER_DIR for non-Pi dev. Recreated here on import, so it survives reboots/RAM clears.
RENDER_DIR = os.environ.get("RENDER_DIR", "/dev/shm/imperfecta")
FRAMES_DIR = os.path.join(RENDER_DIR, "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)
# ────────────────────────────────────────────────────────────────────

# Effect palette for the slideshow loop. Each entry is (display_name, callable);
# the callable takes the burst (list of PIL Images) and returns one PIL Image.
# The B&W distortion family shares _bw_treatment; warhol/lichtenstein/mondrian stay color.
_bw = effects._bw_treatment

def _slit_h(frames):  return _bw(effects.slitscan_horizontal(frames)[0])
def _dither(frames):  return effects.dither(frames)[0]   # already 1-bit B&W, no _bw wrap
def _liq(frames):    return _bw(effects.liquify(frames[len(frames) // 2], wave_amp=30, wave_freq=4, bulge=0.5, twirl_deg=45)[0])
def _hock(frames):   return _bw(effects.hockney_joiner(frames, rows=3, cols=3, rotation_max_deg=12, jitter_frac=0.12, border_px=10, pad_frac=0.04, bleed_frac=0.38)[0])
def _slice(frames):  return effects.slice_displacement(frames)[0]      # B&W internally
def _water(frames):  return effects.water_refraction(frames)[0]        # B&W internally
def _warhol(frames): return effects.warhol(frames)[0]                  # color
def _halftone(frames): return effects.halftone(frames)[0]   # pop halftone (rebuilt lichtenstein)
def _mond(frames):   return effects.mondrian(frames)[0]                # color

# Order = render order = loop order. The spike (2026-06-23) showed hockney is a 1.6s
# outlier at 1024px, so it renders LAST (a cheap effect leads so the first image lands
# inside the 5s WLED ring). Color/B&W interleaved for variety. flipbook = viewer-rendered.
EFFECT_PALETTE = [
    ("warhol",             _warhol),   # ~150ms — cheap, punchy first image
    ("slice displacement", _slice),
    ("halftone",           _halftone),
    ("water refraction",   _water),
    ("slitscan horizontal", _slit_h),
    ("mondrian",           _mond),
    ("dither",             _dither),
    ("liquify",            _liq),
    ("hockney",            _hock),      # ~1.6s — render LAST
]
FLIPBOOK_KIND = "flipbook"   # viewer-rendered item, inserted into the playlist

# ── Flask app ───────────────────────────────────────────────────────
app = Flask(__name__, static_folder=STATIC_DIR)

_trigger_lock = threading.Lock()    # serialize /trigger so two doorbells in a row don't collide
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


def _scale_to_work(img: Image.Image) -> Image.Image:
    """Downscale so the longest side is <= WORK_MAX_DIM (keeps render fast)."""
    w, h = img.size
    longest = max(w, h)
    if longest <= WORK_MAX_DIM:
        return img
    s = WORK_MAX_DIM / longest
    return img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)


def _pull_burst() -> list[Image.Image]:
    """Fetch the burst ZIP from the MaixCam and decode each frame to a PIL Image."""
    url = f"http://{MAIXCAM_HOST}:{MAIXCAM_PORT}/burst?count={BURST_COUNT}"
    t0 = time.perf_counter()
    resp = requests.get(url, timeout=8.0)
    resp.raise_for_status()
    fetch_ms = (time.perf_counter() - t0) * 1000

    frames = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = sorted(zf.namelist())
        for name in names:
            with zf.open(name) as f:
                # Decode JPEG → PIL Image, force load into memory so the zip handle can close.
                img = Image.open(f)
                img.load()
                frames.append(_scale_to_work(img.convert("RGB")))
    decode_ms = (time.perf_counter() - t0) * 1000 - fetch_ms
    print(f"  burst: fetched {len(frames)} frames in {fetch_ms:.0f}ms, decoded in {decode_ms:.0f}ms")
    return frames


def _save_burst_frames(frames: list[Image.Image], stride: int = 2) -> list[str]:
    """Write a decimated copy of the burst to RENDER_DIR/frames/ for the flipbook.
    Returns cache-busted URLs. stride=2 → ~15 frames from 30."""
    import glob
    for old in glob.glob(os.path.join(FRAMES_DIR, "*.jpg")):
        os.remove(old)
    urls = []
    token = str(int(time.time() * 1000))
    for i, f in enumerate(frames[::stride]):
        name = f"f{i:03d}.jpg"
        f.save(os.path.join(FRAMES_DIR, name), "JPEG", quality=82)
        urls.append(f"/frames/{name}?t={token}")
    return urls


def _push_sse(event: str, data: dict) -> None:
    payload = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


@app.route("/")
def viewer():
    return send_from_directory(STATIC_DIR, "viewer.html")


@app.route("/latest_<int:i>.jpg")
def latest_n(i):
    p = os.path.join(RENDER_DIR, f"latest_{i}.jpg")
    if not os.path.exists(p):
        return "no image", 404
    return send_from_directory(RENDER_DIR, f"latest_{i}.jpg")


@app.route("/frames/<path:name>")
def frame(name):
    return send_from_directory(FRAMES_DIR, name)


@app.route("/events")
def events():
    q: queue.Queue = queue.Queue(maxsize=10)
    with _sse_lock:
        _sse_clients.append(q)

    def stream():
        try:
            while True:
                try:
                    yield q.get(timeout=30)
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/trigger", methods=["POST"])
def trigger():
    """Doorbell handler: pull burst → save flipbook frames → stream-render effects.

    Pushes a `playlist-start` (with flipbook frame URLs) then one `append` per effect
    as it finishes, so the viewer can start looping the new playlist while the rest
    render. The viewer keeps showing the current loop until the first still arrives.
    """
    if not _trigger_lock.acquire(blocking=False):
        return jsonify({"error": "busy"}), 429
    try:
        overall = time.perf_counter()
        print(f"\n[{time.strftime('%H:%M:%S')}] trigger received")

        try:
            frames = _pull_burst()
        except Exception as e:
            print(f"  burst failed: {e}")
            return jsonify({"error": "burst", "detail": str(e)}), 502
        if not frames:
            return jsonify({"error": "empty burst"}), 502

        # Flipbook frames + new-playlist signal (no black gap: viewer keeps the old loop
        # until the first still arrives).
        flip_urls = _save_burst_frames(frames)
        _push_sse("playlist-start", {"flipbook": flip_urls, "kind": FLIPBOOK_KIND})

        # Stream-render stills one at a time; push each as it completes. A failing
        # effect is skipped, not fatal.
        for i, (name, fn) in enumerate(EFFECT_PALETTE):
            try:
                t0 = time.perf_counter()
                img = fn(frames)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(os.path.join(RENDER_DIR, f"latest_{i}.jpg"), "JPEG", quality=85)
                token = str(int(time.time() * 1000))
                _push_sse("append", {"index": i, "url": f"/latest_{i}.jpg?t={token}",
                                     "kind": "still", "name": name})
                print(f"  {name}: {(time.perf_counter() - t0) * 1000:.0f}ms")
            except Exception as e:
                print(f"  effect {name} failed, skipping: {e}")

        total_ms = (time.perf_counter() - overall) * 1000
        print(f"  done: {len(EFFECT_PALETTE)} stills, total {total_ms:.0f}ms")
        return jsonify({"ok": True, "stills": len(EFFECT_PALETTE), "total_ms": round(total_ms, 1)})
    finally:
        _trigger_lock.release()


@app.route("/health")
def health():
    return "ok"


if __name__ == "__main__":
    print(f"effects_server: listening on {HOST}:{PORT}")
    print(f"  MaixCam burst:   http://{MAIXCAM_HOST}:{MAIXCAM_PORT}/burst")
    print(f"  Effect palette:  {[n for n, _ in EFFECT_PALETTE]}")
    app.run(host=HOST, port=PORT, threaded=True)
