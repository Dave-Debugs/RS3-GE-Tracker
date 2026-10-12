import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { ChartRange, Settings, PortfolioStats, Recipe, Alert, FlipScannerItem, AlchScannerItem } from "./types";

export function useStatus() {
  return useQuery({
    queryKey: ["status"],
    queryFn: api.status,
    refetchInterval: (query) => (query.state.data?.api_online ? 15000 : 3000),
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
    refetchInterval: 30000,
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
    mutationFn: api.collectNow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracked"] });
      qc.invalidateQueries({ queryKey: ["status"] });
      qc.invalidateQueries({ queryKey: ["scanner"] });
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["tracked"] });
        qc.invalidateQueries({ queryKey: ["status"] });
        qc.invalidateQueries({ queryKey: ["scanner"] });
      }, 2000);
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
    mutationFn: ({ id, group }: { id: number; group: string }) => api.setGroup(id, group),
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
      const res = await fetch(`/api/alerts/${id}`, {
        method: "PUT",
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

export function useFlipScanner(params: {
  minPrice: number;
  maxPrice: number | null;
  minVolume: number;
  members: boolean | null;
  sortBy: string;
}) {
  return useQuery({
    queryKey: ["scanner", "flips", params],
    queryFn: async () => {
      const qs = new URLSearchParams();
      qs.set("min_price", String(params.minPrice));
      if (params.maxPrice) qs.set("max_price", String(params.maxPrice));
      if (params.minVolume) qs.set("min_volume", String(params.minVolume));
      if (params.members !== null) qs.set("members", String(params.members));
      qs.set("sort_by", params.sortBy);
      qs.set("limit", "60");
      const res = await fetch(`/api/scanner/flips?${qs.toString()}`);
      if (!res.ok) throw new Error("Failed to scan flips");
      const data = await res.json();
      return data.items as FlipScannerItem[];
    },
    refetchInterval: 60000,
  });
}

export function useAlchScanner(params: {
  minVolume: number;
  members: boolean | null;
  sortBy: string;
}) {
  return useQuery({
    queryKey: ["scanner", "alch", params],
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.minVolume) qs.set("min_volume", String(params.minVolume));
      if (params.members !== null) qs.set("members", String(params.members));
      qs.set("sort_by", params.sortBy);
      qs.set("limit", "60");
      const res = await fetch(`/api/scanner/alch?${qs.toString()}`);
      if (!res.ok) throw new Error("Failed to scan alchemy");
      return (await res.json()) as { nature_rune_price: number; items: AlchScannerItem[] };
    },
    refetchInterval: 60000,
  });
}
