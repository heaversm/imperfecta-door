#!/usr/bin/env python3
"""
RF diagnostic with corrected timing for Avantek D3-B.
Doorbell uses ~850us for '0' and ~1800us for '1', sync ~3800us between reps.
Threshold = 1300us, sync = 3000us.
"""

import gpiod
from gpiod.line import Direction, Bias, Edge

GPIO_PIN = 17
RF_SYNC_MIN_US = 3000       # catches the ~3861us inter-repetition sync
RF_BIT_THRESHOLD_US = 1300  # midpoint between 850us and 1800us
RF_EXPECTED_BITS = 32

config = gpiod.LineSettings(
    direction=Direction.INPUT,
    bias=Bias.PULL_DOWN,
    edge_detection=Edge.BOTH,
)
request = gpiod.request_lines(
    "/dev/gpiochip0",
    consumer="rf_rawdump",
    config={GPIO_PIN: config},
    event_buffer_size=512,
)

print(f"Listening on GPIO{GPIO_PIN} — press doorbell\n")

last_time_ns = None
rising_us = []
in_burst = False
burst_num = 0
last_code = None

try:
    while True:
        for event in request.read_edge_events(max_events=128):
            now_ns = event.timestamp_ns
            if last_time_ns is None:
                last_time_ns = now_ns
                continue

            gap_us = (now_ns - last_time_ns) // 1000
            last_time_ns = now_ns

            if gap_us >= RF_SYNC_MIN_US:
                if len(rising_us) >= RF_EXPECTED_BITS - 3:
                    burst_num += 1
                    gaps = rising_us[:RF_EXPECTED_BITS]
                    bits = "".join("1" if g >= RF_BIT_THRESHOLD_US else "0" for g in gaps)
                    zeros = [g for g in gaps if g < RF_BIT_THRESHOLD_US]
                    ones  = [g for g in gaps if g >= RF_BIT_THRESHOLD_US]
                    clean = (not zeros or max(zeros) < 1300) and (not ones or min(ones) > 1300)

                    if clean and len(zeros) > 0 and len(ones) > 0:
                        match = "*** DOORBELL MATCH ***" if bits == last_code else ""
                        print(f"CANDIDATE #{burst_num} ({len(rising_us)} edges): {bits}  {match}")
                        if zeros: print(f"  '0':{min(zeros)}-{max(zeros)}us  '1':{min(ones)}-{max(ones)}us")
                        last_code = bits
                    else:
                        print(f"[noise #{burst_num}] {len(rising_us)} edges  sync={gap_us}us")
                        last_code = None

                rising_us = []
                in_burst = True
            elif in_burst and event.event_type.name == "RISING_EDGE":
                rising_us.append(gap_us)

except KeyboardInterrupt:
    print("\nDone")
finally:
    request.release()
