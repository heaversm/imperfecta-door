#!/usr/bin/env python3
"""Sniff 433MHz RF signals using rpi_rf. Press doorbell to capture code."""

import time
from rpi_rf import RFDevice

rf = RFDevice(17)
rf.enable_rx()
print("Listening on GPIO17 — press doorbell button")
print("Ctrl+C to stop\n")

timestamp = None
try:
    while True:
        if rf.rx_code_timestamp != timestamp:
            timestamp = rf.rx_code_timestamp
            print(f"Code: {rf.rx_code}  Pulse: {rf.rx_pulselength}  Protocol: {rf.rx_proto}")
        time.sleep(0.01)
except KeyboardInterrupt:
    print("\nDone")
finally:
    rf.cleanup()
