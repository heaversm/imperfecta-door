"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import WebcamCapture from "./WebcamCapture";

type ModalStep = "capture" | "processing";

interface CaptureModalProps {
  open: boolean;
  onClose: () => void;
}

export default function CaptureModal({ open, onClose }: CaptureModalProps) {
  const [step, setStep] = useState<ModalStep>("capture");
  const [flash, setFlash] = useState(false);

  const reset = useCallback(() => {
    setStep("capture");
    setFlash(false);
  }, []);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  const handleCapture = useCallback(async (imageSrc: string) => {
    setFlash(true);
    setTimeout(() => setFlash(false), 200);

    setStep("processing");

    try {
      const res = await fetch("/api/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageSrc }),
      });
      const data = await res.json();

      if (data.success) {
        handleClose();
      } else {
        console.error("Capture failed:", data.error);
        setStep("capture");
      }
    } catch (error) {
      console.error("Capture error:", error);
      setStep("capture");
    }
  }, [handleClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) handleClose();
          }}
        >
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

          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ type: "spring", damping: 20, stiffness: 300 }}
            className="relative mx-4 flex max-h-[90vh] w-full max-w-lg flex-col items-center
                       gap-6 overflow-y-auto rounded-3xl bg-gray-900 p-8"
          >
            <button
              onClick={handleClose}
              className="absolute right-4 top-4 text-2xl text-white/50 transition-colors hover:text-white"
            >
              &times;
            </button>

            {step === "capture" && (
              <>
                <h2 className="text-xl font-bold text-white">Add Your Face!</h2>
                <WebcamCapture onCapture={handleCapture} />
              </>
            )}

            {step === "processing" && (
              <div className="flex flex-col items-center gap-4 py-12">
                <div className="h-12 w-12 animate-spin rounded-full border-4 border-white/20 border-t-white" />
                <p className="text-lg text-white">Extracting your face...</p>
                <p className="text-sm text-white/50">This takes a few seconds</p>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
