#!/usr/bin/env python3
"""Pi orchestrator: button press → capture faces + trigger LEDs.

Runs on the Raspberry Pi. Listens for a physical button on GPIO,
then fires camera capture and WLED animation in parallel.

Hardware:
  - Momentary push button between GPIO17 (pin 11) and GND (pin 9)
  - No external resistor needed (uses Pi internal pull-up)

Dependencies:
  - requests (pip install requests)
  - RPi.GPIO (pre-installed on Pi OS)

End-to-end flow:
  Button press
    → GET /capture-all on MaixCam (all faces)
    → POST /json/state on WLED (ring preset)
    → For each face: POST /remove-bg on bg removal server
    → Gallery updates via SSE automatically
"""

from __future__ import annotations

import base64
import sys
import time
import threading
import json

import requests

try:
    import gpiod
    from gpiod.line import Direction, Bias, Value
except ImportError:
    gpiod = None
    print("WARNING: gpiod not available — running in dev mode (no GPIO)")

# ── Config ──────────────────────────────────────────────────────────
MAIXCAM_IP = "10.0.0.14"       # MaixCam (Wi-Fi)
MAIXCAM_PORT = 8080

WLED_IP = "10.0.0.220"          # WLED controller (Dig-Quad)

BG_SERVER_IP = "127.0.0.1"     # bg_removal_server.py runs locally on Pi
BG_SERVER_PORT = 5050

RING_PRESET_ID = 1              # WLED preset for ring animation
AMBIENT_PRESET_ID = 2           # WLED preset for night ambient (future use)

GPIO_PIN = 17                   # BCM pin number (physical pin 11)
TRIGGER_MODE = "rf"             # "rf" = 433MHz burst detection (Avantek), "fsr" = active HIGH (FSR + 10K divider), "button" = active LOW
# RF burst detection: we don't decode bits — we fingerprint the Avantek's burst envelope.
# Calibrated 2026-04-28: Avantek presses produced 329-343 edges, 237-252ms duration;
# largest noise burst was 138 edges, 98ms. Threshold is set with comfortable margin.
RF_SYNC_MIN_US = 5000           # gap > this ends a burst
RF_BURST_MIN_EDGES = 250        # min edges to count as Avantek (presses run 329+)
RF_BURST_MIN_DURATION_MS = 150  # min duration ms (presses run 237+)
COOLDOWN_SECONDS = 3.0          # Debounce / cooldown between triggers
REQUEST_TIMEOUT = 10.0          # HTTP request timeout
WLED_RING_DURATION = 5.0        # Seconds to play ring animation before turning off
WLED_AMBIENT_INTERVAL = 30.0    # Seconds between ambient animation triggers
WLED_AMBIENT_DURATION = 30.0    # Seconds to play ambient animation before turning off
# ────────────────────────────────────────────────────────────────────


def check_faces() -> int:
    """Call MaixCam /capture-all to check if faces are present. Returns face count."""
    url = f"http://{MAIXCAM_IP}:{MAIXCAM_PORT}/capture-all"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        count = data.get("count", 0)
        print(f"  Detected {count} face(s)")
        return count
    except requests.RequestException as exc:
        print(f"  MaixCam face check failed: {exc}")
        return 0


def capture_full_frame() -> bytes | None:
    """Call MaixCam /photo to get the full camera frame as JPEG."""
    url = f"http://{MAIXCAM_IP}:{MAIXCAM_PORT}/photo"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        print(f"  Captured full frame ({len(resp.content)} bytes)")
        return resp.content
    except requests.RequestException as exc:
        print(f"  MaixCam photo capture failed: {exc}")
        return None


# Global flag to stop ambient loop when a new ring trigger comes in
_ambient_stop = threading.Event()


def wled_post(payload):
    """Send a state update to WLED."""
    url = f"http://{WLED_IP}/json/state"
    resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT,
                         headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return resp


def ambient_loop():
    """Play ambient animation on/off cycle until stopped."""
    while not _ambient_stop.is_set():
        try:
            wled_post({"on": True, "ps": AMBIENT_PRESET_ID})
        except requests.RequestException:
            pass

        if _ambient_stop.wait(timeout=WLED_AMBIENT_DURATION):
            break

        try:
            wled_post({"on": False})
        except requests.RequestException:
            pass

        # Wait between cycles, but check stop flag
        if _ambient_stop.wait(timeout=WLED_AMBIENT_INTERVAL):
            break

    # Make sure LEDs are off when ambient stops
    try:
        wled_post({"on": False})
    except requests.RequestException:
        pass
    print(f"  Ambient mode stopped")


def trigger_wled_ring():
    """Play ring animation, then start ambient loop."""
    # Stop any running ambient loop
    _ambient_stop.set()

    try:
        wled_post({"on": True, "ps": RING_PRESET_ID})
        print(f"  WLED ring preset {RING_PRESET_ID} activated")

        time.sleep(WLED_RING_DURATION)

        wled_post({"on": False})
        print(f"  WLED off after {WLED_RING_DURATION}s")
    except requests.RequestException as exc:
        print(f"  WLED trigger failed: {exc}")

    # Start ambient loop in background
    _ambient_stop.clear()
    threading.Thread(target=ambient_loop, daemon=True).start()


def send_to_bg_removal(jpeg_bytes: bytes):
    """Send a full-frame JPEG to the bg removal server."""
    url = f"http://{BG_SERVER_IP}:{BG_SERVER_PORT}/remove-bg"
    try:
        resp = requests.post(
            url,
            files={"image": ("capture.jpg", jpeg_bytes, "image/jpeg")},
            timeout=30.0,  # bg removal can be slow
        )
        resp.raise_for_status()
        print(f"  Background removal done")
    except requests.RequestException as exc:
        print(f"  Background removal failed: {exc}")


def handle_button_press():
    """Main handler: check for faces, capture full frame, remove bg, trigger LEDs."""
    print(f"\n[{time.strftime('%H:%M:%S')}] Button pressed!")

    # Fire WLED trigger in parallel with capture
    wled_thread = threading.Thread(target=trigger_wled_ring, daemon=True)
    wled_thread.start()

    # Check if any faces are visible
    face_count = check_faces()
    if face_count == 0:
        print("  No faces detected — skipping capture")
        wled_thread.join(timeout=5.0)
        return

    # Grab the full frame (group photo)
    frame = capture_full_frame()
    if frame is None:
        print("  Failed to capture frame")
        wled_thread.join(timeout=5.0)
        return

    # Send full frame to bg removal → gallery
    send_to_bg_removal(frame)

    # Wait for WLED trigger to complete
    wled_thread.join(timeout=5.0)

    print(f"  Done — group photo with {face_count} face(s)")


def setup_gpio():
    """Request the button line via gpiod v2."""
    if gpiod is None:
        return None

    if TRIGGER_MODE == "rf":
        from gpiod.line import Edge
        bias = Bias.PULL_DOWN
        config = gpiod.LineSettings(direction=Direction.INPUT, bias=bias, edge_detection=Edge.BOTH)
        print(f"GPIO {GPIO_PIN} configured via gpiod (edge detection — RF mode)")
    elif TRIGGER_MODE == "fsr":
        config = gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_DOWN)
        print(f"GPIO {GPIO_PIN} configured via gpiod (pull-down, active HIGH — FSR mode)")
    else:
        config = gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP)
        print(f"GPIO {GPIO_PIN} configured via gpiod (pull-up, active LOW — button mode)")

    request = gpiod.request_lines(
        "/dev/gpiochip0",
        consumer="orchestrator",
        config={GPIO_PIN: config},
        event_buffer_size=512,
    )
    return request


def run_rf_loop():
    """Main loop: detect Avantek RF burst envelope on GPIO17 (no bit decoding) and trigger."""
    if gpiod is None:
        print("No GPIO available. Use --test flag for manual trigger.")
        return

    request = setup_gpio()
    if request is None:
        return

    print(f"\nListening for Avantek RF bursts on GPIO {GPIO_PIN}...")
    print(f"Trigger when burst has edges >= {RF_BURST_MIN_EDGES} and duration >= {RF_BURST_MIN_DURATION_MS}ms")
    print("Press Ctrl+C to exit\n")

    last_trigger = 0.0
    last_time_ns = None
    burst_gaps_us = []

    try:
        while True:
            for event in request.read_edge_events(max_events=512):
                now_ns = event.timestamp_ns
                if last_time_ns is None:
                    last_time_ns = now_ns
                    continue

                gap_us = (now_ns - last_time_ns) // 1000
                last_time_ns = now_ns

                if gap_us >= RF_SYNC_MIN_US:
                    edges = len(burst_gaps_us)
                    duration_ms = sum(burst_gaps_us) // 1000
                    if edges >= RF_BURST_MIN_EDGES and duration_ms >= RF_BURST_MIN_DURATION_MS:
                        now = time.time()
                        if now - last_trigger >= COOLDOWN_SECONDS:
                            last_trigger = now
                            print(f"  RF burst MATCH (edges={edges}, dur={duration_ms}ms) — triggering")
                            handle_button_press()
                        else:
                            remaining = COOLDOWN_SECONDS - (now - last_trigger)
                            print(f"  RF burst MATCH (edges={edges}, dur={duration_ms}ms) — cooldown {remaining:.1f}s")
                    burst_gaps_us = []
                else:
                    burst_gaps_us.append(gap_us)

    except KeyboardInterrupt:
        print("\nShutting down")
    finally:
        request.release()


def run_gpio_loop():
    """Main loop: poll GPIO for FSR or button trigger."""
    if gpiod is None:
        print("No GPIO available. Use --test flag for manual trigger.")
        return

    request = setup_gpio()
    if request is None:
        return

    last_trigger = 0.0

    print(f"\nListening for button press on GPIO {GPIO_PIN}...")
    print("Press Ctrl+C to exit\n")

    try:
        while True:
            trigger_value = Value.ACTIVE if TRIGGER_MODE == "fsr" else Value.INACTIVE
            if request.get_value(GPIO_PIN) == trigger_value:
                now = time.time()
                if now - last_trigger >= COOLDOWN_SECONDS:
                    last_trigger = now
                    handle_button_press()
                else:
                    remaining = COOLDOWN_SECONDS - (now - last_trigger)
                    print(f"  Cooldown: {remaining:.1f}s remaining")

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nShutting down")
    finally:
        request.release()


def run_test_mode():
    """Manual trigger mode for testing without GPIO hardware."""
    print("\n=== TEST MODE (no GPIO) ===")
    print(f"MaixCam: {MAIXCAM_IP}:{MAIXCAM_PORT}")
    print(f"WLED:    {WLED_IP}")
    print(f"BG srv:  {BG_SERVER_IP}:{BG_SERVER_PORT}")
    print("\nPress Enter to simulate button press, Ctrl+C to exit\n")

    try:
        while True:
            input(">>> Press Enter to trigger...")
            handle_button_press()
    except (KeyboardInterrupt, EOFError):
        print("\nDone")


def main():
    if "--test" in sys.argv:
        run_test_mode()
    elif TRIGGER_MODE == "rf":
        run_rf_loop()
    else:
        run_gpio_loop()


if __name__ == "__main__":
    main()
