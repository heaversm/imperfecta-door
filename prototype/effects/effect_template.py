"""Template for a new Imperfecta effect — copy a function into effects.py and rename.

THE CONTRACT
  @_timed
  def my_effect(frames: list[Image.Image]) -> Image.Image
  - `frames`: the burst — a list of equal-size RGB PIL Images (newest last).
  - return ONE RGB PIL Image, same size as the input frames.
  - PURE: no file/network I/O, no global state. @_timed makes callers get (image, ms).
  - Single-frame effects use _middle_frame(frames); temporal effects use the whole burst.
  - If you use randomness, accept a `seed` param so "living" animations stay stable.

Reusable helpers in effects.py: _stack, _middle_frame, _bw_treatment, _numpy_remap,
_halftone_dots, _duotone. See CONTRIBUTING-EFFECTS.md for the full guide + guardrails.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from effects import _timed, _middle_frame, _bw_treatment


@_timed
def my_effect_example(frames: list[Image.Image]) -> Image.Image:
    """Example: posterize the middle frame to 3 levels, then apply the shared B&W look.
    Replace the body with your own transform; keep the signature + return type."""
    src = _middle_frame(frames)
    arr = np.asarray(src).astype(np.float32)
    levels = 3
    arr = np.round(arr / 255.0 * (levels - 1)) / (levels - 1) * 255.0
    posterized = Image.fromarray(arr.astype(np.uint8))
    return _bw_treatment(posterized)   # drop this line to stay in color
