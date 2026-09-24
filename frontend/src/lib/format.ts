export const TZ = "Europe/Kyiv";

export const MONTH_NAMES = [
  "Січень",
  "Лютий",
  "Березень",
  "Квітень",
  "Травень",
  "Червень",
  "Липень",
  "Серпень",
  "Вересень",
  "Жовтень",
  "Листопад",
  "Грудень",
];

export const DAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"];

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Календарні частини дати в Europe/Kyiv, не в TZ браузера. */
export function kyivParts(d: Date = new Date()): {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
} {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "0";
  return {
    year: Number(get("year")),
    month: Number(get("month")),
    day: Number(get("day")),
    hour: Number(get("hour") === "24" ? "0" : get("hour")),
    minute: Number(get("minute")),
  };
}

export function kyivDateKey(d: Date): string {
  const p = kyivParts(d);
  return `${p.year}-${pad2(p.month)}-${pad2(p.day)}`;
}

export function isoDate(year: number, month: number, day: number): string {
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

export function formatTime(iso: string): string {
  const p = kyivParts(new Date(iso));
  return `${pad2(p.hour)}:${pad2(p.minute)}`;
}

export function timeToHhMm(t: string): string {
  return t.slice(0, 5);
}

/** Chrome дає HH:MM, інколи HH:MM:SS — завжди нормалізуємо до HH:MM:SS. */
export function normalizeTime(value: string): string {
  const parts = value.split(":");
  const h = pad2(Number(parts[0]) || 0);
  const m = pad2(Number(parts[1]) || 0);
  const s = pad2(Number(parts[2]) || 0);
  return `${h}:${m}:${s}`;
}

export function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** Понеділок = 0 … неділя = 6 для 1-го числа місяця (Kyiv calendar). */
export function mondayIndexOfFirst(year: number, month: number): number {
  const utc = Date.UTC(year, month - 1, 1);
  const dow = new Date(utc).getUTCDay();
  return dow === 0 ? 6 : dow - 1;
}
