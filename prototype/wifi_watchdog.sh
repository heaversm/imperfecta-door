#!/bin/bash
# Checks Wi-Fi connectivity every minute via cron.
# If disconnected, forces a reconnect.
# Install: sudo crontab -e → add: * * * * * /home/imperfecta/wifi_watchdog.sh

if ! ping -c 1 -W 5 8.8.8.8 > /dev/null 2>&1; then
    logger "wifi_watchdog: no internet, restarting Wi-Fi"
    nmcli radio wifi off
    sleep 2
    nmcli radio wifi on
fi
