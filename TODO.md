# Imperfecta TODO

## ~~1. Run entirely on Pi (eliminate Mac from chain)~~ DONE

BG removal now runs on Pi via Replicate cloud API (`cjwbw/rembg`). Gallery served from Pi at `http://10.0.0.206:5050/`. Both services auto-start on boot via systemd (`orchestrator.service`, `bg_removal.service`). No Mac needed.

## ~~2. Doorbell trigger~~ DONE

Triggering on **433MHz RF burst envelope detection** (no bit decoding) as of 2026-04-29.

The Avantek D3-B uses a proprietary RF protocol that we couldn't decode reliably. Instead, we fingerprint the burst envelope — the Pi notices that *any* burst with the Avantek's shape happened. Since we have a 433MHz receiver wired to GPIO17 already, and we don't actually need to read the bits — we just need to know a press happened.

**Wiring (current):** RX470C-V01 module on the Pi
- Receiver pin 2 (GND) → Pi pin 6
- Receiver pin 3 (VIN) → Pi pin 4 (5V)
- Receiver pin 4 (DATA) → Pi pin 11 (GPIO17)
- Receiver pin 1 (ANT) → soldered coil antenna (32cm spiral)

**How it works:** orchestrator.py `run_rf_loop()` watches GPIO17 edge events, splits into bursts on a sync gap, and triggers when a burst envelope falls in the calibrated Avantek range.

**Calibrated thresholds (see config in orchestrator.py):**
- 250 ≤ edges ≤ 500 (Avantek presses run 329-343)
- 150ms ≤ duration ≤ 400ms (Avantek presses run 237-252ms)

The upper bound rejects a periodic 433MHz transmitter in the area (likely a neighbor's weather sensor) that fires every 57s at ~909 edges / ~950ms. Below-range and above-range bursts get logged as `RF burst REJECTED` for debugging.

**Site layout: zero exterior wiring.** The doorbell is the existing Avantek, untouched. Owner notification still works through the Avantek's own plug-in chime. No FSR, no copper tape, no microswitch — the receiver lives indoors on the Pi and intercepts the existing doorbell's own RF transmission.

**Diagnostic tooling:** `prototype/rf_burst_probe.py` is the standalone calibration script — stop the orchestrator, run the probe, press the doorbell N times, observe burst signatures. Useful if the calibration ever drifts (different doorbell, new periodic noise source) and the thresholds need re-tuning.

### Site layout plan (draft)

**Outdoor (vestibule):**
- If FSR: FSR on doorbell + wire run indoors
- If RF: nothing needed outside (receiver lives on the Pi indoors)
- MaixCam: test shooting through entryway window from inside first (see #7)

**Indoor (gallery):**
- Raspberry Pi (runs orchestrator + bg removal server)
- Dig-Quad + 12V PSU (drives LED strips)
- LED strips in diffuser tubing (mounted on metal beams)
- Display monitor in narrow entryway window (shows gallery)
- All power/networking
- If RF: 433MHz receiver module on Pi

**Zero-exterior-wire dream:** RF trigger + MaixCam shooting through window from inside = no exterior components at all except the existing doorbell and LED tubing.

## 3. LED tubing test

Test the LED strip inside diffuser tubing to validate the visual effect. The current blocker is that the strip has a connector on the end that's too wide to feed through the tubing. Options: desolder the connector and re-attach after threading, cut the connector off and solder new leads, or find tubing with a wider opening. This is a hands-on fabrication task.

## 4. Wire up 4 LED strands (2x2 parallel with extensions)

The final installation needs 4 LED strands total: 2 pairs running in parallel, each pair connected via an extension strip. This means configuring the Dig-Quad's multiple outputs and making sure WLED addresses all 4 strands correctly (segment config in WLED). Physical wiring: each Dig-Quad output drives 2 strips daisy-chained with an extension cable between them.

### Linking strips together
Current strips are WS2815 60 LED/m with **3-pin JST-SM connectors** (+12V, Data, GND). Backup data (BO/BI) is on the PCB but not in the connector. To link two 16.4ft (5m) strips into one 32ft strand:
- **Pre-installed connectors:** Plug the male JST-SM output end of strip 1 into the female input end of strip 2. Check that the arrow direction (data flow) is consistent — DO end of strip 1 → DI end of strip 2. If upgrading to 96 LED/m, verify new strips also use JST-SM so connectors are compatible.
- **Power injection at the join:** For a 10m run at 96 LED/m (960 LEDs), you'll likely need to inject 12V power at the connection point (or at least at the far end). The pre-installed connectors carry power too, but voltage drop over 10m causes dimming at the far end. Run a separate 12V/GND wire pair from the PSU to the midpoint or far end.
- **At 60 LED/m** (600 LEDs per strand, ~10.8A full white): at partial brightness (~30-40% warm amber), current drops to ~3-4A. At that level, connectors alone may be sufficient — try without injection first. If the far end looks dimmer or color-shifts, add injection at the join. Amber (mostly red) holds up better over distance than blue/green.
- **At 96 LED/m** (960 LEDs per strand): 60% more current draw — injection at the midpoint/far end becomes much more important.
- **If connectors don't match:** Cut the connectors, solder or use 3-pin JST pigtails. Strip-to-strip extension cables are also available (~$3-5 for a pack).

### Mounting LED channels to metal beams

The gallery has metal beams. Need a non-permanent mounting solution for the diffuser tubing/channels. Options:
- **Magnetic clips/hooks:** Neodymium magnet clips or magnetic cable clips — snap onto metal beams, hold the tubing. Completely non-permanent, repositionable. Easy to find in various sizes.
- **Magnetic tape:** Adhesive-backed flexible magnetic strip stuck to the back of the diffuser channel. Sticks to the beams directly. Less hold strength than neodymium but very low profile.
- **Neodymium disc magnets + zip ties:** Magnets sit on the beam, zip ties wrap around the tubing and the magnet. Ugly but strong and cheap.
- **3M Command strips (outdoor):** Adhesive strips rated for metal surfaces, removable without residue. Less repositionable than magnets but very clean look.
- **Spring/tension clamps:** Small metal spring clamps that grip the beam flange. Work well on I-beams or angle iron.

**Recommendation:** Magnetic clips or neodymium disc magnets — strongest hold on metal, fully non-permanent, easy to adjust during install.

## ~~5. Photo filter / funhouse effect~~ DONE

Funhouse distortion (wave + barrel/bulge) applied in bg_removal_server.py using PIL/numpy. Randomized parameters per image (0 to max for wave amplitude, frequency, and bulge strength). Gallery layout uses overlapping, slightly rotated faces.

## ~~6. Wi-Fi resilience~~ DONE

Three layers: NetworkManager infinite retries (`autoconnect-retries 0`), wifi_watchdog.sh cron (pings every minute, toggles radio if down), wifi_switch.sh for easy network changes. See TESTING_PLAYBOOK.md Wi-Fi Resilience section.

## 7. Camera placement

**Test first:** Can the MaixCam shoot through the entryway window from inside and still detect faces at the doorbell? Hold the MaixCam up to the window from inside, have someone stand at the doorbell, check if faces register. If yes, mount it inside (no weatherproofing needed, just a USB-C power cable to a nearby outlet).

**If window doesn't work:** Mount in vestibule. MaixCam has Wi-Fi (already talks to Pi wirelessly). Only needs 5V USB-C power — run a USB-C cable/extension from an indoor outlet. Fabricate or buy a small angled mount/case. Consider weatherproofing if exposed.

## 8. Display monitor for gallery

Find a monitor to display the photo gallery in the narrow window at the side of the entryway. Considerations: physical dimensions (must fit the narrow window), orientation (likely portrait), input (HDMI from Pi or a dedicated cheap device running the browser), and how to hide cables/power.

## 9. Venue-switch friction reduction (post-2026-05-01 gallery trip)

The first gallery install required ~3 hours of troubleshooting that should have been near-zero. Capturing the remaining work to make "show up and switch" the actual reality.

### 9a. Verify mDNS resolution from the Pi (device-dependent)

`orchestrator.py` now uses mDNS hostnames (`maixcam-288c.local`, `wled-dig-quad-v3.local`) by default. Verify these resolve from the Pi:

```bash
ssh imperfecta-pi-gallery "getent hosts maixcam-288c.local; getent hosts wled-dig-quad-v3.local"
```

If they don't resolve, the Pi needs `nss-mdns` (Debian: `sudo apt install libnss-mdns`) and avahi-daemon running. If installing isn't an option, override at startup with `MAIXCAM_HOST=<ip> WLED_HOST=<ip>` env vars on the orchestrator service unit.

### 9b. Set WLED's backup network (device-dependent)

WLED's web UI has two Wi-Fi slots — primary and backup. Today only the primary (`imperfecta 5/2.4`) is set. Browse to `http://wled-dig-quad-v3.local/settings/wifi` and fill in the backup as `VIRUSDETECTED` / `ifyaknowyakn0w!`. Then WLED auto-rejoins at home without the AP-mode dance.

### 9c. Strip hardcoded Wi-Fi from MaixCam `face_capture_server/main.py` (device-dependent)

`/maixapp/apps/face_capture_server/main.py` on the MaixCam has `WIFI_SSID = "VIRUSDETECTED"` / `WIFI_PASSWORD = ...` hardcoded. Wi-Fi is now handled at the system level via `/boot/wpa_supplicant.conf`, so the in-app `connect_wifi()` should be removed (or short-circuit when an IP already exists, which it already does — but the hardcoded creds are stale and misleading).

### 9d. Update home IP for the Pi (device-dependent, do once back home)

The Pi at home was `10.0.0.206`. Confirm next time you're home and the Pi auto-rejoins `VIRUSDETECTED`. Update `~/.ssh/config` `imperfecta-pi` HostName if DHCP gives it a different address.

### 9e. Pre-flight protocol (process)

Before each venue trip:
1. Pre-program any new venue's Wi-Fi creds on all 3 devices (drop into `/boot/wpa_supplicant.conf` on Pi + MaixCam, set as backup network on WLED).
2. At the venue, power on all 3 devices, wait 60s.
3. Run `prototype/smoke_test.sh` from the Mac. PASS = ready. FAIL = drill into whatever it flagged.

This replaces the multi-page runbook for the 80% case.
