#!/bin/bash
# Deploy the Pi-side runtime: orchestrator + effects server + viewer.
# Override host with: PI_HOST=imperfecta-pi-gallery ./deploy.sh
set -e
PI_HOST="${PI_HOST:-imperfecta-pi}"
SRC=/Users/mheavers/Desktop/imperfecta/_project/prototype

scp "$SRC/orchestrator.py" "$SRC/effects_server.py" "$SRC/palette.py" "$SRC/effects/effects.py" "$PI_HOST":~/
ssh "$PI_HOST" "mkdir -p ~/static"
scp "$SRC/static/viewer.html" "$PI_HOST":~/static/
# Restart both services. -t allocates a TTY so sudo can prompt for the password in your
# terminal (a plain `ssh "host" "sudo ..."` has no TTY and fails with "a password is
# required"). bg_removal.service still has the old unit name.
# Sync the facecapture app source (NOT node_modules — native arm64 modules are built
# on the Pi via `npm install` during setup, see the plan's Task 4).
rsync -a --exclude node_modules --exclude .next \
  "$SRC/../facecapture/container/" "$PI_HOST":~/facecapture/container/

ssh -t "$PI_HOST" "sudo systemctl restart bg_removal orchestrator facecapture"
ssh "$PI_HOST" "systemctl is-active bg_removal orchestrator facecapture"

# Reload the kiosk browser onto the new viewer.html WITHOUT a reboot: wait for the server
# to come back + the viewer to reconnect its SSE, then broadcast a reload event.
ssh "$PI_HOST" "for i in 1 2 3 4 5; do curl -sf http://127.0.0.1:5050/health >/dev/null && break; sleep 1; done; sleep 2; curl -s -X POST http://127.0.0.1:5050/reload >/dev/null && echo 'viewer reload sent'"
