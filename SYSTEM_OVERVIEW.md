# Imperfecta — System Overview (for second opinion)

## What it is

An art installation at a museum entryway. When a visitor rings the doorbell, the installation:
1. Captures a photo of the visitor's face (MaixCam camera)
2. Removes the background, applies funhouse distortion
3. Adds the face to an ever-growing gallery displayed on a monitor in the entryway window
4. Triggers a light animation — a moving "hotspot" travels along LED strips in black diffusion tubing, mounted on the gallery's metal beams

Existing doorbell (Avantek D3-B, 433MHz wireless) must continue to work normally (chime still rings). Our trigger just needs to *also* fire when the button is pressed.

## Hardware in place

- **Raspberry Pi 4** (10.0.0.206, `imperfecta-pi`) — runs everything:
  - `orchestrator.py` — main event loop, listens for doorbell trigger, tells MaixCam to capture, sends frames for processing, drives WLED
  - `bg_removal_server.py` — Flask server on :5050, calls Replicate `cjwbw/rembg`, applies PIL/numpy funhouse distortion, serves gallery HTML
  - Both services auto-start via systemd
- **MaixCam** (10.0.0.14) — Wi-Fi camera, face detection on-device, sends frames to Pi on demand
- **WLED Dig-Quad** (10.0.0.220) — ESP32 LED controller, drives addressable strips, HTTP JSON API
- **LED strips** — WS2815 12V 60/m, in black silicone diffuser channels, mounted with neodymium magnets to metal beams. Will be 4 strands (2 pairs, daisy-chained with extensions).
- **12V Mean Well PSU** with fused distribution
- **Avantek D3-B wireless doorbell** — existing, 433MHz, proprietary protocol, plug-in chime unit elsewhere in the gallery

## Doorbell trigger — the open question

The doorbell trigger is the last unsolved piece. Context:

### What we tried

1. **FSR (force-sensitive resistor)** adhered to the button face — worked on bench but requires running wires from the exterior doorbell indoors to Pi GPIO. Not ideal: visible wiring, weatherproofing concerns, mechanical wear.

2. **433MHz RF interception** — bought an RX470C-V01 superheterodyne receiver + 32cm spiral antenna, wired to Pi GPIO17. Goal: decode the Avantek's 433MHz signal so no exterior hardware is needed.
   - Spent many hours writing custom gpiod edge-detection decoders (rf_decode.py, rf_gaps.py, rf_rawdump.py in `prototype/`)
   - Captured raw bursts: bimodal timing ~850µs / ~1800µs, 32 bits per repetition, ~6 repetitions per press
   - **Never got a consistent code across presses.** Avantek D3-B uses a proprietary encoding (possibly rolling-code or with sync/checksum bits we can't identify). No library supports it (`rpi_rf`, `rtl_433`, Tasmota/Sonoff RF Bridge all fail to decode or give inconsistent output).
   - Confirmed via research: Sonoff RF Bridge users report Avantek doorbells don't decode reliably on Tasmota.

3. **Sonoff RF Bridge + Tasmota** — considered, but evidence suggests it won't work with Avantek specifically (same underlying issue — proprietary protocol).

4. **rtl_433 + RTL-SDR dongle** — considered. Could probably decode the Avantek with enough reverse-engineering effort, but requires adding an SDR to the install and writing a custom decoder.

### Current plan (what we're about to do)

Bought a **$5 generic 433MHz EV1527 wireless button** from AliExpress. EV1527 is a well-known fixed-code protocol natively supported by the `rpi_rf` Python library. The plan:
- When the button arrives, run an isolated test script (`prototype/ev1527_test.py`) that uses `rpi_rf` to capture the button's code
- Confirm the code is consistent across 5+ presses
- Copy the code into `orchestrator.py`, replace the custom decode loop with `rpi_rf`'s high-level API
- Mount the new EV1527 button next to (or replacing) the existing Avantek doorbell button

This gives us:
- No exterior wiring (RF)
- Known-good protocol with library support
- Dead-simple code path

The Avantek's chime keeps working independently because we're not touching it. Visitors press the new button, which fires both the Avantek (if we stack them) and our Pi trigger.

### What we want a second opinion on

1. **Is abandoning the Avantek decode the right call?** We spent hours on it and got nowhere. Is there an approach we missed (specific Tasmota build, known Avantek reverse-engineering writeups, rtl_433 decoder that does work)?
2. **Is the EV1527 button pivot sound?** Any gotchas with `rpi_rf`, EV1527 range, interference with the Avantek also transmitting in the same band?
3. **Physical integration**: mounting a second button next to/over the existing doorbell — any cleaner options we haven't considered? We specifically do NOT want to open the existing doorbell or modify the chime unit.
4. **Are we over-indexing on "no exterior wires"?** The FSR worked. Is a thin wire run from a weatherproofed FSR enclosure back indoors actually fine, and we're over-engineering this?

## Project files on disk (for reference)

- `plan.md` — original build plan (pre-hardware, comprehensive but dated on doorbell section)
- `TODO.md` — live task list with current status
- `DOORBELL_OPTIONS.md` — earlier options comparison (pre-RF-failure)
- `prototype/orchestrator.py` — main Pi service
- `prototype/bg_removal_server.py` — Flask gallery server
- `prototype/ev1527_test.py` — new isolated test script, ready to run when button arrives
- `prototype/rf_*.py` — abandoned custom decoders
