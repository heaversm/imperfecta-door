# LED Strip Buzzer Prototype Guide (Phase-by-Phase)

This guide gets you from **fresh Raspberry Pi** to **programmatic control of one strip**.

## Scope of this prototype

- Hardware: Dig-Quad + Mean Well 12V PSU + 1x WS2815 strip
- Software: WLED on controller + Python script on Pi 3
- Goal: quickly test colors/effects/presets from code before scaling to full install
- Wiring schematic: see `wiring.md`
- Editable diagram: `wiring.drawio`

---

## Phase 0 - Bench safety and prep

1. Work on a non-conductive surface.
2. Keep AC wiring physically separated from low-voltage wiring.
3. Start with **one short strip segment** (or one full strip at low brightness).
4. Do not hot-plug data/power wires while powered.

---

## Phase 1 - Fresh Raspberry Pi 3 setup

Use Raspberry Pi OS Lite (fresh install recommended).

### 1) Flash OS

- Use Raspberry Pi Imager.
- Configure:
  - hostname (e.g. `led-pi`)
  - Wi-Fi credentials
  - SSH enabled

### 2) Initial updates

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip git curl
```

### 3) Create project env on Pi

```bash
mkdir -p ~/imperfecta-prototype
cd ~/imperfecta-prototype
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

Copy `requirements.txt` and `wled_client.py` from this repo's `prototype/` folder, then:

```bash
pip install -r requirements.txt
```

---

## Phase 2 - Controller + strip bring-up (minimal)

Communication note:

- Pi controls Dig-Quad over local network via WLED API (`/json/state`).
- No direct Pi-to-Dig-Quad control wire is required for this prototype phase.

### 1) Flash/configure WLED on Dig-Quad

- Connect controller to USB
- Flash WLED (if not pre-flashed)
- Join Wi-Fi and note WLED IP address

On mac - look for wled-ap: wifi password is `wled1234`
mDNS address: `http://wled-7fbab4.local`

This is what you enter in the browser to control the dig-quad
LED Voltage: WS2815 (12mA)
GPIO 0 = Push Button
Configure each output channel to control a different strip
Length 300 - GPIO 16, etc.
Brightness Limiter: 1250 if off the normal power supply, otherwise 4000

### 2) Minimal wiring

- PSU -> Dig-Quad power input (12V and GND)
- Dig-Quad data output 1 -> strip data input
- Common GND must be shared (controller and strip)
- For this first test, keep brightness capped low in WLED (e.g. <= 80/255)

### 3) Verify via browser

Open `http://<WLED_IP>` and test manual on/off + color.

---

## Phase 3 - Programmatic control from Pi (Python)

From your Pi:

```bash
source ~/imperfecta-prototype/.venv/bin/activate
python wled_client.py --host <WLED_IP> status
python wled_client.py --host <WLED_IP> on
python wled_client.py --host <WLED_IP> color --rgb 255,120,20 --brightness 160
python wled_client.py --host <WLED_IP> off
```

Preset control example:

```bash
python wled_client.py --host <WLED_IP> preset --id 1
```

---

## Phase 4 - Build your first usable behavior

1. In WLED, create and save presets:
   - Preset 1: ambient (low activity)
   - Preset 2: ring one-shot (brighter hotspot)
2. Use Python to trigger presets by ID.
3. Tune orange color and brightness until it looks right in your diffuser sample.

---

## Phase 5 - Add reliability layers before scaling

Before moving to 2x30ft:

1. Add fusing per injection branch.
2. Add power injection at both strip ends.
3. Add cable strain relief and enclosure routing.
4. Add TVS protection on 12V rail near strip entry.
5. Run 1-2 hour burn test with repeated preset triggers.

---

## Next scaling step (after one-strip success)

- Add second strip on output 2.
- Keep same code path (HTTP preset calls).
- Then add schedule logic (night mode) on Pi.

---

## Troubleshooting quick checks

- No LEDs at all:
  - verify PSU output and polarity
  - verify strip input end (direction arrow)
- Wrong/flickering colors:
  - verify strip type and color order in WLED
  - ensure common ground
- API calls fail:
  - verify Pi and WLED are on same network
  - test `http://<WLED_IP>/json/state` in browser first
