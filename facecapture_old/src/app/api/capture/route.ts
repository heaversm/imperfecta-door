import { NextResponse } from "next/server";
import { removeBackgroundFromImage } from "@/lib/background-removal";
import { saveHead } from "@/lib/storage";
import type { CaptureResponse } from "@/types";

export async function POST(request: Request): Promise<NextResponse<CaptureResponse>> {
  try {
    const { image } = await request.json();

    if (!image || typeof image !== "string") {
      return NextResponse.json(
        { success: false, error: "Missing image data" },
        { status: 400 }
      );
    }

    // Decode base64 image
    const base64Data = image.replace(/^data:[^;]+;base64,/, "");
    const imageBuffer = Buffer.from(base64Data, "base64");
    console.log(`[capture] Received image: ${imageBuffer.length} bytes, starts with: ${imageBuffer.slice(0, 4).toString("hex")}`);

    // Remove background
    const cutoutBuffer = await removeBackgroundFromImage(imageBuffer);

    // Save to disk
    const head = await saveHead(imageBuffer, cutoutBuffer);

    return NextResponse.json({ success: true, head });
  } catch (error) {
    console.error("[capture] Error:", error);
    return NextResponse.json(
      { success: false, error: "Failed to process image" },
      { status: 500 }
    );
  }
}
