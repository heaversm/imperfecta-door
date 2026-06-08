"""Effects server (replaces bg_removal_server.py).

Runs on the Pi. On `POST /trigger`:
  1. Pulls the last 30 frames from the MaixCam burst endpoint (one HTTP call, ~250KB ZIP).
  2. Picks a random effect from the v1 palette and renders one image.
  3. Saves it as static/latest.jpg and pushes an SSE 'replace' event to the viewer.

No accumulation, no Replicate, no internet dependency. Same `effects.py` module
runs here and on the Mac preview rig.
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
# The MaixCam now captures full-res (sharp source). But rendering 9 effects per
# press at full res would blow the ~4s budget on the Pi 3B+, and a 3-up grid of
# full-res tiles is far bigger than the ~1024px display can show. So downscale
# each burst frame to this longest-side cap first: ~512px tiles → ~1536px grid,
# sharp on screen and fast to render. Tune via env without redeploying code.
WORK_MAX_DIM = int(os.environ.get("WORK_MAX_DIM", "640"))

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
LATEST_PATH = os.path.join(STATIC_DIR, "latest.jpg")
# ────────────────────────────────────────────────────────────────────

# v1 effect palette. Each entry is (display_name, callable).
# The callable takes a list of PIL Images and returns a PIL Image.
# Wraps each effect to discard its timing tuple (we measure ours).
def _effect(fn, *args, **kwargs):
    def call(frames):
        result = fn(*args, frames=frames, **kwargs) if "frames" in fn.__code__.co_varnames else fn(frames, *args, **kwargs)
        # All effects return (image, ms) via @_timed
        return result[0]
    return call


def _slit_v(frames): return effects.slitscan_vertical(frames)[0]
def _slit_h(frames): return effects.slitscan_horizontal(frames)[0]
def _emax(frames):   return effects.echo_max(frames)[0]
def _tgrid(frames):  return effects.time_grid(frames, rows=8, cols=6)[0]
def _hock(frames):
    return effects.hockney_joiner(
        frames, rows=3, cols=3,
        rotation_max_deg=12, jitter_frac=0.12, border_px=10
    )[0]
def _liq(frames):
    middle = frames[len(frames) // 2]
    return effects.liquify(
        middle, wave_amp=30, wave_freq=4, bulge=0.5, twirl_deg=45
    )[0]
def _warhol(frames):    return effects.warhol(frames)[0]
def _licht(frames):     return effects.lichtenstein(frames)[0]
def _mond(frames):      return effects.mondrian(frames)[0]

EFFECT_PALETTE = [
    ("slitscan vertical",   _slit_v),
    ("slitscan horizontal", _slit_h),
    ("echo max",            _emax),
    ("time grid 8x6",       _tgrid),
    ("hockney 3x3",         _hock),
    ("liquify extreme",     _liq),
    ("warhol",              _warhol),
    ("lichtenstein",        _licht),
    ("mondrian",            _mond),
]

# Grid layout: render all 9 effects per press, composite into rows × cols.
# Keeps each tile near its native source resolution (avoiding the 4×
# upscale that made single fullscreen images pixelated).
GRID_ROWS = 3
GRID_COLS = 3


def render_grid(frames: list[Image.Image]) -> tuple[Image.Image, list[tuple[str, float]]]:
    """Render every effect from the same burst and composite into a grid.

    Returns (composite_image, [(effect_name, ms), …]).
    """
    rendered: list[tuple[str, Image.Image, float]] = []
    for name, fn in EFFECT_PALETTE:
        t0 = time.perf_counter()
        img = fn(frames)
        ms = (time.perf_counter() - t0) * 1000
        rendered.append((name, img, ms))

    # All tiles snap to the source frame size for a clean uniform grid.
    tile_w, tile_h = frames[0].size
    composite = Image.new("RGB", (tile_w * GRID_COLS, tile_h * GRID_ROWS), (0, 0, 0))

    for i, (_name, img, _ms) in enumerate(rendered):
        if img.size != (tile_w, tile_h):
            img = img.resize((tile_w, tile_h), Image.LANCZOS)
        r, c = divmod(i, GRID_COLS)
        composite.paste(img, (c * tile_w, r * tile_h))

    return composite, [(n, ms) for (n, _img, ms) in rendered]

# ── Flask app ───────────────────────────────────────────────────────
app = Flask(__name__, static_folder=STATIC_DIR)

_trigger_lock = threading.Lock()    # serialize /trigger so two doorbells in a row don't collide
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()
_latest_token = "0"                  # cache-buster updated on each render


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


@app.route("/latest.jpg")
def latest():
    if not os.path.exists(LATEST_PATH):
        return "no image yet", 404
    return send_from_directory(STATIC_DIR, "latest.jpg")


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
    """Doorbell handler: pull burst → run effect → save → push SSE."""
    if not _trigger_lock.acquire(blocking=False):
        return jsonify({"error": "busy"}), 429

    global _latest_token
    try:
        overall = time.perf_counter()
        print(f"\n[{time.strftime('%H:%M:%S')}] trigger received")

        # 1. Burst capture
        try:
            frames = _pull_burst()
        except Exception as e:
            print(f"  burst failed: {e}")
            return jsonify({"error": "burst", "detail": str(e)}), 502

        if not frames:
            return jsonify({"error": "empty burst"}), 502

        # 2. Render all effects into a grid composite
        t0 = time.perf_counter()
        try:
            composite, per_effect = render_grid(frames)
        except Exception as e:
            print(f"  render_grid raised: {e}")
            return jsonify({"error": "render", "detail": str(e)}), 500
        render_ms = (time.perf_counter() - t0) * 1000
        slowest = max(per_effect, key=lambda x: x[1])
        print(f"  rendered {len(per_effect)} effects in {render_ms:.0f}ms (slowest: {slowest[0]} {slowest[1]:.0f}ms)")

        # 3. Save (JPEG, quality 85 — small + fast)
        t0 = time.perf_counter()
        composite.save(LATEST_PATH, "JPEG", quality=85, optimize=False)
        save_ms = (time.perf_counter() - t0) * 1000

        # 4. SSE push with a cache-busting token
        _latest_token = str(int(time.time() * 1000))
        _push_sse("replace", {"url": f"/latest.jpg?t={_latest_token}", "grid": f"{GRID_ROWS}x{GRID_COLS}"})

        total_ms = (time.perf_counter() - overall) * 1000
        print(f"  done: render {render_ms:.0f}ms, save {save_ms:.0f}ms, total {total_ms:.0f}ms")
        return jsonify({
            "ok": True,
            "grid": f"{GRID_ROWS}x{GRID_COLS}",
            "render_ms": round(render_ms, 1),
            "save_ms": round(save_ms, 1),
            "total_ms": round(total_ms, 1),
            "per_effect_ms": {n: round(ms, 1) for (n, ms) in per_effect},
        })
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
