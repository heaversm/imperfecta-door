# On-Screen Experience v2 — Fullscreen Slideshow + New Effects

**Date:** 2026-06-23
**Status:** Design approved, pending spec + plan review

## Context

Today the doorbell triggers a single render: `effects_server.py` runs all 9 effects
from the MaixCam burst, composites them into a 3×3 **grid**, saves one `latest.jpg`,
and the viewer crossfades to it. On the 1024×600 gallery display the grid shrinks each
effect to ~1/3 size, wasting detail. The effect set also leans heavily on one visual
family (slit-scan / smear) and is half vibrant color pop-art, which clashes with the
gritty B&W distorted-portrait aesthetic the artist is going for.

This redesign replaces the grid with a **fullscreen slideshow that loops until the next
ring**, trims redundant effects, adds new B&W distortion effects plus a low-frame-rate
"flipbook" of the live burst, and renders at display resolution via a streaming pipeline
so the first image appears quickly on the slow Pi 3B+.

### Goals
- One effect on screen at a time, fullscreen, crossfading — not a grid.
- Loop continuously until the next doorbell ring (screen never goes black/idle).
- More visual variety; a cohesive B&W distortion family alongside color punctuation.
- Add: vertical slice-displacement, water refraction, and an animated burst flipbook.
- Stay feasible on the Pi 3B+ — validated by measurement before full build.

### Non-goals
- No change to the doorbell/orchestrator trigger path or WLED.
- No new hardware. No cloud/Replicate.
- Not changing the cold-boot kiosk hardening (already shipped).

## Aesthetic direction

**Mix.** Keep the color pop-art effects (warhol, lichtenstein, mondrian) as occasional
punctuation; add a cohesive **B&W distortion family** (high-contrast grayscale + film
grain) for the gritty reference look. New/converted distortion effects share one B&W
treatment helper so they read as a family.

## Effect roster (10)

| Group | Effect | Status |
|---|---|---|
| Color | warhol | keep (color) |
| Color | lichtenstein | keep (color) |
| Color | mondrian | keep (color) |
| B&W distortion | slitscan_vertical | keep, convert to B&W treatment |
| B&W distortion | echo_max | keep, convert to B&W |
| B&W distortion | liquify | keep, convert to B&W |
| B&W distortion | hockney_joiner | keep (works either; B&W variant) |
| B&W distortion | **slice_displacement** | NEW |
| B&W distortion | **water_refraction** | NEW |
| Animated | **flipbook** | NEW (viewer-side playback, ~0 render) |

- **Dropped:** `slitscan_horizontal` (trim slit-scan 2→1), `time_grid` (too close to the
  grid look being retired). Code may remain in `effects.py` but is removed from the
  active playlist roster.

### New effect mechanics
- **slice_displacement** (`effects.py`): cut the frame into ~16 vertical bands; offset
  each band vertically (and slight horizontal) by a per-band amount (seeded noise or
  phase-shifted sine). Pure numpy array slicing + roll. B&W treatment applied. → fractured
  shuffled-strips look (the "Dia 6" reference).
- **water_refraction** (`effects.py`): build a ripple displacement field (sum of sines +
  optional radial component) and warp through the existing `_numpy_remap`. Same cost class
  as `liquify`. B&W treatment applied. → underwater refraction.
- **flipbook** (viewer-side): NOT a rendered still. The viewer plays the already-fetched
  burst frames at ~4 fps, ping-pong, for ~5s, then crossfades to the next effect. Server
  exposes the burst frames as static URLs; no extra render compute.
- **B&W treatment helper** (`effects.py`): grayscale → contrast stretch (autocontrast/levels)
  → additive film grain. Applied to the distortion family only; color effects untouched.

## Architecture: streaming playlist

Trigger path unchanged: orchestrator → `POST /trigger` on `effects_server.py`.

**Server (`effects_server.py`):**
1. Fetch the burst once (~1024×576). Downscale per-effect to the render work size as needed.
2. Save the raw burst frames to `static/` (e.g. `frame_000.jpg`…) so the viewer can play
   the flipbook.
3. Push SSE **`playlist-start`** (signals a fresh capture; includes the flipbook frame URLs).
4. Render effects **one at a time** (streaming). After each, save `latest_<i>.jpg` and push
   SSE **`append`** `{index, url, kind: "still"|"clip"}`. An effect that throws is skipped
   (logged), not fatal.
5. `/trigger` returns once rendering is kicked off (or after the first image) so the
   orchestrator isn't blocked for the full render.

**Viewer (`static/viewer.html`):**
- Holds a `playlist` array of items (`still` = image URL; `clip` = flipbook frame list).
- On `playlist-start`: begin building a NEW playlist, but keep crossfading the CURRENT one
  until the new playlist has ≥1 (ideally ≥2) items — **no black gap**, no flash of partial.
- On `append`: add the item; when the new playlist is "ready," switch to it.
- Crossfade through the active playlist (~4s/item), loop indefinitely.
- `clip` (flipbook) item: animate its frames at ~4 fps ping-pong for ~5s, then advance.
- Keeps the existing self-heal (reload on SSE close / 20s no-connect).

**Between rings:** the viewer just loops the last playlist. Server idle. Zero render CPU.

## Performance plan (feasibility)

Measured this session (≈640px render): mondrian ~4ms, warhol ~36ms, time_grid ~88ms,
echo ~107ms, liquify ~123ms, lichtenstein ~123ms, slitscan ~150ms, **hockney ~410ms**.
New effects land in this range; flipbook ≈ 0 render. Burst fetch+decode: 640×360 ≈ ~2s,
1280×720 ≈ ~6s.

**Decisions:**
- **Capture ~1024×576** on the MaixCam (`CAPTURE_WIDTH/HEIGHT`) — sharp enough fullscreen,
  burst ~3.5-4s (vs ~6s at 720p).
- **Render at display res (~1024)** per effect, **streamed** — first image ≈ burst + one
  effect (~4-5s), landing as the 5s WLED ring finishes; rest fill in during the loop.
- **Loop amortizes cost** — render happens once per ring (minutes apart); sustained CPU ≈ 0.

**Spike gate (build step 1):** before building all effects, measure per-effect render at
1024px + burst time on the actual Pi. If the streaming timeline doesn't hold (first image
> ~6s, or total render starves the loop), adjust capture res / work res / roster before
proceeding. Do not build the full roster on estimates.

## Build order

1. **Measurement spike** — on the Pi: capture at 1024×576, render the existing effects at
   1024px, log per-effect ms + burst fetch/decode. Confirm the streaming timeline. Gate.
2. **Effects** — add `slice_displacement`, `water_refraction`, B&W treatment helper to
   `effects.py`; preview on the Mac rig (`effects/preview_rig.py`).
3. **Server** — `effects_server.py`: streaming render loop + SSE `playlist-start`/`append`;
   save burst frames as static files for the flipbook.
4. **Viewer** — `static/viewer.html`: playlist state machine, crossfade loop, flipbook
   playback; preserve self-heal.
5. **Deploy + tune** — push to Pi (`deploy.sh` + MaixCam capture-res change via the jump-host
   deploy), tune slide cadence and crossfade on the real display.

## Error handling
- Burst fetch fails → keep showing the current loop; do not blank or error the screen.
- An effect render throws → skip that item, continue the playlist (log it).
- SSE connection drops → existing viewer self-heal (reload on close / 20s no-connect).
- Cold-boot kiosk behavior (loading page → viewer) is unchanged and must still pass.

## Storage & cleanup

**Bounded by design — nothing accumulates.** Per-ring outputs reuse fixed names:
`latest_0.jpg`…`latest_<N-1>.jpg` overwrite each ring, and the flipbook frames dir is
wiped before each new capture. The total on-disk footprint is constant (~9 stills + ~15
frames ≈ a few MB), regardless of how many times the doorbell is pressed.

**Render outputs live in RAM, not on the SD card.** Writing ~24 JPEGs per ring to the SD
card all day for weeks is real write-wear (the first card already died). So the ephemeral
render outputs (`latest_*.jpg`, flipbook `frames/`) are written to a **tmpfs at
`/dev/shm/imperfecta/`** (RAM-backed, present by default on Pi OS) and Flask serves them
from there. They never need to persist — they're regenerated on the next ring. This also
makes the go-live read-only overlay filesystem seamless: these writes are already in RAM,
so nothing conflicts with a read-only root.

**Legacy cleanup (one-time):** the retired `bg_removal_server.py` pipeline accumulated
face captures under `~/static/`. With the effects pipeline these are obsolete; delete any
leftover legacy capture files once (see plan Task 6). RUNBOOK §3 ("clearing the gallery")
no longer applies.

## Verification
- Spike: per-effect render ms + burst time logged on the Pi; streaming timeline confirmed.
- Visual: on the gallery display, ring → fullscreen effects crossfade and loop; flipbook
  plays the burst back as motion; B&W family reads cohesively next to color punctuation.
- Timing: first image appears around when the WLED ring (5s) ends; loop runs smoothly with
  ~0 sustained CPU (`top`/`vcgencmd get_throttled` = 0x0).
- Regression: cold-boot still comes straight up into the experience (no desktop, no blank).

## Files touched
- `prototype/effects/effects.py` — new effects + B&W helper; roster trim.
- `prototype/effects_server.py` — streaming render, SSE playlist events, serve burst frames.
- `prototype/static/viewer.html` — playlist loop + flipbook.
- `maixcam/face_capture/face_capture_multi_server.py` — `CAPTURE_WIDTH/HEIGHT` → 1024×576
  (deploy via Pi jump host; reboot MaixCam).
- `prototype/effects/preview_rig.py` — exercise new effects on the Mac (no Pi needed).
