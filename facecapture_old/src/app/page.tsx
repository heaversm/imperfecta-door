"use client";

import { useRef, useState, useCallback } from "react";
import Webcam from "react-webcam";
import { AnimatePresence, motion } from "framer-motion";
import HeadGallery from "@/components/HeadGallery";

export default function Home() {
  const webcamRef = useRef<Webcam>(null);
  const [capturing, setCapturing] = useState(false);
  const [flash, setFlash] = useState(false);

  const handleCapture = useCallback(async () => {
    if (capturing || !webcamRef.current) return;
    const imageSrc = webcamRef.current.getScreenshot();
    if (!imageSrc) return;

    setFlash(true);
    setTimeout(() => setFlash(false), 200);
    setCapturing(true);

    try {
      await fetch("/api/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageSrc }),
      });
    } catch (error) {
      console.error("Capture error:", error);
    }

    setCapturing(false);
  }, [capturing]);

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#0a0a0a]">
      {/* Live webcam feed */}
      <div className="fixed bottom-28 left-1/2 z-40 -translate-x-1/2 overflow-hidden rounded-2xl border-2 border-white/20 shadow-2xl">
        <Webcam
          ref={webcamRef}
          audio={false}
          screenshotFormat="image/jpeg"
          mirrored
          width={320}
          height={240}
          videoConstraints={{ width: 1280, height: 720, facingMode: "user" }}
        />
      </div>

      {/* Flash overlay */}
      <AnimatePresence>
        {flash && (
          <motion.div
            initial={{ opacity: 1 }}
            animate={{ opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="pointer-events-none fixed inset-0 z-[60] bg-white"
          />
        )}
      </AnimatePresence>

      {/* Gallery fills the viewport */}
      <HeadGallery />

      {/* Add Your Face button */}
      <div className="fixed bottom-8 left-1/2 z-40 -translate-x-1/2">
        <button
          onClick={handleCapture}
          disabled={capturing}
          className="rounded-full bg-white px-8 py-4 text-lg font-bold text-black
                     shadow-2xl transition-all hover:scale-105 hover:bg-gray-100
                     active:scale-95 disabled:opacity-50 disabled:hover:scale-100"
        >
          {capturing ? "Processing..." : "Add Your Face"}
        </button>
      </div>
    </main>
  );
}
