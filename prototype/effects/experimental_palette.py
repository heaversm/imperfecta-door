"""Experimental effect roster — Mac preview rig ONLY.

palette.py (production, deployed to the Pi) does NOT import this, so these effects
never enter the gallery loop. Add a thin wrapper + one EXPERIMENTAL_PALETTE entry per
effect as it is built. Promote by moving the function into effects.py and adding a
STILL_PALETTE entry in palette.py.
"""
import effects_experimental as fx  # noqa: F401  (used by wrappers added per effect)


def _thermal(frames): return fx.thermal_map(frames)[0]
def _mirror(frames): return fx.mirror_smear(frames)[0]
def _stripint(frames): return fx.strip_interlace(frames)[0]
def _diagint(frames): return fx.diagonal_interlace(frames)[0]
def _blockmos(frames): return fx.block_mosaic(frames)[0]
def _slicestr(frames): return fx.slice_stretch(frames)[0]

EXPERIMENTAL_PALETTE = [
    ("thermal map", _thermal),
    ("mirror smear", _mirror),
    ("strip interlace", _stripint),
    ("diagonal interlace", _diagint),
    ("block mosaic", _blockmos),
    ("slice stretch", _slicestr),
]
