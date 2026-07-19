"""Experimental effects derived from the reference images (2026-07-18 batch).

ISOLATED from production: these functions are NOT in palette.py's STILL_PALETTE, and
this file is NOT copied by deploy.sh, so nothing here reaches the Pi gallery loop.
The Mac preview rig renders them via experimental_palette.py. To promote an approved
effect, move its function (and _gradient_map, when thermal is promoted) into effects.py
and add one STILL_PALETTE line in palette.py.

Same contract as effects.py: @_timed pure function, frames -> one same-size RGB Image,
seed param where randomness is used.
"""
from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageOps

from effects import _timed, _middle_frame, _bw_treatment


def _gradient_map(gray_arr: np.ndarray, stops: list[tuple[int, int, int]]) -> Image.Image:
    """Map a grayscale array (H, W) through an N-stop RGB gradient LUT.

    Generalizes effects._duotone from 2 stops to N, evenly spaced across 0..255.
    Input may be float (it is clipped and cast to uint8 for the lookup).
    """
    stops_arr = np.asarray(stops, dtype=np.float32)            # (S, 3)
    positions = np.linspace(0.0, 255.0, len(stops_arr))
    lut = np.empty((256, 3), dtype=np.float32)
    for c in range(3):
        lut[:, c] = np.interp(np.arange(256), positions, stops_arr[:, c])
    idx = np.clip(gray_arr, 0, 255).astype(np.uint8)
    out = lut[idx]                                             # (H, W, 3)
    return Image.fromarray(out.astype(np.uint8))
