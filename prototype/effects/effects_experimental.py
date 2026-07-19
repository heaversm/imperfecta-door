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


@_timed
def thermal_map(frames: list[Image.Image], spatial: float = 0.35,
                seed: int | None = None) -> Image.Image:
    """Spectral 'thermal' gradient map (ref 5.26): source luminance blended with a
    diagonal positional ramp, mapped through a teal -> red -> orange -> yellow -> green
    LUT, so colored light sweeps across the subject. `spatial` sets how much the
    diagonal ramp biases the mapping (0 = pure luminance heatmap)."""
    src = _middle_frame(frames)
    gray = np.asarray(ImageOps.autocontrast(src.convert("L"), cutoff=2)).astype(np.float32)
    h, w = gray.shape
    ys, xs = np.indices((h, w), dtype=np.float32)
    diag = (xs / w + (1.0 - ys / h)) * 0.5 * 255.0          # brightest toward upper-right
    idx = np.clip((1.0 - spatial) * gray + spatial * diag, 0, 255)
    stops = [(12, 40, 55), (200, 30, 45), (240, 120, 30), (240, 220, 60), (70, 180, 95)]
    return _gradient_map(idx, stops)


@_timed
def mirror_smear(frames: list[Image.Image], split: float = 0.5,
                 smear_px: int = 70, seed: int | None = None) -> Image.Image:
    """Mirrored-world composite (ref 5.30): top = image, bottom = a vertically flipped
    copy; the seam row is broadcast across a band so the join reads as vertically
    stretched 'edge pixels'. B&W family."""
    src = _bw_treatment(_middle_frame(frames), seed=seed)
    arr = np.asarray(src)
    h, w, _ = arr.shape
    split_y = int(np.clip(split, 0.1, 0.9) * h)
    flipped = arr[::-1]
    out = np.vstack([arr[:split_y], flipped[:h - split_y]])   # exactly h rows
    band = min(max(2, smear_px), h)
    seam_i = min(split_y, h - 1)
    seam = out[seam_i:seam_i + 1]                             # (1, w, 3)
    y0 = max(0, split_y - band // 2)
    y1 = min(h, y0 + band)
    out[y0:y1] = np.repeat(seam, y1 - y0, axis=0)
    return Image.fromarray(out)
