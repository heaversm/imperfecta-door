#!/usr/bin/env python3
"""
RF diagnostic: three stages
  1. Shows ALL bursts (no filter) so you can see if receiver is picking up anything
  2. Marks "clean" bursts (bimodal gaps, 29-35 bits) as CANDIDATE
  3. Marks consecutive identical CANDIDATEs as DOORBELL MATCH
Press doorbell and watch for CANDIDATE / DOORBELL lines.
"""

import gpiod
from gpiod.line import Direction, Bias, Edge

GPIO_PIN = 17
RF_SYNC_MIN_US = 4500
RF_BIT_THRESHOLD_US = 3000
RF_EXPECTED_BITS = 32

config = gpiod.LineSettings(
    direction=Direction.INPUT,
    bias=Bias.PULL_DOWN,
    edge_detection=Edge.BOTH,
)
request = gpiod.request_lines(
    "/dev/gpiochip0",
    consumer="rf_gaps",
    config={GPIO_PIN: config},
    event_buffer_size=512,
)

print(f"Listening on GPIO{GPIO_PIN} — press doorbell\n")
print("Legend: [noise] = background, CANDIDATE = clean OOK burst, DOORBELL = repeated match\n")

last_time_ns = None
rising_us = []
in_burst = False
burst_num = 0
last_candidate = None

def is_clean_ook(gaps):
    """True if gaps are clearly bimodal at ~2000us and ~4000us (no ambiguous values 2500-3500)."""
    if len(gaps) < 29:
        return False
    ambiguous = sum(1 for g in gaps if 2500 < g < 3500)
    zeros = [g for g in gaps if g <= RF_BIT_THRESHOLD_US]
    ones  = [g for g in gaps if g >  RF_BIT_THRESHOLD_US]
    return ambiguous == 0 and len(zeros) > 0 and len(ones) > 0

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
                    gaps32 = rising_us[:RF_EXPECTED_BITS]
                    bits = "".join("1" if g >= RF_BIT_THRESHOLD_US else "0" for g in gaps32)

                    if is_clean_ook(gaps32):
                        zeros = [g for g in gaps32 if g <= RF_BIT_THRESHOLD_US]
                        ones  = [g for g in gaps32 if g >  RF_BIT_THRESHOLD_US]
                        print(f"CANDIDATE #{burst_num} ({len(rising_us)} bits): {bits}")
                        print(f"  '0':{min(zeros)}-{max(zeros)}us  '1':{min(ones)}-{max(ones)}us")
                        if last_candidate == bits:
                            print(f"  *** DOORBELL MATCH: {bits} ***")
                        last_candidate = bits
                    else:
                        print(f"[noise #{burst_num}] {len(rising_us)} bits — {bits[:16]}...")
                        last_candidate = None

                rising_us = []
                in_burst = True
            elif in_burst and event.event_type.name == "RISING_EDGE":
                rising_us.append(gap_us)

except KeyboardInterrupt:
    print("\nDone")
finally:
    request.release()
