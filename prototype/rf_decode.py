#!/usr/bin/env python3
"""
Capture full doorbell burst, split at internal sync gaps, decode repeating code.
Avantek D3-B: ~850us='0', ~1800us='1', inter-rep sync ~3800us.
"""

import gpiod
from gpiod.line import Direction, Bias, Edge

GPIO_PIN = 17
RF_SYNC_MIN_US = 4500       # only triggers between full presses
RF_INTER_REP_US = 2500      # split burst into repetitions at gaps >= this
RF_BIT_THRESHOLD_US = 1300  # midpoint 850/1800
RF_EXPECTED_BITS = 32

config = gpiod.LineSettings(
    direction=Direction.INPUT,
    bias=Bias.PULL_DOWN,
    edge_detection=Edge.BOTH,
)
request = gpiod.request_lines(
    "/dev/gpiochip0",
    consumer="rf_decode",
    config={GPIO_PIN: config},
    event_buffer_size=512,
)

print(f"Listening on GPIO{GPIO_PIN} — press doorbell\n")

last_time_ns = None
rising_us = []
in_burst = False
press_num = 0

def decode_gaps(gaps):
    return "".join("1" if g >= RF_BIT_THRESHOLD_US else "0" for g in gaps)

def split_repetitions(gaps):
    """Split gap list at inter-repetition sync boundaries."""
    reps = []
    current = []
    for g in gaps:
        if g >= RF_INTER_REP_US:
            if len(current) >= RF_EXPECTED_BITS - 3:
                reps.append(current[:RF_EXPECTED_BITS])
            current = []
        else:
            current.append(g)
    if len(current) >= RF_EXPECTED_BITS - 3:
        reps.append(current[:RF_EXPECTED_BITS])
    return reps

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
                if len(rising_us) >= RF_EXPECTED_BITS:
                    press_num += 1
                    reps = split_repetitions(rising_us)
                    codes = [decode_gaps(r) for r in reps]
                    print(f"\nPress {press_num}: {len(rising_us)} edges, {len(reps)} repetitions")
                    for i, code in enumerate(codes):
                        print(f"  rep {i+1}: {code}")
                    if len(set(codes)) == 1:
                        print(f"  *** CONSISTENT CODE: {codes[0]} ***")
                    elif codes:
                        # find most common
                        from collections import Counter
                        most_common = Counter(codes).most_common(1)[0][0]
                        print(f"  Most common: {most_common} ({Counter(codes)[most_common]}/{len(codes)} reps)")
                rising_us = []
                in_burst = True
            elif in_burst and event.event_type.name == "RISING_EDGE":
                rising_us.append(gap_us)

except KeyboardInterrupt:
    print("\nDone")
finally:
    request.release()
