# Doorbell Integration Options

## Goal

Mount something on top of the Avantek D3-B wireless doorbell button that:
1. Detects the press and triggers the Pi orchestrator
2. Passes the press through so the doorbell still rings normally
3. Is thin/low-profile — not bulky
4. Is reliable

The doorbell is indoors at a museum. The Pi orchestrator already listens on GPIO17 for a button press (active LOW with pull-up). Any solution that pulls GPIO17 to GND on press works with zero code changes.

---

## Option 1: TTP223 Capacitive Touch Module + Copper Tape (recommended)

**How it works:** TTP223 is a tiny board (~10mm x 10mm) with a built-in touch IC. Solder a wire from its touch pad to a strip of copper tape on the doorbell button face. When someone touches the copper, TTP223 outputs HIGH. The doorbell button still gets pressed physically underneath.

**Wiring:**
- TTP223 VCC → Pi 3.3V
- TTP223 GND → Pi GND
- TTP223 SIG → Pi GPIO17

**Note:** The current orchestrator expects active LOW (pull-up, triggered when pulled to GND). The TTP223 outputs active HIGH by default. Two options:
- Bridge the solder jumper on the TTP223 to switch it to active LOW output
- Or change one line in orchestrator.py: `Value.INACTIVE` → `Value.ACTIVE`

**Pros:**
- Very thin — copper tape is paper-thin, TTP223 hides behind the doorbell or runs via wire to the Pi
- No moving parts, nothing to wear out
- Instant response, very reliable for bare skin
- Cheap (~$1 for TTP223, copper tape on hand)

**Cons:**
- Won't work with thick gloves (not a concern indoors)
- Needs 3.3V power (from Pi, always available)

**Buy:** TTP223 module — https://www.amazon.com/s?k=TTP223+capacitive+touch+sensor+module (~$5 for a 10-pack)

**Fallback:** If TTP223 fails or loses power, the physical press still goes through to the doorbell underneath. Doorbell rings regardless. The Pi experience just doesn't trigger.

---

## Option 2: Piezo Disc Sensor

**How it works:** A thin piezo disc (~0.5mm) stuck on top of the doorbell button. When pressed, the mechanical force generates a small voltage spike. Press passes through to doorbell underneath.

**Wiring:**
- One piezo lead → Pi GPIO17
- Other lead → Pi GND
- 1M ohm resistor across the two leads (bleeds charge, prevents floating)
- Optional: zener diode (3.3V) to clamp voltage spikes and protect the Pi GPIO

**Pros:**
- Paper-thin, nearly invisible
- Works with gloves, bare hands, anything that applies pressure
- No power needed (generates its own voltage)
- Already on hand

**Cons:**
- Signal is a brief voltage spike (~ms) — may need software debouncing or a small RC circuit to stretch the pulse
- Can generate false triggers from vibration (door slam, etc.)
- May need to adjust orchestrator polling to catch the short pulse
- Likely needs code changes to handle the spike vs sustained LOW signal

**Buy:** Nothing — already have one.

**Fallback:** Same as Option 1 — physical press still reaches doorbell.

---

## Option 3: Force-Sensitive Resistor (FSR)

**How it works:** Thin film sensor on the doorbell button face. Resistance drops when pressed. Use a voltage divider to convert to a digital signal on GPIO17.

**Wiring:**
- FSR one lead → Pi 3.3V
- FSR other lead → Pi GPIO17 + 10K resistor to GND (voltage divider)
- When pressed, voltage on GPIO17 rises above logic HIGH threshold

**Pros:**
- Thin and flexible
- Works with gloves
- Already on hand

**Cons:**
- User has had reliability issues with FSR before (buggy readings)
- Needs voltage divider circuit
- Analog signal — threshold tuning may be needed
- Same active HIGH issue as TTP223 (needs code change or inverter)
- Degrades over time with repeated presses

**Buy:** Nothing — already have one.

**Fallback:** Same — physical press still reaches doorbell.

---

## Option 4: 433MHz RF Receiver (intercept doorbell signal)

**How it works:** A small RF receiver module wired to the Pi listens for the doorbell transmitter's 433.92MHz signal directly. No physical contact with the doorbell needed. Pi decodes the signal and triggers the orchestrator.

**Wiring:**
- RF module VCC → Pi 3.3V or 5V (depends on module)
- RF module GND → Pi GND
- RF module DATA → Pi GPIO17

**Pros:**
- No physical modification to the doorbell at all
- Works regardless of how the button is pressed
- Can work from a distance (receiver doesn't need to be near the button)

**Cons:**
- Need to buy an RF receiver module (~$5-7)
- Need to "learn" the doorbell's code (one-time setup)
- Requires new Python library (`rpi-rf` or custom decoding)
- Code changes needed in orchestrator
- Possible false triggers from other 433MHz devices
- More complex than a simple switch

**Buy:** 433MHz receiver module — search Amazon for "433MHz RF receiver module Arduino" (~$5-7 for a transmitter+receiver kit). Example: https://www.amazon.com/s?k=433MHz+RF+receiver+module+raspberry+pi

**Fallback:** Doorbell always rings normally (RF receiver is passive, doesn't interfere). If RF decoding fails, doorbell still works as a doorbell — just the Pi experience doesn't trigger.

---

## Recommendation

**Go with Option 1 (TTP223 + copper tape).** It's the most reliable for an indoor museum setting, thinnest profile, no wear-out, and the fallback is built in — the doorbell always rings even if the Pi side fails. Order a TTP223 pack and you're set.

If you want to prototype today with parts on hand, try **Option 2 (piezo)** — just know it may need a small protection circuit and code tweaks for the short pulse.
