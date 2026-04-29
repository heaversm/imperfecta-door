#!/usr/bin/env python3
"""
RF burst probe — characterizes 433MHz bursts on GPIO17 without decoding.

Goal: fingerprint the Avantek doorbell's RF burst envelope (edge count, duration,
gap timing histogram) so we can later detect "the doorbell was pressed" without
trying to read the actual bits (which we already know we can't decode).

Does NOT touch orchestrator.py.

Prereqs:
  - Stop the orchestrator first so GPIO17 is free:
      ssh imperfecta-pi "sudo systemctl stop orchestrator"
  - RX470C-V01 receiver wired (VIN→5V, GND→GND, DATA→GPIO17, antenna soldered)

Usage:
  ssh imperfecta-pi "python3 ~/rf_burst_probe.py"

How to interpret output:
  - Press the Avantek doorbell 5+ times. Each press should print one burst line.
  - Avantek bursts (from earlier debugging) should look like:
      edges=~150-200, dur=~200-300ms, two gap peaks near 850us and 1800us
  - Let it run with no presses for ~10 min to record any ambient noise bursts.
  - Press Ctrl+C to stop. Summary sorts all bursts by edge count.

If Avantek bursts cluster cleanly and stand out from ambient — we have a
fingerprint we can use. Share the output with the next step.
"""

import time
import gpiod
from gpiod.line import Direction, Bias, Edge

GPIO_PIN = 17
SYNC_GAP_US = 5000      # gap > this = end of burst (between presses, or noise lull)
MIN_BURST_EDGES = 8     # ignore tiny noise blips in live output

AVANTEK_PEAK_SHORT_US = 850
AVANTEK_PEAK_LONG_US = 1800
AVANTEK_PEAK_TOL_US = 300

config = gpiod.LineSettings(
    direction=Direction.INPUT,
    bias=Bias.PULL_DOWN,
    edge_detection=Edge.BOTH,
)
request = gpiod.request_lines(
    "/dev/gpiochip0",
    consumer="rf_burst_probe",
    config={GPIO_PIN: config},
    event_buffer_size=4096,
)

print(f"Listening on GPIO{GPIO_PIN} for RF bursts.")
print("Press the Avantek 5+ times, then let it run ~10 min for ambient noise.")
print("Ctrl+C to stop and print summary.\n")

last_time_ns = None
current_gaps_us = []
current_start_ns = None
all_bursts = []  # (start_ns, edges_count, duration_us, gaps_us)


def is_avantek_like(gaps_us):
    """True if gaps cluster near both Avantek peaks (~850us and ~1800us)."""
    near_short = sum(1 for g in gaps_us if abs(g - AVANTEK_PEAK_SHORT_US) < AVANTEK_PEAK_TOL_US)
    near_long = sum(1 for g in gaps_us if abs(g - AVANTEK_PEAK_LONG_US) < AVANTEK_PEAK_TOL_US)
    return near_short >= 10 and near_long >= 10


def end_burst():
    global current_gaps_us, current_start_ns
    if len(current_gaps_us) < MIN_BURST_EDGES:
        current_gaps_us = []
        return
    edges = len(current_gaps_us)
    duration_ms = sum(current_gaps_us) // 1000
    avantek_like = is_avantek_like(current_gaps_us)
    tag = "  *** AVANTEK-LIKE ***" if avantek_like else ""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] burst: edges={edges:>4}  dur={duration_ms:>4}ms{tag}")
    all_bursts.append((time.time(), edges, duration_ms, list(current_gaps_us)))
    current_gaps_us = []


try:
    while True:
        for event in request.read_edge_events(max_events=1024):
            now_ns = event.timestamp_ns
            if last_time_ns is None:
                last_time_ns = now_ns
                continue
            gap_us = (now_ns - last_time_ns) // 1000
            last_time_ns = now_ns

            if gap_us >= SYNC_GAP_US:
                end_burst()
                current_start_ns = now_ns
            else:
                if not current_gaps_us:
                    current_start_ns = now_ns
                current_gaps_us.append(gap_us)

except KeyboardInterrupt:
    end_burst()
    print(f"\n--- Summary: {len(all_bursts)} bursts ---")
    sorted_bursts = sorted(all_bursts, key=lambda b: b[1], reverse=True)
    for ts, edges, duration_ms, gaps in sorted_bursts[:50]:
        avantek = is_avantek_like(gaps)
        # bin gap timings into 200us buckets, show top 4 buckets
        hist = {}
        for g in gaps:
            b = (g // 200) * 200
            hist[b] = hist.get(b, 0) + 1
        top = sorted(hist.items(), key=lambda kv: -kv[1])[:4]
        top_str = ", ".join(f"{b}us:{c}" for b, c in top)
        tag = "  *** AVANTEK-LIKE" if avantek else ""
        ts_str = time.strftime("%H:%M:%S", time.localtime(ts))
        print(f"  {ts_str}  edges={edges:>4}  dur={duration_ms:>4}ms  top: {top_str}{tag}")
    print()
    avantek_count = sum(1 for _, _, _, g in all_bursts if is_avantek_like(g))
    other_count = len(all_bursts) - avantek_count
    print(f"AVANTEK-LIKE bursts:  {avantek_count}")
    print(f"OTHER bursts (noise): {other_count}")
    if avantek_count > 0:
        print("Looks promising — Avantek-like bursts have a recognizable shape.")
        print("Note the typical edges + dur for AVANTEK-LIKE rows; that's our threshold.")
    else:
        print("No Avantek-like bursts detected. Check wiring and try pressing harder/closer.")
finally:
    request.release()
