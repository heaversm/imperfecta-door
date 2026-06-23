#!/usr/bin/env python3
"""Feasibility spike: time each effect at a target render size + report burst fetch.

Run on the Pi:  python3 spike_render.py --host maixcam-288c.local --work 1024 --count 30
Run on the Mac with a local image dir: python3 spike_render.py --dir ./output/<session> --work 1024
"""
import argparse, io, time, zipfile
import requests
from PIL import Image
import effects

EFFECTS = [
    ("slitscan_vertical", lambda f: effects.slitscan_vertical(f)[0]),
    ("echo_max",          lambda f: effects.echo_max(f)[0]),
    ("liquify",           lambda f: effects.liquify(f[len(f)//2])[0]),
    ("hockney_joiner",    lambda f: effects.hockney_joiner(f, rows=3, cols=3)[0]),
    ("warhol",            lambda f: effects.warhol(f)[0]),
    ("lichtenstein",      lambda f: effects.lichtenstein(f)[0]),
    ("mondrian",          lambda f: effects.mondrian(f)[0]),
]


def scale(img, work):
    """Resize so the longest side == work (up OR down) — measures render cost at the
    target work size regardless of source resolution."""
    w, h = img.size
    s = work / max(w, h)
    return img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)


def pull_burst(host, count):
    t0 = time.perf_counter()
    r = requests.get(f"http://{host}:8080/burst?count={count}", timeout=15)
    r.raise_for_status()
    fetch = (time.perf_counter() - t0) * 1000
    frames = []
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for n in sorted(zf.namelist()):
            with zf.open(n) as fh:
                im = Image.open(fh)
                im.load()
                frames.append(im.convert("RGB"))
    decode = (time.perf_counter() - t0) * 1000 - fetch
    return frames, fetch, decode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host")
    ap.add_argument("--dir")
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--work", type=int, default=1024)
    a = ap.parse_args()
    if a.host:
        frames, fetch, decode = pull_burst(a.host, a.count)
        print(f"burst: {len(frames)} frames @ {frames[0].size}, fetch {fetch:.0f}ms, decode {decode:.0f}ms")
    else:
        import glob, os
        paths = sorted(glob.glob(os.path.join(a.dir, "*.jpg")))[:a.count]
        frames = [Image.open(p).convert("RGB") for p in paths]
        print(f"loaded {len(frames)} frames from {a.dir}")
    frames = [scale(f, a.work) for f in frames]
    print(f"work size: {frames[0].size}")
    total = 0.0
    for name, fn in EFFECTS:
        t0 = time.perf_counter()
        img = fn(frames)
        ms = (time.perf_counter() - t0) * 1000
        total += ms
        print(f"  {name:20s} {ms:7.0f}ms  -> {img.size}")
    print(f"TOTAL render (7 effects): {total:.0f}ms")


if __name__ == "__main__":
    main()
