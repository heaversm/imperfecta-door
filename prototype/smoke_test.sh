#!/bin/bash
# Pre-flight health check for Imperfecta install.
# Run from your Mac (must be on same Wi-Fi as the devices).
# Verifies all 3 devices are reachable and their HTTP endpoints respond.
#
# Usage:
#   ./smoke_test.sh
# Override hosts if mDNS isn't working:
#   PI_HOST=10.1.10.206 MAIXCAM_HOST=10.1.10.14 WLED_HOST=10.1.10.221 ./smoke_test.sh

set -u

PI_HOST="${PI_HOST:-imperfecta-pi3.local}"
MAIXCAM_HOST="${MAIXCAM_HOST:-maixcam-288c.local}"
WLED_HOST="${WLED_HOST:-wled-dig-quad-v3.local}"

PASS=0
FAIL=0

check() {
  local label="$1"
  local cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "  PASS — $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL — $label"
    FAIL=$((FAIL + 1))
  fi
}

check_http() {
  local label="$1"
  local url="$2"
  local code
  code=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "  PASS — $label (HTTP $code)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL — $label (HTTP $code)"
    FAIL=$((FAIL + 1))
  fi
}

echo "Imperfecta pre-flight check"
echo "  Pi:       $PI_HOST"
echo "  MaixCam:  $MAIXCAM_HOST"
echo "  WLED:     $WLED_HOST"
echo

echo "Reachability:"
check "Pi reachable"      "ping -c 1 -W 2000 $PI_HOST"
check "MaixCam reachable" "ping -c 1 -W 2000 $MAIXCAM_HOST"
check "WLED reachable"    "ping -c 1 -W 2000 $WLED_HOST"

echo
echo "HTTP endpoints:"
check_http "MaixCam capture API"     "http://$MAIXCAM_HOST:8080/photo"
check_http "WLED JSON info"          "http://$WLED_HOST/json/info"
check_http "Pi gallery page"         "http://$PI_HOST:5050/"
check_http "Pi bg_removal /faces"    "http://$PI_HOST:5050/faces"

echo
echo "Pi services (via SSH):"
PI_SSH="${PI_SSH:-imperfecta-pi-gallery}"
ssh -o ConnectTimeout=5 -o BatchMode=yes "$PI_SSH" "true" 2>/dev/null && {
  check "orchestrator service running" "ssh -o ConnectTimeout=5 $PI_SSH 'systemctl is-active orchestrator | grep -q active'"
  check "bg_removal service running"   "ssh -o ConnectTimeout=5 $PI_SSH 'systemctl is-active bg_removal | grep -q active'"
} || echo "  SKIP — SSH to $PI_SSH not configured (set PI_SSH=<ssh-alias>)"

echo
echo "─────────────────────"
echo "PASS: $PASS    FAIL: $FAIL"
[ $FAIL -eq 0 ] && exit 0 || exit 1
