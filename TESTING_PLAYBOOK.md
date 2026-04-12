# Imperfecta Integration Testing Playbook

## Device IPs

| Device | IP | Access |
|--------|-----|--------|
| MaixCam | 10.0.0.14 | Wi-Fi (DHCP). SSH: `ssh root@10.0.0.14` (no password) |
| Raspberry Pi | 10.0.0.206 | `ssh imperfecta-pi` (passwordless via SSH key) |
| WLED / Dig-Quad | 10.0.0.220 | Browser: http://10.0.0.220 |

Note: MaixCam and WLED IPs are DHCP — may change after router reboot. If they stop responding, find them with `dns-sd -B _http._tcp local` or `arp -a | grep 10.0.0`.

## Quick Start

1. **Plug in MaixCam, Dig-Quad, and Pi** — all three auto-start on boot
2. **Mac browser:** `http://10.0.0.206:5050/`
3. **Press the button** with faces visible to MaixCam

Everything runs on the Pi — no Mac terminal needed. BG removal uses Replicate cloud API.

Pi services auto-start via systemd. To manage manually: `ssh imperfecta-pi`, then:
- `sudo systemctl stop/start/status orchestrator`
- `sudo systemctl stop/start/status bg_removal`

## Verification (if something seems wrong)

### MaixCam (should auto-start ~30s after power on)
```
curl -m 10 http://10.0.0.14:8080/capture-all
```

### WLED
```
python3 /Users/mheavers/Desktop/imperfecta/_project/prototype/wled_client.py --host 10.0.0.220 status
```

### BG removal server on Pi
```
ssh imperfecta-pi "curl -s http://localhost:5050/health"
```

## Running the Full Chain

1. Stand in front of the MaixCam (confirm green boxes on MaixCam screen)
2. Press the physical button on the Pi (GPIO17, wired via breadboard)
3. **Expected sequence:**
   - Pi console: `Button pressed!` → `Detected N face(s)` → `Captured full frame` → `Background removal done`
   - LEDs: Ring Bell animation plays for ~5 seconds, then turns off
   - Gallery: New group photo appears in browser (background removed)
   - LEDs: After 30 seconds of dark, ambient Twinkle starts cycling (30s on, 30s off)
4. Press button again → ambient stops, Ring Bell plays, ambient resumes after

## Individual Component Tests

### MaixCam face detection (from Mac or Pi terminal)
```
curl http://10.0.0.14:8080/capture-all
```

### MaixCam full frame
```
curl http://10.0.0.14:8080/photo --output frame.jpg
```

### WLED Ring Bell preset
```
python3 /Users/mheavers/Desktop/imperfecta/_project/prototype/wled_client.py --host 10.0.0.220 preset --id 1
```

### WLED Ambient preset
```
python3 /Users/mheavers/Desktop/imperfecta/_project/prototype/wled_client.py --host 10.0.0.220 preset --id 2
```

### WLED off
```
python3 /Users/mheavers/Desktop/imperfecta/_project/prototype/wled_client.py --host 10.0.0.220 off
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| MaixCam not responding after boot | Wait 30s. If still nothing, check if IP changed: `dns-sd -B _http._tcp local` |
| Orchestrator shows wrong IPs | Restart service: `ssh imperfecta-pi "sudo systemctl restart orchestrator"` |
| `curl` to MaixCam returns empty faces | Make sure a face is visible to camera (check for green boxes on MaixCam screen) |
| WLED not responding | Check it's powered on. Find IP: `dns-sd -B _http._tcp local` |
| bg removal slow (>5s) | Normal for first request (Replicate cold start). Subsequent requests faster. |
| Gallery not updating | Check browser console for SSE connection. Refresh the page. |
| Button not triggering | Check breadboard wiring: red wire → Pi pin 11 (GPIO17), black wire → Pi pin 9 (GND) |
| Need to update MaixCam script | Plug MaixCam into Mac, push via MaixVision, then `ssh root@10.0.0.14` and run: `cp /tmp/maixpy_run/main.py /maixapp/apps/face_capture_server/main.py` |
| Pi not reachable | Check it's on Wi-Fi. Try `ping 10.0.0.206`. If no response, unplug/replug and wait 30s. |

## File Locations

| File | Location | Runs on |
|------|----------|---------|
| face_capture_multi_server.py | `/Users/mheavers/Desktop/imperfecta/_project/maixcam/face_capture/` | MaixCam (auto-starts on boot) |
| bg_removal_server.py | Source: `/Users/mheavers/Desktop/imperfecta/_project/prototype/`. Pi: `~/bg_removal_server.py` | Pi (Replicate cloud API) |
| orchestrator.py | Source: `/Users/mheavers/Desktop/imperfecta/_project/prototype/`. Pi: `~/orchestrator.py` | Pi |
| deploy.sh | `/Users/mheavers/Desktop/imperfecta/_project/prototype/` | Mac (deploys all Pi files) |
| wled_client.py | Pi: `~/wled_client.py`. Source: `/Users/mheavers/Desktop/imperfecta/_project/prototype/` | Pi / Mac |
| gallery.html | Source: `/Users/mheavers/Desktop/imperfecta/_project/prototype/static/`. Pi: `~/static/gallery.html` | Served by bg_removal_server on Pi |
| bg_removal.service | `/etc/systemd/system/` on Pi | Pi (systemd) |
| orchestrator.service | `/etc/systemd/system/` on Pi | Pi (systemd) |

To deploy all updated files to Pi from Mac:
```
~/Desktop/imperfecta/_project/prototype/deploy.sh
```
(Passwordless — uses SSH key.)

## Config

### orchestrator.py (Pi: `~/orchestrator.py`)

| Setting | Value |
|---------|-------|
| MaixCam IP | `MAIXCAM_IP = "10.0.0.14"` |
| WLED IP | `WLED_IP = "10.0.0.220"` |
| BG server IP | `BG_SERVER_IP = "127.0.0.1"` (localhost — runs on Pi) |
| Ring duration | `WLED_RING_DURATION = 5.0` |
| Ambient interval | `WLED_AMBIENT_INTERVAL = 30.0` |
| Ambient duration | `WLED_AMBIENT_DURATION = 30.0` |
| Ring preset ID | `RING_PRESET_ID = 1` |
| Ambient preset ID | `AMBIENT_PRESET_ID = 2` |
| GPIO pin | `GPIO_PIN = 17` (physical pin 11) |
| Cooldown | `COOLDOWN_SECONDS = 3.0` |

### bg_removal.service (environment)

| Setting | Value |
|---------|-------|
| Replicate API token | Set in `/etc/systemd/system/bg_removal.service` as `Environment=REPLICATE_API_TOKEN=...` |
| Replicate model | `cjwbw/rembg` |

## Architecture

```
[Physical button on Pi GPIO17]
        |
        v
  [Pi orchestrator.py]
        |
        +──→ GET /capture-all ──→ MaixCam (10.0.0.14, Wi-Fi)
        |         |                    checks for faces
        |         v
        |    GET /photo ──→ MaixCam returns full frame JPEG
        |         |
        |         v
        |    POST /remove-bg ──→ Pi bg_removal_server (localhost:5050)
        |                              ──→ Replicate API (cloud)
        |                              saves PNG, pushes SSE
        |                              v
        |                    Browser gallery shows new photo
        |                    (http://10.0.0.206:5050/)
        |
        +──→ POST /json/state ──→ WLED (10.0.0.220)
                                  Ring Bell plays 5s, then off
                                  Then ambient Twinkle cycles
```
