import { NextResponse } from "next/server";
import { listHeads } from "@/lib/storage";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const heads = await listHeads();
    return NextResponse.json(heads);
  } catch (error) {
    console.error("[heads] Error:", error);
    return NextResponse.json([], { status: 500 });
  }
}
