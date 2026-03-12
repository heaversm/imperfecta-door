import { GoogleGenAI } from "@google/genai";
import { removeBackgroundFromImage } from "./background-removal";
import sharp from "sharp";

const genai = new GoogleGenAI({ apiKey: process.env.GOOGLE_API_KEY || "" });

export async function applyEffect(
  cutoutBuffer: Buffer,
  prompt: string
): Promise<Buffer> {
  // Convert cutout to base64 for Gemini
  // First flatten to white background for better Gemini results
  const flattenedBuffer = await sharp(cutoutBuffer)
    .flatten({ background: { r: 255, g: 255, b: 255 } })
    .png()
    .toBuffer();

  const base64Image = flattenedBuffer.toString("base64");

  console.log("[effects] Sending to Gemini...");
  const startTime = Date.now();

  const response = await genai.models.generateContent({
    model: "gemini-2.0-flash-preview-image-generation",
    contents: [
      {
        role: "user",
        parts: [
          {
            inlineData: {
              mimeType: "image/png",
              data: base64Image,
            },
          },
          {
            text: `Edit this portrait photo: ${prompt}. Keep the same framing and composition. Output the edited image.`,
          },
        ],
      },
    ],
    config: {
      responseModalities: ["TEXT", "IMAGE"],
    },
  });

  console.log(`[effects] Gemini responded in ${Date.now() - startTime}ms`);

  // Extract image from response
  const parts = response.candidates?.[0]?.content?.parts;
  if (!parts) throw new Error("No response from Gemini");

  for (const part of parts) {
    if (part.inlineData?.data) {
      const resultBuffer = Buffer.from(part.inlineData.data, "base64");

      // Re-run through bg removal to restore transparency
      console.log("[effects] Re-running bg removal for transparency...");
      const transparentResult = await removeBackgroundFromImage(resultBuffer);

      return transparentResult;
    }
  }

  throw new Error("No image in Gemini response");
}
