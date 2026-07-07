# Melt Gallery Mode — Design Spec

**Date:** 2026-07-07
**Status:** Approved (brainstorming) — ready for implementation planning
**Owner:** Mike Heavers

## Summary

Add a friend's "melt + cutout-mosaic" experience to the Imperfecta doorbell gallery as an
**additive, feature-flagged mode** that runs alongside the current `viewer.html` effects loop.
On a doorbell ring, a live camera preview freezes and dissolves into ~99k particles that slurp
upward, while an accumulating collage of background-removed head cutouts grows underneath.

The friend's code already lives in the repo at `facecapture/` (commit 699f5d6). The core of
this work is **reusing his standalone, offline-capable app** and **adding a doorbell trigger +
an install-mode flag** — without removing or modifying any current functionality. The kiosk
default flips to the new mode only after it is validated on the Pi.

## Goals

- Bring the whole melt web-app experience in as a selectable display mode.
- **Preserve all current functionality** (the `viewer.html` effects slideshow + `effects_server.py`
  + MaixCam pipeline) untouched and usable as a fallback until the new mode is tested.
- Keep the installation **fully offline** (no internet dependency at the venue).
- Reuse the friend's code as-is where possible; additions must be purely additive so his
  standalone "tablet demo" still works with the flag off.

## Non-Goals

- Retiring the MaixCam or the effects pipeline (deferred until melt mode is validated as primary).
- Porting the melt into `effects_server.py` / `viewer.html` (rejected — his standalone server
  already does everything offline; porting would be redundant work).
- Running the friend's Cloudflare/R2 backend (rejected — the install is offline; standalone mode
  covers it).

## Existing Building Blocks (verified)

- `facecapture/container/public/index.html` — the melt UI. Pure **WebGL vertex-shader** dissolve,
  ~99k `GL_POINTS`, all motion computed in the vertex shader (CPU idle per frame; author comment:
  *"smooth even on a Raspberry Pi"*). One-shot ~4.7s. Samples a 720px snapshot canvas.
- `facecapture/container/server.mjs` — Hono server with two modes. **Standalone mode** (env
  `STORAGE_DIR` set) owns everything locally: `POST /api/capture`, `GET /api/heads`,
  `WebSocket /ws` (full-feed broadcast), `GET /files/...`, and a disk `manifest.json`. No
  Cloudflare/R2/internet.
- `facecapture/container/removal.mjs` — background removal via `@imgly/background-removal-node`
  (local ONNX model, **fully offline**).
- `prototype/effects_server.py` + `prototype/static/viewer.html` — the current effects loop
  (crossfaded stills/flipbooks + Oblique Strategies cards), driven by SSE `/events`.
- `prototype/orchestrator.py` — RF doorbell (Avantek 433MHz burst) handler; on trigger it POSTs
  `/trigger` to the effects server today.
- `prototype/static/shader_test.html` at `/shader` — a WebGL prototype whose stated purpose is to
  gauge GPU perf on the Pi 3B+. Proves WebGL runs on this hardware (native VC4/Mesa; the kiosk
  Chromium launch has no `--disable-gpu`).
- `prototype/kiosk_autostart.sh` — launches fullscreen Chromium (labwc/Wayland) at a loading page
  that navigates to the live viewer; `/goto` (SSE) can flip connected pages to any URL.

## Camera Hardware (resolved)

**Logitech C920** (purchased 2026-07-07, arriving in a few days).

- The Pi kiosk has **no browser-accessible webcam**; the melt uses `getUserMedia`, which requires
  a local **UVC** device. The MaixCam is a networked HTTP-JPEG device and structurally cannot be
  a `getUserMedia` source; a GoPro-as-webcam needs `ffmpeg` + `v4l2loopback` transcoding (rejected
  — fragile, CPU-heavy on a Pi 3B+).
- **720p** is all the app uses (pipeline caps at 720px; the panel is 1024×600), so a 1080p sensor
  is not optimized for — resolution was not the deciding factor.
- The C920 has a **1/4"-20 tripod thread**, so it mounts via a compact 1/4"→GoPro adapter into an
  **existing GoPro base** (adhesive or screw to the box; finger-joint provides tilt/pan). No
  separate stand.
- The **MaixCam stays** wired to the current effects mode as the tested fallback.

## Architecture

### What runs where

- The friend's **standalone server** (`server.mjs` with `STORAGE_DIR` set) runs on the **Pi**
  (Node), fed by the **C920** via `getUserMedia`, with local disk storage and offline bg-removal.
- **Kiosk mode switch:** which page the Pi's Chromium shows — the existing `viewer.html` effects
  loop **or** the melt app — is chosen by a config default and can be flipped live with the
  existing `/goto` mechanism. `viewer.html` and `effects_server.py` are never modified.

### Additions (purely additive)

1. **Doorbell trigger into the melt app.** Add `POST /api/ring` to `server.mjs` (standalone mode).
   It broadcasts `{type:'ring'}` over the **existing `/ws`**. The page's WebSocket handler, on a
   `ring` message, calls the existing `capture()` function. The "Ring Doorbell" button remains as
   a manual test trigger. `orchestrator.py`'s RF handler POSTs `/api/ring` on a doorbell burst
   (in addition to, or instead of, its current `/trigger` POST depending on active mode).

2. **Install-mode flag** (e.g. env `IMPERFECTA_INSTALL=1`):
   - **off** (default): the friend's tablet demo exactly as-is (button-triggered capture, webcam).
   - **on**: enables the doorbell path (`/api/ring` → `/ws` → `capture()`) and any kiosk niceties
     (e.g. hide/keep the button, autoplay/permission handling for a headless kiosk).

### End-to-end trigger flow (melt mode)

```
RF doorbell burst
  → orchestrator.py (RF handler)
  → POST /api/ring   (facecapture standalone server)
  → WebSocket /ws broadcast {type:'ring'}
  → page: capture()  (freeze frame + white flash + fx.start() melt)
  → POST /api/capture {image}
  → @imgly offline background removal → sharp trim → store cutout PNG on disk
  → /ws feed broadcast (full head list)
  → collage grows (pop-in of the newest cutout)
```

## Data Contract (existing, reused)

- `POST /api/capture` body `{ image: <dataURL> }` → returns a head entry
  `{ id, original, cutout, originalUrl, cutoutUrl, createdAt }`.
- `GET /api/heads` → array of head entries (newest first).
- `WebSocket /ws` → server pushes `{ type: 'feed', heads: [...] }` on connect and after each
  capture. **New:** server also pushes `{ type: 'ring' }` when `/api/ring` is hit.

## Validation

Open validation item (belongs in the implementation plan, not a blocker):

- **Measure the melt's real FPS on the Pi 3B+** once the C920 arrives. Low risk — all motion is in
  the vertex shader and the one-time cost is a ~2.4 MB buffer upload per ring — but measure rather
  than assume. If FPS is unacceptable, reduce the `GRID` particle count (currently 420 across).

## Staging Plan

1. Run the friend's standalone server on the **Mac** against the C920 to confirm baseline behavior.
2. Add `POST /api/ring` + the `{type:'ring'}` `/ws` broadcast + the page's `ring` handler, gated by
   the install-mode flag. Verify his demo is unchanged with the flag off.
3. Deploy to the **Pi**; wire `orchestrator.py`'s RF handler to POST `/api/ring`; measure melt FPS.
4. Flip the kiosk default to melt mode **only after** it passes on the Pi. The effects mode +
   MaixCam remain available as the fallback throughout.

## Risks / Open Questions

- **Pi GPU perf** of the melt — mitigated by the vertex-shader design and a `GRID` knob; validated
  in stage 3.
- **Node + ONNX bg-removal latency** on the Pi 3B+ — the melt (~4.7s) covers the wait; if removal
  is much slower than the melt, the collage update lags but the experience still reads correctly.
  Measure in stage 3.
- **Kiosk `getUserMedia` permission** — Chromium in kiosk mode may need a flag/policy to
  auto-grant camera access without a prompt; handled by the install-mode kiosk niceties.
- **Coexistence of two triggers** — while both modes exist, `orchestrator.py` must route the RF
  trigger to the active mode's endpoint (`/trigger` for effects, `/api/ring` for melt). The mode
  selection mechanism is finalized in the plan.
