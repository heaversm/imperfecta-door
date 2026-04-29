#!/usr/bin/env python3
from rpi_rf import RFDevice
rf = RFDevice(17)
rf.enable_rx()
print("rpi_rf working!")
rf.cleanup()
