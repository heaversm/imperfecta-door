# Imperfecta TODO

## ~~1. Run entirely on Pi (eliminate Mac from chain)~~ DONE

BG removal now runs on Pi via Replicate cloud API (`cjwbw/rembg`). Gallery served from Pi at `http://10.0.0.206:5050/`. Both services auto-start on boot via systemd (`orchestrator.service`, `bg_removal.service`). No Mac needed.

## 2. Doorbell trigger — IN PROGRESS

FSR (force-sensitive resistor) is wired and working as of 2026-04-13. Wiring: FSR lead 1 → Pi 3.3V (pin 1), FSR lead 2 → GPIO17 (pin 11) + 10K resistor → GND (pin 9). `TRIGGER_MODE = "fsr"` in orchestrator.py.

**Two options under consideration:**

### Option A: FSR (current working prototype)
- Fabricate a housing that adheres the FSR to the doorbell button face while hiding the wires running from the FSR back to the Pi
- Solder FSR circuit onto perfboard for durability
- Requires running 2 thin wires from exterior doorbell back indoors to Pi GPIO
- Pro: already working and tested. Con: exterior wiring.

### Option B: 433MHz RF receiver (no exterior wires) — IN PROGRESS
- RX470C-V01 receiver module purchased and wired to Pi GPIO17
- Wiring: receiver pin 2 (GND) → Pi pin 6, pin 3 (VIN) → Pi pin 4 (5V), pin 4 (DATA) → Pi pin 11 (GPIO17)
- Doorbell signal confirmed captured — bursts 52-56 in rf_test.py output show clean OOK pattern
- Decoded 32-bit code: `11001000000000001100000010100111`
- orchestrator.py updated with `TRIGGER_MODE = "rf"` and full RF decode/match logic
- **NOT YET WORKING END-TO-END** — deployed to Pi but no match triggered on doorbell press
- Next step: debug why orchestrator isn't matching. Possible causes:
  - Bit decoding off-by-one or wrong edge direction being counted
  - Code may need to be re-verified (run rf_test.py, capture 3+ consecutive bursts, confirm bits are identical)
  - Try printing raw decoded codes in the orchestrator to compare against RF_DOORBELL_CODE

**Decision:** RF is preferred if it can be made reliable (eliminates all exterior wiring).

See DOORBELL_OPTIONS.md and DOORBELL_WIRING.md for details.

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
