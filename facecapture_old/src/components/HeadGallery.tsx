"use client";

import { useState, useEffect, useRef } from "react";
import FloatingHead from "./FloatingHead";
import type { HeadEntry } from "@/types";

interface HeadGalleryProps {
  onNewHead?: (head: HeadEntry) => void;
}

export default function HeadGallery({ onNewHead }: HeadGalleryProps) {
  const [heads, setHeads] = useState<HeadEntry[]>([]);
  const knownIdsRef = useRef<Set<string>>(new Set());
  const [newIds, setNewIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fetchHeads = async () => {
      try {
        const res = await fetch("/api/heads");
        const data: HeadEntry[] = await res.json();

        // Detect new heads
        const freshIds = new Set<string>();
        for (const head of data) {
          if (!knownIdsRef.current.has(head.id)) {
            freshIds.add(head.id);
            knownIdsRef.current.add(head.id);
            onNewHead?.(head);
          }
        }

        if (freshIds.size > 0) {
          setNewIds((prev) => new Set([...prev, ...freshIds]));
          // Clear "new" status after animation
          setTimeout(() => {
            setNewIds((prev) => {
              const next = new Set(prev);
              freshIds.forEach((id) => next.delete(id));
              return next;
            });
          }, 1000);
        }

        setHeads(data);
      } catch (err) {
        console.error("Failed to fetch heads:", err);
      }
    };

    // Initial fetch
    fetchHeads();

    // Poll every 3 seconds
    const interval = setInterval(fetchHeads, 3000);
    return () => clearInterval(interval);
  }, [onNewHead]);

  if (heads.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-lg text-white/40">No faces collected yet. Be the first!</p>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap content-start items-start p-8 pl-12">
      {heads.map((head, i) => (
        <div key={head.id} style={{ zIndex: i }}>
          <FloatingHead head={head} isNew={newIds.has(head.id)} />
        </div>
      ))}
    </div>
  );
}
