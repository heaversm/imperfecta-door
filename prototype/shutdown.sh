#!/bin/bash
# Safe power-off for the imperfecta Pi. Deployed to ~/shutdown on the Pi.
# Passwordless via /etc/sudoers.d/010-poweroff (poweroff/reboot/shutdown only).
#
# ALWAYS use this (or `sudo poweroff`) instead of pulling the plug — yanking power
# while the Pi is running can corrupt the SD card (that's what killed the first one).
# Wait for the green activity LED to go dark before unplugging.
sudo poweroff
