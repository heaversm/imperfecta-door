# Effect Contributor Onboarding — Design

**Date:** 2026-06-23
**Status:** Design approved, pending spec + plan review

## Context

An experienced developer (a friend) will contribute new visual effects to the Imperfecta
gallery loop. The effects system is already built for this: each effect in
`prototype/effects/effects.py` is a **pure function** (burst of PIL Images → one PIL Image)
with no I/O or global state, and the same module already runs on both the Pi and the Mac
preview rig. So no new infrastructure is needed — this is a *documentation + lightweight
guardrail* task so the contributor knows the contract, how to develop solo, how to tie an
effect into the loop, and what bar an effect must clear before it ships to the wall.

Integration is **PR-based** (or a direct code copy). The contributor needs no access to the
gallery hardware: he develops against his own laptop webcam via the existing preview rig.

### Goals
- A contributor can build, preview, and validate an effect entirely on his own machine.
- "Tying in" a finished effect is a 2-line change he can make confidently.
- Clear guardrails protect the live gallery (perf, memory, purity) — nothing he writes can
  silently break the unattended display.
- Minimal: docs + a template + an optional check script. No registry/sandbox infrastructure.

### Non-goals
- No auto-registration / plugin-discovery system (PR review is the gate).
- No separate sandbox repo (he works in this repo on a branch).
- No changes to the runtime effect architecture.

## The effect contract

```python
@_timed
def my_effect(frames: list[Image.Image]) -> Image.Image: ...
```
- **Input:** `frames` — the burst, a list of equal-size RGB PIL Images (newest last).
- **Output:** one RGB PIL Image, same dimensions as the input frames.
- **Pure:** no file/network I/O, no global mutation. `@_timed` wraps it so callers receive
  `(image, elapsed_ms)`; they use `effects.my_effect(frames)[0]`.
- **Reusable helpers** in `effects.py`: `_stack`, `_middle_frame`, `_bw_treatment`,
  `_numpy_remap`, `_halftone_dots`, `_duotone`.
- **Single-frame vs temporal:** single-frame effects pull `_middle_frame(frames)`; temporal
  effects use the whole burst. An effect that renders cleanly from one frame can also be a
  "living" (animated) effect.

## Develop-solo loop (no gallery hardware)

`prototype/effects/preview_rig.py` captures a short burst from the contributor's **own
laptop webcam** and renders the effect palette in a browser. Loop: clone → run preview rig →
iterate → see the effect live. The preview rig must render the live palettes (see plan) so a
tied-in effect appears in preview automatically.

## Tie-in (2 lines)

In `effects_server.py`: add a thin wrapper and one entry to a palette.
- `STILL_PALETTE` — rendered once per ring (a still).
- `ANIM_PALETTE` — a "living" clip; must render cleanly from a single frame and be cheap.

## Guardrails / acceptance criteria

1. **Contract:** pure function as above; RGB Image out, same size as input.
2. **Performance:** target **< ~1s render at 1024px** on a Pi 3B+; effects sum per ring, so
   cheaper is better. **~3s is the hard ceiling** (set by hockney). Living effects should be
   well under, since they render N frames.
3. **Memory:** **bounded** — never build a float32 stack of all ~30 frames at 1024px (~200MB
   → swaps the 1GB Pi to death; this was a real bug in `echo`). Accumulate incrementally.
4. **Seeded randomness:** if the effect uses `random`/`np.random`, accept a `seed` param so
   living-effect animations stay stable frame-to-frame.
5. **Dependencies:** stdlib + `numpy` + `Pillow` only. No new dependencies without a heads-up.

## Contribution flow

Branch → add the effect (`effects.py`) + tie-in (`effects_server.py`) → verify in the
preview rig and with `validate_effect.py` → open a PR → owner reviews (perf + taste) →
merge → `prototype/deploy.sh` ships it to the Pi.

## Deliverables

1. **`prototype/effects/CONTRIBUTING-EFFECTS.md`** — the contract, helpers, dev loop, tie-in,
   guardrails, and PR flow. The single doc a contributor reads.
2. **`prototype/effects/effect_template.py`** — a commented, working template effect to copy.
3. **`prototype/effects/validate_effect.py`** — runs a named effect against a sample/synthetic
   burst and checks: returns an RGB image, correct size, render time vs budget, and a rough
   memory ceiling. The automated guardrail; runnable by the contributor and at PR review.
4. **Preview-rig wiring** — ensure `preview_rig.py` renders the current `STILL_PALETTE` +
   `ANIM_PALETTE` so a tied-in effect shows in preview without separate wiring.

## Verification
- A new effect built from the template, validated by `validate_effect.py`, previewed in the
  rig, tied into a palette, and shown in the gallery loop after `deploy.sh` — start to finish
  using only the docs.
- `validate_effect.py` correctly flags a deliberately too-slow or too-memory-hungry effect.
