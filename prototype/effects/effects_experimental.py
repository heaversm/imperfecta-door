"""Experimental effects staging module — Mac preview rig ONLY.

ISOLATED from production: functions here are NOT in palette.py's STILL_PALETTE, and this
file is NOT copied by deploy.sh, so nothing here reaches the Pi gallery loop. The Mac
preview rig renders them via experimental_palette.py.

Workflow: write a new effect here (same contract as effects.py — @_timed pure function,
frames -> one same-size RGB Image, seed where random), register it in
experimental_palette.py, iterate in the preview rig. To PROMOTE an approved effect, move
its function into effects.py and add one STILL_PALETTE line in palette.py.

Reusable helpers now live in effects.py: _timed, _middle_frame, _bw_treatment,
_gradient_map, _scaled_shifted, _numpy_remap, _duotone, _halftone_dots.

The 2026-07-18 reference batch (thermal_map, mirror_smear, strip_interlace,
diagonal_interlace, block_mosaic, slice_stretch) has been promoted to effects.py.
This module is intentionally empty until the next experiment.
"""
from __future__ import annotations

import random  # noqa: F401  (available for new experiments)

import numpy as np  # noqa: F401
from PIL import Image, ImageOps  # noqa: F401

from effects import (  # noqa: F401  (import helpers here when staging a new effect)
    _timed,
    _middle_frame,
    _bw_treatment,
    _gradient_map,
    _scaled_shifted,
)
