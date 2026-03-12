"use client";

import { useRef, useCallback } from "react";
import Webcam from "react-webcam";

interface WebcamCaptureProps {
  onCapture: (imageSrc: string) => void;
  disabled?: boolean;
}

const videoConstraints = {
  width: 640,
  height: 480,
  facingMode: "user",
};

export default function WebcamCapture({ onCapture, disabled }: WebcamCaptureProps) {
  const webcamRef = useRef<Webcam>(null);

  const capture = useCallback(() => {
    if (webcamRef.current) {
      const imageSrc = webcamRef.current.getScreenshot();
      if (imageSrc) {
        onCapture(imageSrc);
      }
    }
  }, [onCapture]);

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative overflow-hidden rounded-2xl border-2 border-white/20">
        <Webcam
          ref={webcamRef}
          audio={false}
          screenshotFormat="image/jpeg"
          videoConstraints={videoConstraints}
          mirrored
          className="block w-full max-w-md"
        />
      </div>
      <button
        onClick={capture}
        disabled={disabled}
        className="rounded-full bg-white px-8 py-4 text-lg font-bold text-black
                   transition-all hover:scale-105 hover:bg-gray-100
                   active:scale-95 disabled:opacity-50 disabled:hover:scale-100"
      >
        Snap!
      </button>
    </div>
  );
}
