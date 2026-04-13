# Imperfecta TODO

## ~~1. Run entirely on Pi (eliminate Mac from chain)~~ DONE

BG removal now runs on Pi via Replicate cloud API (`cjwbw/rembg`). Gallery served from Pi at `http://10.0.0.206:5050/`. Both services auto-start on boot via systemd (`orchestrator.service`, `bg_removal.service`). No Mac needed.

## 2. Replace button with doorbell trigger — IN PROGRESS

FSR (force-sensitive resistor) is wired and working as of 2026-04-13. Wiring: FSR lead 1 → Pi 3.3V (pin 1), FSR lead 2 → GPIO17 (pin 11) + 10K resistor → GND (pin 9). `TRIGGER_MODE = "fsr"` in orchestrator.py.

Remaining: mount FSR onto the physical doorbell button at the museum. May need to solder onto perfboard for durability. See DOORBELL_OPTIONS.md and DOORBELL_WIRING.md for details.

## 3. LED tubing test

Test the LED strip inside diffuser tubing to validate the visual effect. The current blocker is that the strip has a connector on the end that's too wide to feed through the tubing. Options: desolder the connector and re-attach after threading, cut the connector off and solder new leads, or find tubing with a wider opening. This is a hands-on fabrication task.

## 4. Wire up 4 LED strands (2x2 parallel with extensions)

The final installation needs 4 LED strands total: 2 pairs running in parallel, each pair connected via an extension strip. This means configuring the Dig-Quad's multiple outputs and making sure WLED addresses all 4 strands correctly (segment config in WLED). Physical wiring: each Dig-Quad output drives 2 strips daisy-chained with an extension cable between them.

## ~~5. Photo filter / funhouse effect~~ DONE

Funhouse distortion (wave + barrel/bulge) applied in bg_removal_server.py using PIL/numpy. Randomized parameters per image (0 to max for wave amplitude, frequency, and bulge strength). Gallery layout uses overlapping, slightly rotated faces.

## ~~6. Wi-Fi resilience~~ DONE

Three layers: NetworkManager infinite retries (`autoconnect-retries 0`), wifi_watchdog.sh cron (pings every minute, toggles radio if down), wifi_switch.sh for easy network changes. See TESTING_PLAYBOOK.md Wi-Fi Resilience section.
