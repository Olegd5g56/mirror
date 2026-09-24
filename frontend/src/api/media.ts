import { api } from "./client";

export interface Media {
  id: number;
  name: string;
  type: "image" | "video";
  status: "pending" | "processing" | "converting" | "ready" | "failed";
  progress: number;
  mime_type: string;
  size_bytes: number;
  duration_sec: number | null;
  width: number | null;
  height: number | null;
  thumb_url: string | null;
  poster_url: string | null;
  air_url: string | null;
  created_at: string;
  used_in_events: number;
  used_in_schedule: number;
}

export async function listMedia(): Promise<Media[]> {
  const { data } = await api.get<Media[]>("/media");
  return data;
}

export async function deleteMedia(id: number): Promise<void> {
  await api.delete(`/media/${id}`);
}
