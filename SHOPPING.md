# Imperfecta — Shopping List

Real purchase links. Updated 2026-06-05. See `EQUIPMENT.md` for full specs/rationale.

---

## ORDER NOW — Power (fixes the brownouts + the "stuck" parallel session)

### 1. Pi 3B+ power supply — 5V/3A micro-USB
The current 2.5A browns out when the display draws from the Pi's USB. **Pi 3B+ uses micro-USB, NOT USB-C** — so the CanaKit 3.5A (USB-C, Pi 4 only) does NOT fit.

**▶ Top pick: Argon 5.25V 3A micro-USB** — outputs 5.25V to actively prevent undervoltage (exactly your problem). UL listed.
https://www.amazon.com/Argon-Raspberry-Listed-Power-Supply/dp/B07MC7B9X3

Alternates (5V/3A micro-USB, UL listed):
- iUniker 15W 5V/3A w/ switch — https://www.amazon.com/Listed-iUniker-Raspberry-Supply-Switch/dp/B0B79FVPQ4
- ABOX 5V/3A w/ switch — https://www.amazon.com/ABOX-Raspberry-Supply-Adapter-Switch/dp/B07J4XJ8F8

### 2. LED power supply — 12V 12.5A (150W) for the WS2815 strip
WS2815 is **12V**. 300 LEDs × ~0.3W = ~90W (~7.5A) worst case → 150W gives full headroom.
Verify your existing 12V supply's rating first — only buy if it's under ~10A or died in the pop.

**▶ Top pick: MEANWELL LRS-150-12 (12V/12.5A/150W)** — the standard reliable LED driver, protection built in.
https://www.amazon.com/Meanwell-LRS-150-12-12-5A-Supply-Driver/dp/B078GPM65V

Alternate (barrel-plug brick, easier if no wiring):
- COOLM 12V/12.5A/150W w/ 5.5×2.5mm DC plug — https://www.amazon.com/12V-12-5A-Power-Supply-Replacement/dp/B0FHHFZ6RC

---

## Enclosure & mount

Layout: camera (6×4") stacked ON TOP of display (7.5×4.8") → enclosure ~**8–9"W × 10"H × 2.5"D**.
Fits inside the 11"-wide glass window so all 4 suction cups land on glass, not the 1.75" wood frame.
(Confirm window HEIGHT ≥ ~11" before ordering the box.)

- **Enclosure** — target ~10"L × 8"W × 3"D ABS/clear project box, drillable. Filter search to that size:
  https://www.amazon.com/s?k=ABS+project+box+10x8x3+inch
  (A clear hinged box also works and is easy to hack: https://www.amazon.com/clear-project-box/s?k=clear+project+box )
- **Heavy-duty suction cups w/ M5 threaded stud** (×4) — lever/windshield camera-mount style:
  ▶ HYS windshield suction cup, M5 + ¼" stud — https://us.amazon.com/HYS-Windshield-Threaded-Standard-Converter/dp/B0F53MKZFS
- **Paintable adhesive cable raceway** (~6 ft):
  https://www.amazon.com/s?k=paintable+adhesive+cable+raceway
- **Micro-USB to USB-A cable** (display touch → Pi, if not in a drawer):
  https://www.amazon.com/s?k=micro+usb+to+usb+a+cable+3ft

Note: MaixCam needs its OWN USB-C power (it's a WiFi device, no data cable to Pi). Either a 2nd cable down the frame or power Pi + MaixCam from one multi-port USB brick = one wall plug.

---

## Already owned (do NOT buy)
- Raspberry Pi 3B+
- Waveshare 7" HDMI capacitive touch display (1024×600)
- MaixCam
- WS2815 LED strip (B07LG6J39V) — https://www.amazon.com/dp/B07LG6J39V
- QuinLED Dig-Quad v3 controller
