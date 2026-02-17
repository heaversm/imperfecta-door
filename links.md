# Imperfecta – LED Strip Buzzer Links

This file centralizes reference pages and example purchase links for the build.

## Core concept references (image-heavy)

- QuinLED controller ecosystem home
  - https://quinled.info/

## LED controller (WLED-capable)

- QuinLED Dig-Quad (overview/specs/photos)
  - https://quinled.info/quinled-dig-quad/
- Pre-assembled QuinLED Dig-Quad (photos, what’s included)
  - https://quinled.info/pre-assembled-quinled-dig-quad/

## LED strips (addressable, 12V)

- WS2815 12V 60 LED/m 5m reel (example listings)
  - https://www.aliexpress.com/item/32894488333.html
  - https://www.aliexpress.com/item/1005001274462701.html

## Diffusion (black/smoke “neon” channel)

- Black silicone LED diffuser channel (referenced product)
  - https://www.amazon.com/dp/B08ZRZN5P7

## Power supply (12V)

- Mean Well LRS-350-12 (12V, 350W) (specs/photos)
  - https://www.mouser.com/ProductDetail/MEAN-WELL/LRS-350-12/?qs=ah3jBNVE1PRuo5/c9niR6A%3D%3D

## WLED (what it is / how it’s controlled)

- WLED project (overview)
  - https://kno.wled.ge/
- WLED JSON API docs (for controlling from Python/Node)
  - https://kno.wled.ge/interfaces/json-api/

## Orchestration (easy programming on Raspberry Pi)

- Raspberry Pi 5 product page (overview)
  - https://www.raspberrypi.com/products/raspberry-pi-5/
- Home Assistant WLED integration (turnkey control)
  - https://www.home-assistant.io/integrations/wled/
- Node-RED (optional low-code orchestration)
  - https://nodered.org/

## Light sensor (for day/night gating)

- Adafruit TSL2591 (higher-quality digital lux sensor, I2C)
  - https://www.adafruit.com/product/1980
  - https://learn.adafruit.com/adafruit-tsl2591
- BH1750 module (budget digital lux sensor, I2C)
  - https://www.amazon.com/HiLetgo-BH1750FVI-intensity-illumination-arduino/dp/B00M0F29OS

## Wiring / install hardware (examples)

- WAGO 221 Series Lever-Nuts (wire splicing connectors)
  - https://www.wago.com/us/lp-221
- Inline ATC/ATO blade fuse holders (examples)
  - https://www.amazon.com/MCIGICM-Inline-Fuse-Holder-Blade/dp/B081DHT8Y7
  - https://www.amazon.com/SIM-NAT-Automotive-Standard-Replacement/dp/B0CN6TVHKH
- IP65 junction/enclosure box examples (hinged, clear cover)
  - https://www.amazon.com/LMioEtool-Dustproof-Waterproof-Electrical-Transparent/dp/B07PK8K8S2
- Cable glands assortment (strain relief)
  - https://www.amazon.com/Creative-Idea-30pcs-Waterproof-Nylon-Protector/dp/B07WS9HBV4

## Protection components (reference)

- TVS diode example part (SMBJ15A class; 600W TVS)
  - https://www.mouser.com/ProductDetail/Diodes-Incorporated/SMBJ15A-13-F?qs=gaDBXWSqsDC%2BdBb/JB5/xQ%3D%3D

## Quantity + indoor optionality cheat sheet (for this project)

Assumes 2 runs x ~30ft each, WS2815 12V, controller box near strips.

- **LED strip reels (required)**
  - Qty: **4 x 5m reels** (20m total)
  - Indoor optional?: **No**
- **Diffuser channel/tube (recommended)**
  - Qty: **~20m** total (+10% spare if possible)
  - Indoor optional?: **Technically yes**, but strongly recommended for your visual goal
- **12V injection wire (required)**
  - Qty: start with **100ft** spool (14–16 AWG is a good starting point)
  - Indoor optional?: **No**
- **Data/signal wire (required)**
  - Qty: **15–25ft** is usually enough if controller is nearby
  - Indoor optional?: **No**
- **Inline fuse holders (required)**
  - Qty: **4 minimum** (one per injection branch: 2 strips x both ends)
  - Indoor optional?: **No**
- **Blade fuses (required)**
  - Qty: **8–12 assorted** (for tuning + spares)
  - Indoor optional?: **No**
- **Cable glands / strain relief (recommended)**
  - Qty: **8–12** depending on enclosure cable count
  - Indoor optional?: **Optional but strongly recommended**
- **Wire protectors (braided sleeve / split loom) (recommended)**
  - Qty: **25–50ft** depending on visible routing
  - Indoor optional?: **Optional**, but recommended for abrasion protection + clean install
- **TVS diodes (recommended protection)**
  - Qty: **2–4**
  - Indoor optional?: **Optional**, but recommended for reliability
- **Enclosure (required)**
  - Qty: **1** (controller + PSU + wiring)
  - Indoor optional?: **No**

## Notes

- Doorbell integration links are intentionally omitted until the brand/model is confirmed.
