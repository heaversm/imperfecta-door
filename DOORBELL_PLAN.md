# Doorbell Trigger — The Plan

> **STATUS (2026-04-29): SUPERSEDED.** This document explored FSR-based triggering. It's no longer the active approach. The current solution is **433MHz RF burst-envelope detection** via the existing RX470C-V01 receiver — see TODO.md item #2 and DOORBELL_OPTIONS.md "Recommendation". The FSR backup wiring below is kept here for reference only, in case we ever revisit.

The trigger is the sensor that detects "someone pressed the doorbell" and tells the Pi orchestrator to fire the camera + LEDs.

**Was using (now superseded):** FSR (force-sensitive resistor) on a breadboard. Worked when contact was reliable, but breadboard jumpers wiggle and FSR tabs are heat-sensitive (can't be soldered without damage). The RF burst approach replaces this entirely.

---

## Primary plan: Solid FSR wiring with a Clincher connector (no breadboard, no soldering FSR)

**DO NOT solder directly to the FSR tabs.** Both SparkFun and Adafruit explicitly warn against this — the FSR's substrate melts and the sensor is ruined. SparkFun says "only recommended for advanced users". This is why nobody on the internet has a photo of a soldered FSR with wires; they crimp instead.

The right permanent solution is an **Amphenol FCI Clincher connector** ($1.89, SparkFun): a small plastic clamp that bites onto the FSR's tabs and exposes two standard pin headers on the other side.

### Parts to order (one item, ~$2)

- 1× **Amphenol FCI Clincher Connector — 2 Position, Female** — SparkFun product page, search "Amphenol FCI Clincher 2 position female" on sparkfun.com. ~$1.89.

(Get a couple in case you mess one up — they're cheap.)

### Parts on hand

- 1× FSR
- 1× 10K resistor (or 4.7K — see notes)
- 3× wires, length depending on where the FSR mounts (e.g. 12–18 inches each)
- Heat-shrink tubing (small diameter, e.g. 1/16" or 3/32")
- Pliers (regular slip-joint pliers, or flush pliers if you have them)
- Soldering iron + solder (for the resistor only — not the FSR)
- 3× female DuPont jumper-end connectors OR a Pi GPIO breakout cable

### How the clincher works

```
   FSR (tabs cut off close to body)
        │
        ▼
  ┌──────────────┐
  │   CLINCHER   │  ← squeeze closed with pliers, teeth bite
  │   (clamped)  │     into the FSR conductors
  └──┬────────┬──┘
     │        │
   pin 1    pin 2     ← standard 0.1" header pins, like a breadboard
```

After clinching, the FSR is firmly held with two pin headers exposed. You connect those pins to the rest of the circuit with normal jumper wires or solder them to the wires going to the Pi.

### Step-by-step

1. **Cut off the FSR's solder tabs** with scissors or wire cutters, as close to the FSR body as possible (per SparkFun's instructions). This sounds destructive but is what the connector is designed for. The conductive material extends to the edge.

2. **Insert the cut end of the FSR into the clincher's slot.**

3. **Squeeze the clincher closed with pliers**, applying force in the center of the latch. You'll hear a small pop when the teeth bite through the FSR conductors.

4. **Verify the connection.** A multimeter from one clincher pin to the other should read high resistance unpressed and drop when you press the FSR.

5. **Solder the rest of the circuit.** This part involves only normal wires and a normal resistor — no FSR heat risk:

   ```
   Pi pin 1  (3.3V)   ──wire──── solder to ──── clincher pin 1
                                                      │
                                                    [FSR]
                                                      │
   Pi pin 11 (GPIO17) ──wire──── solder ─┬──── clincher pin 2
                                         │
                                         ├──── one leg of 10K resistor
                                         │
                                      [10K resistor]
                                         │
                                      other leg of 10K resistor
                                         │
   Pi pin 9  (GND)    ──wire──── solder ─┘
   ```

   Note the GPIO17 junction: wire #2 going to the Pi *and* one leg of the 10K resistor both meet at clincher pin 2. Solder all three together at that pin (the resistor leg, the GPIO17 wire, and clincher pin 2).

6. **Heat-shrink every solder joint** to insulate. Slide the tubing on the wire BEFORE soldering — you can't get it past a finished joint.

7. **The other ends of the three wires go to the Pi:**
   - Wire #1 → Pi pin 1 (3.3V) — top-right corner of the GPIO header, looking at the board
   - Wire #2 → Pi pin 11 (GPIO17)
   - Wire #3 → Pi pin 9 (GND)

   Crimp female DuPont connectors on each wire end (cheap kit ~$10 with crimper) so they push onto the Pi GPIO pins. Or use a Pi GPIO breakout cable.

8. **Mount the FSR** on the doorbell button face with double-sided tape. Make sure there's a **rigid backing** behind it — FSRs need pressure transferred evenly across the sensing area, not bent or curved.

That's it. No breadboard. No risk of frying the FSR with a soldering iron.

### If you want to skip ordering the clincher

A **Phoenix screw terminal block** (e.g. Phoenix Contact #1881448, ~$2 at Adafruit or DigiKey) also works as a permanent FSR connection — push the tab into a hole, tighten a tiny screw. Bulkier than a clincher but available at most electronics shops and doesn't need pliers.

### If it's still flaky after the clincher install

Two knobs to turn:

- **Swap 10K → 4.7K (or 3.3K) resistor.** This makes the FSR trigger with lighter pressure. Unsolder the 10K and solder a 4.7K in its place.
- **Improve the FSR mounting.** The FSR needs even pressure across its sensing area. If the doorbell button has a curved face, the FSR only contacts at one point. Glue a thin (1mm) flat plastic sheet between the FSR and the button face to spread the press evenly.

---

## Backup options (if FSR keeps failing)

These are sensors I've researched as alternatives. None are ordered yet. Listed in order of recommendation.

### Backup #1: TTP223 capacitive touch + copper tape

- **Cost:** ~$1 per board (~$5 for 10-pack on Amazon)
- **What it does:** detects when a finger gets near a metal pad. Outputs a clean digital HIGH on touch. No moving parts, no force tuning, never wears out.
- **How it'd be wired:** TTP223 board hidden behind the doorbell, with a single wire from its touch pad to a strip of copper tape on the doorbell face. Touch the tape → triggers.
- **What "bridge the solder jumper" means:** TTP223 boards have a tiny pair of pads marked "A/B" or similar. A drop of solder across them switches the output between active-HIGH and active-LOW. Active-HIGH matches our current `fsr` orchestrator mode (zero code changes).
- **Pros:** rock solid, super thin, can be invisible
- **Cons:** capacitive sensors sometimes false-trigger near other electronics; needs tuning of the on-board sensitivity pot

### Backup #2: EV1527 wireless RF button (already ordered, AliExpress)

- **Cost:** ~$5
- **What it does:** a battery-powered plastic button that broadcasts a 433MHz code when pressed. Pi receives the code via the existing RX module + `rpi_rf` library.
- **How it'd be installed:** mount the button next to or on top of the doorbell. Push it = doorbell rings + Pi triggers.
- **Pros:** zero wiring, plug-and-play
- **Cons:** it's a generic plastic button, may not blend with the doorbell aesthetic; relies on a coin-cell battery (years of life, but not zero maintenance)
- **Status:** ordered, in transit

### Backup #3: Wired momentary push button (testing only)

- **Cost:** $1, you probably have one
- **What it does:** standard pushbutton, no resistor needed. Use this for testing the rest of the system when the FSR is being weird.
- **How it'd be wired:** one pin → Pi GPIO17 (pin 11), other pin → Pi GND (pin 9). Pi internal pull-up handles the rest.
- **Code change:** set `TRIGGER_MODE = "button"` in `orchestrator.py:53`, run `./deploy.sh`.
- **Pros:** dead simple, 100% reliable
- **Cons:** not a real install solution; just a debugging tool

### Backup #4: Wireless ESP32 + TTP223 + battery (overkill, future option)

- **Cost:** ~$15 (ESP32-C3 + TTP223 + LiPo battery)
- **What it does:** custom wireless module — TTP223 senses touch, ESP32 sends HTTP request to Pi over Wi-Fi.
- **Pros:** completely hidden, no wires to the Pi, months of battery life
- **Cons:** more parts, requires writing/flashing Arduino sketch, requires soldering
- **When to consider:** if running wires through the wall is a non-starter and the EV1527 button doesn't look right.

---

## Decision tree

```
Does the FSR work after soldering + (maybe) lower resistor?
├── YES → done. Mount it on doorbell. Move on.
└── NO  → Is the EV1527 button (already ordered) here yet?
         ├── YES → tape it next to/on the doorbell, switch orchestrator to use rpi_rf code
         └── NO  → order TTP223 modules now ($5 for 10-pack on Amazon, 2-day ship). When they arrive, install per Backup #1.
```

---

## Reference: orchestrator trigger modes

In `prototype/orchestrator.py:53`, the `TRIGGER_MODE` config selects how the Pi reads GPIO17:

| Mode | Use with | Pin behavior |
|---|---|---|
| `"fsr"` | FSR + voltage divider, OR active-HIGH TTP223 | Pi waits for HIGH signal on GPIO17 |
| `"button"` | Momentary pushbutton to GND | Pi waits for LOW signal on GPIO17 (uses internal pull-up) |
| `"rf"` | 433MHz receiver (abandoned for Avantek doorbell) | Pi decodes RF bursts on GPIO17 |

Currently set to `"fsr"`. Don't touch unless you change the trigger hardware.

After changing this file, redeploy: `cd prototype/ && ./deploy.sh`
