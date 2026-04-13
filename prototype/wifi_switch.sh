#!/bin/bash
# Switch Pi to a new Wi-Fi network.
# Usage: ./wifi_switch.sh "NetworkName" "password"

if [ $# -lt 2 ]; then
    echo "Usage: $0 SSID PASSWORD"
    exit 1
fi

SSID="$1"
PASS="$2"

echo "Connecting to $SSID..."
nmcli dev wifi connect "$SSID" password "$PASS"

if [ $? -eq 0 ]; then
    echo "Connected. New IP:"
    hostname -I
else
    echo "Failed to connect to $SSID"
    exit 1
fi
