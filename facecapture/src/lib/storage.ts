import { supabase } from "./supabase";
import { HEADS_PER_ROW } from "./constants";
import type { HeadEntry } from "@/types";

const BUCKET = "faces";

function getPublicUrl(path: string): string {
  const { data } = supabase.storage.from(BUCKET).getPublicUrl(path);
  return data.publicUrl;
}

function rowToHeadEntry(row: {
  id: string;
  original_path: string;
  cutout_path: string;
  effect_path: string | null;
  effect_name: string | null;
  gallery_row: number;
  gallery_col: number;
  gallery_rotation: number;
  gallery_scale: number;
  created_at: string;
}): HeadEntry {
  return {
    id: row.id,
    originalUrl: getPublicUrl(row.original_path),
    cutoutUrl: getPublicUrl(row.cutout_path),
    effectUrl: row.effect_path ? getPublicUrl(row.effect_path) : undefined,
    effectName: row.effect_name ?? undefined,
    galleryPosition: {
      row: row.gallery_row,
      col: row.gallery_col,
      rotation: row.gallery_rotation,
      scale: row.gallery_scale,
    },
    createdAt: row.created_at,
  };
}

export async function saveHead(
  originalBuffer: Buffer,
  cutoutBuffer: Buffer
): Promise<HeadEntry> {
  // Count existing rows to determine grid position
  const { count } = await supabase
    .from("heads")
    .select("*", { count: "exact", head: true });
  const index = count ?? 0;
  const row = Math.floor(index / HEADS_PER_ROW);
  const col = index % HEADS_PER_ROW;

  // Insert DB row first to get the UUID
  const { data: dbRow, error: dbError } = await supabase
    .from("heads")
    .insert({
      original_path: "placeholder",
      cutout_path: "placeholder",
      gallery_row: row,
      gallery_col: col,
      gallery_rotation: (Math.random() - 0.5) * 20,
      gallery_scale: 0.9 + Math.random() * 0.2,
    })
    .select()
    .single();

  if (dbError || !dbRow) throw new Error(`DB insert failed: ${dbError?.message}`);

  const id = dbRow.id;
  const originalPath = `originals/${id}.jpg`;
  const cutoutPath = `cutouts/${id}.png`;

  // Upload images
  const [origUpload, cutoutUpload] = await Promise.all([
    supabase.storage.from(BUCKET).upload(originalPath, originalBuffer, {
      contentType: "image/jpeg",
    }),
    supabase.storage.from(BUCKET).upload(cutoutPath, cutoutBuffer, {
      contentType: "image/png",
    }),
  ]);

  if (origUpload.error) throw new Error(`Original upload failed: ${origUpload.error.message}`);
  if (cutoutUpload.error) throw new Error(`Cutout upload failed: ${cutoutUpload.error.message}`);

  // Update DB row with actual paths
  const { data: updated, error: updateError } = await supabase
    .from("heads")
    .update({ original_path: originalPath, cutout_path: cutoutPath })
    .eq("id", id)
    .select()
    .single();

  if (updateError || !updated) throw new Error(`DB update failed: ${updateError?.message}`);

  return rowToHeadEntry(updated);
}

export async function saveEffect(
  headId: string,
  effectBuffer: Buffer,
  effectName: string
): Promise<HeadEntry> {
  const effectPath = `effects/${headId}-${effectName}.png`;

  const { error: uploadError } = await supabase.storage
    .from(BUCKET)
    .upload(effectPath, effectBuffer, { contentType: "image/png", upsert: true });

  if (uploadError) throw new Error(`Effect upload failed: ${uploadError.message}`);

  const { data: updated, error: dbError } = await supabase
    .from("heads")
    .update({ effect_path: effectPath, effect_name: effectName })
    .eq("id", headId)
    .select()
    .single();

  if (dbError || !updated) throw new Error(`DB update failed: ${dbError?.message}`);

  return rowToHeadEntry(updated);
}

export async function listHeads(): Promise<HeadEntry[]> {
  const { data, error } = await supabase
    .from("heads")
    .select("*")
    .order("created_at", { ascending: true });

  if (error) throw new Error(`DB query failed: ${error.message}`);

  return (data ?? []).map(rowToHeadEntry);
}

export async function loadImage(
  type: "originals" | "cutouts" | "effects",
  filename: string
): Promise<Buffer> {
  const path = `${type}/${filename}`;
  const { data, error } = await supabase.storage.from(BUCKET).download(path);

  if (error) throw new Error(`Download failed: ${error.message}`);

  const arrayBuffer = await data.arrayBuffer();
  return Buffer.from(arrayBuffer);
}
