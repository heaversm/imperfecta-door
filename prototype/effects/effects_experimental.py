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
def mirror_smear(frames: list[Image.Image], offset_frac: float = 0.33,
                 smear_px: int = 60, seed: int | None = None) -> Image.Image:
    """Offset mirror (ref 5.30): an upside-down copy of the whole scene fills the top,
    shifted down by `offset_frac` of the height so the bottom band keeps the original
    upright. The top and bottom EDGES are broadcast across a band so both read as
    vertically stretched 'smears'. B&W family, light grain."""
    src = _bw_treatment(_middle_frame(frames), grain=0.03, seed=seed)
    arr = np.asarray(src)
    h, w, _ = arr.shape
    off = max(1, int(np.clip(offset_frac, 0.1, 0.49) * h))
    flipped = arr[::-1]                           # whole image, upside down
    out = arr.copy()                              # original in the bottom band
    out[:h - off] = flipped[off:]                 # top (h-off) = upside-down whole scene, offset down
    band = min(max(2, smear_px), off)
    out[:band] = np.repeat(out[band:band + 1], band, axis=0)                 # smear top edge
    out[h - band:] = np.repeat(out[h - band - 1:h - band], band, axis=0)     # smear bottom edge
    return Image.fromarray(out)


@_timed
def strip_interlace(frames: list[Image.Image], n_strips: int = 14,
                    seed: int | None = None) -> Image.Image:
    """Interlace vertical strips of a B&W capture with a color capture from a different
    point in the burst (ref 5.33). Strip widths are randomly scaled 85%-115% of the base
    width so the columns are uneven. Light grain so the B&W reads as film, not static."""
    rng = random.Random(seed)
    n = len(frames)
    color = np.asarray(frames[n // 2].convert("RGB"))
    bw = np.asarray(_bw_treatment(frames[n // 4] if n >= 4 else frames[0],
                                  grain=0.03, seed=seed))
    h, w, _ = color.shape
    out = bw.copy()
    base = w / n_strips
    x, i = 0, 0
    while x < w:
        sw = max(4, int(base * rng.uniform(0.85, 1.15)))
        x1 = min(w, x + sw)
        if i % 2 == 1:                            # odd strips -> color; even stay B&W
            out[:, x:x1] = color[:, x:x1]
        x, i = x1, i + 1
    return Image.fromarray(out)


@_timed
def diagonal_interlace(frames: list[Image.Image], n_sectors: int = 9,
                       stroke_px: int = 4, seed: int | None = None) -> Image.Image:
    """Radiating diagonal wedges (ref 5.37): 8-10 angular sectors around an off-center
    point, alternating B&W and color, with randomly uneven wedge widths ('random
    scaling') and a white stroke on every wedge boundary. Light grain on the B&W."""
    rng = random.Random(seed)
    src = _middle_frame(frames)
    color = np.asarray(src.convert("RGB"))
    bw = np.asarray(_bw_treatment(src, grain=0.03, seed=seed))
    h, w, _ = color.shape
    cx, cy = w * 0.5, h * 0.62                               # fan origin, lower-center
    ys, xs = np.indices((h, w), dtype=np.float32)
    ang = np.arctan2(ys - cy, xs - cx)                      # -pi..pi
    r = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)

    n_sectors = max(3, n_sectors)
    widths = np.array([rng.uniform(0.85, 1.15) for _ in range(n_sectors)], dtype=np.float64)
    widths = widths / widths.sum() * (2 * np.pi)
    bounds = (np.cumsum(widths) - np.pi)                    # sector upper boundaries

    sector = np.zeros((h, w), dtype=np.int32)
    prev = -np.pi
    for i, b in enumerate(bounds):
        sector[(ang >= prev) & (ang < b)] = i
        prev = b
    sector[ang >= bounds[-1]] = n_sectors - 1

    use_color = (sector % 2 == 0)
    out = np.where(use_color[..., None], color, bw).astype(np.uint8)

    stroke = np.zeros((h, w), dtype=bool)                   # white stroke on each boundary
    for b in bounds:
        da = np.abs(((ang - b + np.pi) % (2 * np.pi)) - np.pi)   # angular dist to boundary
        stroke |= (da * r < stroke_px)
    out[stroke] = 255
    return Image.fromarray(out)


@_timed
def block_mosaic(frames: list[Image.Image], block: int = 40, coverage: float = 0.55,
                 seed: int | None = None) -> Image.Image:
    """Coarse block mosaic over the upper-left region with a stepped (staircase) diagonal
    edge (ref 5.34); source color preserved outside the region. `block` is the mosaic
    cell size in px; `coverage` sets how far the staircase extends toward lower-right."""
    src = _middle_frame(frames)
    arr = np.asarray(src.convert("RGB")).copy()
    h, w, _ = arr.shape
    nby, nbx = h // block, w // block
    if nby == 0 or nbx == 0:
        return Image.fromarray(arr)
    trimmed = arr[:nby * block, :nbx * block].astype(np.float32)
    pooled = trimmed.reshape(nby, block, nbx, block, 3).mean(axis=(1, 3)).astype(np.uint8)
    thresh = (nby + nbx) * coverage
    for by in range(nby):
        for bx in range(nbx):
            if by + bx < thresh:                            # upper-left staircase region
                y0, x0 = by * block, bx * block
                arr[y0:y0 + block, x0:x0 + block] = pooled[by, bx]
    return Image.fromarray(arr)


@_timed
def slice_stretch(frames: list[Image.Image], slice_frac: float = 0.5,
                  seed: int | None = None) -> Image.Image:
    """Datamosh horizontal smear (ref 5.25): take one vertical column and streak it
    across the region to its right, blended under a left->right alpha gradient so it
    fades from the untouched image into a full sideways smear. `slice_frac` picks the
    source column (fraction of width)."""
    src = _middle_frame(frames)
    arr = np.asarray(src.convert("RGB")).copy()
    h, w, _ = arr.shape
    x0 = int(np.clip(slice_frac, 0.0, 0.95) * w)
    span = w - x0
    if span <= 1:
        return Image.fromarray(arr)
    col = arr[:, x0:x0 + 1, :].astype(np.float32)           # (h, 1, 3)
    streak = np.repeat(col, span, axis=1)                   # (h, span, 3)
    region = arr[:, x0:w, :].astype(np.float32)
    ramp = np.linspace(0.0, 1.0, span, dtype=np.float32)[None, :, None]
    blended = region * (1.0 - ramp) + streak * ramp
    arr[:, x0:w, :] = blended.astype(np.uint8)
    return Image.fromarray(arr)
