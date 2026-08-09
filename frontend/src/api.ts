import type {
  ChartRange,
  ItemStats,
  MoversResponse,
  PriceSeries,
  SearchResult,
  Settings,
  StatusInfo,
  TrackedItem,
  TrendInfo,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    let detail = `${resp.status}`;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep status */
    }
    throw new Error(detail);
  }
  return resp.json();
}

export const api = {
  search: (q: string) =>
    request<{ results: SearchResult[] }>(
      `/api/items/search?q=${encodeURIComponent(q)}`
    ),
  tracked: () => request<{ tracked: TrackedItem[] }>("/api/tracked"),
  track: (item_id: number) =>
    request("/api/tracked", { method: "POST", body: JSON.stringify({ item_id }) }),
  untrack: (item_id: number) =>
    request(`/api/tracked/${item_id}`, { method: "DELETE" }),
  favorite: (item_id: number, favorite: boolean) =>
    request(`/api/tracked/${item_id}/favorite`, {
      method: "PUT",
      body: JSON.stringify({ favorite }),
    }),
  setGroup: (item_id: number, group: string) =>
    request(`/api/tracked/${item_id}/group`, {
      method: "PUT",
      body: JSON.stringify({ group }),
    }),
  prices: (item_id: number, range: ChartRange, ma: string[]) =>
    request<PriceSeries>(
      `/api/prices/${item_id}?range=${range}` +
        (ma.length ? `&ma=${ma.join(",")}` : "")
    ),
  stats: (item_id: number) => request<ItemStats>(`/api/stats/${item_id}`),
  trend: (item_id: number) => request<TrendInfo>(`/api/trends/${item_id}`),
  movers: (period: string) =>
    request<MoversResponse>(`/api/movers?period=${period}`),
  status: () => request<StatusInfo>("/api/status"),
  settings: () => request<Settings>("/api/settings"),
  updateSettings: (patch: Partial<Settings>) =>
    request<Settings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  collectNow: () => request("/api/status/collect-now", { method: "POST" }),
  exportUrl: (item_id: number, format: "csv" | "json", range: ChartRange) =>
    `/api/export/${item_id}?format=${format}&range=${range}`,
};
