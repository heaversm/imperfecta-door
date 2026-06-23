# Contributing Effects to Imperfecta

This is everything you need to build a new visual effect for the gallery display. You can do
all of it on your own laptop — no access to the gallery hardware required.

The gallery shows a looping slideshow of effects applied to a short burst of webcam frames
captured when someone rings a doorbell. Your job: write one function that turns a burst into
an image.

---

## 1. What an effect is

An effect is a **pure function** in `effects.py`:

```python
@_timed
def my_effect(frames: list[Image.Image]) -> Image.Image:
    ...
```

- **Input** `frames`: the burst — a list of equal-size **RGB PIL Images**, oldest first, newest
  last (~30 frames).
- **Output:** exactly **one RGB PIL Image**, same dimensions as the input frames.
- **Pure:** no file/network I/O, no global state, no side effects. The `@_timed` decorator wraps
  it so callers receive `(image, elapsed_ms)` — you just return the image.
- **Single-frame vs temporal:**
  - *Single-frame* effects ignore time — use `_middle_frame(frames)` and transform that one
    frame (e.g. dither, warhol, liquify).
  - *Temporal* effects use the whole burst — motion across frames is the point (e.g. slitscan,
    echo).
- **Randomness:** if you use `random`/`np.random`, take a `seed` parameter and seed from it, so
  the same input is reproducible. This is **required** for "living" effects (see §5).

## 2. Helpers you can use (in `effects.py`)

- `_timed` — the decorator above; put it on every effect.
- `_middle_frame(frames)` — the temporal-center frame (the representative still).
- `_stack(frames)` — frames as one `(N, H, W, 3)` numpy uint8 array (for temporal effects).
- `_bw_treatment(img)` — the shared grayscale + contrast + film-grain look; wrap your output in
  it to join the B&W family.
- `_numpy_remap(arr, src_x, src_y)` — warp/displace pixels by a coordinate field (used by
  liquify, water_refraction).
- `_halftone_dots(gray, dot_spacing)` — a halftone-dot overlay sized by darkness.
- `_duotone(gray, dark, light)` — map a grayscale array to a two-color gradient.

Read the existing effects in `effects.py` — they're short and the best examples.

## 3. Start from the template

Copy the function in `effect_template.py` into `effects.py`, rename it, and replace the body.
Keep the signature and the `@_timed` decorator.

## 4. Develop solo (your laptop, no gallery hardware)

```bash
cd prototype/effects
pip install -r requirements.txt     # first time
python preview_rig.py
```
Open `http://localhost:8000`, hit **CAPTURE** — it grabs a burst from your laptop webcam and
renders the whole roster (including your effect, once you've tied it in) in a browser grid with
per-effect timings. Iterate freely.

## 5. Tie in — one place

The roster lives in **`prototype/palette.py`**. Add a thin wrapper and one entry:

```python
def _my_effect(frames): return effects.my_effect(frames)[0]   # or wrap in _bw(...) for B&W family

STILL_PALETTE = [
    ...,
    ("my effect", _my_effect),      # a still: rendered once per ring
]
```

For a **"living" effect** (animates — the subject moves through frames), add it to
`ANIM_PALETTE` instead. Its callable takes `([single_frame], seed)` and must render cleanly
from a single frame and be cheap (it's rendered across `ANIM_FRAMES` frames):

```python
def _a_my_effect(fr, seed): return effects.my_effect(fr, seed=seed)[0]

ANIM_PALETTE = [
    ...,
    ("my effect (live)", _a_my_effect),
]
```

That one edit makes the effect show in both the preview rig and the gallery loop.

## 6. Validate — the guardrails

Run the checker (must print `PASS`):

```bash
cd prototype/effects
python validate_effect.py my_effect
```

It renders your effect against a synthetic 1024×576 / 30-frame burst and checks:

| Guardrail | Bar |
|---|---|
| **Returns an RGB PIL Image** | required |
| **Output size** | matches the input frames (the server scales, but match it) |
| **Render time** | target **< ~1s** at 1024px on a Pi 3B+; **~3s is the hard ceiling** (all effects sum per ring) |
| **Memory** | **bounded** — never build a float32 stack of the whole burst (~200MB → swaps the 1GB Pi to death; a real bug we hit with `echo`). Accumulate incrementally instead. |
| **Dependencies** | stdlib + `numpy` + `Pillow` only — no new deps without a heads-up |

Note: `validate_effect.py` on a Mac is a **sanity check** — the Mac is ~3-4× faster than the Pi
and undercounts numpy memory. The owner re-runs it on the actual Pi at review for the real
numbers. (A memory-thrashing effect also shows up as *slow*, so the time check catches it.)

## 7. Working with Claude

This codebase is built to be driven by Claude (Claude Code). The fastest path:

1. Open Claude Code in the repo root.
2. Point it at the contract and an example, then describe the effect — a reference image, an
   Instagram link, a technique, or sample code. A good starter prompt:

   > Read `prototype/effects/CONTRIBUTING-EFFECTS.md` and `prototype/effects/effects.py`. I want
   > a new effect: **[describe it / "make it look like this" + attach a reference image or link /
   > "port this code:" + paste]**. Build it as a pure effect function following the contract,
   > add a wrapper + entry to `prototype/palette.py` as a **[still | living]** effect, and run
   > `prototype/effects/validate_effect.py <name>` until it prints PASS. Keep render under ~1s at
   > 1024px and memory bounded (no float32 stack of the whole burst). Show me the preview-rig
   > result before we commit.

3. Let Claude iterate against `validate_effect.py` and the preview rig. Review the rendered
   output, refine ("make the dots bigger", "more contrast", "B&W not color"), repeat.
4. When you're happy, have Claude open a PR (§8).

Give Claude the **reference** (image/link/description) and the **constraint** ("per the
contract / under the perf budget") — it has everything else from this guide and the existing
effects.

## 8. Submit

```bash
git checkout -b effect/<name>
# (effect in effects.py + entry in palette.py committed)
git push -u origin effect/<name>
```
Open a PR. The owner reviews (re-runs `validate_effect.py` on the Pi for the real perf number,
checks the look), merges, and `prototype/deploy.sh` ships it to the gallery. Done.
