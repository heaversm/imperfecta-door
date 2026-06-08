#!/usr/bin/env python3
"""Multi-face capture HTTP server for MaixCam.

Run this on MaixCam via MaixVision instead of face_capture.py.
Sits waiting for HTTP requests rather than waiting for screen taps.

Endpoints:
  GET /capture-all  — detect ALL faces above confidence threshold,
                      return JSON array of base64-encoded face JPEGs
  GET /capture      — backward compat: returns largest face JPEG only
  GET /photo        — full camera frame as JPEG
  GET /burst?count=N — last N frames from a continuously-filled ring buffer,
                       returned as a ZIP of frame_000.jpg … frame_NNN.jpg

Requires MaixPy environment (maix.camera, maix.nn, maix.image).
"""

from maix import camera, nn, image, display, network, err
import base64
import collections
import io
import json
import threading
import time
import zipfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── Config ──────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8080
CONFIDENCE_THRESHOLD = 0.5
FACE_PADDING = 60          # px padding around detected face box
CAPTURE_COOLDOWN = 1.0     # seconds between captures to avoid duplicates
BURST_BUFFER_SIZE = 60     # max frames retained for /burst (FPS × ~2s typical)

# Capture resolution — DECOUPLED from the YOLO detector input. Previously the
# camera was sized to the model input (~320px), so every /burst frame the gallery
# pipeline uses was tiny and mushy. The effects pipeline pulls RAW frames (no
# detection), so it just needs detail. Detection for the legacy /capture-all
# endpoint now runs on a downscaled copy (see detect_faces).
# Sized just above the effects work-res (512px longest side) so /burst frames are
# sharp but small to ship — capturing at 1280×720 only to downscale to 512 on the
# Pi wasted ~4× the transfer+decode time and blew the 4s budget (measured 7.2s).
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 360

WIFI_SSID = "VIRUSDETECTED"
WIFI_PASSWORD = "ifyaknowyakn0w!"
# ────────────────────────────────────────────────────────────────────

# Global state
last_capture_time = 0.0
cam = None
detector = None
disp = None
latest_frame = None
frame_lock = threading.Lock()
# Continuously filled ring of JPEG-encoded frames for instant burst delivery.
# The doorbell trigger gives zero advance warning, so capturing N frames *after*
# the trigger would cost ~N × frame_interval — fatal for the 4-second budget.
# Filling continuously means /burst returns immediately.
frame_buffer = collections.deque(maxlen=BURST_BUFFER_SIZE)
buffer_lock = threading.Lock()


def connect_wifi():
    """Connect to Wi-Fi and print the assigned IP."""
    w = network.wifi.Wifi()
    ip = w.get_ip()
    if ip and ip != "0.0.0.0":
        print(f"Already connected to Wi-Fi, IP: {ip}")
        return ip
    print(f"Connecting to Wi-Fi: {WIFI_SSID}")
    e = w.connect(WIFI_SSID, WIFI_PASSWORD, wait=True, timeout=60)
    err.check_raise(e, "Failed to connect to WiFi")
    ip = w.get_ip()
    print(f"Wi-Fi connected, IP: {ip}")
    return ip


def init_hardware():
    """Initialize Wi-Fi, camera, display, and face detector."""
    global cam, detector, disp
    wifi_ip = connect_wifi()
    detector = nn.YOLOv8(model="/root/models/yolov8n_face.mud", dual_buff=True)
    # Full-resolution capture (NOT the detector's tiny input size). The gallery
    # effects pipeline pulls raw /burst frames and needs the detail.
    cam = camera.Camera(CAPTURE_WIDTH, CAPTURE_HEIGHT)
    disp = display.Display()
    print(f"Camera and face detector initialized")
    print(f"Reachable at http://{wifi_ip}:{PORT}")


def camera_loop():
    """Continuously read camera, detect faces, show preview with boxes.

    Also fills the burst ring buffer: every frame is JPEG-encoded once and
    appended, so /burst can return the last N frames with no latency.
    """
    global latest_frame
    while True:
        img = cam.read()
        with frame_lock:
            latest_frame = img.copy()
        # Append a JPEG copy to the burst buffer. Use a separate tmp path so
        # this doesn't race with /capture-all's own JPEG encoding.
        try:
            tmp_path = "/tmp/_burst_tmp.jpg"
            img.save(tmp_path)
            with open(tmp_path, "rb") as f:
                jpeg = f.read()
            with buffer_lock:
                frame_buffer.append(jpeg)
        except Exception as e:
            print(f"[burst] frame encode failed: {e}")
        # Show the live frame on the MaixCam's own screen. We no longer run YOLO
        # per frame: the gallery uses raw /burst frames, and detecting at full
        # capture res would mismatch the model input. /capture-all still detects
        # on demand (downscaled copy). Dropping it also speeds up burst fill.
        disp.show(img)


def capture_frame():
    """Return the latest frame from the continuous camera loop."""
    with frame_lock:
        if latest_frame is None:
            return None
        return latest_frame.copy()


def detect_faces(frame):
    """Run face detection, return list of bounding boxes sorted by area (largest first).

    Each entry: {"x": int, "y": int, "w": int, "h": int, "confidence": float}
    """
    # Capture res is now larger than the model input, so detect on a downscaled
    # copy and scale boxes back to full-res coords (crop_face then yields hi-res crops).
    det_w, det_h = detector.input_width(), detector.input_height()
    small = frame.resize(det_w, det_h)
    sx = frame.width() / det_w
    sy = frame.height() / det_h
    objects = detector.detect(small, conf_th=CONFIDENCE_THRESHOLD, iou_th=0.45)
    faces = []
    for obj in objects:
        faces.append({
            "x": int(obj.x * sx),
            "y": int(obj.y * sy),
            "w": int(obj.w * sx),
            "h": int(obj.h * sy),
            "confidence": obj.score,
        })
    # Sort largest first
    faces.sort(key=lambda f: f["w"] * f["h"], reverse=True)
    return faces


def crop_face(frame, face):
    """Crop a face from the frame with padding, clamped to image bounds."""
    img_w = frame.width()
    img_h = frame.height()

    x1 = max(0, face["x"] - FACE_PADDING)
    y1 = max(0, face["y"] - FACE_PADDING)
    x2 = min(img_w, face["x"] + face["w"] + FACE_PADDING)
    y2 = min(img_h, face["y"] + face["h"] + FACE_PADDING)

    cropped = frame.crop(x1, y1, x2 - x1, y2 - y1)
    return cropped


def image_to_jpeg_bytes(img):
    """Convert a maix.image.Image to JPEG bytes.

    Uses save-to-file workaround to avoid VPSS format conversion issues
    with to_format(FMT_JPEG) on cropped images (same approach as face_capture.py).
    """
    tmp_path = "/tmp/_face_tmp.jpg"
    img.save(tmp_path)
    with open(tmp_path, "rb") as f:
        return f.read()


def face_to_base64_jpeg(frame, face):
    """Crop face from frame and encode as base64 JPEG string."""
    cropped = crop_face(frame, face)
    jpeg_bytes = image_to_jpeg_bytes(cropped)
    return base64.b64encode(jpeg_bytes).decode("ascii")


class CaptureHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quieter logging
        print(f"[{time.strftime('%H:%M:%S')}] {args[0] if args else ''}")

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_jpeg(self, jpeg_bytes, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(jpeg_bytes)

    def _enforce_cooldown(self):
        global last_capture_time
        now = time.time()
        if now - last_capture_time < CAPTURE_COOLDOWN:
            self._send_json({"error": "cooldown", "retry_after": CAPTURE_COOLDOWN}, 429)
            return False
        last_capture_time = now
        return True

    def _send_zip(self, zip_bytes, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(zip_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(zip_bytes)

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/capture-all":
            self._handle_capture_all()
        elif route == "/capture":
            self._handle_capture_single()
        elif route == "/photo":
            self._handle_photo()
        elif route == "/burst":
            self._handle_burst(parsed.query)
        else:
            self._send_json({"error": "not found"}, 404)

    def _handle_burst(self, query_str):
        """Return the last N frames from the ring buffer as a ZIP of JPEGs."""
        qs = parse_qs(query_str)
        try:
            count = int(qs.get("count", ["30"])[0])
        except (ValueError, TypeError):
            count = 30
        count = max(1, min(count, BURST_BUFFER_SIZE))

        with buffer_lock:
            frames = list(frame_buffer)[-count:]

        if not frames:
            self._send_json({"error": "burst buffer empty"}, 503)
            return

        buf = io.BytesIO()
        # ZIP_STORED: no compression — JPEG data is already compressed, and
        # storage-only is much faster on a constrained device. Explicit
        # date_time avoids "ZIP does not support timestamps before 1980" if
        # the MaixCam boots before NTP syncs the clock.
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            for i, jpeg in enumerate(frames):
                info = zipfile.ZipInfo(
                    filename=f"frame_{i:03d}.jpg",
                    date_time=(2026, 1, 1, 0, 0, 0),
                )
                zf.writestr(info, jpeg)
        body = buf.getvalue()
        print(f"Burst served: {len(frames)} frames, {len(body)} bytes")
        self._send_zip(body)

    def _handle_capture_all(self):
        """Detect ALL faces, return JSON array of base64 JPEGs."""
        if not self._enforce_cooldown():
            return

        frame = capture_frame()
        if frame is None:
            self._send_json({"error": "camera not ready"}, 503)
            return
        faces = detect_faces(frame)

        if not faces:
            self._send_json({"faces": [], "count": 0})
            return

        results = []
        for face in faces:
            b64 = face_to_base64_jpeg(frame, face)
            results.append({
                "jpeg_base64": b64,
                "confidence": round(face["confidence"], 3),
                "bbox": {"x": face["x"], "y": face["y"],
                         "w": face["w"], "h": face["h"]},
            })

        print(f"Captured {len(results)} face(s)")
        self._send_json({"faces": results, "count": len(results)})

    def _handle_capture_single(self):
        """Backward compat: return largest face as raw JPEG."""
        if not self._enforce_cooldown():
            return

        frame = capture_frame()
        if frame is None:
            self._send_json({"error": "camera not ready"}, 503)
            return
        faces = detect_faces(frame)

        if not faces:
            self._send_json({"error": "no face detected"}, 404)
            return

        # Largest face (already sorted)
        cropped = crop_face(frame, faces[0])
        jpeg_bytes = image_to_jpeg_bytes(cropped)
        print(f"Captured 1 face (largest of {len(faces)})")
        self._send_jpeg(jpeg_bytes)

    def _handle_photo(self):
        """Return full camera frame as JPEG."""
        frame = capture_frame()
        if frame is None:
            self._send_json({"error": "camera not ready"}, 503)
            return
        jpeg_bytes = image_to_jpeg_bytes(frame)
        self._send_jpeg(jpeg_bytes)


def main():
    init_hardware()
    # Start background camera loop (live preview + keeps frames fresh)
    cam_thread = threading.Thread(target=camera_loop, daemon=True)
    cam_thread.start()
    server = HTTPServer((HOST, PORT), CaptureHandler)
    print(f"Face capture server listening on {HOST}:{PORT}")
    print(f"  GET /capture-all   — all faces (JSON + base64)")
    print(f"  GET /capture       — largest face (JPEG)")
    print(f"  GET /photo         — full frame (JPEG)")
    print(f"  GET /burst?count=N — last N buffered frames (ZIP of JPEGs)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.server_close()


if __name__ == "__main__":
    main()
