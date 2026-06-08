#!/bin/sh
# Imperfecta gallery kiosk launcher.
# Deployed to ~/.config/labwc/autostart on the Pi — labwc runs this on login.
# The Pi auto-logs into the labwc (Wayland) session, so this fires on every boot.

# Wait for the effects server (systemd: bg_removal.service) to be serving
# before opening the browser, so we never land on a connection-refused page.
i=0
while [ $i -lt 30 ]; do
  if curl -sf -o /dev/null http://localhost:5050/; then
    break
  fi
  i=$((i + 1))
  sleep 1
done

# Launch Chromium fullscreen at the gallery.
#   --password-store=basic  → never prompt for the GNOME keyring
#   --kiosk                 → fullscreen, no chrome
#   --incognito             → no profile cruft / "restore pages" bubble
#   --check-for-update-interval huge → no update nags during an exhibit
chromium \
  --kiosk \
  --password-store=basic \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  --incognito \
  "http://localhost:5050/" &
