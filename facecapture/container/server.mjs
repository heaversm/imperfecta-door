import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";
import sharp from "sharp";
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { removeBg } from "./removal.mjs";

// Two modes, one image:
// - On Cloudflare (default): pure compute — the Worker (src/worker.ts) owns
//   storage/R2, the API, and the /ws feed; this server only does /remove and
//   serves the static app.
// - Standalone (STORAGE_DIR set, e.g. Railway with a volume): this server owns
//   everything — /api/capture, /api/heads, /ws broadcasts, and image storage
//   on local disk, served under /files/.
const STORAGE_DIR = process.env.STORAGE_DIR || "";
const IMPORT_FEED_URL = process.env.IMPORT_FEED_URL || "";

const app = new Hono();

app.get("/api/health", (c) => c.json({ ok: true }));

// Raw image bytes in -> background-removed, trimmed PNG out (or null when the
// model found no subject — storing that would be a blank hole in the feed).
async function processImage(original) {
  // The slow part: model inference.
  const cut = await removeBg(new Uint8Array(original));

  // Trim the transparent margin so heads sit tight in the feed.
  let cutout;
  try {
    cutout = await sharp(cut).trim().png().toBuffer();
  } catch {
    cutout = await sharp(cut).png().toBuffer();
  }

  const stats = await sharp(cutout).stats();
  const alpha = stats.channels[stats.channels.length - 1];
  if (alpha.mean < 8) return null;
  return cutout;
}

// Pure compute endpoint used by the Cloudflare Worker.
app.post("/remove", async (c) => {
  try {
    const original = Buffer.from(await c.req.arrayBuffer());
    if (original.length === 0) {
      return c.json({ error: "empty body" }, 400);
    }
    const cutout = await processImage(original);
    if (!cutout) return c.json({ error: "no subject detected" }, 422);
    return c.body(cutout, 200, { "content-type": "image/png" });
  } catch (err) {
    console.error("[remove]", err);
    return c.json({ error: "failed to process image" }, 500);
  }
});

// ---------------- standalone mode: storage + API + live feed ----------------
let broadcast = () => {};
// Doorbell "ring" push over the same /ws the feed uses. Assigned in the wss block
// below (standalone mode only); a no-op until then so a stray call can't throw.
let broadcastRing = () => {};

if (STORAGE_DIR) {
  const manifestPath = join(STORAGE_DIR, "manifest.json");

  const readManifest = async () => {
    try {
      return JSON.parse(await readFile(manifestPath, "utf8"));
    } catch {
      return [];
    }
  };

  // Serialize manifest read/append/write so concurrent captures don't clobber
  // the feed.
  let chain = Promise.resolve();
  const withLock = (fn) => {
    const run = chain.then(fn, fn);
    chain = run.then(
      () => {},
      () => {}
    );
    return run;
  };

  app.get("/api/heads", async (c) => {
    const manifest = await readManifest();
    return c.json(manifest.slice().reverse());
  });

  // Doorbell trigger: the Pi orchestrator POSTs this on an RF burst. It just
  // fans a "ring" out to every connected page over the existing /ws — the page
  // runs the same capture() the on-screen button does. No body needed.
  app.post("/api/ring", (c) => {
    broadcastRing();
    return c.json({ ok: true });
  });

  app.post("/api/capture", async (c) => {
    try {
      const body = await c.req.json();
      const image = body?.image;
      if (!image || typeof image !== "string") {
        return c.json({ error: "missing image" }, 400);
      }
      const original = Buffer.from(
        image.replace(/^data:[^;]+;base64,/, ""),
        "base64"
      );

      const cutout = await processImage(original);
      if (!cutout) return c.json({ error: "no subject detected" }, 422);

      const id = randomUUID();
      const originalKey = `originals/${id}.jpg`;
      const cutoutKey = `cutouts/${id}.png`;
      await Promise.all([
        writeFile(join(STORAGE_DIR, originalKey), original),
        writeFile(join(STORAGE_DIR, cutoutKey), cutout),
      ]);

      const entry = {
        id,
        original: originalKey,
        cutout: cutoutKey,
        originalUrl: `/files/${originalKey}`,
        cutoutUrl: `/files/${cutoutKey}`,
        createdAt: new Date().toISOString(),
      };

      await withLock(async () => {
        const manifest = await readManifest();
        manifest.push(entry);
        await writeFile(manifestPath, JSON.stringify(manifest));
        broadcast(manifest);
      });

      return c.json(entry);
    } catch (err) {
      console.error("[capture]", err);
      return c.json({ error: "failed to process image" }, 500);
    }
  });

  // Stored images.
  app.get("/files/:dir/:name", async (c) => {
    const { dir, name } = c.req.param();
    if (!["originals", "cutouts"].includes(dir) || name.includes(".."))
      return c.notFound();
    try {
      const data = await readFile(join(STORAGE_DIR, dir, name));
      return c.body(data, 200, {
        "content-type": name.endsWith(".png") ? "image/png" : "image/jpeg",
        "cache-control": "public, max-age=31536000, immutable",
      });
    } catch {
      return c.notFound();
    }
  });
}

// Static tablet app. HTML must revalidate on every load so deploys are not
// masked by stale cached pages.
app.use("/*", async (c, next) => {
  await next();
  const path = c.req.path;
  if (path === "/" || path.endsWith(".html")) {
    c.header("cache-control", "no-cache");
  }
});
app.use("/*", serveStatic({ root: "./public" }));
app.get("/", serveStatic({ path: "./public/index.html" }));

// One-time import of an existing feed (e.g. the R2 public bucket) into the
// local volume on first boot.
async function importFeed() {
  if (!IMPORT_FEED_URL || existsSync(join(STORAGE_DIR, "manifest.json"))) return;
  try {
    const base = IMPORT_FEED_URL.replace(/\/$/, "");
    const feed = await (await fetch(`${base}/manifest.json`)).json();
    const imported = [];
    for (const e of feed) {
      for (const key of [e.cutout, e.original]) {
        const res = await fetch(`${base}/${key}`);
        if (res.ok)
          await writeFile(
            join(STORAGE_DIR, key),
            Buffer.from(await res.arrayBuffer())
          );
      }
      imported.push({
        ...e,
        originalUrl: `/files/${e.original}`,
        cutoutUrl: `/files/${e.cutout}`,
      });
    }
    await writeFile(
      join(STORAGE_DIR, "manifest.json"),
      JSON.stringify(imported)
    );
    console.log(`imported ${imported.length} faces from ${base}`);
  } catch (err) {
    console.error("[import]", err.message);
  }
}

const port = Number(process.env.PORT) || 8080;

if (STORAGE_DIR) {
  await mkdir(join(STORAGE_DIR, "originals"), { recursive: true });
  await mkdir(join(STORAGE_DIR, "cutouts"), { recursive: true });
  await importFeed();
}

const server = serve({ fetch: app.fetch, port, hostname: "0.0.0.0" });
console.log(
  `facecapture ${STORAGE_DIR ? "standalone" : "compute"} server on :${port}`
);

// Live feed WebSocket (standalone mode only — on Cloudflare the Worker's
// Durable Object owns /ws).
if (STORAGE_DIR) {
  const { WebSocketServer } = await import("ws");
  const wss = new WebSocketServer({ server, path: "/ws" });
  wss.on("connection", async (sock) => {
    try {
      const manifest = JSON.parse(
        await readFile(join(STORAGE_DIR, "manifest.json"), "utf8")
      );
      sock.send(JSON.stringify({ type: "feed", heads: manifest.slice().reverse() }));
    } catch {
      sock.send(JSON.stringify({ type: "feed", heads: [] }));
    }
  });
  broadcast = (manifest) => {
    const msg = JSON.stringify({
      type: "feed",
      heads: manifest.slice().reverse(),
    });
    for (const client of wss.clients) {
      if (client.readyState === 1) client.send(msg);
    }
  };
  broadcastRing = () => {
    const msg = JSON.stringify({ type: "ring" });
    for (const client of wss.clients) {
      if (client.readyState === 1) client.send(msg);
    }
  };
}

// Pre-warm: load the model + onnx session at boot so the first real capture
// doesn't pay the model-load penalty.
sharp({
  create: { width: 64, height: 64, channels: 3, background: "#808080" },
})
  .jpeg()
  .toBuffer()
  .then((buf) => removeBg(new Uint8Array(buf)))
  .then(() => console.log("model pre-warmed"))
  .catch((err) => console.error("[prewarm]", err.message));
