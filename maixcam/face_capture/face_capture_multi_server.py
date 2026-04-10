#!/usr/bin/env python3
"""Multi-face capture HTTP server for MaixCam.

Run this on MaixCam via MaixVision instead of face_capture.py.
Sits waiting for HTTP requests rather than waiting for screen taps.

Endpoints:
  GET /capture-all  — detect ALL faces above confidence threshold,
                      return JSON array of base64-encoded face JPEGs
  GET /capture      — backward compat: returns largest face JPEG only
  GET /photo        — full camera frame as JPEG

Requires MaixPy environment (maix.camera, maix.nn, maix.image).
"""

from maix import camera, nn, image, display, network, err
import json
import base64
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Config ──────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8080
CONFIDENCE_THRESHOLD = 0.5
FACE_PADDING = 60          # px padding around detected face box
CAPTURE_COOLDOWN = 1.0     # seconds between captures to avoid duplicates

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
    cam = camera.Camera(detector.input_width(), detector.input_height(),
                        detector.input_format())
    disp = display.Display()
    print(f"Camera and face detector initialized")
    print(f"Reachable at http://{wifi_ip}:{PORT}")


def camera_loop():
    """Continuously read camera, detect faces, show preview with boxes."""
    global latest_frame
    while True:
        img = cam.read()
        with frame_lock:
            latest_frame = img.copy()
        # Draw detection boxes on preview (not on the saved frame)
        objs = detector.detect(img, conf_th=CONFIDENCE_THRESHOLD, iou_th=0.45)
        for obj in objs:
            img.draw_rect(obj.x, obj.y, obj.w, obj.h,
                         color=image.COLOR_GREEN, thickness=2)
        if objs:
            img.draw_string(10, 10, f"Faces: {len(objs)}",
                           color=image.COLOR_GREEN, scale=1.5)
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
    objects = detector.detect(frame, conf_th=CONFIDENCE_THRESHOLD, iou_th=0.45)
    faces = []
    for obj in objects:
        faces.append({
            "x": obj.x,
            "y": obj.y,
            "w": obj.w,
            "h": obj.h,
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

    def do_GET(self):
        if self.path == "/capture-all":
            self._handle_capture_all()
        elif self.path == "/capture":
            self._handle_capture_single()
        elif self.path == "/photo":
            self._handle_photo()
        else:
            self._send_json({"error": "not found"}, 404)

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
    print(f"  GET /capture-all  — all faces (JSON + base64)")
    print(f"  GET /capture      — largest face (JPEG)")
    print(f"  GET /photo        — full frame (JPEG)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.server_close()


if __name__ == "__main__":
    main()
