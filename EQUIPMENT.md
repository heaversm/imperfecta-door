# Imperfecta — Equipment Inventory

Canonical hardware list. **Update this when anything changes.** Don't make me re-ask.

Last updated: 2026-06-05

---

## Compute

| Item | Spec | Notes |
|---|---|---|
| **Raspberry Pi 3B+** | Full-size HDMI, **micro-USB power** (NOT USB-C), lower perf than Pi 4/5 | Runs orchestrator + effects server + kiosk viewer. The fixed compute for the install. |
| **MaixCam (Sipeed)** | **6" × 4" footprint** (measured, incl. case/mount), GC4653 sensor up to 2560×1440 (4MP) | Face capture. Standalone WiFi device — Pi talks to it over HTTP, no data cable between them; needs its own USB-C power. ⚠ Capture currently bound to YOLO detector input res (~320–640px) in `face_capture_multi_server.py:76` — real image-quality bottleneck, not the display. |
| **Mac** | dev machine | deploy.sh source; not part of the install. |

## Power Supplies

| Item | Spec | Status |
|---|---|---|
| **Pi PSU (current)** | CanaKit **5V / 2.5A** micro-USB | ⚠ UNDERPOWERED — browns out when Waveshare draws power through Pi USB. Replace. |
| **Pi PSU (to order)** | **5V / 3.5A micro-USB** (CanaKit recommended, ~$10) | Voltage held at 5.1–5.25V to offset cable drop — fixes the undervoltage. One wall plug powers Pi + display + touch. |
| **LED PSU** | **12V**, ≥10A (120W) min, **12.5A (150W) recommended** | For WS2815 strip (see below). Verify what's currently installed — may have been damaged in the LED "pop" event 2026-06-05. |

## Display

| Item | Spec | Notes |
|---|---|---|
| **Waveshare 7" HDMI capacitive touch** | **1024×600**, ~170 PPI | Owned. Single port does BOTH 5V power + USB touch → micro-USB-to-USB-A to the Pi (loads Pi USB → brownouts on weak PSU). |
| **Official Pi Touch Display 2** | **720×1280** (1280×720 landscape), ~215 PPI, ~$60 | ✅ COMPATIBLE with Pi 3B+ (DSI ribbon + GPIO power; auto-detected). Sharper than Waveshare. Cleaner wiring: no HDMI cable, no USB-touch cable — DSI data + GPIO power only. Still needs the 3A PSU since GPIO draw routes through Pi micro-USB. |
| ~~Original Pi 7" Touchscreen~~ | 800×480, DSI | ❌ Lower res than the Waveshare. No reason to use. |

## LEDs

| Item | Spec | Notes |
|---|---|---|
| **LED strip** | **WS2815, 12V, 5m, 60 LED/m = 300 LEDs** | Amazon B07LG6J39V. WS2815 is 12V addressable (has backup data line). |
| **WLED controller** | **QuinLED Dig-Quad v3** | mDNS: `wled-dig-quad-v3.local`. Drives up to 4 channels. |

### LED power math (WS2815, 300 LEDs)
- Full white worst case: ~0.3W/LED → **~90W → ~7.5A at 12V**
- **12V / 12.5A (150W)** = full headroom, never sags.
- **12V / 10A (120W)** = minimum; enable WLED's power/current limiting to cap draw.
- Almost never run at full white in practice, but spec for the worst case to be safe.

## Networking / Other

| Item | Notes |
|---|---|
| WLED, mDNS hostnames | See memory: device IPs per venue (home vs gallery). |
| Doorbell trigger | Avantek 433MHz RF burst detection (see orchestrator.py TRIGGER_MODE="rf"). |

---

## Open hardware tasks
- [ ] Order Pi 5V/3.5A micro-USB PSU
- [ ] Verify/replace 12V LED PSU (≥10A) — check for damage after the pop
- [ ] Diagnose LED "pop" event (2026-06-05) — likely jarred cable shorted a rail on the Dig-Quad
- [ ] Enclosure for display (ABS project box) — pending glass-panel measurements
- [ ] Suction-cup mount + paintable cable raceway
