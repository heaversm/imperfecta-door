#!/usr/bin/env python3
"""Debug script to check if GPIO17 is receiving any signal from the RF module.
Press the doorbell button while this runs. Should see ACTIVE values if wiring is correct."""

import gpiod
from gpiod.line import Direction, Bias, Value
import time

print("Reading GPIO17 for 10 seconds — press the doorbell now...")

with gpiod.request_lines(
    "/dev/gpiochip0",
    consumer="rf_debug",
    config={17: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_DOWN)},
) as req:
    for _ in range(200):
        val = req.get_value(17)
        print("1" if val == Value.ACTIVE else "0", end="", flush=True)
        time.sleep(0.05)

print("\nDone. All 0s = no signal reaching Pi (check wiring). Mixed = signal detected.")
