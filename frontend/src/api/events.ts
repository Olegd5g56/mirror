import { api } from "./client";

export interface EventItem {
  id: number;
  name: string;
  start_at: string;
  end_at: string;
  duration: string;
  until_midnight: boolean;
  media_id: number;
  media_name: string;
}

export async function listEvents(): Promise<EventItem[]> {
  const { data } = await api.get<EventItem[]>("/events");
  return data;
}

export async function createEvent(body: {
  name: string;
  start_at: string;
  end_at: string;
  media_id: number;
}): Promise<EventItem> {
  const { data } = await api.post<EventItem>("/events", body);
  return data;
}

export async function deleteEvent(id: number): Promise<void> {
  await api.delete(`/events/${id}`);
}
