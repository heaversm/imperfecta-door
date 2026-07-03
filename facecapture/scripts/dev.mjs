// Local UI dev server — no Docker needed.
//
//   npm run dev:ui   →  http://localhost:8790
//
// Serves container/public/ straight from disk (edit + refresh) and proxies
// /api/* and the /ws WebSocket to the live deployment, so the feed and
// captures are real. Note: captures made here land in the LIVE feed.
import { createServer } from "node:http";
import { connect as tlsConnect } from "node:tls";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const ORIGIN = "facecapture.mike-3cd.workers.dev";
const PORT = Number(process.env.PORT) || 8790;
const ROOT = fileURLToPath(new URL("../container/public", import.meta.url));

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".css": "text/css",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

const collect = (req) =>
  new Promise((resolve) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
  });

const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");

  // API → live deployment
  if (url.pathname.startsWith("/api/")) {
    try {
      const body = await collect(req);
      const r = await fetch(`https://${ORIGIN}${req.url}`, {
        method: req.method,
        headers: { "content-type": req.headers["content-type"] ?? "" },
        body: ["GET", "HEAD"].includes(req.method) ? undefined : body,
      });
      res.writeHead(r.status, {
        "content-type": r.headers.get("content-type") ?? "text/plain",
      });
      res.end(Buffer.from(await r.arrayBuffer()));
    } catch (err) {
      res.writeHead(502);
      res.end(`proxy error: ${err.message}`);
    }
    return;
  }

  // everything else → local files
  const p = url.pathname === "/" ? "/index.html" : normalize(url.pathname);
  try {
    const data = await readFile(join(ROOT, p));
    res.writeHead(200, {
      "content-type": MIME[extname(p)] ?? "application/octet-stream",
      "cache-control": "no-store",
    });
    res.end(data);
  } catch {
    res.writeHead(404);
    res.end("not found");
  }
});

// /ws → raw tunnel to the live WebSocket
server.on("upgrade", (req, socket, head) => {
  const upstream = tlsConnect(443, ORIGIN, { servername: ORIGIN }, () => {
    upstream.write(
      [
        `GET ${req.url} HTTP/1.1`,
        `Host: ${ORIGIN}`,
        `Connection: Upgrade`,
        `Upgrade: websocket`,
        `Sec-WebSocket-Key: ${req.headers["sec-websocket-key"]}`,
        `Sec-WebSocket-Version: ${req.headers["sec-websocket-version"] ?? "13"}`,
        "",
        "",
      ].join("\r\n")
    );
    if (head?.length) upstream.write(head);
    socket.pipe(upstream);
    upstream.pipe(socket);
  });
  upstream.on("error", () => socket.destroy());
  socket.on("error", () => upstream.destroy());
});

server.listen(PORT, () => {
  console.log(`UI dev server: http://localhost:${PORT}`);
  console.log(`editing:       container/public/`);
  console.log(`api + ws:      proxied to https://${ORIGIN} (LIVE data)`);
});
