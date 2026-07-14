import type { ForecastSnapshot, HistoryPoint } from "./types";

export async function fetchLatest(): Promise<ForecastSnapshot> {
  const res = await fetch("/api/latest.json");
  if (!res.ok) {
    throw new Error(`加载 latest.json 失败 (${res.status})`);
  }
  return (await res.json()) as ForecastSnapshot;
}

export async function fetchHistory(): Promise<HistoryPoint[]> {
  const res = await fetch("/api/history");
  if (!res.ok) {
    throw new Error(`加载历史失败 (${res.status})`);
  }
  return (await res.json()) as HistoryPoint[];
}
