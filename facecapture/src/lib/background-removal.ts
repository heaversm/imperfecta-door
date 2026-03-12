import { removeBackground } from "@imgly/background-removal-node";
import sharp from "sharp";
import { RESIZE_WIDTH } from "./constants";

let modelWarmedUp = false;

export async function warmUpModel() {
  if (modelWarmedUp) return;
  console.log("[bg-removal] Warming up model...");
  // Run a small test image through to trigger model download/load
  const testImg = await sharp({
    create: { width: 64, height: 64, channels: 3, background: { r: 128, g: 128, b: 128 } },
  })
    .png()
    .toBuffer();

  try {
    await removeBackground(
      new Blob([new Uint8Array(testImg)], { type: "image/png" }),
      { model: "small", output: { format: "image/png" } }
    );
    modelWarmedUp = true;
    console.log("[bg-removal] Model warmed up successfully");
  } catch (e) {
    console.warn("[bg-removal] Warm-up failed (will retry on first request):", e);
  }
}

export async function removeBackgroundFromImage(
  imageBuffer: Buffer
): Promise<Buffer> {
  // Resize to target width first (biggest speed optimization)
  const resized = await sharp(imageBuffer)
    .resize(RESIZE_WIDTH)
    .jpeg({ quality: 90 })
    .toBuffer();

  console.log("[bg-removal] Processing image...");
  const startTime = Date.now();

  const blob = await removeBackground(
    new Blob([new Uint8Array(resized)], { type: "image/jpeg" }),
    { model: "small", output: { format: "image/png" } }
  );

  const arrayBuffer = await blob.arrayBuffer();
  const resultBuffer = Buffer.from(arrayBuffer);

  console.log(`[bg-removal] Done in ${Date.now() - startTime}ms`);

  // Trim transparent pixels
  const trimmed = await sharp(resultBuffer)
    .trim()
    .png()
    .toBuffer();

  return trimmed;
}
