import type { EffectPreset } from "@/types";

export const EFFECT_PRESETS: EffectPreset[] = [
  {
    id: "bugged-eyes",
    label: "Bug Eyes",
    prompt:
      "Make the eyes comically huge and bugged out, like a cartoon character surprised. Keep the rest of the face the same.",
    emoji: "👀",
  },
  {
    id: "cartoon",
    label: "Cartoon",
    prompt:
      "Transform this face into a colorful cartoon/anime style with bold outlines and vibrant colors. Keep it recognizable.",
    emoji: "🎨",
  },
  {
    id: "vampire",
    label: "Vampire",
    prompt:
      "Make this person look like a vampire with pale skin, fangs, red eyes, and a gothic appearance.",
    emoji: "🧛",
  },
  {
    id: "alien",
    label: "Alien",
    prompt:
      "Transform this face to look like a friendly alien with green-tinted skin, larger eyes, and subtle otherworldly features.",
    emoji: "👽",
  },
  {
    id: "neon",
    label: "Neon",
    prompt:
      "Apply a vibrant neon/cyberpunk effect with glowing neon colors, electric blue and hot pink highlights.",
    emoji: "💜",
  },
  {
    id: "old-timey",
    label: "Old Timey",
    prompt:
      "Make this look like an old-timey sepia-toned daguerreotype photograph from the 1800s with vintage texture.",
    emoji: "📜",
  },
];
