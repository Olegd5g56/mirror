import type { AxiosError } from "axios";

function stripPydanticPrefix(msg: string): string {
  return msg.replace(/^(Value error|Assertion failed),\s*/, "");
}

export function apiErrorMessage(e: unknown, fallback = "Помилка"): string {
  const err = e as AxiosError<{ detail?: string | { msg: string }[] }>;
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return stripPydanticPrefix(detail[0].msg);
  return err?.message || fallback;
}
