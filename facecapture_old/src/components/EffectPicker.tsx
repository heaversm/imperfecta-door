"use client";

import { EFFECT_PRESETS } from "@/lib/constants-client";
import type { EffectPreset } from "@/types";

interface EffectPickerProps {
  onSelect: (effect: EffectPreset) => void;
  onSkip: () => void;
  loading?: boolean;
  loadingEffectId?: string;
}

export default function EffectPicker({
  onSelect,
  onSkip,
  loading,
  loadingEffectId,
}: EffectPickerProps) {
  return (
    <div className="flex flex-col items-center gap-4">
      <h3 className="text-lg font-semibold text-white">Add a fun effect?</h3>
      <div className="grid grid-cols-3 gap-3">
        {EFFECT_PRESETS.map((effect) => (
          <button
            key={effect.id}
            onClick={() => onSelect(effect)}
            disabled={loading}
            className={`flex flex-col items-center gap-1 rounded-xl border-2 px-4 py-3
                       transition-all hover:scale-105 active:scale-95
                       disabled:opacity-50 disabled:hover:scale-100
                       ${
                         loadingEffectId === effect.id
                           ? "border-purple-400 bg-purple-500/20"
                           : "border-white/20 bg-white/5 hover:border-white/40"
                       }`}
          >
            <span className="text-2xl">{effect.emoji}</span>
            <span className="text-sm text-white">{effect.label}</span>
          </button>
        ))}
      </div>
      <button
        onClick={onSkip}
        disabled={loading}
        className="mt-2 text-sm text-white/50 underline transition-colors
                   hover:text-white/80 disabled:opacity-50"
      >
        Skip - use original
      </button>
    </div>
  );
}
