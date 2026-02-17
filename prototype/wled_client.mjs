#!/usr/bin/env node
import axios from "axios";

function parseArgs(argv) {
  const out = { host: "", cmd: "" };
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === "--host") {
      out.host = argv[i + 1] || "";
      i += 1;
      continue;
    }
    if (!out.cmd) {
      out.cmd = token;
    }
  }
  return out;
}

async function main() {
  const { host, cmd } = parseArgs(process.argv);
  if (!host || !cmd) {
    console.error("Usage: node wled_client.mjs --host <WLED_IP> <status|on|off>");
    process.exit(1);
  }

  const base = `http://${host}`;

  try {
    if (cmd === "status") {
      const res = await axios.get(`${base}/json/state`, { timeout: 5000 });
      console.log(JSON.stringify(res.data, null, 2));
      return;
    }

    if (cmd === "on") {
      const res = await axios.post(`${base}/json/state`, { on: true }, { timeout: 5000 });
      console.log(JSON.stringify({ ok: true, on: res.data?.on }, null, 2));
      return;
    }

    if (cmd === "off") {
      const res = await axios.post(`${base}/json/state`, { on: false }, { timeout: 5000 });
      console.log(JSON.stringify({ ok: true, on: res.data?.on }, null, 2));
      return;
    }

    console.error(`Unsupported command: ${cmd}`);
    process.exit(1);
  } catch (err) {
    const message = err?.response?.data || err?.message || String(err);
    console.error("Request failed:", message);
    process.exit(1);
  }
}

main();
