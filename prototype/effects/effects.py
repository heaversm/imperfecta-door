"""Visual effects for the Imperfecta installation.

Pure functions — input is a list of PIL Images (a burst), output is one PIL Image
plus elapsed milliseconds. No I/O, no global state. Same module runs on Mac
(preview rig) and Pi (production effects server).
"""

from __future__ import annotations

import random
import time
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


def _timed(fn: Callable) -> Callable:
    """Wrap an effect so it returns (image, elapsed_ms)."""
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        return result, (time.perf_counter() - t0) * 1000.0
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _stack(frames: list[Image.Image]) -> np.ndarray:
    """Stack frames into a (N, H, W, 3) uint8 array, asserting consistent shape."""
    arrs = [np.asarray(f.convert("RGB")) for f in frames]
    h, w = arrs[0].shape[:2]
    for a in arrs[1:]:
        assert a.shape[:2] == (h, w), f"frame size mismatch: {a.shape} vs {(h, w)}"
    return np.stack(arrs, axis=0)


def _middle_frame(frames: list[Image.Image]) -> Image.Image:
    """Pick the temporal centerpoint of the burst — usually the most representative."""
    return frames[len(frames) // 2].convert("RGB")


def _duotone(gray_arr: np.ndarray, dark: tuple, light: tuple) -> Image.Image:
    """Map a grayscale array (H, W) to an RGB gradient between `dark` and `light`."""
    t = gray_arr.astype(np.float32) / 255.0
    out = np.empty((*gray_arr.shape, 3), dtype=np.uint8)
    for i in range(3):
        out[..., i] = np.clip(dark[i] * (1 - t) + light[i] * t, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def _numpy_remap(arr: np.ndarray, src_x: np.ndarray, src_y: np.ndarray) -> np.ndarray:
    """Nearest-neighbor remap. Pure numpy, single fancy-index op, no cv2.

    `src_x`/`src_y` are float arrays the size of the output image; each cell
    holds the source-pixel coordinate to read. Out-of-bounds gets clamped.
    """
    h, w = arr.shape[:2]
    xi = np.clip(np.round(src_x).astype(np.int32), 0, w - 1)
    yi = np.clip(np.round(src_y).astype(np.int32), 0, h - 1)
    return arr[yi, xi]


# ─── Slitscan ──────────────────────────────────────────────────────────────

@_timed
def slitscan_vertical(frames: list[Image.Image]) -> Image.Image:
    """Each column of output = same column from a different frame in time.

    Result: horizontal motion gets smeared into surreal stretching.
    """
    stack = _stack(frames)
    n, h, w, _ = stack.shape
    # column c pulls from frame index (c * n // w)
    col_to_frame = (np.arange(w) * n // w).clip(0, n - 1)
    out = stack[col_to_frame, :, np.arange(w), :]  # (W, H, 3)
    out = out.transpose(1, 0, 2)  # → (H, W, 3)
    return Image.fromarray(out)


@_timed
def slitscan_horizontal(frames: list[Image.Image]) -> Image.Image:
    """Each row of output = same row from a different frame in time.

    Result: vertical motion gets smeared into surreal stretching.
    """
    stack = _stack(frames)
    n, h, w, _ = stack.shape
    row_to_frame = (np.arange(h) * n // h).clip(0, n - 1)
    out = stack[row_to_frame, np.arange(h), :, :]  # (H, W, 3)
    return Image.fromarray(out)


# ─── Echo (max-blend only) ─────────────────────────────────────────────────

@_timed
def echo_max(frames: list[Image.Image]) -> Image.Image:
    """Per-pixel max across frames — bright streaks where things moved."""
    stack = _stack(frames)
    out = stack.max(axis=0)
    return Image.fromarray(out)


# ─── Time grid mosaic ──────────────────────────────────────────────────────

@_timed
def time_grid(frames: list[Image.Image], rows: int = 4, cols: int = 4) -> Image.Image:
    """Output split into rows×cols tiles; each tile pulled from a different frame.

    Earlier frames go top-left, later frames bottom-right.
    """
    stack = _stack(frames)
    n, h, w, _ = stack.shape
    cell_h, cell_w = h // rows, w // cols
    out = np.zeros((h, w, 3), dtype=np.uint8)
    n_cells = rows * cols
    for r in range(rows):
        for c in range(cols):
            idx = ((r * cols + c) * n) // n_cells
            idx = min(idx, n - 1)
            y0, x0 = r * cell_h, c * cell_w
            out[y0:y0 + cell_h, x0:x0 + cell_w] = stack[idx, y0:y0 + cell_h, x0:x0 + cell_w]
    return Image.fromarray(out)


# ─── Hockney joiner ────────────────────────────────────────────────────────

@_timed
def hockney_joiner(
    frames: list[Image.Image],
    rows: int = 4,
    cols: int = 4,
    rotation_max_deg: float = 7.0,
    jitter_frac: float = 0.08,
    border_px: int = 6,
    bg_color: tuple[int, int, int] = (180, 200, 215),
    seed: int | None = None,
) -> Image.Image:
    """Hockney-style photo joiner: bordered tiles, rotated, jittered, overlapping.

    Each tile is a crop from a different frame in the burst, so the subject is
    fragmented across time as well as space. Tiles paste back roughly where
    they came from, preserving readability of the subject.

    Params:
      rows/cols          — grid density
      rotation_max_deg   — each tile rotated ±this much
      jitter_frac        — each tile offset by ±this fraction of cell size
      border_px          — white border simulating physical photo edge
      bg_color           — background canvas color
      seed               — fix for reproducible rendering; None = random
    """
    rng = random.Random(seed)
    stack = _stack(frames)
    n, h, w, _ = stack.shape

    # Canvas larger than source so rotated/jittered tiles don't clip
    pad = int(max(h, w) * 0.25)
    canvas = Image.new("RGB", (w + 2 * pad, h + 2 * pad), bg_color)

    cell_h = h // rows
    cell_w = w // cols
    # Bleed each tile slightly past its cell so neighbors overlap pleasingly
    bleed = max(cell_h, cell_w) // 8

    n_cells = rows * cols
    for r in range(rows):
        for c in range(cols):
            idx = ((r * cols + c) * n) // n_cells
            idx = min(idx, n - 1)
            y0 = max(0, r * cell_h - bleed)
            x0 = max(0, c * cell_w - bleed)
            y1 = min(h, (r + 1) * cell_h + bleed)
            x1 = min(w, (c + 1) * cell_w + bleed)
            tile_arr = stack[idx, y0:y1, x0:x1]
            tile_img = Image.fromarray(tile_arr)

            # White border
            bw, bh = tile_img.width + 2 * border_px, tile_img.height + 2 * border_px
            bordered = Image.new("RGB", (bw, bh), (255, 255, 255))
            bordered.paste(tile_img, (border_px, border_px))

            # Rotate with transparent corners
            angle = rng.uniform(-rotation_max_deg, rotation_max_deg)
            rotated = bordered.convert("RGBA").rotate(
                angle, resample=Image.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0)
            )

            # Paste centered on the tile's original location, plus jitter
            jx = int(rng.uniform(-cell_w * jitter_frac, cell_w * jitter_frac))
            jy = int(rng.uniform(-cell_h * jitter_frac, cell_h * jitter_frac))
            cx = (x0 + x1) // 2 + pad + jx
            cy = (y0 + y1) // 2 + pad + jy
            px = cx - rotated.width // 2
            py = cy - rotated.height // 2
            canvas.paste(rotated, (px, py), rotated)

    return canvas


# ─── Liquify ───────────────────────────────────────────────────────────────

@_timed
def liquify(
    frame: Image.Image,
    wave_amp: float = 18.0,
    wave_freq: float = 2.5,
    bulge: float = 0.35,
    twirl_deg: float = 25.0,
) -> Image.Image:
    """Single-frame distortion: sine wave + radial bulge + twirl.

    All parameters in pixels / degrees / unit-relative. Reasonable extremes:
      wave_amp 0–30, wave_freq 0–5, bulge -0.6 to 0.6, twirl_deg 0–90.
    """
    arr = np.asarray(frame.convert("RGB"))
    h, w = arr.shape[:2]

    # Build a remap: for each output pixel, which source pixel do we read?
    ys, xs = np.indices((h, w), dtype=np.float32)
    cx, cy = w / 2.0, h / 2.0
    dx = xs - cx
    dy = ys - cy
    r = np.sqrt(dx * dx + dy * dy)
    r_max = np.sqrt(cx * cx + cy * cy)
    r_norm = r / r_max  # 0 at center, 1 at corner

    # 1) Wave displacement
    src_x = xs + wave_amp * np.sin(2 * np.pi * wave_freq * ys / h)
    src_y = ys + wave_amp * np.sin(2 * np.pi * wave_freq * xs / w)

    # 2) Radial bulge — positive = bulge out, negative = pinch in
    # scale source-radius by (1 - bulge * (1 - r_norm)^2)
    scale = 1.0 - bulge * (1.0 - r_norm) ** 2
    src_x = cx + (src_x - cx) * scale
    src_y = cy + (src_y - cy) * scale

    # 3) Twirl — rotate by an angle that falls off with radius
    angle = np.deg2rad(twirl_deg) * (1.0 - r_norm) ** 2
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    tx = src_x - cx
    ty = src_y - cy
    src_x = cx + cos_a * tx - sin_a * ty
    src_y = cy + sin_a * tx + cos_a * ty

    return Image.fromarray(_numpy_remap(arr, src_x, src_y))


# ─── Warhol ────────────────────────────────────────────────────────────────

WARHOL_PALETTES = [
    ((220, 20, 110), (255, 230, 50)),    # magenta on yellow
    ((20, 50, 200), (60, 230, 90)),      # blue on green
    ((20, 20, 20), (240, 240, 240)),     # b&w
    ((210, 30, 30), (255, 200, 100)),    # red on cream
]


@_timed
def warhol(frames: list[Image.Image]) -> Image.Image:
    """Pop-art 2×2 grid: same frame, four clashing duotone palettes."""
    src = _middle_frame(frames)
    w, h = src.size
    cell = src.resize((w // 2, h // 2))
    gray = np.asarray(cell.convert("L"))

    canvas = Image.new("RGB", (w, h))
    positions = [(0, 0), (w // 2, 0), (0, h // 2), (w // 2, h // 2)]
    for (px, py), (dark, light) in zip(positions, WARHOL_PALETTES):
        canvas.paste(_duotone(gray, dark, light), (px, py))
    return canvas


# ─── Lichtenstein ──────────────────────────────────────────────────────────

def _halftone_dots(gray_arr: np.ndarray, dot_spacing: int = 8) -> np.ndarray:
    """Generate a halftone-dot overlay: darker areas → bigger black dots.

    Returns a (H, W) uint8 array, 0 where dot ink lives, 255 elsewhere.
    Pure numpy, no Python loops over pixels.
    """
    h, w = gray_arr.shape
    dh, dw = h // dot_spacing, w // dot_spacing
    trimmed = gray_arr[:dh * dot_spacing, :dw * dot_spacing]
    # Average brightness per cell
    cell_mean = trimmed.reshape(dh, dot_spacing, dw, dot_spacing).mean(axis=(1, 3))
    max_r = dot_spacing / 2 - 0.5
    radii = (1.0 - cell_mean / 255.0) * max_r  # (dh, dw)

    yy, xx = np.indices((dot_spacing, dot_spacing), dtype=np.float32)
    c = (dot_spacing - 1) / 2.0
    dist = np.sqrt((yy - c) ** 2 + (xx - c) ** 2)  # (dot_spacing, dot_spacing)

    # broadcast: (dh, 1, dw, 1) vs (1, dot_spacing, 1, dot_spacing) → (dh, dot_spacing, dw, dot_spacing)
    inside = dist[None, :, None, :] <= radii[:, None, :, None]
    inside = inside.reshape(dh * dot_spacing, dw * dot_spacing)

    out = np.full((h, w), 255, dtype=np.uint8)
    out[:dh * dot_spacing, :dw * dot_spacing][inside] = 0
    return out


@_timed
def lichtenstein(
    frames: list[Image.Image],
    dot_spacing: int = 18,
    edge_threshold: int = 70,
) -> Image.Image:
    """Pop-comic-book look: 5-color palette + coarse Ben-Day dots + bold outlines.

    Palette is mapped from brightness ranges:
      darkest → blue (cobalt shadows)
      mid     → pink skin base; halftone dots in this range render as red
                (classic Lichtenstein skin-tone)
      light   → yellow
      bright  → white
    Edges drawn last in heavy black.
    """
    src = _middle_frame(frames)
    gray = np.asarray(src.convert("L"))
    h, w = gray.shape

    # Flat-color base by brightness threshold
    out = np.empty((h, w, 3), dtype=np.uint8)
    out[:] = (250, 250, 250)              # default = white highlights
    out[gray < 80] = (35, 80, 200)        # shadows  → blue
    out[gray > 200] = (245, 220, 60)      # bright   → yellow
    skin_mask = (gray >= 80) & (gray <= 200)
    out[skin_mask] = (245, 200, 195)      # skin base = pink

    # Coarse halftone over the skin region → reads as red Ben-Day dots
    halftone = _halftone_dots(gray, dot_spacing=dot_spacing)
    dot_mask = (halftone == 0) & skin_mask
    out[dot_mask] = (220, 30, 30)

    # Heavy black outlines (smoothed → edge-detected → thresholded → dilated)
    edges = (src.convert("L")
                .filter(ImageFilter.SMOOTH)
                .filter(ImageFilter.FIND_EDGES))
    edge_mask = np.asarray(edges) > edge_threshold
    edge_img = Image.fromarray((edge_mask.astype(np.uint8) * 255))
    edge_img = edge_img.filter(ImageFilter.MaxFilter(3))   # dilate for boldness
    edge_mask = np.asarray(edge_img) > 0
    out[edge_mask] = (15, 15, 15)

    return Image.fromarray(out)


# ─── Mondrian ──────────────────────────────────────────────────────────────

MONDRIAN_PALETTE = [
    (235, 30, 30),    # red
    (230, 200, 30),   # yellow
    (30, 70, 200),    # blue
    (250, 250, 250), (250, 250, 250), (250, 250, 250),  # white (weighted)
    (15, 15, 15),     # black
]


@_timed
def mondrian(
    frames: list[Image.Image],
    max_depth: int = 5,
    min_cell: int = 60,
    seed: int | None = None,
) -> Image.Image:
    """Recursive rectangular subdivision; primary-color fills + black grid lines.

    The most centered rectangle gets the actual face crop so the subject reads
    through one window of the composition.
    """
    rng = random.Random(seed)
    src = _middle_frame(frames)
    w, h = src.size
    canvas = Image.new("RGB", (w, h), (245, 245, 245))
    line_color = (12, 12, 12)
    line_width = max(3, min(w, h) // 180)

    rects: list[tuple[int, int, int, int, tuple]] = []

    def split(x0: int, y0: int, x1: int, y1: int, depth: int) -> None:
        rw, rh = x1 - x0, y1 - y0
        if (
            depth >= max_depth
            or (rw < min_cell * 2 and rh < min_cell * 2)
            or (depth >= 2 and rng.random() < 0.25)
        ):
            rects.append((x0, y0, x1, y1, rng.choice(MONDRIAN_PALETTE)))
            return
        # Pick split direction biased by aspect
        if rw > rh * 1.3:
            direction = "v"
        elif rh > rw * 1.3:
            direction = "h"
        else:
            direction = "v" if rng.random() < 0.5 else "h"
        if direction == "v" and rw >= min_cell * 2:
            sx = x0 + rng.randint(rw // 3, rw * 2 // 3)
            split(x0, y0, sx, y1, depth + 1)
            split(sx, y0, x1, y1, depth + 1)
        elif direction == "h" and rh >= min_cell * 2:
            sy = y0 + rng.randint(rh // 3, rh * 2 // 3)
            split(x0, y0, x1, sy, depth + 1)
            split(x0, sy, x1, y1, depth + 1)
        else:
            rects.append((x0, y0, x1, y1, rng.choice(MONDRIAN_PALETTE)))

    split(0, 0, w, h, 0)

    # Distribute face crops across most cells — fragmented portrait through a
    # Mondrian frame. The most-central cell is forced to be a face crop so the
    # composition always has an anchor on the subject.
    cx_img, cy_img = w / 2, h / 2
    center_idx = min(
        range(len(rects)),
        key=lambda i: ((rects[i][0] + rects[i][2]) / 2 - cx_img) ** 2
                      + ((rects[i][1] + rects[i][3]) / 2 - cy_img) ** 2,
    )
    face_prob = 0.45  # ~45% of cells show face; rest are primary-color panels

    # Decide upfront which cells are face vs colored
    face_set = {center_idx}
    for i in range(len(rects)):
        if i != center_idx and rng.random() < face_prob:
            face_set.add(i)
    non_face = [i for i in range(len(rects)) if i not in face_set]

    # Guarantee at least one red, blue, and white panel
    required = [(235, 30, 30), (30, 70, 200), (250, 250, 250)]
    if len(non_face) >= len(required):
        forced = rng.sample(non_face, len(required))
        for idx, color in zip(forced, required):
            x0, y0, x1, y1, _ = rects[idx]
            rects[idx] = (x0, y0, x1, y1, color)

    draw = ImageDraw.Draw(canvas)
    for i, (x0, y0, x1, y1, color) in enumerate(rects):
        if i in face_set:
            canvas.paste(src.crop((x0, y0, x1, y1)), (x0, y0))
        else:
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=color)

    # Borders drawn last so they sit over the fills + face crops
    for (x0, y0, x1, y1, _) in rects:
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=line_color, width=line_width)

    return canvas


