export interface HeadEntry {
  id: string;
  originalUrl: string;
  cutoutUrl: string;
  effectUrl?: string;
  effectName?: string;
  galleryPosition: {
    row: number;
    col: number;
    rotation: number;
    scale: number;
  };
  createdAt: string;
}

export interface CaptureResponse {
  success: boolean;
  head?: HeadEntry;
  error?: string;
}

export interface EffectResponse {
  success: boolean;
  head?: HeadEntry;
  error?: string;
}

export type EffectPreset = {
  id: string;
  label: string;
  prompt: string;
  emoji: string;
};
