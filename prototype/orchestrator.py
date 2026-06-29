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
import socket
import sys
import time
import threading
import json

import os

import requests

try:
    import gpiod
    from gpiod.line import Direction, Bias, Value
except ImportError:
    gpiod = None
    print("WARNING: gpiod not available — running in dev mode (no GPIO)")

# ── Config ──────────────────────────────────────────────────────────
# Devices are reached by mDNS hostname so we don't have to update IPs per venue.
# Override with env vars (e.g. MAIXCAM_HOST=10.0.0.14) if mDNS fails on a network.
# Requires nss-mdns / avahi-daemon on the Pi for *.local resolution to work.
MAIXCAM_IP = os.environ.get("MAIXCAM_HOST", "maixcam-288c.local")
WLED_IP    = os.environ.get("WLED_HOST",    "wled-dig-quad-v3.local")

MAIXCAM_PORT = 8080

BG_SERVER_IP = "127.0.0.1"     # bg_removal_server.py runs locally on Pi
BG_SERVER_PORT = 5050

RING_PRESET_ID = 1              # WLED preset for ring animation
AMBIENT_PRESET_ID = 2           # WLED preset for night ambient (future use)

GPIO_PIN = 17                   # BCM pin number (physical pin 11)
TRIGGER_MODE = "rf"             # "rf" = 433MHz burst detection (Avantek), "fsr" = active HIGH (FSR + 10K divider), "button" = active LOW
# RF burst detection: we don't decode bits — we fingerprint the Avantek's burst envelope.
# Calibrated 2026-04-29: Avantek presses are 329-343 edges / 237-252ms.
# A periodic 433MHz transmitter (likely a neighbor's weather sensor) fires exactly
# every 57s at 909 edges / 900-950ms — bigger than Avantek, so we cap on the high end too.
RF_SYNC_MIN_US = 5000           # gap > this ends a burst
RF_BURST_MIN_EDGES = 250        # presses run 329+, with margin
RF_BURST_MAX_EDGES = 500        # rejects the 909-edge periodic transmitter
RF_BURST_MIN_DURATION_MS = 150  # presses run 237+, with margin
RF_BURST_MAX_DURATION_MS = 400  # rejects the ~950ms periodic transmitter
COOLDOWN_SECONDS = 5.0          # Debounce / cooldown between triggers; matches WLED_RING_DURATION to avoid ring-thread races
REQUEST_TIMEOUT = 10.0          # HTTP request timeout
WLED_RING_DURATION = 5.0        # Seconds to play the ring chase before returning to ambient
# Ambient now runs continuously (set once, WLED animates it) — no on/off cycle constants.
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


# Reuse one connection and a cached IP so the ring fires the instant the bell is hit.
_wled_session = requests.Session()
_wled_addr: str | None = None   # cached IP for WLED_IP (resolved once)


def _wled_host() -> str:
    """Resolve the WLED mDNS hostname to an IP once and cache it.

    `.local` (mDNS) lookups cost hundreds of ms each and were happening on *every*
    ring — the main reason the LEDs lagged behind the on-screen flash. Resolve once,
    reuse the IP. Falls back to the hostname (requests will resolve it) on failure.
    """
    global _wled_addr
    if _wled_addr:
        return _wled_addr
    try:
        _wled_addr = socket.gethostbyname(WLED_IP)
    except OSError:
        _wled_addr = WLED_IP
    return _wled_addr


def wled_post(payload):
    """Send a state update to WLED (cached IP + persistent session)."""
    global _wled_addr
    url = f"http://{_wled_host()}/json/state"
    try:
        resp = _wled_session.post(url, json=payload, timeout=REQUEST_TIMEOUT,
                                  headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp
    except requests.RequestException:
        _wled_addr = None   # IP may be stale (DHCP) — re-resolve on the next call
        raise


def ambient_loop():
    """Run the ambient animation continuously until a ring interrupts it.

    WLED animates the effect itself on its controller, so we set the preset ONCE and just
    wait — no on/off cycling (that read as sparse / cutting out). The slow, subtle look
    lives in the preset itself (AMBIENT_PRESET_ID, editable in the WLED UI). A ring sets
    _ambient_stop, releasing the wait so this thread exits and the ring takes over.
    """
    try:
        wled_post({"on": True, "ps": AMBIENT_PRESET_ID})
        print(f"  WLED ambient preset {AMBIENT_PRESET_ID} running (continuous)")
    except requests.RequestException as exc:
        print(f"  WLED ambient failed: {exc}")
    _ambient_stop.wait()   # block until a ring interrupts; WLED keeps animating meanwhile


def trigger_wled_ring():
    """Snap to the ring chase immediately, then fall back to the continuous ambient."""
    # Interrupt ambient instantly so the ring takes over with no overlap.
    _ambient_stop.set()

    try:
        # tt:0 → no fade-in transition; the ring chase snaps on the moment the bell is hit.
        wled_post({"on": True, "ps": RING_PRESET_ID, "tt": 0})
        print(f"  WLED ring preset {RING_PRESET_ID} activated")

        time.sleep(WLED_RING_DURATION)
        # Don't turn the LEDs off — restart ambient below so they return to the idle
        # animation (a gentle default-transition fade) rather than going dark.
    except requests.RequestException as exc:
        print(f"  WLED trigger failed: {exc}")

    # Resume the continuous ambient animation.
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
    """Main handler: kick WLED + fire the effects pipeline.

    The effects server pulls the burst from MaixCam, picks an effect at random,
    renders it, and pushes the result to the viewer via SSE — all in one POST.
    """
    print(f"\n[{time.strftime('%H:%M:%S')}] Button pressed!")

    # Fire WLED in parallel with effect generation
    wled_thread = threading.Thread(target=trigger_wled_ring, daemon=True)
    wled_thread.start()

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

    wled_thread.join(timeout=10.0)
    print("  Done")


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
    print(f"Trigger when {RF_BURST_MIN_EDGES} <= edges <= {RF_BURST_MAX_EDGES} and {RF_BURST_MIN_DURATION_MS}ms <= duration <= {RF_BURST_MAX_DURATION_MS}ms")
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
                    in_edge_range = RF_BURST_MIN_EDGES <= edges <= RF_BURST_MAX_EDGES
                    in_dur_range = RF_BURST_MIN_DURATION_MS <= duration_ms <= RF_BURST_MAX_DURATION_MS
                    if in_edge_range and in_dur_range:
                        now = time.time()
                        if now - last_trigger >= COOLDOWN_SECONDS:
                            last_trigger = now
                            print(f"  RF burst MATCH (edges={edges}, dur={duration_ms}ms) — triggering")
                            handle_button_press()
                        else:
                            remaining = COOLDOWN_SECONDS - (now - last_trigger)
                            print(f"  RF burst MATCH (edges={edges}, dur={duration_ms}ms) — cooldown {remaining:.1f}s")
                    elif edges >= RF_BURST_MIN_EDGES:
                        # Big enough to be a candidate but failed shape — log for debug
                        print(f"  RF burst REJECTED (edges={edges}, dur={duration_ms}ms) — outside Avantek envelope")
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
    # Start the continuous ambient animation at boot so the LEDs are always alive,
    # not just after the first ring. A ring preempts it instantly, then it resumes.
    threading.Thread(target=ambient_loop, daemon=True).start()

    if "--test" in sys.argv:
        run_test_mode()
    elif TRIGGER_MODE == "rf":
        run_rf_loop()
    else:
        run_gpio_loop()


if __name__ == "__main__":
    main()
