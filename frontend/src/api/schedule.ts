import { api } from "./client";

export interface ScheduleItem {
  id: number;
  media_id: number;
  media_name: string;
  start_at: string;
}

export async function listSchedule(params: {
  from?: string;
  to?: string;
  date?: string;
}): Promise<ScheduleItem[]> {
  const { data } = await api.get<ScheduleItem[]>("/schedule", { params });
  return data;
}

export async function createSchedule(body: {
  media_id: number;
  start_at: string;
}): Promise<ScheduleItem> {
  const { data } = await api.post<ScheduleItem>("/schedule", body);
  return data;
}

export async function deleteSchedule(id: number): Promise<void> {
  await api.delete(`/schedule/${id}`);
}
