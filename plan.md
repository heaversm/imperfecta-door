# Imperfecta Project Plan

## LED Strip Buzzer

### Goals

- **Effect**: Door buzzer triggers a one-shot animation: a bright “hotspot” travels away from the buzzer along two strips (optionally slightly offset), then returns.
- **Physical**: 2 runs, ~30ft each, indoor, light viewed through black diffusion tubing.
- **Look**: Bright “neon ember” / Edison-like warm orange glow; mostly dark except the moving hotspot, which would be about a foot long at full brightness.
- **Operating hours**: No daytime animation. During dim hours (early morning / late night), run an ambient animation even without a ring (e.g., auto-trigger every ~60s).
- **Reliability**: Install-grade wiring (power injection, fusing, surge/ESD protection), self-contained controller box.

### Recommended system architecture (2026 best-practice)

- **Controller (recommended)**: ESP32 running **WLED**, using a purpose-built pixel controller board.
  - **Best fit boards** (pick 1):
    - **QuinLED Dig-Quad** (robust power distribution, fusing options, multiple outputs)
    - **QuinLED Dig-Uno** (if you only need one data output and simpler distribution)
- **Why WLED/ESP32**:
  - Appliance-like (boots straight into the show)
  - Easy iteration (presets, web UI)
  - Sync options if we ever split into multiple controllers
- **Data topology**:
  - For 2x ~30ft runs, drive both strips from **one controller** (two outputs, or one output split if needed).
  - Keep the controller physically near the start of strips to keep data wires short.
- **Trigger input**:
  - Prefer a **clean dry-contact / low-voltage trigger** into an opto-isolated GPIO input.
  - Trigger plays a WLED preset / custom effect for a defined duration.
- **Day/night gating**:
  - Use WLED **scheduling/timers** (NTP + “night hours” presets).
  - Optional (more robust than clock time): add a **light sensor** (photocell or I2C lux sensor) so the system can disable itself in bright conditions.

### Software stack (ideal solution path)

#### Design principle

- Use a **two-tier** setup:
  - **Tier 1 (real-time LED driving)**: ESP32 + WLED (stable, purpose-built, handles the strict LED timing).
  - **Tier 2 (easy programming + integrations)**: a small always-on computer running Python/Node for doorbell events, schedules, sensors, and “business logic.”

#### Tier 1: WLED (ESP32)

- Role: output pixels reliably, store presets, run effects.
- Control surface:
  - **HTTP JSON API** (easy from Python/Node)
  - Optional: **MQTT** (if you want an event bus)
- What we’ll use:
  - A “night ambient” preset
  - A “ring one-shot” preset

#### Tier 2: Orchestrator (recommended: Raspberry Pi)

- Recommended hardware: **Raspberry Pi** (small, self-contained, runs Linux; more pleasant than firmware dev).
- Why this solves the “microcontroller pain”:
  - Your code runs in **Python or Node.js**
  - Better libraries for integrations (doorbells, webhooks, schedulers)
  - Easier logging/monitoring and remote updates
- Development workflow:
  - Develop/test the orchestrator code on a **Mac**.
  - Deploy the same code to the **Pi** for the gallery install.

#### Orchestrator software options

- **Option A (most turnkey integrations)**: Home Assistant + automations
  - Pros: supports many doorbells and sensors; UI for schedules; durable automations.
  - Cons: heavier stack than a small custom script.
  - WLED integration is mature.
- **Option B (simple + hackable)**: Node.js or Python service
  - Pros: minimal moving parts; exactly the logic you want.
  - Cons: you own the integration work.
  - Suggested libraries:
    - Node: `axios` (HTTP), `node-schedule` (timers), optional `mqtt`
    - Python: `requests` (HTTP), `APScheduler` (timers), optional `paho-mqtt`
  - Pattern:
    - Ring event → call WLED HTTP API → activate ring preset
    - Night mode → periodic timer (every ~60s) → call ambient preset

#### Sensors (optional)

- Preferred: connect any sensors to the **Pi** (I2C lux sensor) and let the orchestrator decide whether to enable output.
- This avoids custom ESP32 firmware work.

### LED strip recommendation

#### Addressable vs “single color”

- **Addressable (pixel) strip is required** for a traveling hotspot. A non-addressable “single color” strip (analog) can only dim the whole strip at once.
- “**Smart RGB**” usually means **addressable RGB pixels** (WS2812B/WS2815 class). Even if you only want orange, RGB is still useful:
  - You can tune a very specific amber (e.g., mostly red + some green)
  - You can correct for diffuser/tube color shifts

#### Voltage

- **Prefer 12V addressable** for 30ft runs (less voltage-drop pain than 5V).
- Recommended baseline: **WS2815 12V** (addressable RGB).

#### Density

- Start with **60 LEDs/m**. With diffusion tubing, it often reads continuous enough for a creeping hotspot.
- If testing shows visible “dotting,” go to **96 LEDs/m** (higher cost + more power).

#### Diffusion / tubing recommendation

- Plan around a common **10–12mm-wide** strip.
- For a continuous-looking hotspot at **60 LED/m**, prioritize diffusion geometry over density:
  - Use a diffuser/tube with an internal cavity that comfortably fits the strip and wiring, typically **~12–14mm inner clearance**.
  - Ensure there’s enough distance between LEDs and the “viewing surface” (thicker wall / larger cross-section helps).
- If the referenced tubing is primarily protective sleeving (very thin wall), expect more visible points; in that case prefer:
  - a dedicated **LED “neon flex” style diffuser** or a rigid channel + diffuser, in black/smoke.

#### Color (warm orange)

- Baseline approach: **RGB strip** set to an amber/orange palette.
- If you find RGB can’t hit the “Edison glow” you want, consider:
  - **RGBW addressable** strips (adds a dedicated white channel), but availability/voltage options are more limited.
  - Or keep RGB and tune palette + gamma; for your effect, palette tuning usually solves this.

### Power & protection (the reliability upgrades)

- **Power injection**:
  - Plan to inject power at **both ends** of each 30ft strip.
  - If brightness/voltage sag shows up, add a **midpoint** injection.
- **Fusing**:
  - Fuse each injection branch (protects against shorts and strip failures).
- **Surge/ESD**:
  - Add a **TVS diode** across the strip’s +V/GND near each strip entry.
  - Add a small **series resistor** on each data line near the controller.
- **Grounding**:
  - Common ground between controller and strips.
  - Star-like wiring back to the power distribution point.

### Draft materials list (shopping categories)

#### LEDs & diffusion

- **Addressable LED strip**: WS2815 12V, 60 LED/m (or 96 LED/m if needed), total length ~60ft + spare.
- **Diffusion** (pick 1 approach):
  - Black/smoke “neon flex” diffuser compatible with 10–12mm strips (preferred for a continuous look)
  - Or black tube/sleeve as referenced, if it provides sufficient diffusion in testing
- **Mounting**: clips, channel, or adhesive backing reinforcement (3M VHB / silicone as needed).

#### Control

- **Pixel controller board**:
  - QuinLED Dig-Quad (preferred) or Dig-Uno
- **ESP32** (typically integrated/compatible with the controller ecosystem above).
- **Data conditioning** (if not integrated):
  - 3.3V-to-5V level shifter (e.g., 74AHCT125)
  - 33–100Ω series resistor per data line

#### Trigger

- **Opto-isolated input module** (or optocoupler + resistor network) for trigger → GPIO.
- Optional: separate **momentary test button** on the controller enclosure.

#### Door button trigger pickup (preferred location)

- **Pickup point**: at the **door button location** (vestibule / somewhat sheltered).
- **Goal**: preserve the existing smart doorbell’s normal operation (phone notification + any chime) and add a separate, reliable trigger for the LED controller.
- **Constraint**: single button only (no separate “LED-only” button).
- **Assumption**: existing doorbell is **battery / wireless**.
- **Approach A (preferred, most foolproof)**: integrate from the doorbell ecosystem’s **ring event** (software or accessory), then trigger WLED.
  - Options (depending on brand/model):
    - Local hub / home automation integration (e.g., a hub can emit an event)
    - Cloud/webhook integration (event → webhook → local trigger)
  - This avoids fragile physical sensing and keeps single-button behavior.
- **Approach B (often practical)**: trigger from the **wireless chime/receiver** (if one exists).
  - Many wireless doorbells have an indoor plug-in chime with an LED/buzzer; we can sense that output (e.g., via an opto/relay) without touching the outdoor button.
- **Approach C**: replace the doorbell with one that provides a **local ring signal** we can sense.
  - Requirement: phone notifications + audible notification + some form of local output (dry contact / wired chime interface / supported integration).
- **Approach D (last resort)**: non-invasive sensing at the outdoor button (microswitch/vibration).
  - Works without ecosystem integration, but is the least deterministic.

#### Optional sensors / scheduling helpers

- If using time-based gating: Wi-Fi + NTP (built-in to WLED) + configured timers.
- If using ambient-light gating: **photocell module** or **lux sensor** (I2C) and corresponding WLED/user code.

#### Power

- **12V PSU (Mean Well class)** sized for worst-case with headroom.
  - Starting point for budgeting: **12V 350W** (e.g., Mean Well LRS-350-12).
  - We can downsize after strip choice + brightness tests.
- **AC inlet / switch**: IEC C14 inlet + fuse + rocker switch (optional but clean).
- **DC distribution**:
  - Fused distribution block or inline blade fuse holders (one per injection branch)
  - DIN rail terminals or WAGO lever nuts for serviceability

#### Wiring & connectors

- **Wire**:
  - 12V injection runs: 14–18 AWG (final gauge depends on injection spacing)
  - Data runs: shielded 2-conductor or CAT5e/CAT6 for longer data if needed
- **Connectors**:
  - Locking 3-pin connectors for strip hookups (or screw terminals inside an enclosure)
- **Heatshrink** + strain relief + cable glands.

#### Protection & enclosure

- **TVS diodes** for 12V lines near strip entry (part selected to match 12V system).
- **Enclosure** sized for PSU + controller + wiring.
- Optional: **small fan** if enclosure gets warm (not required if ventilated and derated).

### Build plan (concrete steps)

1. **Decide strip SKU** (WS2815 12V 60/m vs 96/m) and order enough length + 10–20% spare.
2. **Bench test one short segment**:
   - Validate color palette (amber/orange), brightness through diffuser, and whether 60/m looks continuous.
   - Confirm the hotspot looks ~1ft long at full brightness through the diffuser.
3. **Assemble controller box**:
   - Mount PSU + controller + distribution + fuses.
   - Wire AC safely (strain relief, enclosure grounding as applicable).
4. **Wire and test one full 30ft run** on the floor:
   - Inject power at both ends (and midpoint if needed).
   - Confirm no visible dimming at far end during bright moments.
5. **Add surge/ESD protection**:
   - Install TVS near strip input(s) and verify data resistor/level shifting.
6. **Implement ambient + trigger behavior**:
   - Configure WLED preset(s) for:
     - Ambient “low activity” animation (night hours)
     - One-shot “ring” animation (brighter, longer travel, out-and-back)
   - Configure how ambient runs (pick 1):
     - A continuous subtle ambient preset during night hours, or
     - A timer that triggers the ambient preset every ~60s
   - Wire opto-isolated trigger input; test repeatability (many presses).
7. **Implement day/night gating**:
   - Configure WLED timers for the desired hours.
   - If adding a light sensor, validate it reliably disables output in bright conditions.
8. **Install door-button trigger pickup**:
   - Preferred: integrate from the wireless doorbell ecosystem’s **ring event** (or hub) into the Pi.
   - If available, sense the **indoor wireless chime/receiver** output as a local hardware signal.
   - If neither is feasible, replace the doorbell with a model that provides a reliable integration/local signal.
   - Confirm a ring action triggers both:
     - the existing smart doorbell notifications
     - the LED one-shot effect
9. **Finalize choreography**:
   - Out-and-back timing, “offset” between strips if desired, fade tail, hotspot size.
10. **Installation**:
   - Mount tubing/strips, route injection wiring, label everything, strain relief.
11. **Burn-in test**:
   - Run repeated triggers for 1–2 hours; check enclosure temps, flicker, resets.

### Shopping list (BOM) + example links (v1)

#### Required: LED + control

- **Addressable LED strip**: WS2815 12V, 60 LED/m
  - Qty: **4x 5m reels** (20m total) to cover ~18.3m needed + spare
  - Example listings:
    - https://www.aliexpress.com/item/32894488333.html
    - https://www.aliexpress.com/item/1005001274462701.html
- **Diffuser**: black/smoke silicone “neon” diffuser channel compatible with 10–11mm strips
  - Qty: ~**20m** total (or enough for both runs + slack)
  - Example listing (matches the referenced style):
    - https://www.amazon.com/dp/B08ZRZN5P7
- **Pixel controller**: QuinLED Dig-Quad (preferred) or Dig-Uno
  - Reference pages (photos/specs/purchase paths):
    - https://quinled.info/quinled-dig-quad/
    - https://quinled.info/pre-assembled-quinled-dig-quad/

#### Required: power + safety

- **Power supply**: Mean Well LRS-350-12 (12V, 350W) as a safe starting point
  - Example link:
    - https://www.mouser.com/ProductDetail/MEAN-WELL/LRS-350-12/?qs=ah3jBNVE1PRuo5/c9niR6A%3D%3D
- **Fusing**: inline blade fuse holders or fused distribution block
  - Qty: plan **4 fused branches** minimum (2 strips × both-ends injection). Add more if midpoint injection is needed.
- **Surge/ESD**: TVS diodes suitable for 12V rails
  - Qty: 2–4 (at least at the main strip entry points)
- **Enclosure**: sized for PSU + controller + wiring, with strain relief
- **Wiring**:
  - DC injection: 14–18 AWG (final gauge depends on injection distances)
  - Data: keep short; use decent cable management and strain relief
- **Consumables**: ferrules, heatshrink, cable glands, labels

#### Required: orchestration (easy programming)

- **Raspberry Pi** (Pi 4 or Pi 5), plus:
  - microSD (or SSD), PSU, network
- Software (choose one):
  - Home Assistant (turnkey integrations)
  - Node.js/Python service (minimal, hackable)

#### Doorbell integration (TBD until brand/model is known)

- If doorbell supports it: hub/API/webhook ring event → Pi → WLED HTTP API
- If there is an indoor chime/receiver: hardware sense output → Pi GPIO/opto → WLED
- If neither: replace doorbell with one that supports reliable integrations/local signal

### Diagrams (for non-technical explanation)

#### System overview (power + control)

```text
          [Wall AC]
             |
             v
     +------------------+
     | 12V Power Supply  |
     +------------------+
             |
             v
     +--------------------------+
     | Fused DC Distribution    |
     +--------------------------+
        |                  |
        |                  |
   (12V inject)        (12V inject)
        |                  |
        v                  v
   [LED Strip A]      [LED Strip B]

     +------------------+
     | WLED Controller   |
     | (ESP32 + Dig-Quad)|
     +------------------+
        |          |
      data        data
        |          |
        v          v
   [LED Strip A]  [LED Strip B]
```

#### Event flow (doorbell → light animation)

```text
[Wireless Doorbell Button]
          |
          v
   (Ring event in ecosystem)
          |
          v
[Raspberry Pi Orchestrator] ---> (HTTP) ---> [WLED Preset: Ring One-Shot]
          |
          +--------------------> (timer) --> [WLED Preset: Night Ambient]
```

### Open questions (need to resolve before final purchase sizing)

- **Exact strip placement**: are both 30ft runs co-located (same path) or different paths?
- **Diffusion choice**: confirm whether the referenced black tubing is “diffusive enough” or whether we should use a dedicated neon/diffuser product.
- **Brightness target**: confirm “night hours” ambient brightness vs ring brightness (so PSU sizing can be less wasteful).
- **Electrical source**: where AC power will be taken from (ceiling vs near door) and cable routing constraints.
- **Doorbell integration** (preserve phone + chime):
  - Confirm whether we’re doing:
    - **Approach A**: software/accessory integration from the existing wireless doorbell ring event, or
    - **Approach B**: sense the indoor wireless chime/receiver output, or
    - **Approach C**: replace the doorbell with one that provides a **local ring signal** we can sense, or
    - **Approach D**: non-invasive sensing on the existing button.
  - Confirm the **doorbell brand/model** and whether there is an **indoor plug-in chime/receiver**.
  - Confirm whether any part of the door button area is exposed to rain/splashes (to select IP-rated parts).
- **Controller location**: distance from controller box to strip start points.
- **Future expansion**: idle animation, scheduling, or network control desired later.
