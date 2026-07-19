#!/usr/bin/env python3
"""Validate an effect against the gallery guardrails.

Usage:  python3 validate_effect.py <effect_function_name>   (run from prototype/effects/)
Checks: returns an RGB PIL Image at the input size; render time vs budget; peak Python memory.

Caveat: run on a Mac this is a SANITY check — the Mac is ~3-4x faster than the Pi 3B+ and
tracemalloc undercounts numpy's C allocations. The real perf gate is running this ON THE PI
at PR review. A memory-thrashing effect also shows up as slow, so the time check is the
effective guardrail.
"""
import importlib
import sys
import time
import tracemalloc

from PIL import Image

WORK = (1024, 576)
N = 30
TIME_WARN_MS = 1000
TIME_FAIL_MS = 3000
MEM_WARN_MB = 150


def make_burst():
    # Synthetic shifting gradient so temporal effects see "motion".
    return [Image.new("RGB", WORK, ((i * 8) % 256, (i * 5) % 256, 128)) for i in range(N)]


def main():
    if len(sys.argv) not in (2, 3):
        print("usage: python3 validate_effect.py <effect_name> [module]  (default module: effects)")
        sys.exit(2)
    name = sys.argv[1]
    module_name = sys.argv[2] if len(sys.argv) == 3 else "effects"
    mod = importlib.import_module(module_name)
    fn = getattr(mod, name, None)
    if not callable(fn):
        print(f"FAIL: {module_name}.{name} not found / not callable")
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
