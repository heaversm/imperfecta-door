export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { warmUpModel } = await import("@/lib/background-removal");
    // Warm up the model in the background so first request is fast
    warmUpModel().catch((err) => {
      console.warn("[instrumentation] Failed to warm up bg-removal model:", err);
    });
  }
}
