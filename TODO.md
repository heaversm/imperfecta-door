# Imperfecta TODO

## 1. Run entirely on Pi (eliminate Mac from chain)

Install rembg and its dependencies on the Pi so background removal and the gallery web server run there instead of on the Mac. This means the only things needed to run the installation are the Pi, MaixCam, WLED, and power — no laptop required. The main risk is that rembg on a Pi 3 may be too slow (could be 10-30s per image vs ~1.5s on Mac), so we may need to test on a Pi 4/5 or find a lighter-weight bg removal model.

## 2. Replace button with doorbell trigger

Swap the breadboard button for the actual museum hardware — a wireless doorbell whose signal the Pi can detect. This likely means wiring the doorbell's receiver to a GPIO pin (or intercepting its RF signal). The orchestrator already treats the button as a generic trigger, so the code change is minimal — it's mostly a hardware/wiring task. Need to identify the doorbell model and figure out how to tap into its output.

## 3. LED tubing test

Test the LED strip inside diffuser tubing to validate the visual effect. The current blocker is that the strip has a connector on the end that's too wide to feed through the tubing. Options: desolder the connector and re-attach after threading, cut the connector off and solder new leads, or find tubing with a wider opening. This is a hands-on fabrication task.

## 4. Wire up 4 LED strands (2x2 parallel with extensions)

The final installation needs 4 LED strands total: 2 pairs running in parallel, each pair connected via an extension strip. This means configuring the Dig-Quad's multiple outputs and making sure WLED addresses all 4 strands correctly (segment config in WLED). Physical wiring: each Dig-Quad output drives 2 strips daisy-chained with an extension cable between them.

## 5. Photo filter / funhouse effect

Apply a visual distortion to captured photos so people aren't directly identifiable — something playful like a funhouse mirror warp, fisheye, swirl, or painterly effect. This would happen in the bg removal pipeline (either on the server side after rembg, or as a new processing step). Options include OpenCV distortion maps, PIL/Pillow transforms, or a lightweight style-transfer model. The effect should be consistent and fun, not creepy.
