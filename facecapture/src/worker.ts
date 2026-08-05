// Worker front door + storage layer. The Worker (via this Durable Object) owns
// all R2 access through a native binding — no S3 credentials anywhere. The
// container is pure compute: it runs the background-removal model and serves
// the static tablet app; everything else happens here.
import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  REMOVAL: DurableObjectNamespace<RemovalContainer>;
  BUCKET: R2Bucket;
  R2_PUBLIC_URL: string;
}

interface FeedEntry {
  id: string;
  original: string;
  cutout: string;
  originalUrl: string;
  cutoutUrl: string;
  createdAt: string;
}

const MANIFEST_KEY = "manifest.json";

// The kiosk page runs as a plain local HTML file (e.g. on a Raspberry Pi) and
// calls this API cross-origin, so every /api response carries CORS headers.
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "content-type",
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", ...CORS },
  });
}

export class RemovalContainer extends Container<Env> {
  // Matches the port the Node server listens on (see container/server.mjs).
  defaultPort = 8080;
  // Keep the container warm for a while so captures stay snappy; it sleeps when idle.
  sleepAfter = "30m";

  // Serialize manifest read/append/write so concurrent captures don't clobber
  // the feed. All traffic pins to the "main" instance, so one chain is enough.
  private chain: Promise<unknown> = Promise.resolve();
  private withLock<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.chain.then(fn, fn);
    this.chain = run.then(
      () => {},
      () => {}
    );
    return run;
  }

  override async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "OPTIONS" && url.pathname.startsWith("/api/")) {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (url.pathname === "/ws") return this.wsConnect(request);
    if (url.pathname === "/api/heads") return this.heads();
    if (url.pathname === "/api/capture" && request.method === "POST") {
      return this.capture(request);
    }
    // Static tablet app + /api/health live in the container.
    return super.fetch(request);
  }

  // Live feed updates: clients hold a WebSocket and get the full feed pushed
  // on connect and after every capture — no polling.
  private wsConnect(request: Request): Response {
    if (request.headers.get("Upgrade") !== "websocket") {
      return new Response("expected websocket", { status: 426 });
    }
    const pair = new WebSocketPair();
    this.ctx.acceptWebSocket(pair[1]);
    this.readManifest()
      .then((manifest) => {
        pair[1].send(
          JSON.stringify({ type: "feed", heads: manifest.slice().reverse() })
        );
      })
      .catch((err) => console.error("[ws connect]", err));
    return new Response(null, { status: 101, webSocket: pair[0] });
  }

  private broadcast(manifest: FeedEntry[]): void {
    const msg = JSON.stringify({
      type: "feed",
      heads: manifest.slice().reverse(),
    });
    for (const ws of this.ctx.getWebSockets()) {
      try {
        ws.send(msg);
      } catch {
        // client gone; hibernation API cleans it up
      }
    }
  }

  // Required for the WebSocket hibernation API; the feed is server-push only.
  async webSocketMessage(): Promise<void> {}
  async webSocketClose(): Promise<void> {}

  private publicUrl(key: string): string {
    return `${this.env.R2_PUBLIC_URL.replace(/\/$/, "")}/${key}`;
  }

  private async readManifest(): Promise<FeedEntry[]> {
    const obj = await this.env.BUCKET.get(MANIFEST_KEY);
    if (!obj) return [];
    return (await obj.json()) as FeedEntry[];
  }

  // Newest-first feed for the web app.
  private async heads(): Promise<Response> {
    try {
      const manifest = await this.readManifest();
      return json(manifest.slice().reverse());
    } catch (err) {
      console.error("[heads]", err);
      return json({ error: "failed to read feed" }, 500);
    }
  }

  // Capture: raw image in -> container removes the background -> stored in R2
  // via the binding -> feed entry out.
  private async capture(request: Request): Promise<Response> {
    try {
      const body = (await request.json()) as { image?: string };
      const image = body?.image;
      if (!image || typeof image !== "string") {
        return json({ error: "missing image" }, 400);
      }

      const base64 = image.replace(/^data:[^;]+;base64,/, "");
      const original = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));

      // The slow part: model inference in the container.
      const res = await this.containerFetch(
        "http://container/remove",
        {
          method: "POST",
          headers: { "content-type": "application/octet-stream" },
          body: original,
        },
        this.defaultPort
      );
      if (!res.ok) {
        console.error("[capture] container /remove failed", res.status);
        return json({ error: "failed to process image" }, 500);
      }
      const cutout = await res.arrayBuffer();

      const id = crypto.randomUUID();
      const originalKey = `originals/${id}.jpg`;
      const cutoutKey = `cutouts/${id}.png`;

      await Promise.all([
        this.env.BUCKET.put(originalKey, original, {
          httpMetadata: { contentType: "image/jpeg" },
        }),
        this.env.BUCKET.put(cutoutKey, cutout, {
          httpMetadata: { contentType: "image/png" },
        }),
      ]);

      const entry: FeedEntry = {
        id,
        original: originalKey,
        cutout: cutoutKey,
        originalUrl: this.publicUrl(originalKey),
        cutoutUrl: this.publicUrl(cutoutKey),
        createdAt: new Date().toISOString(),
      };

      await this.withLock(async () => {
        const manifest = await this.readManifest();
        manifest.push(entry);
        await this.env.BUCKET.put(MANIFEST_KEY, JSON.stringify(manifest), {
          httpMetadata: { contentType: "application/json" },
        });
        this.broadcast(manifest);
      });

      return json(entry);
    } catch (err) {
      console.error("[capture]", err);
      return json({ error: "failed to process image" }, 500);
    }
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // "main" pins all traffic to one container instance so the manifest write
    // lock and feed stay consistent.
    return getContainer(env.REMOVAL, "main").fetch(request);
  },
};
