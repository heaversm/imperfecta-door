# facecapture — kiosk page

`index.html` is fully standalone: copy it to the Raspberry Pi (or any
machine) and open it in a browser. It talks directly to the live server at
https://facecapture.mike-3cd.workers.dev/ (which now sends CORS headers), so
captures land in the LIVE feed. No Node, no server, no build.

Kiosk launch on the Pi, with the camera pre-allowed:

```sh
chromium-browser --kiosk --use-fake-ui-for-media-stream file:///home/pi/index.html
```

(`--use-fake-ui-for-media-stream` auto-accepts the camera prompt.)

This file is an export — the source of truth lives in the repo at
`facecapture/container/public/index.html`.
