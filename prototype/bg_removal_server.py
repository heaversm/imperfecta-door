"""
Background Removal Server + Face Gallery Display (Replicate Edition)

Runs on Pi. Receives a face JPEG from the orchestrator,
sends it to Replicate for bg removal, saves the PNG,
and pushes updates to a browser gallery via SSE.

Usage:
    REPLICATE_API_TOKEN=r8_xxx python3 bg_removal_server.py

Then open http://<pi-ip>:5050/ in a browser.
"""

from flask import Flask, request, Response, jsonify, send_from_directory
from PIL import Image
import numpy as np
import replicate
import io
import os
import time
import glob
import json
import queue
import threading
import urllib.request

# ── Funhouse distortion config ────────────────────────────────
DISTORT_ENABLED = True             # set False to disable distortion
DISTORT_WAVE_AMP_MAX = 15         # max wave amplitude in pixels (0 to this)
DISTORT_WAVE_FREQ_MAX = 3.0       # max wave frequency (0 to this)
DISTORT_BULGE_STRENGTH_MAX = 0.3  # max barrel bulge (0 to this)
# ──────────────────────────────────────────────────────────────

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(SAVE_DIR, exist_ok=True)

MAX_FACES = 100

app = Flask(__name__, static_folder=STATIC_DIR)

face_list = []
face_lock = threading.Lock()

sse_clients = []
sse_lock = threading.Lock()


def funhouse_distort(img):
    """Apply randomized funhouse mirror distortion to a PIL Image (RGBA)."""
    if not DISTORT_ENABLED:
        return img

    import random
    wave_amp = random.uniform(0, DISTORT_WAVE_AMP_MAX)
    wave_freq = random.uniform(0, DISTORT_WAVE_FREQ_MAX)
    bulge = random.uniform(0, DISTORT_BULGE_STRENGTH_MAX)

    arr = np.array(img, dtype=np.float64)
    h, w = arr.shape[:2]

    # Build coordinate grids
    y_coords, x_coords = np.mgrid[0:h, 0:w]

    # Normalize to -1..1 centered
    nx = (x_coords - w / 2) / (w / 2)
    ny = (y_coords - h / 2) / (h / 2)

    # Wave distortion
    src_x = x_coords + wave_amp * np.sin(wave_freq * np.pi * ny)
    src_y = y_coords + wave_amp * np.sin(wave_freq * np.pi * nx)

    # Barrel/bulge distortion
    if bulge > 0.01:
        r = np.sqrt(nx ** 2 + ny ** 2)
        r_distorted = r * (1 + bulge * r ** 2)
        scale = np.where(r > 0, r_distorted / r, 1.0)
        src_x = (nx * scale) * (w / 2) + w / 2 + wave_amp * np.sin(wave_freq * np.pi * ny)
        src_y = (ny * scale) * (h / 2) + h / 2 + wave_amp * np.sin(wave_freq * np.pi * nx)

    # Clamp and map
    src_x = np.clip(src_x, 0, w - 1).astype(np.int32)
    src_y = np.clip(src_y, 0, h - 1).astype(np.int32)
    result = arr[src_y, src_x]

    return Image.fromarray(result.astype(np.uint8))


def restore_face_list():
    """Scan captures/ on startup to restore state."""
    global face_list
    pattern = os.path.join(SAVE_DIR, "removed_*.png")
    files = sorted(glob.glob(pattern), key=os.path.getmtime)
    face_list = [os.path.basename(f) for f in files]
    while len(face_list) > MAX_FACES:
        oldest = face_list.pop(0)
        _delete_face_files(oldest)
    print(f"Restored {len(face_list)} faces from captures/")


def _delete_face_files(filename):
    """Delete a removed_*.png and its matching original_*.jpg."""
    try:
        os.remove(os.path.join(SAVE_DIR, filename))
    except OSError:
        pass
    original = filename.replace("removed_", "original_").replace(".png", ".jpg")
    try:
        os.remove(os.path.join(SAVE_DIR, original))
    except OSError:
        pass


def send_sse_event(event_type, data):
    """Push an SSE event to all connected clients."""
    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    with sse_lock:
        dead = []
        for q in sse_clients:
            try:
                q.put_nowait(message)
            except queue.Full:
                dead.append(q)
        for q in dead:
            sse_clients.remove(q)


restore_face_list()


@app.route("/")
def gallery():
    return send_from_directory(STATIC_DIR, "gallery.html")


@app.route("/remove-bg", methods=["POST"])
def remove_bg():
    if "image" not in request.files:
        return "No image provided", 400

    start = time.time()

    img_bytes = request.files["image"].read()
    img = Image.open(io.BytesIO(img_bytes))

    # Save original
    timestamp = int(time.time())
    img.save(os.path.join(SAVE_DIR, f"original_{timestamp}.jpg"))

    # Send to Replicate for bg removal
    output = replicate.run(
        "cjwbw/rembg:fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003",
        input={"image": io.BytesIO(img_bytes)},
    )

    # output is a FileOutput object — read it directly
    png_bytes = output.read()

    # Apply funhouse distortion
    result_img = Image.open(io.BytesIO(png_bytes))
    result_img = funhouse_distort(result_img)
    output_buf = io.BytesIO()
    result_img.save(output_buf, format="PNG")
    png_bytes = output_buf.getvalue()

    # Save result
    filename = f"removed_{timestamp}.png"
    with open(os.path.join(SAVE_DIR, filename), "wb") as f:
        f.write(png_bytes)

    # Update face list and enforce max
    removed_face = None
    with face_lock:
        face_list.append(filename)
        if len(face_list) > MAX_FACES:
            removed_face = face_list.pop(0)

    if removed_face:
        _delete_face_files(removed_face)
        send_sse_event("remove", {"filename": removed_face})

    send_sse_event("add", {"filename": filename})

    elapsed = time.time() - start
    print(f"Background removed in {elapsed:.1f}s ({img.size[0]}x{img.size[1]}) -> {filename}")

    return Response(png_bytes, mimetype="image/png")


@app.route("/faces", methods=["GET"])
def faces():
    with face_lock:
        return jsonify(list(face_list))


@app.route("/captures/<filename>")
def serve_capture(filename):
    return send_from_directory(SAVE_DIR, filename)


@app.route("/events")
def sse_stream():
    """SSE endpoint for real-time gallery updates."""
    q = queue.Queue(maxsize=50)
    with sse_lock:
        sse_clients.append(q)

    def generate():
        try:
            while True:
                try:
                    message = q.get(timeout=30)
                    yield message
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            with sse_lock:
                if q in sse_clients:
                    sse_clients.remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/health", methods=["GET"])
def health():
    return "ok"


if __name__ == "__main__":
    if not os.environ.get("REPLICATE_API_TOKEN"):
        print("ERROR: Set REPLICATE_API_TOKEN environment variable")
        print("  Get your token at: https://replicate.com/account/api-tokens")
        exit(1)
    print("Starting background removal server on port 5050 (Replicate)...")
    print("Open http://<this-ip>:5050/ for the face gallery")
    app.run(host="0.0.0.0", port=5050, threaded=True)
