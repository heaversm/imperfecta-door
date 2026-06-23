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
def _hock(frames):   return _bw(effects.hockney_joiner(frames, rows=3, cols=3, rotation_max_deg=12, jitter_frac=0.12, border_px=10, pad_frac=0.04, bleed_frac=0.38)[0])
def _water(frames):  return effects.water_refraction(frames)[0]        # B&W internally
def _warhol(frames): return effects.warhol(frames)[0]                  # color
def _slice(frames):  return effects.slice_displacement(frames)[0]      # still (random bands per render)

STILL_PALETTE = [
    ("warhol",              _warhol),   # cheap → first image fast
    ("slice displacement",  _slice),
    ("water refraction",    _water),
    ("slitscan horizontal", _slit_h),
    ("liquify",             _liq),
    ("hockney",             _hock),      # ~3s outlier → rendered LAST
]

ANIM_FRAMES = 6   # frames per living-effect clip

def _a_dither(fr, seed): return effects.dither(fr)[0]
def _a_mond(fr, seed):   return effects.mondrian(fr, seed=seed)[0]

ANIM_PALETTE = [
    ("dither (live)",   _a_dither),
    ("mondrian (live)", _a_mond),
]
FLIPBOOK_KIND = "flipbook"   # raw burst clip, inserted at the front of the playlist
