#!/usr/bin/env python3
"""
Test script for EV1527 button. Does NOT touch orchestrator.py.
Run this, press your button 5+ times, confirm code is identical every time.
Then copy the code + pulse into orchestrator.py.

Usage:
  ssh imperfecta-pi "sudo systemctl stop orchestrator && python3 ev1527_test.py"
"""

import time
from rpi_rf import RFDevice

GPIO_PIN = 17

print(f"Listening on GPIO{GPIO_PIN} for EV1527 button presses")
print("Press your button 5+ times — codes should be IDENTICAL each time")
print("Ctrl+C when done\n")

rf = RFDevice(GPIO_PIN)
rf.enable_rx()

timestamp = None
seen_codes = []

try:
    while True:
        if rf.rx_code_timestamp != timestamp:
            timestamp = rf.rx_code_timestamp
            code = rf.rx_code
            pulse = rf.rx_pulselength
            proto = rf.rx_proto
            seen_codes.append(code)

            consistent = len(set(seen_codes)) == 1
            status = "✓ CONSISTENT" if consistent else f"!! {len(set(seen_codes))} different codes seen"

            print(f"Press {len(seen_codes):>3}: Code={code:<12} Pulse={pulse}  Protocol={proto}  {status}")

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n--- Summary ---")
    if not seen_codes:
        print("No codes received. Check wiring and antenna.")
    elif len(set(seen_codes)) == 1:
        print(f"✓ GOOD: Consistent code across all {len(seen_codes)} presses")
        print(f"\nAdd these to orchestrator.py:")
        print(f"  RF_DOORBELL_CODE = {seen_codes[0]}")
        print(f"  RF_PULSELENGTH   = {rf.rx_pulselength}")
    else:
        print(f"!! Multiple codes seen: {set(seen_codes)}")
        print("Button may not be EV1527 or interference is corrupting reads.")
finally:
    rf.cleanup()
