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

# Force the panel's native 1024x600. Its EDID reads null, so without this the Pi defaults
# to 1024x768 and the 1024x600 panel mis-scales it (off-center / black bars on the glass).
wlr-randr --output HDMI-A-1 --custom-mode 1024x600@60 2>/dev/null || true

# Which experience to show. 'effects' (default) = viewer.html slideshow;
# 'melt' = the facecapture app. Flip with:  echo melt > ~/display_mode  (then relaunch).
MODE="$(cat /home/imperfecta/display_mode 2>/dev/null || echo effects)"

# --use-fake-ui-for-media-stream auto-accepts the getUserMedia camera prompt using
# the REAL default device (the C920) — needed for the melt mode's live preview in a
# headless kiosk. Harmless in effects mode (no getUserMedia there).
chromium \
  --kiosk \
  --password-store=basic \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  --incognito \
  --allow-file-access-from-files \
  --use-fake-ui-for-media-stream \
  "file:///home/imperfecta/kiosk_loading.html?mode=${MODE}" &
