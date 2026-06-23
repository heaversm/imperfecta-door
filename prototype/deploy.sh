#!/bin/bash
# Deploy the Pi-side runtime: orchestrator + effects server + viewer.
# Override host with: PI_HOST=imperfecta-pi-gallery ./deploy.sh
set -e
PI_HOST="${PI_HOST:-imperfecta-pi}"
SRC=/Users/mheavers/Desktop/imperfecta/_project/prototype

scp "$SRC/orchestrator.py" "$SRC/effects_server.py" "$SRC/palette.py" "$SRC/effects/effects.py" "$PI_HOST":~/
ssh "$PI_HOST" "mkdir -p ~/static"
scp "$SRC/static/viewer.html" "$PI_HOST":~/static/
# Restart both services. bg_removal.service still has the old unit name; if
# you rename the unit to effects.service later, change this line.
ssh "$PI_HOST" "sudo systemctl restart bg_removal orchestrator && sudo systemctl status --no-pager bg_removal orchestrator | tail -25"
