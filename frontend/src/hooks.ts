import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { ChartRange, Settings, PortfolioStats, Recipe, Alert } from "./types";

export function useStatus() {
  return useQuery({
    queryKey: ["status"],
    queryFn: api.status,
    refetchInterval: 60000,
  });
}

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
  });
}

export function useTracked() {
  return useQuery({
    queryKey: ["tracked"],
    queryFn: async () => {
      const res = await api.tracked();
      return res.tracked;
    },
    refetchInterval: 60000,
  });
}

export function usePrices(chartIds: number[], range: ChartRange, maKeys: string[]) {
  return useQuery({
    queryKey: ["prices", chartIds, range, maKeys],
    queryFn: async () => {
      if (!chartIds.length) return [];
      const single = chartIds.length === 1;
      const ma = single ? maKeys : [];
      return Promise.all(chartIds.map((id) => api.prices(id, range, ma)));
    },
    enabled: chartIds.length > 0,
    refetchInterval: 60000,
  });
}

export function useStats(itemId: number | null) {
  return useQuery({
    queryKey: ["stats", itemId],
    queryFn: () => (itemId ? api.stats(itemId) : null),
    enabled: !!itemId,
    refetchInterval: 60000,
  });
}

export function useTrend(itemId: number | null) {
  return useQuery({
    queryKey: ["trend", itemId],
    queryFn: () => (itemId ? api.trend(itemId) : null),
    enabled: !!itemId,
    refetchInterval: 60000,
  });
}

export function useMovers(period: string) {
  return useQuery({
    queryKey: ["movers", period],
    queryFn: () => api.movers(period),
    refetchInterval: 60000,
  });
}

export function useCollectNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/collector/run", { method: "POST" });
      if (!res.ok) throw new Error("Failed to trigger collection");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracked"] });
      qc.invalidateQueries({ queryKey: ["status"] });
    },
  });
}

export function useTrackItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.track,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tracked"] }),
  });
}

export function useUntrackItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.untrack,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tracked"] }),
  });
}

export function useFavoriteItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, fav }: { id: number; fav: boolean }) => api.favorite(id, fav),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tracked"] }),
  });
}

export function useSetGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, group }: { id: number; group: string }) => {
      const res = await fetch(`/api/tracked/${id}/group`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group }),
      });
      if (!res.ok) throw new Error("Failed to set group");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracked"] });
    },
  });
}

export function useDeleteGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (group: string) => {
      const res = await fetch(`/api/tracked/groups/${encodeURIComponent(group)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete group");
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracked"] });
    },
  });
}

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: async () => {
      const res = await fetch("/api/portfolio");
      if (!res.ok) throw new Error("Failed to fetch portfolio");
      return res.json() as Promise<PortfolioStats>;
    },
    refetchInterval: 60000,
  });
}

export function useAddPortfolioItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: { item_id: number; quantity: number; buy_price_per_item: number }) => {
      const res = await fetch("/api/portfolio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to add portfolio item");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }),
  });
}

export function useDeletePortfolioItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/portfolio/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete portfolio item");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }),
  });
}

export function useRecipes() {
  return useQuery({
    queryKey: ["recipes"],
    queryFn: async () => {
      const res = await fetch("/api/recipes");
      if (!res.ok) throw new Error("Failed to fetch recipes");
      const data = await res.json();
      return data.recipes as Recipe[];
    },
    refetchInterval: 60000,
  });
}

export function useCreateRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: any) => {
      const res = await fetch("/api/recipes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to create recipe");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipes"] }),
  });
}

export function useDeleteRecipe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/recipes/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete recipe");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recipes"] }),
  });
}

export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: async () => {
      const res = await fetch("/api/alerts");
      if (!res.ok) throw new Error("Failed to fetch alerts");
      const data = await res.json();
      return data.alerts as Alert[];
    },
    refetchInterval: 30000,
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: { item_id: number; condition: string; threshold_price: number }) => {
      const res = await fetch("/api/alerts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to create alert");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useUpdateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, active }: { id: number; active: boolean }) => {
      const res = await fetch(`/api/alerts/${id}/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active }),
      });
      if (!res.ok) throw new Error("Failed to update alert");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/alerts/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete alert");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}
