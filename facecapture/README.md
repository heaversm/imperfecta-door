# Face Collector

A tablet/kiosk web app for an installation: capture a face from the webcam, the
background is removed **on Cloudflare**, and the cutout drops into a live feed —
newest face big on top, everyone else small (5 per row).

Built to run the kiosk page on a Raspberry Pi (it only renders + uploads; all the
heavy ML happens in the cloud).

## Architecture

```
Raspberry Pi (kiosk browser)
        │  photo (jpeg)  ─────────────► POST /api/capture
        │                               ┌─────────────────────────────┐
        │                               │ Cloudflare Worker (src/worker.ts)
        │                               │   routes everything into ↓   │
        │                               │ Cloudflare Container (Docker)│
        │                               │   • serves this web app      │
        │  ◄── cutout url + feed ───────│   • @imgly bg removal        │
                                        │   • stores to R2 (S3 API)    │
                                        └─────────────────────────────┘
                                                      │
                                                 R2 bucket
                                          images + manifest.json
```

Why a Container and not a plain Worker: `@imgly/background-removal` is a native
Node ML package (onnxruntime). Workers can't run native binaries, so the model
runs in a Cloudflare **Container** (real Node in Docker). The Worker fronts it,
handles `/api/capture` + `/api/heads`, and owns all R2 storage through a native
binding — the container is pure compute (`POST /remove`) plus the static app.
No S3 credentials or Worker secrets anywhere.

## Prerequisites

- A Cloudflare account on the **Workers Paid plan** ($5/mo) — Containers require it.
- Node 20+ and `npm install` at the repo root.
- No local Docker needed: the container image is built by GitHub Actions at
  deploy time (`.github/workflows/deploy.yml`).

## One-time setup

1. **Install deps**
   ```bash
   npm install
   npx wrangler login
   ```

2. **Create the R2 bucket and make it public** (so the tablet can load the
   cutout images):
   ```bash
   npx wrangler r2 bucket create facecapture
   npx wrangler r2 bucket dev-url enable facecapture
   ```
   Put the printed `https://pub-xxxx.r2.dev` URL in `wrangler.jsonc` →
   `vars.R2_PUBLIC_URL`.

3. **Create a Cloudflare API token for deploys**: dashboard → My Profile →
   API Tokens → Create Token → start from the **Edit Cloudflare Workers**
   template and add **Account → Containers → Edit**. Then store it as a repo
   secret:
   ```bash
   gh secret set CLOUDFLARE_API_TOKEN
   ```


## Deploy

Push to `main` (or run the **Deploy** workflow manually in GitHub Actions).
The runner builds the Docker image, pushes it, and deploys the Worker. First
deploy takes a few minutes. You'll get a
`https://facecapture.<your-subdomain>.workers.dev` URL.

If you do have Docker locally, `npm run deploy` still works.

## Run the kiosk on the Raspberry Pi

Point Chromium at the deployed URL in kiosk mode, e.g.:

```bash
chromium-browser --kiosk --autoplay-policy=no-user-gesture-required \
  https://facecapture.<your-subdomain>.workers.dev
```

Camera access (`getUserMedia`) needs HTTPS — the `workers.dev` URL provides it.
Allow the camera permission once.

## Local development

`npm run dev` (wrangler dev) builds and runs the container locally, so it *does*
require Docker on your machine. Without Docker, test against the deployed
workers.dev URL instead.

## API

- `POST /api/capture` — body `{ "image": "data:image/jpeg;base64,..." }` →
  removes the background, stores to R2, returns the new feed entry.
- `GET /api/heads` — returns the feed, newest first.
- `GET /api/health` — `{ ok: true }`.

## Tuning

- **Speed vs quality:** `container/removal.mjs` uses `isnet_quint8` (fastest).
  Switch to `isnet` for cleaner edges at higher latency.
- **Cost:** `wrangler.jsonc` → `containers[0].instance_type`. `standard` (4 GiB)
  is safe for the model; try `basic` (1 GiB) to save money.
- **Faces per row:** CSS `#grid { grid-template-columns: repeat(5, 1fr) }` in
  `container/public/index.html`.
