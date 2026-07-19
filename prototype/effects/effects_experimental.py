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


def _scaled_shifted(img: Image.Image, scale: float, ox: int, oy: int) -> np.ndarray:
    """Return an (H, W, 3) array of `img` scaled about its center and shifted by (ox, oy).

    The scaled copy is composited over an untouched full-size copy of the same image,
    so downscaling (< 1.0) never leaves black borders — the original shows behind it.
    Upscaling (> 1.0) crops to the frame. Used to give each interlace slice its own
    random zoom/offset so copies deliberately misalign.
    """
    w, h = img.size
    sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
    resized = img.resize((sw, sh), Image.LANCZOS)
    canvas = img.copy()                                       # base avoids black gaps
    canvas.paste(resized, ((w - sw) // 2 + ox, (h - sh) // 2 + oy))
    return np.asarray(canvas.convert("RGB"))


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
                    scale_jitter: float = 0.15, shift_px: int = 45,
                    seed: int | None = None) -> Image.Image:
    """Interlace vertical strips of a B&W base with a color capture (ref 5.33). Each color
    strip samples from a copy of the color frame that is randomly scaled (±`scale_jitter`)
    and shifted (±`shift_px`), so every strip's content misaligns with its neighbours —
    the fractured interlace. B&W base stays upright; light grain."""
    rng = random.Random(seed)
    n = len(frames)
    color_img = frames[n // 2].convert("RGB")
    bw = np.asarray(_bw_treatment(frames[n // 4] if n >= 4 else frames[0],
                                  grain=0.03, seed=seed))
    h, w, _ = bw.shape
    out = bw.copy()
    strip_w = max(1, w // n_strips)
    for i in range(n_strips):
        if i % 2 == 0:                            # even strips stay B&W (the base)
            continue
        x0 = i * strip_w
        if x0 >= w:
            break
        x1 = w if i == n_strips - 1 else min(w, (i + 1) * strip_w)
        s = 1.0 + rng.uniform(-scale_jitter, scale_jitter)
        layer = _scaled_shifted(color_img, s, rng.randint(-shift_px, shift_px),
                                rng.randint(-shift_px, shift_px))
        out[:, x0:x1] = layer[:, x0:x1]
    return Image.fromarray(out)


@_timed
def diagonal_interlace(frames: list[Image.Image], n_cuts: int = 4, stroke_px: int = 4,
                       scale_jitter: float = 0.15, shift_px: int = 55,
                       seed: int | None = None) -> Image.Image:
    """Random diagonal shards (ref 5.37): `n_cuts` straight diagonal lines at random
    angles/positions carve the frame into triangular/polygonal regions. Each region is
    filled from one of several candidate copies of the image — a mix of B&W and color,
    each randomly scaled (±`scale_jitter`) and shifted — so shards misalign. A white
    stroke is drawn along every cut line. Light grain on the B&W."""
    rng = random.Random(seed)
    src = _middle_frame(frames)
    color_img = src.convert("RGB")
    bw_img = _bw_treatment(src, grain=0.03, seed=seed)
    w, h = color_img.size
    ys, xs = np.indices((h, w), dtype=np.float32)

    # Random diagonal cut lines in normal form: xs*c + ys*s - off, sign = which side.
    lines = []
    for _ in range(max(1, n_cuts)):
        th = rng.uniform(0.0, np.pi)
        px, py = rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h
        c, s = float(np.cos(th)), float(np.sin(th))
        lines.append((c, s, px * c + py * s))

    label = np.zeros((h, w), dtype=np.int32)                # region id = side-bits of each line
    for k, (c, s, off) in enumerate(lines):
        label += ((xs * c + ys * s - off) > 0).astype(np.int32) << k

    # Candidate copies: mix of B&W and color, each with its own random zoom/shift.
    layers = []
    for _ in range(6):
        base = color_img if rng.random() < 0.5 else bw_img
        sc = 1.0 + rng.uniform(-scale_jitter, scale_jitter)
        layers.append(_scaled_shifted(base, sc, rng.randint(-shift_px, shift_px),
                                      rng.randint(-shift_px, shift_px)))

    out = np.asarray(bw_img).copy()
    for val in np.unique(label):                            # assign a random copy per shard
        out[label == val] = layers[rng.randrange(len(layers))][label == val]

    for c, s, off in lines:                                 # white stroke along each cut
        out[np.abs(xs * c + ys * s - off) < stroke_px] = 255
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
