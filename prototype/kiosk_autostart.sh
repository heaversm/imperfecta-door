#!/bin/sh
# Imperfecta gallery kiosk launcher.
# Deployed to ~/.config/labwc/autostart on the Pi — labwc runs this on login.
# The Pi auto-logs into the labwc (Wayland) session, so this fires on every boot.
#
# Launches Chromium IMMEDIATELY at a local black loading page (file://) so the Pi
# desktop is never visible during boot. That page polls the effects server and
# navigates to the live viewer the instant it's ready — so there's no fixed wait
# and no connection-refused race (the old "wait 30s then launch and hope" left
# Chromium stuck on a dead page if the Pi 3B+ booted slowly).
#
#   --password-store=basic         → never prompt for the GNOME keyring
#   --kiosk                        → fullscreen, no chrome
#   --incognito                    → no profile cruft / "restore pages" bubble
#   --allow-file-access-from-files → let the local loading page reach the server
#   --check-for-update-interval huge → no update nags during an exhibit
chromium \
  --kiosk \
  --password-store=basic \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  --incognito \
  --allow-file-access-from-files \
  "file:///home/imperfecta/kiosk_loading.html" &
