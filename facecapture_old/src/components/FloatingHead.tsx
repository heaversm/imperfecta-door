"use client";

import { motion } from "framer-motion";
import type { HeadEntry } from "@/types";

interface FloatingHeadProps {
  head: HeadEntry;
  isNew?: boolean;
}

export default function FloatingHead({ head, isNew }: FloatingHeadProps) {
  const { rotation, scale } = head.galleryPosition;
  const src = head.effectUrl || head.cutoutUrl;

  return (
    <motion.div
      initial={isNew ? { scale: 0, opacity: 0, rotate: rotation - 20 } : false}
      animate={{ scale: 1, opacity: 1, rotate: rotation }}
      transition={
        isNew
          ? { type: "spring", stiffness: 200, damping: 15, mass: 0.8 }
          : { duration: 0 }
      }
      className="inline-block"
      style={{
        transform: `scale(${scale})`,
        //filter: "drop-shadow(0 4px 12px rgba(0,0,0,0.5))",
        marginLeft: "-50px",
        marginTop: "-50px",
      }}
    >
      <img
        src={src}
        alt="Collected face"
        className="h-[200px] w-auto select-none pointer-events-none"
        draggable={false}
      />
    </motion.div>
  );
}
