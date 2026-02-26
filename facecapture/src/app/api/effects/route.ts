import { NextResponse } from "next/server";
import { applyEffect } from "@/lib/effects";
import { loadImage, saveEffect } from "@/lib/storage";
import type { EffectResponse } from "@/types";

export async function POST(request: Request): Promise<NextResponse<EffectResponse>> {
  try {
    const { headId, effectId, prompt } = await request.json();

    if (!headId || !effectId || !prompt) {
      return NextResponse.json(
        { success: false, error: "Missing required fields" },
        { status: 400 }
      );
    }

    // Load the cutout image
    const cutoutBuffer = await loadImage("cutouts", `${headId}.png`);

    // Apply effect via Gemini
    const effectBuffer = await applyEffect(cutoutBuffer, prompt);

    // Save the effect
    const head = await saveEffect(headId, effectBuffer, effectId);

    return NextResponse.json({ success: true, head });
  } catch (error) {
    console.error("[effects] Error:", error);
    return NextResponse.json(
      { success: false, error: "Failed to apply effect" },
      { status: 500 }
    );
  }
}
