import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { ChartRange, Settings } from "./types";

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

// Mutations
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tracked"] }),
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.updateSettings,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
}

export function useCollectNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.collectNow,
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["status"] });
        qc.invalidateQueries({ queryKey: ["tracked"] });
      }, 4000);
    },
  });
}
