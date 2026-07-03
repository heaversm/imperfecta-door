import { removeBackground } from "@imgly/background-removal-node";

// "small" is the fastest model variant — best fit for "remove the bg as fast
// as possible". Swap to "medium" for cleaner edges at higher latency.
const MODEL = "small";

// The library needs a MIME type to decode the input, so sniff the magic bytes.
function sniffMime(bytes) {
  if (bytes[0] === 0xff && bytes[1] === 0xd8) return "image/jpeg";
  if (bytes[0] === 0x89 && bytes[1] === 0x50) return "image/png";
  if (bytes[0] === 0x52 && bytes[1] === 0x49) return "image/webp";
  return "image/jpeg";
}

/**
 * Remove the background from a raw image buffer.
 * @param {Uint8Array} input - source image bytes (jpeg/png/webp)
 * @returns {Promise<Buffer>} PNG with transparent background
 */
export async function removeBg(input) {
  const blob = new Blob([input], { type: sniffMime(input) });
  const result = await removeBackground(blob, {
    model: MODEL,
    output: { format: "image/png" },
  });
  const ab = await result.arrayBuffer();
  return Buffer.from(ab);
}
