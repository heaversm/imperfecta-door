"""The effect roster — the SINGLE place to tie in an effect.

Imported by both effects_server.py (gallery) and effects/preview_rig.py (dev), so adding an
entry here shows the effect in both the live loop and the preview rig. To contribute an
effect, write the pure function in effects.py, then add a wrapper + one palette entry here.
See effects/CONTRIBUTING-EFFECTS.md.

Two kinds of loop item:
 - STILL_PALETTE: one rendered image per ring (rendered first → fast first image; hockney is
   the ~3s outlier, so it renders LAST).
 - ANIM_PALETTE: cheap single-frame effects rendered across several burst frames so the
   subject MOVES ("living" effects). Each callable takes ([single_frame], seed); a stable
   per-clip seed keeps random structure fixed while only the subject moves.

The B&W distortion family shares _bw_treatment; warhol/mondrian stay color.
"""
import effects

_bw = effects._bw_treatment

def _slit_h(frames): return _bw(effects.slitscan_horizontal(frames)[0])
def _liq(frames):    return _bw(effects.liquify(frames[len(frames) // 2], wave_amp=30, wave_freq=4, bulge=0.5, twirl_deg=45)[0])
def _hock(frames):   return effects.hockney_joiner(frames, rows=3, cols=3, rotation_max_deg=12, jitter_frac=0.12, border_px=10, pad_frac=0.04, bleed_frac=0.38)[0]   # color
def _water(frames):  return effects.water_refraction(frames)[0]        # B&W internally
def _warhol(frames): return effects.warhol(frames)[0]                  # color
def _slice(frames):  return effects.slice_displacement(frames)[0]      # still (random bands per render)
def _mond(frames):   return effects.mondrian(frames)[0]                # color (still — gets Ken Burns)
def _dither(frames): return effects.dither(frames, fg=(255, 255, 255), bg=(0, 0, 0))[0]  # B/W stipple (still)

# Reference-batch STILLS (2026-07-18): interlace / smear family. These stay stills —
# strip & diagonal interlace are too heavy to render per-frame on the Pi; slice stretch
# reads fine as a still.
def _stripint(frames): return effects.strip_interlace(frames)[0]       # color|bw|thermal strips
def _diagint(frames):  return effects.diagonal_interlace(frames)[0]    # random diagonal shards
def _slicestr(frames): return effects.slice_stretch(frames)[0]         # color datamosh smear

# Reference-batch CLIPS (2026-07-18): cheap effects rendered on one burst frame at a time
# so the SUBJECT MOVES (6fps stop-motion in the viewer). Callable signature
# ([single_frame], seed, j) — j (frame index) is unused; the fixed per-clip seed keeps the
# effect's random structure stable so only the subject animates.
def _c_thermal(frames, seed, j=0): return effects.thermal_map(frames, seed=seed)[0]
def _c_mosaic(frames, seed, j=0):  return effects.block_mosaic(frames, seed=seed)[0]
def _c_mirror(frames, seed, j=0):  return effects.mirror_smear(frames, seed=seed)[0]

STILL_PALETTE = [
    ("warhol",              _warhol),   # cheap → first image fast
    ("slice displacement",  _slice),
    ("water refraction",    _water),
    ("slice stretch",       _slicestr),
    ("slitscan horizontal", _slit_h),
    ("liquify",             _liq),
    ("strip interlace",     _stripint),
    ("mondrian",            _mond),
    ("diagonal interlace",  _diagint),
    ("dither",              _dither),
    ("hockney",             _hock),      # ~3s outlier → rendered LAST
]

ANIM_FRAMES = 8   # frames per clip (played back as ~6fps stop-motion, ping-pong, in the viewer)

# Moving effects — rendered across ANIM_FRAMES burst frames and streamed as a clip.
ANIM_PALETTE = [
    ("thermal map",  _c_thermal),
    ("block mosaic", _c_mosaic),
    ("mirror smear", _c_mirror),
]
FLIPBOOK_KIND = "flipbook"   # raw burst clip, inserted at the front of the playlist
