# Imperfecta Gallery Installation Runbook

Step-by-step for moving the system from the home test bench to the gallery, supporting both networks during dev cycles, and common ops during the install. Read top-to-bottom on the day of install.

---

## ⚡ Quick venue switch (CURRENT — supersedes §1–2 below)

> The networking model changed (2026-06): devices are addressed by **mDNS hostname**
> (no more hand-editing IPs), the Pi + MaixCam **auto-join both networks**, and WLED
> is switched with a **script**. The older §1–2 details (AP dance, hardcoded-IP swap,
> "WLED two networks") are stale — use this section.

**Before you leave (while still on the current network):**
```bash
ssh imperfecta-pi '~/wled_switch.sh gallery'   # or 'home' — WLED holds ONE network, so pre-point it
```

**At the venue:** just power everything on.
- **Pi** auto-joins (`VIRUSDETECTED` + `gallery-2.4` both saved).
- **MaixCam** auto-joins (both in `/boot/wpa_supplicant.conf`).
- **WLED** joins whatever `wled_switch.sh` last set.

**Confirm everything's reachable:**
```bash
cd ~/Desktop/imperfecta/_project/prototype && ./smoke_test.sh
```

**Daily ops:**
```bash
ssh imperfecta-pi '~/shutdown'                              # safe power-off (no password prompt)
ssh imperfecta-pi '~/kiosk'                                  # relaunch fullscreen display
ssh imperfecta-pi '~/kiosk stop'                             # close it
ssh imperfecta-pi 'curl -s -X POST http://localhost:5050/trigger'   # fire a capture manually
ssh imperfecta-pi 'sudo journalctl -u orchestrator -f'      # watch doorbell triggers live
```
MaixCam access (through the Pi): `ssh -J imperfecta-pi -i ~/.ssh/id_imperfecta root@<maixcam-ip>`.

**Shutting down:** always use `~/shutdown` (or `sudo poweroff`) and wait for the green LED
to go dark before pulling power. Yanking power while running can corrupt the SD card —
that's what killed the first card. (Until the read-only filesystem is enabled — see Go-live.)

---

## 🚀 Go-live hardening (do these LAST, before the unattended gallery run)

Skip these while actively developing — they make code deploys a two-reboot chore.
Enable them only once the code is stable and the Pi will sit power-cycled by a wall switch.

- [ ] **Read-only filesystem** so pulling the plug can't corrupt the card:
      `sudo raspi-config` → **Performance Options → Overlay File System → enable** → reboot.
      - With it ON, the SD is read-only; `latest.jpg`/logs live in RAM (fine — ephemeral).
      - **To deploy code afterward:** raspi-config → disable overlay → reboot → `deploy.sh` →
        re-enable overlay → reboot. (That's why it's a go-live-only step.)
      - Saved WiFi/presets/config persist (baked into the image); you just can't *add* new
        ones without toggling overlay off.
- [ ] Confirm cold-boot comes straight up into the experience (black → grid), no desktop.
- [ ] Confirm WLED is pointed at the gallery network (`~/wled_switch.sh gallery`).
- [ ] `./smoke_test.sh` all green.

---

## 0. Before you leave home — checklist

- [ ] Pi (with breadboard + RX470C-V01 receiver wired, antenna soldered)
- [ ] Avantek doorbell button + plug-in chime
- [ ] MaixCam + USB-C power cable
- [ ] WLED Dig-Quad + 12V Mean Well PSU + power cord
- [ ] LED strips, diffuser tubing, mounting magnets
- [ ] Laptop with this repo cloned at `/Users/mheavers/Desktop/imperfecta/_project`
- [ ] **Gallery Wi-Fi credentials** (SSID + password) — get these in advance
- [ ] Phone with hotspot as a backup network if gallery Wi-Fi flakes
- [ ] Confirm at home that everything works end-to-end before leaving

You also want to know the gallery's network setup ahead of time:
- Is it open Wi-Fi or WPA2/WPA3?
- Is there client isolation enabled? (some museum networks block device-to-device traffic — fatal for this setup)
- Can you ask the gallery for static IP reservations for the three devices? Helpful but not required.

---

## 1. At the gallery — first-time setup

The Pi, MaixCam, and WLED all need to be on the same network for the system to work. Each switches differently.

### 1a. Switch the Pi to gallery Wi-Fi

Connect the Pi to a monitor + keyboard, OR (if your laptop is on the gallery Wi-Fi already) SSH directly to it via its current IP.

If you're already SSH'd in via your home Wi-Fi (because you brought everything home from somewhere), you can switch from Mac like this:

```bash
ssh imperfecta-pi "~/wifi_switch.sh 'GalleryNetworkName' 'GalleryPassword'"
```

The script uses `nmcli` and adds the new network as a profile. **NetworkManager keeps your old profiles too** — when you go home later and the home SSID is in range again, the Pi auto-reconnects. No reset needed.

After connecting, the Pi prints its new IP. **Write it down** — you'll need it for SSH and for the gallery URL.

If you can't SSH in (because the Pi isn't on a network you can reach), plug a monitor + USB keyboard into the Pi and run the same `~/wifi_switch.sh` command in a local terminal.

### 1b. Switch the MaixCam to gallery Wi-Fi

Same procedure you used to put it on your home Wi-Fi originally. If you've forgotten:
- SSH in via current IP (`ssh root@10.0.0.14`, no password) and edit the Wi-Fi config there, or
- Use whatever on-device UI/setup mode the MaixCam uses

Once it joins the gallery network, find its new IP from the Pi:
```bash
ssh imperfecta-pi "arp -a | grep -i maix" 
# OR
ssh imperfecta-pi "sudo nmap -sn 192.168.x.0/24" # use the gallery subnet
```

Test it:
```bash
ssh imperfecta-pi "curl -m 10 http://NEW_MAIXCAM_IP:8080/capture-all"
```

### 1c. Switch the WLED Dig-Quad to gallery Wi-Fi

> ⚠️ CORRECTED 2026-06: this WLED build holds **only ONE** network (not two). Use the
> `wled_switch.sh` script instead of the AP dance below. The script + the constant mDNS
> name (`wled-dig-quad-v3.local`) is the supported path.

```bash
# Run on the Pi WHILE WLED is still reachable on the current network, then move venues:
ssh imperfecta-pi '~/wled_switch.sh gallery'   # or 'home'
```
WLED reboots and joins that network. Creds live in `~/.venue_wifi.env` on the Pi.

Fallback recovery (if WLED is stranded off-network): power-cycle the Dig-Quad; if it
can't find its saved network it opens `WLED-AP` (password `wled1234`) → browse to
`http://4.3.2.1` → Settings → WiFi to fix it. Find its IP from the Pi:
```bash
ssh imperfecta-pi "for i in \$(seq 1 254); do curl -s --connect-timeout 1 http://10.0.0.\$i/json/info 2>/dev/null | grep -q WLED && echo 10.0.0.\$i; done"
```

### 1d. Update the orchestrator's hardcoded IPs

`prototype/orchestrator.py` has a `LOCATION CONFIG` block near the top with two pre-staged blocks — HOME and GALLERY. To swap locations, **comment one block out and uncomment the other**:

```python
# === LOCATION CONFIG: comment one block, uncomment the other when swapping ===
# --- HOME ---
# MAIXCAM_IP = "10.0.0.14"
# WLED_IP    = "10.0.0.220"
# --- GALLERY ---
MAIXCAM_IP = "192.168.x.y"     # filled in on first gallery trip
WLED_IP    = "192.168.x.z"
# === /LOCATION CONFIG ===
```

The first time you go to the gallery, replace the `<fill in>` placeholders with the actual gallery IPs (find via `ssh imperfecta-pi "arp -a"` after MaixCam and WLED have joined the gallery Wi-Fi). After that first trip the gallery values stay in the file as comments — every subsequent swap is just commenting one block and uncommenting the other.

Then deploy:
```bash
cd /Users/mheavers/Desktop/imperfecta/_project/prototype
./deploy.sh
```

`deploy.sh` scp's the file to the Pi and restarts the service.

**No secrets in this file.** Only LAN IPs go in code. Wi-Fi SSIDs and passwords live only in NetworkManager's encrypted store on the Pi (after you've called `wifi_switch.sh` once); they never enter `orchestrator.py` or any other committed file.

### 1e. Confirm end-to-end

Watch the orchestrator logs:
```bash
ssh imperfecta-pi "sudo journalctl -u orchestrator -f"
```

Press the Avantek doorbell. You should see `RF burst MATCH` → `Button pressed!` → `WLED ring preset 1 activated` → `Captured full frame` → `Background removal done`. If WLED line says "No route to host," the WLED IP is wrong — re-find and re-edit.

Open the gallery in a browser at `http://NEW_PI_IP:5050/`. New face should appear within ~5s of pressing the doorbell.

---

## 2. Supporting both home and gallery Wi-Fi

NetworkManager profiles persist on the Pi. Once you've connected to both networks, **the Pi auto-picks whichever is in range** when it boots. No manual switching needed — bring the Pi home, it joins your home network; bring it to the gallery, it joins the gallery network.

WLED does **NOT** hold two networks (confirmed 2026-06) — switch it with `~/wled_switch.sh home|gallery` on the Pi before moving (see the Quick venue switch section up top).

The MaixCam holds both networks in `/boot/wpa_supplicant.conf` (gallery priority 10, home 5) and auto-joins whichever is in range — no manual switching.

To list the Pi's saved Wi-Fi profiles:
```bash
ssh imperfecta-pi "nmcli connection show"
```

To delete one you no longer want (e.g. an old test network):
```bash
ssh imperfecta-pi "nmcli connection delete 'OldNetworkName'"
```

### Caveat: IPs change between networks

When the Pi moves to a new network it gets a new IP. Same for MaixCam and WLED. The orchestrator's hardcoded IPs need to match the **current** network.

We've handled this with the `LOCATION CONFIG` block at the top of `orchestrator.py` (see section 1d). Both home and gallery IPs are stored side-by-side in the file as comments — swapping is just toggling which block is commented and running `./deploy.sh`.

Long-term alternative if you ever do many round-trips: assign **static IP reservations** by MAC address on both routers (home + gallery). The IPs then never change for either network and the LOCATION CONFIG block becomes unnecessary. Skip this for now since you only expect 2-3 swaps total.

---

## 3. Clearing the gallery of images manually

Captures live at `~/captures/` on the Pi as paired files:
- `original_<timestamp>.jpg` — the raw frame from the MaixCam
- `removed_<timestamp>.png` — the bg-removed face displayed in the gallery

The bg_removal server reads the directory once at startup into an in-memory list, so deleting files alone won't clear the live gallery — you also need to restart the service.

### Clear all images:
```bash
ssh imperfecta-pi "rm -f ~/captures/*.png ~/captures/*.jpg && sudo systemctl restart bg_removal"
```

Refresh the gallery page in your browser — it should be empty.

### Clear only some images (e.g. test photos taken during install):

```bash
# List all captures with timestamps
ssh imperfecta-pi "ls -lh ~/captures/"

# Delete a specific pair (replace timestamp)
ssh imperfecta-pi "rm ~/captures/original_1775853441.jpg ~/captures/removed_1775853441.png"

# Then restart so the in-memory list is refreshed
ssh imperfecta-pi "sudo systemctl restart bg_removal"
```

### Alternative: just nuke the Pi's view, leave files

If you want to keep the originals on disk but reset what visitors see, you'd need a `/clear` endpoint added to `bg_removal_server.py`. None exists today. Easier to just delete the files and restart.

---

## 4. Other things to verify at the gallery

Beyond Wi-Fi swaps, the install has a few moving parts that change physically:

### 4a. Power
- Run a 120V AC outlet to the Pi enclosure
- Run a 120V AC outlet to the LED PSU (Mean Well 12V)
- USB-C from Pi area to MaixCam location
- All cables routed cleanly (cable cover, conduit, or behind trim)

### 4b. Doorbell + chime
- Avantek button mounted at door (existing, just confirm it works)
- Avantek chime plugged in somewhere within range, audible to the gallery owner
- Test: press button → chime rings + Pi triggers (RF range from button to Pi must be sufficient — typically 30+ ft through walls is fine; verify by pressing from the actual door location)

### 4c. WLED + LED strips
- Dig-Quad mounted in enclosure with PSU
- Strips run through diffuser tubing, mounted to the metal beams (TODO #4)
- Power injection at strip ends for long runs (TODO #4)
- WLED preset 1 (Ring Bell) and preset 2 (Ambient) configured — these should already be saved on the Dig-Quad from home testing; if not, see TESTING_PLAYBOOK.md

### 4d. MaixCam placement
- Decide indoor-through-window vs. outdoor mounted (TODO #7)
- Test face detection from the chosen position before committing
- Confirm 5V USB-C power runs to it

### 4e. Display monitor for visitor gallery
- Monitor mounted in the entryway window
- Connected via HDMI to Pi (or to a dedicated cheap device running a browser fullscreen at `http://<pi-ip>:5050/`)
- Browser autostarts fullscreen on boot (kiosk mode — needs setup)
- Cables hidden

### 4f. Ambient mode hours

Check `prototype/orchestrator.py` config (`WLED_AMBIENT_INTERVAL`, `WLED_AMBIENT_DURATION`) for ambient timing. If gallery hours are different from your test setup, tune these.

### 4g. False-positive monitoring at the gallery

Your home environment had a periodic 433MHz transmitter (909 edges, every 57s) that we filtered out with the upper bound. The gallery may have **different** RF noise — different neighbors, different devices. After install, watch logs for ~1 hour:

```bash
ssh imperfecta-pi "sudo journalctl -u orchestrator -f"
```

If you see `RF burst MATCH ... — triggering` lines without anyone pressing the doorbell, we have a new false-positive source. Capture the edge counts and we can re-tune the thresholds in `orchestrator.py`.

---

## 5. Daily ops cheat sheet (during install + after)

| Goal | Command |
|---|---|
| Watch live logs | `ssh imperfecta-pi "sudo journalctl -u orchestrator -f"` |
| Recent logs | `ssh imperfecta-pi "sudo journalctl -u orchestrator -n 50 --no-pager"` |
| Restart orchestrator only | `ssh imperfecta-pi "sudo systemctl restart orchestrator"` |
| Restart bg server only | `ssh imperfecta-pi "sudo systemctl restart bg_removal"` |
| Restart both | `ssh imperfecta-pi "sudo systemctl restart orchestrator bg_removal"` |
| Stop orchestrator (free GPIO17) | `ssh imperfecta-pi "sudo systemctl stop orchestrator"` |
| Deploy code changes | `cd /Users/mheavers/Desktop/imperfecta/_project/prototype && ./deploy.sh` |
| Clear gallery | `ssh imperfecta-pi "rm -f ~/captures/*.png ~/captures/*.jpg && sudo systemctl restart bg_removal"` |
| Switch Pi Wi-Fi | `ssh imperfecta-pi "~/wifi_switch.sh 'SSID' 'password'"` |
| Test MaixCam | `ssh imperfecta-pi "curl -m 10 http://MAIXCAM_IP:8080/capture-all"` |
| Test WLED reachable | `ssh imperfecta-pi "ping -c 2 WLED_IP"` |
| Find devices on subnet | `ssh imperfecta-pi "arp -a"` |
| List saved Wi-Fi profiles | `ssh imperfecta-pi "nmcli connection show"` |
| Reboot Pi | `ssh imperfecta-pi "sudo reboot"` |

Gallery URL (open in browser): `http://<PI_IP>:5050/`

---

## 6. Troubleshooting

### "I can't reach the Pi from my laptop"
- Make sure your laptop is on the **gallery Wi-Fi** (not your phone hotspot or VPN)
- Disable any active VPN — it routes LAN traffic away from the LAN
- Find the Pi's IP: connect a monitor + keyboard, run `hostname -I`

### "Firefox/Chrome won't load the gallery URL"
- Make sure URL is `http://` not `https://`
- Disable any active VPN
- Try Safari/Chrome (Firefox HTTPS-Only mode is aggressive)

### "Doorbell press doesn't trigger anything"
- Check service is up: `ssh imperfecta-pi "sudo systemctl is-active orchestrator"`
- Watch logs while pressing: `ssh imperfecta-pi "sudo journalctl -u orchestrator -f"` — do you see `RF burst` lines at all?
  - If yes but no MATCH: the burst envelope is outside our calibrated window (250-500 edges, 150-400ms). Different doorbell or RF environment — share the burst details and we recalibrate.
  - If no bursts at all: the receiver isn't seeing the transmission. Check antenna soldering, check the Pi is in RF range of the doorbell, verify wiring (RX VIN→5V, GND→GND, DATA→GPIO17).

### "WLED isn't lighting up but logs show MATCH"
- Logs show `WLED trigger failed: No route to host`? WLED is unreachable. Confirm it powered on and joined the network: `ssh imperfecta-pi "ping -c 2 WLED_IP"`.
- Wrong WLED IP in `orchestrator.py`? Re-find IP, edit, deploy.

### "MaixCam returns 0 faces"
- Confirm MaixCam is reachable: `curl http://MAIXCAM_IP:8080/capture-all`
- Confirm someone is in frame at press time
- Check MaixCam screen for the face-detection green box overlay

### "False positives — lights firing without anyone there"
- Capture the burst details from logs
- Likely a periodic 433MHz transmitter in range (weather sensor, etc.)
- Fix is to adjust `RF_BURST_MIN/MAX_EDGES` and `RF_BURST_MIN/MAX_DURATION_MS` in `orchestrator.py`. See SYSTEM_OVERVIEW.md doorbell section + DOORBELL_OPTIONS.md for the calibration approach. Run `prototype/rf_burst_probe.py` (after stopping orchestrator) to gather fresh signature data.

### "Gallery stops updating"
- Page disconnected from SSE feed. Refresh the browser.
- Or bg_removal service crashed: `ssh imperfecta-pi "sudo systemctl status bg_removal"`. Restart with `sudo systemctl restart bg_removal`.

---

## 7. When you go home from the gallery

The Pi and MaixCam auto-reconnect to home Wi-Fi when in range (both hold both networks). WLED holds only one — run `ssh imperfecta-pi '~/wled_switch.sh home'` before leaving the gallery so it joins home on arrival.

You'll need to update `orchestrator.py`'s `MAIXCAM_IP` and `WLED_IP` to whatever those devices got from your home router. `arp -a` from the Pi will show you. Then `./deploy.sh`.

Or — set up static IP reservations on both your home router AND the gallery router (assign by MAC address), and the IPs stay the same forever. Strongly recommended if you'll be moving back and forth more than once.
