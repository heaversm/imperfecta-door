# Reference Effects Batch — Design

**Date:** 2026-07-18
**Status:** Approved for planning
**Branch:** `melt-gallery-mode` (or a fresh branch off it)

## Goal

Raise the visual quality of the Imperfecta gallery experience by recreating six new
effects derived from a folder of annotated fashion-editorial references
(`~/Desktop/imperfecta/references`). All six must:

- Run within the existing hardware envelope (Pi 3B+, ~1 GB RAM, 1024px work size,
  pure numpy — no cv2 in effect functions).
- Fit the existing effect contract (`frames: list[Image.Image] → Image.Image`,
  `@_timed`).
- Be previewable first on the Mac via `prototype/effects/preview_rig.py` before any
  Pi deploy, so the look can be judged from a live webcam capture.
- **Stay fully isolated from the production gallery loop** while experimental — see
  Isolation below — so any effect we don't like can be tossed with zero impact on
  what plays on the Pi.
- Only be interspersed into the production loop *after* per-effect approval, via a
  deliberate promotion step.

Animation is a **Phase 2** concern (see below): this pass delivers polished stills.

## The six effects

Chosen for maximum diversity from the current roster (which is heavy on B&W
distortion — slitscan, liquify, water_refraction, slice_displacement — plus
warhol/mondrian/dither/hockney). Two Tier-1 candidates were dropped for overlapping
existing effects: *offset/scaled/flipped slices* (5.31 ≈ `slice_displacement`) and
*stretch-and-cap smear* (5.36 ≈ `slitscan`).

Each is a new pure function in the isolated experimental module (see Isolation) plus
one entry in the experimental roster. Randomness takes a `seed` parameter (per the
contributor guide).

### 1. Thermal / spectrum gradient map (ref 5.26)

The one bold-color hero. Map the source luminance through a multi-stop color LUT
(deep teal → red → orange → yellow → green) so the face reads as a heat/spectrum
image. This is a direct generalization of the existing `_duotone` helper from two
stops to N stops.

- **Algorithm:** grayscale the middle frame → build an (N,3) gradient LUT →
  interpolate per-pixel by luminance → optionally bias the gradient's spatial center
  toward one side so the "hot" band sweeps diagonally (as in the reference).
- **New helper:** `_gradient_map(gray, stops)` — generalizes `_duotone`; keep
  `_duotone` as the 2-stop special case.
- **Cost:** trivial (one LUT lookup, vectorized). Well under 100ms at 1024px.
- **Color/B&W:** color.

### 2. Mirror-flip + edge-pixel smear (ref 5.30)

Surreal mirrored-world composition: the top half is the image; the bottom half is a
vertically flipped copy, and the seam edge-row is smeared (broadcast) to blend the
two, giving the "edge pixels stretched vertically" band in the reference.

- **Algorithm:** take the middle frame; composite `[image ; flip(image)]` (or a
  chosen split fraction). At the seam, broadcast the boundary row across a band of M
  pixels (`np.repeat` of one row) so the join reads as a stretched smear rather than
  a hard mirror line.
- **Cost:** trivial (slicing + flip + broadcast).
- **Color/B&W:** B&W family (`_bw_treatment`) to match the reference's editorial tone.

### 3. B&W ⁄ color vertical strip interlace (ref 5.33)

Interlace vertical strips alternating between a B&W treatment and the original color
capture — puts the currently-unused color burst frames to work.

- **Algorithm:** pick two frames from the burst (e.g. first and middle) for temporal
  variety. Slice into K vertical strips; even strips = `_bw_treatment(frameA)`, odd
  strips = color `frameB`, optionally scaled/offset slightly so the color strips read
  as a distinct layer. Assemble side by side.
- **Cost:** trivial (column slicing + paste).
- **Color/B&W:** mixed (that's the point).

### 4. Diagonal bisect + offset B&W/color interlace (ref 5.37)

Diagonal geometry to contrast the roster's vertical-strip effects. Split the frame
along a diagonal; one triangle is B&W, the other is color, and the two are offset
horizontally so they interlace at the seam.

- **Algorithm:** build a diagonal boolean mask (`ys * a + xs * b > c`). Composite
  `_bw_treatment(frame)` where mask, color `np.roll(frame, dx, axis=1)` where not.
  A second, shallower diagonal band can add the "interlaced" secondary seam seen in
  the reference.
- **Cost:** trivial (mask + roll + where).
- **Color/B&W:** mixed.

### 5. Regional mosaic + banded pixel blocks (ref 5.34)

Blocky mosaic pixelation of a region — genuinely new since `dither` is fine stipple,
not coarse blocks. A rectangular region (e.g. upper-left over the face) is pooled into
large square blocks; a stepped "staircase" of blocks bleeds out of the region, and a
banded vertical gradient fills alongside.

- **Algorithm:** block-mean pooling via reshape (`arr.reshape(h//b, b, w//b, b, 3).mean((1,3))`)
  then nearest-neighbor upscale over the target region. Draw a stepped block staircase
  along the region boundary. Add a few solid/gradient vertical bands beside it.
- **Cost:** low-medium (pooling is vectorized; staircase is a small loop over blocks).
- **Color/B&W:** the mosaic keeps source color; bands can be a chosen accent (matching
  the reference's pink), configurable.

### 6. Vertical slice → stretch + gradient (ref 5.25)

The one "smear" representative: take a vertical slice of the image, stretch it
horizontally across a region in place, and lay a gradient over it — the classic
datamosh horizontal-smear look.

- **Algorithm:** select a source column band; `np.repeat`/resize it horizontally to
  fill a target region so its pixels streak sideways; blend a linear alpha gradient
  (transparent → opaque) over the streaked region so it fades into the untouched image.
- **Cost:** trivial (column broadcast + gradient blend).
- **Color/B&W:** keep source color with a subtle gradient tint; can join B&W family if
  it reads better in preview.

## Isolation (keep production untouched)

The production gallery server (`effects_server.py`, runs on the Pi) and the Mac
preview rig **both** import the roster from `prototype/palette.py` today, so anything
added to `STILL_PALETTE` ships to the gallery immediately. To keep experimental work
out of the production experience until we choose to promote it:

1. **New effect functions live in a dedicated module:**
   `prototype/effects/effects_experimental.py`. Tossing an effect = delete its
   function (or its one roster line). `effects.py` (the production library) is only
   touched by the single shared helper below.
2. **A separate experimental roster:** `EXPERIMENTAL_PALETTE` in
   `prototype/palette.py` (a new list, alongside `STILL_PALETTE`). The **preview rig
   imports and renders it**; `effects_server.py` does **not** import it. Production
   `STILL_PALETTE` is left exactly as-is.
3. **Promotion is deliberate and per-effect:** once an effect is approved, move its
   function into `effects.py` and add one line to `STILL_PALETTE`. Nothing reaches the
   gallery loop before that step.

The one exception that touches production code: the shared helper `_gradient_map`
(generalizes `_duotone`) is added to `effects.py` since it's a pure, reusable
primitive — it changes no existing behavior and adds nothing to the production roster.

## Architecture

**No structural change to the pipeline.** Each effect follows the established pattern:
`@_timed` pure function, `seed` param where randomness is used, returns one same-size
RGB `Image`; tied in through one roster entry (in `EXPERIMENTAL_PALETTE` while
experimental).

**Preview data flow:** the preview rig renders `STILL_PALETTE + EXPERIMENTAL_PALETTE`
so the new effects appear in the grid next to the current ones (a small one-line
addition to `preview_rig.run_all_effects`, a dev-only tool — not production).

**Production data flow (unchanged, and untouched this pass):** doorbell → burst →
`effects_server.py` stream-renders each `STILL_PALETTE` entry → SSE `append` → viewer
loops with crossfade/Ken Burns.

**Ordering (at promotion time):** insert promoted effects into `STILL_PALETTE`
interspersed with existing ones (not clustered), cheapest-first so the first on-screen
image stays fast. The ~3s `hockney` stays last.

## Error handling

Inherits the existing model: `effects_server.py` wraps each effect render in
try/except and **skips a failing effect** (logs, non-fatal) rather than aborting the
ring. Each new function must degrade gracefully on edge inputs (single-frame burst,
odd dimensions) — validated by `prototype/effects/validate_effect.py` before tie-in.

## Testing / preview

Primary loop is the **Mac preview rig**:

```bash
cd prototype/effects
python preview_rig.py   # open http://localhost:8000, hit CAPTURE
```

Each effect is developed and iterated here against live webcam bursts, viewed in the
grid with per-effect timings (so we catch anything too slow for the Pi early). Run
`validate_effect.py` on each new function for the contract checks (size, mode, purity,
seed-reproducibility). No Pi deploy until the look is approved from the preview rig.

## Phase 2 — animation (out of scope for this pass, noted for continuity)

After the stills are approved, add motion **in the viewer via CSS transforms** on the
rendered still — zero extra Pi compute, reusing the existing Ken Burns / vertical-sweep
machinery:

- Thermal gradient map → slow hue/position drift of the gradient overlay.
- Vertical slice stretch → the streak region sweeps horizontally.
- Regional mosaic → block-by-block reveal.
- (Ring rotation / puzzle-tile slides from Tier 2 are the natural next candidates if we
  extend beyond the six.)

The genuinely animation-dependent reference — particle dissolve (5.27 / 5.35) — is
explicitly **deferred**; it wants WebGL/canvas and belongs with the melt-shader track,
not this numpy-stills batch.

## Out of scope

- Particle dissolve / "face disappearing" (5.27, 5.35) — WebGL track.
- The two dropped smear/slice variants (5.31, 5.36) — redundant with existing effects.
- Collage effects needing external background plates/textures beyond what the burst
  provides (the torn-paper 5.38 white-gap collage is Tier 2, not in this six).
- Any change to the capture pipeline, SSE protocol, or viewer loop structure.
