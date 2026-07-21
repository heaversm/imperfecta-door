// Verifies the doorbell path end to end at the transport level:
// connect to /ws, POST /api/ring, assert a {type:'ring'} message arrives.
// Run against a live standalone server:
//   STORAGE_DIR=/tmp/facecapture-data PORT=8090 node server.mjs   (in one shell)
//   node test-ring.mjs                                            (in another)
import WebSocket from "ws";

const PORT = Number(process.env.PORT) || 8090;
const ws = new WebSocket(`ws://localhost:${PORT}/ws`);

const timer = setTimeout(() => {
  console.error("FAIL: no ring message within 5s");
  process.exit(1);
}, 5000);

ws.on("open", async () => {
  const res = await fetch(`http://localhost:${PORT}/api/ring`, { method: "POST" });
  if (!res.ok) {
    console.error(`FAIL: /api/ring returned ${res.status}`);
    process.exit(1);
  }
});

ws.on("message", (data) => {
  const msg = JSON.parse(data.toString());
  if (msg.type === "ring") {
    clearTimeout(timer);
    console.log("PASS: received ring over /ws");
    process.exit(0);
  }
});

ws.on("error", (err) => {
  console.error("FAIL: ws error", err.message);
  process.exit(1);
});
