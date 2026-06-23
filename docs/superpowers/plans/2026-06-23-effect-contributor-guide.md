# Effect Contributor Onboarding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an experienced contributor build, preview, validate, and tie in new effects using only the existing pure-function architecture — via a guide, a template, a guardrail check script, and a single shared roster so tie-in is one edit.

**Architecture:** Effects stay pure functions in `effects.py`. A shared `palette.py` holds the roster (wrappers + STILL_PALETTE/ANIM_PALETTE), imported by both `effects_server.py` (gallery) and `preview_rig.py` (dev), so adding an effect to one list shows it in both. A `validate_effect.py` script enforces the guardrails locally; PR review is the gate.

**Tech Stack:** Python 3 (Pillow, numpy), the existing Flask preview rig, git/GitHub PRs.

**Spec:** `docs/superpowers/specs/2026-06-23-effect-contributor-guide-design.md`

**Note on `git`:** the Bash sandbox currently denies `getcwd()` on the `~/Desktop` path; run git commits with the sandbox bypass if they fail with "Unable to read current working directory."

---

## Task 1: Effect template

A commented, working effect a contributor copies to start. Teaches the contract by example.

**Files:**
- Create: `prototype/effects/effect_template.py`

- [ ] **Step 1: Write the template**

```python
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
```

- [ ] **Step 2: Verify it runs**

```bash
cd prototype/effects && python3 -c "
from PIL import Image
import effect_template as t
frames=[Image.new('RGB',(1024,576),(i*8%256,90,140)) for i in range(30)]
img,ms=t.my_effect_example(frames)
assert img.size==(1024,576) and img.mode=='RGB'
print(f'template runs: {img.size} {ms:.0f}ms')
"
```
Expected: `template runs: (1024, 576) <n>ms`.

- [ ] **Step 3: Commit**

```bash
git add prototype/effects/effect_template.py
git commit -m "Add effect template for contributors"
```

---

## Task 2: Guardrail validation script

Runs a named effect against a synthetic 30-frame burst and checks format, size, render time,
and peak memory. The contributor runs it locally; the owner re-runs it on the Pi at review
(the Pi is the real perf arbiter — see the caveat printed by the script).

**Files:**
- Create: `prototype/effects/validate_effect.py`

- [ ] **Step 1: Write the validator**

```python
#!/usr/bin/env python3
"""Validate an effect against the gallery guardrails.

Usage:  python3 validate_effect.py <effect_function_name>   (run from prototype/effects/)
Checks: returns an RGB PIL Image at the input size; render time vs budget; peak Python memory.

Caveat: run on a Mac this is a SANITY check — the Mac is ~3-4x faster than the Pi 3B+ and
tracemalloc undercounts numpy's C allocations. The real perf gate is running this ON THE PI
at PR review. A memory-thrashing effect also shows up as slow, so the time check is the
effective guardrail.
"""
import sys
import time
import tracemalloc
from PIL import Image
import effects

WORK = (1024, 576)
N = 30
TIME_WARN_MS = 1000
TIME_FAIL_MS = 3000
MEM_WARN_MB = 150


def make_burst():
    # Synthetic shifting gradient so temporal effects see "motion".
    return [Image.new("RGB", WORK, ((i * 8) % 256, (i * 5) % 256, 128)) for i in range(N)]


def main():
    if len(sys.argv) != 2:
        print("usage: python3 validate_effect.py <effect_name>")
        sys.exit(2)
    name = sys.argv[1]
    fn = getattr(effects, name, None)
    if not callable(fn):
        print(f"FAIL: effects.{name} not found / not callable")
        sys.exit(1)

    frames = make_burst()
    tracemalloc.start()
    t0 = time.perf_counter()
    result = fn(frames)
    ms = (time.perf_counter() - t0) * 1000.0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak / 1e6

    img = result[0] if isinstance(result, tuple) else result  # @_timed returns (img, ms)
    ok = True
    if not isinstance(img, Image.Image):
        print(f"FAIL: did not return a PIL Image (got {type(img).__name__})")
        ok = False
    else:
        if img.mode != "RGB":
            print(f"FAIL: mode {img.mode}, expected RGB")
            ok = False
        if img.size != WORK:
            print(f"WARN: size {img.size} != input {WORK} (server scales, but matching is cleaner)")

    print(f"render: {ms:.0f}ms  (warn >{TIME_WARN_MS}, fail >{TIME_FAIL_MS}) [Mac ~3-4x faster than Pi]")
    if ms > TIME_FAIL_MS:
        print("FAIL: too slow for the per-ring budget")
        ok = False
    elif ms > TIME_WARN_MS:
        print("WARN: slower than ideal — all effects sum per ring")

    print(f"peak Python mem: {peak_mb:.0f}MB  (warn >{MEM_WARN_MB}; note: undercounts numpy)")
    if peak_mb > MEM_WARN_MB:
        print("WARN: high memory — avoid float32 stacks of the whole burst")

    print("PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it passes a good effect and flags a bad one**

```bash
cd prototype/effects
python3 validate_effect.py warhol            # expect: PASS
python3 validate_effect.py my_effect_example 2>&1 || true   # only if added to effects.py; else skip
python3 validate_effect.py nonexistent_effect; echo "exit=$?"   # expect: FAIL, exit=1
```
Expected: `warhol` prints `PASS`; the missing name prints `FAIL` and exits 1.

- [ ] **Step 3: Commit**

```bash
git add prototype/effects/validate_effect.py
git commit -m "Add effect guardrail validator (format/size/time/memory)"
```

---

## Task 3: Shared roster module (tie-in in one place)

Extract the roster (wrappers + palettes) from `effects_server.py` into `palette.py` so both the
gallery server and the preview rig import the same lists — a contributor ties in once.

**Files:**
- Create: `prototype/palette.py`
- Modify: `prototype/effects_server.py` (remove the wrappers + STILL/ANIM palette defs; import them)

- [ ] **Step 1: Read the current roster**

Open `prototype/effects_server.py` and locate the block from `_bw = effects._bw_treatment`
through the `ANIM_PALETTE = [...]` definition (the wrappers + `STILL_PALETTE`, `ANIM_FRAMES`,
`ANIM_PALETTE`, `FLIPBOOK_KIND`). This whole block moves to `palette.py`.

- [ ] **Step 2: Create `prototype/palette.py`**

Move the exact block into a new module. It must import `effects`:

```python
"""The effect roster — the single place to tie in an effect. Imported by both
effects_server.py (gallery) and effects/preview_rig.py (dev), so adding an entry here
shows the effect in both. See effects/CONTRIBUTING-EFFECTS.md.
"""
import effects

_bw = effects._bw_treatment

def _slit_h(frames): return _bw(effects.slitscan_horizontal(frames)[0])
def _liq(frames):    return _bw(effects.liquify(frames[len(frames) // 2], wave_amp=30, wave_freq=4, bulge=0.5, twirl_deg=45)[0])
def _hock(frames):   return _bw(effects.hockney_joiner(frames, rows=3, cols=3, rotation_max_deg=12, jitter_frac=0.12, border_px=10, pad_frac=0.04, bleed_frac=0.38)[0])
def _slice(frames):  return effects.slice_displacement(frames)[0]
def _water(frames):  return effects.water_refraction(frames)[0]
def _warhol(frames): return effects.warhol(frames)[0]

STILL_PALETTE = [
    ("warhol",              _warhol),
    ("slice displacement",  _slice),
    ("water refraction",    _water),
    ("slitscan horizontal", _slit_h),
    ("liquify",             _liq),
    ("hockney",             _hock),
]

ANIM_FRAMES = 6

def _a_dither(fr, seed): return effects.dither(fr)[0]
def _a_mond(fr, seed):   return effects.mondrian(fr, seed=seed)[0]

ANIM_PALETTE = [
    ("dither (live)",   _a_dither),
    ("mondrian (live)", _a_mond),
]
FLIPBOOK_KIND = "flipbook"
```

- [ ] **Step 3: Update `effects_server.py` to import the roster**

Delete the moved block from `effects_server.py` and, near the top (after `import effects`), add:

```python
from palette import STILL_PALETTE, ANIM_PALETTE, ANIM_FRAMES, FLIPBOOK_KIND
```
Leave the rest of `effects_server.py` (trigger, routes) unchanged — it already references those names.

- [ ] **Step 4: Verify the server still imports + renders**

```bash
cd prototype && PYTHONPATH="$(pwd)/effects" python3 -c "
import palette
print('stills:', [n for n,_ in palette.STILL_PALETTE])
print('living:', [n for n,_ in palette.ANIM_PALETTE])
"
```
Expected: prints the 6 stills + 2 living names. (Then a real check happens on deploy.)

- [ ] **Step 5: Commit**

```bash
git add prototype/palette.py prototype/effects_server.py
git commit -m "Extract effect roster into shared palette.py (tie-in in one place)"
```

---

## Task 4: Wire the preview rig to the shared roster

So a contributor's tied-in effect appears in the preview rig automatically (dev/gallery parity).

**Files:**
- Modify: `prototype/effects/preview_rig.py`

- [ ] **Step 1: Read `preview_rig.py`**

Open `prototype/effects/preview_rig.py`. Find how it currently lists/renders effects (it likely
has its own hardcoded list). The goal: render `palette.STILL_PALETTE` (and optionally the
`ANIM_PALETTE` effects as stills) instead of a separate list.

- [ ] **Step 2: Import and render the shared roster**

Add near its imports (preview_rig.py lives in `effects/`, so `palette.py` in the parent must be
importable — add the parent to `sys.path`):

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # prototype/
import palette
```
Replace its internal effect list with `palette.STILL_PALETTE + [(f"{n} (live)", lambda fr, fn=fn: fn([fr[len(fr)//2]], 0)) for n, fn in palette.ANIM_PALETTE]` (render living effects as a single still in preview), or simply `palette.STILL_PALETTE` if living-preview isn't needed. Match the rig's existing render call signature `(name, fn)` where `fn(frames)->image`.

- [ ] **Step 3: Verify the rig lists the roster effects**

```bash
cd prototype/effects && python3 -c "import sys,os; sys.path.insert(0, os.path.dirname(os.getcwd())); import preview_rig" 2>&1 | head -3
```
Expected: no import errors. (Full check: run the rig and confirm the effects render in the browser.)

- [ ] **Step 4: Commit**

```bash
git add prototype/effects/preview_rig.py
git commit -m "Preview rig renders the shared roster (dev/gallery parity)"
```

---

## Task 5: The contributor guide

The single doc a contributor reads.

**Files:**
- Create: `prototype/effects/CONTRIBUTING-EFFECTS.md`

- [ ] **Step 1: Write the guide**

Write `CONTRIBUTING-EFFECTS.md` with these sections (use real content, not placeholders):
1. **What an effect is** — the contract (signature, RGB out, same size, pure, `@_timed`),
   single-frame vs temporal, the `seed` rule for living effects.
2. **Helpers you can use** — `_stack`, `_middle_frame`, `_bw_treatment`, `_numpy_remap`,
   `_halftone_dots`, `_duotone`, with a one-line description of each.
3. **Start from the template** — copy `effect_template.py`'s function into `effects.py`, rename.
4. **Develop solo** — run `effects/preview_rig.py`; it grabs a burst from your laptop webcam and
   renders the roster in a browser. No gallery hardware needed.
5. **Tie in (one place)** — add a wrapper + one entry to `palette.py`: `STILL_PALETTE` for a
   still, `ANIM_PALETTE` for a living clip (must render cleanly from a single frame, be cheap).
6. **Validate** — `python3 validate_effect.py <name>` must print `PASS`. Explain the guardrails:
   pure function, RGB/size, render < ~1s (hard ceiling ~3s) at 1024px on a Pi 3B+, bounded
   memory (no float32 stack of the whole burst — cite the echo bug), seeded randomness,
   deps = stdlib+numpy+Pillow only.
7. **Submit** — branch, commit, open a PR. Owner reviews (re-runs `validate_effect.py` on the
   Pi for the real perf number, checks taste) and merges; `deploy.sh` ships it to the gallery.

- [ ] **Step 2: Verify the guide references match reality**

```bash
cd prototype/effects
grep -q "validate_effect.py" CONTRIBUTING-EFFECTS.md && grep -q "palette.py" CONTRIBUTING-EFFECTS.md && echo "refs present"
ls effect_template.py validate_effect.py ../palette.py   # all referenced files exist
```
Expected: `refs present` and all three files listed.

- [ ] **Step 3: Commit**

```bash
git add prototype/effects/CONTRIBUTING-EFFECTS.md
git commit -m "Add CONTRIBUTING-EFFECTS guide for contributors"
```

---

## Verification (whole feature)
- A contributor can read `CONTRIBUTING-EFFECTS.md`, copy the template, develop against the
  preview rig (own webcam), `validate_effect.py` → PASS, add one entry to `palette.py`, open a
  PR, and after merge + `deploy.sh` the effect appears in the gallery loop.
- `validate_effect.py warhol` → PASS; a missing name → FAIL/exit 1.
- `palette.py` is the single roster source; `effects_server.py` and `preview_rig.py` both import
  it; the gallery still renders 6 stills + 2 living + flipbook after the refactor (confirm on a
  Pi deploy + one `/trigger`).
