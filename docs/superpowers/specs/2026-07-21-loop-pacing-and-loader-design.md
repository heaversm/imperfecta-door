# Loop Pacing + Loader/Quotes — Design

**Date:** 2026-07-21
**Status:** Approved
**Branch:** `melt-gallery-mode`

## Problem

On the Pi the ring feels slow: the USB burst grab alone is ~12.7s (30 frames @ 1280×720
via ffmpeg, ~0.42s/frame — abnormally slow) before any effect renders, then ~28s of
streamed rendering. During that window the loop has little to show and repeats the few
ready effects. Two fronts: make it faster (root cause) and mask the remaining wait.

## Changes

### A. Faster capture (`effects_server.py`)
- `BURST_COUNT` default **30 → 12**. Clips sample 8 frames; slitscan takes the rest and
  degrades gracefully. Still env-overridable.
- `_usb_grab`: add an input framerate request (`-framerate 30` before `-i`) to the ffmpeg
  v4l2 command so it captures at the C920's real rate instead of dawdling.
- Expected: burst grab ~12.7s → ~2–3s. (MaixCam path unchanged; we're on USB/C920.)

### B. Cheap effects first (`palette.py`)
- Reorder `STILL_PALETTE` cheapest-first (measured on the Pi): mondrian ~89ms,
  slice-stretch ~100ms, warhol ~166ms, dither ~187ms, then slice-displacement, water,
  slitscan, liquify, then the heavy interlaces (strip ~2.2s, diagonal ~1.6s), **hockney
  last (~2.7s)**. A real effect appears within ~½s of the burst finishing.
- Clips (`ANIM_PALETTE`) still render after the stills stream (unchanged), so a couple of
  quick stills show before the motion clips arrive.

### C. Loader + interleaved quotes (`static/viewer.html`)
- Keep the instant **first photo** shown on the `first` SSE event (unchanged).
- **Interleave Oblique Strategy cards throughout the loop**, not just at `playlist-end`:
  after every `QUOTE_EVERY` (=3) effect items, show one card, then continue. A card is
  inserted *between* effects (it does not consume/skip an effect).
- **Gap-filler:** this same counter naturally breaks up repetition while the playlist is
  still small (only 1–2 effects arrived), so the same image isn't shown back-to-back.
- Remove the forced single card at `playlist-end` (the interleaving supersedes it) so we
  don't double up on cards.
- Effects that haven't rendered yet are already skipped — the loop only plays items that
  arrived via `append`; the card interleaving fills the gaps.

## Out of scope (next thread — the "motion" observation)
- Converting more effects to clips; animating the mosaic's block positions over time
  (use the per-frame index `j` to shift the grid). Effect-quality work, tracked separately.

## Verification
- Deploy to the Pi; trigger a ring; read `effects_server` logs to confirm burst grab
  dropped to ~2–3s and a cheap effect is first. Watch the display: quotes interleave, no
  long dead wait, no back-to-back repeats. Screenshot via grim.
