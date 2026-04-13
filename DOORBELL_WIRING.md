# Doorbell Sensor Wiring Guide

## Current State

The orchestrator code has been updated to trigger on HIGH signal (active HIGH with pull-down bias) instead of LOW. This works with both the touch sensor and the FSR voltage divider. The code is deployed but NOT yet on the Pi — run `deploy.sh` after wiring.

**Important:** The old breadboard button (active LOW) will NOT work with the updated code. If you need to revert to the button, the two lines to change back are in `orchestrator.py` — search for "pull-down" and "ACTIVE".

---

## Option A: FSR (simpler, recommended to try first)

### Parts
- FSR (the round one, item #1 from your parts photo)
- 10K ohm resistor
- 3 jumper wires

### Wiring

```
Pi 3.3V (pin 1) ──── FSR lead 1
                          │
                        FSR
                          │
Pi GPIO17 (pin 11) ── FSR lead 2 ──── 10K resistor ──── Pi GND (pin 9)
```

This is a voltage divider. When not pressed, the 10K resistor pulls GPIO17 to GND (LOW). When pressed, FSR resistance drops and GPIO17 goes HIGH.

### How to wire on breadboard
1. FSR lead 1 → breadboard row A
2. FSR lead 2 → breadboard row B
3. Jumper: Pi 3.3V (pin 1) → row A
4. Jumper: Pi GPIO17 (pin 11) → row B
5. 10K resistor: row B → row C
6. Jumper: Pi GND (pin 9) → row C

### Mounting on doorbell
- Tape the FSR disc directly on top of the doorbell button face
- Run the two FSR leads back to the Pi (they're thin and flexible)
- When someone presses, their finger pushes the FSR AND the doorbell button underneath

---

## Option B: Touch Sensor (Grove Touch V1.1) + Copper Tape

### Parts
- Touch sensor board (item #3 from your parts photo)
- Copper tape (item #2)
- 1 short wire (to connect sensor pad to copper tape)
- 3 jumper wires

### Wiring

```
Touch sensor VCC → Pi 3.3V (pin 1)
Touch sensor GND → Pi GND (pin 9)
Touch sensor SIG → Pi GPIO17 (pin 11)
```

### Extending to copper tape
- Solder a wire from the touch pad on the sensor board to a strip of copper tape
- Stick the copper tape on the doorbell button face
- Tuck the sensor board behind the doorbell or along the wire run to the Pi

### Mounting on doorbell
- Copper tape on the button face (what people touch)
- Sensor board hidden behind/beside the doorbell
- Wire connects the two

---

## Testing (same for both options)

1. Wire the sensor to the Pi on the breadboard
2. From Mac, deploy the updated code:
   ```
   ~/Desktop/imperfecta/_project/prototype/deploy.sh
   ```
3. Check it started:
   ```
   ssh imperfecta-pi "sudo journalctl -u orchestrator -n 5 --no-pager"
   ```
   Should show: `GPIO 17 configured via gpiod (pull-down, active HIGH — touch sensor)`
4. Touch/press the sensor
5. Check logs:
   ```
   ssh imperfecta-pi "sudo journalctl -u orchestrator -n 10 --no-pager"
   ```
   Should show: `Button pressed!` followed by face detection output

## Reverting to the old physical button

If you need to go back to the breadboard button, change two things in `orchestrator.py`:

1. `Bias.PULL_DOWN` → `Bias.PULL_UP`
2. `Value.ACTIVE` → `Value.INACTIVE`

Then run `deploy.sh`.
