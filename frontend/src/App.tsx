import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import {
  useStatus, useSettings, useTracked, usePrices, useStats, useTrend,
  useTrackItem, useUntrackItem, useFavoriteItem, useSetGroup, useCollectNow
} from "./hooks";
import Header from "./components/Header";
import PriceChart from "./components/PriceChart";
import SearchBar from "./components/SearchBar";
import SettingsPanel from "./components/SettingsPanel";
import StatsPanel from "./components/StatsPanel";
import TopMovers from "./components/TopMovers";
import TrackedList from "./components/TrackedList";
import type { ChartMode, ChartRange } from "./types";

const RANGES: ChartRange[] = ["1h", "6h", "24h", "7d", "14d"];
const MA_OPTIONS = ["1h", "6h", "24h", "7d"];

export default function App() {
  const { data: status, error: statusError } = useStatus();
  const { data: settings } = useSettings();
  const { data: trackedData = [] } = useTracked();
  
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const [viewedUntracked, setViewedUntracked] = useState<{item_id: number, name: string} | null>(null);
  
  const [range, setRange] = useState<ChartRange>("24h");
  const [mode, setMode] = useState<ChartMode>("price");
  const [maKeys, setMaKeys] = useState<string[]>([]);
  const [showVolume, setShowVolume] = useState(false);
  const [showHighLow, setShowHighLow] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Sync selected IDs logic from old App.tsx
  useEffect(() => {
    if (!trackedData.length) return;
    setSelectedIds((prev) => {
      const ids = new Set(trackedData.map((t) => t.item_id));
      const kept = new Set([...prev].filter((id) => ids.has(id)));
      for (const t of trackedData) {
        if (!prev.size || !prev.has(t.item_id)) {
          if (!kept.size || !prev.has(t.item_id)) kept.add(t.item_id);
        }
      }
      return kept.size ? kept : ids;
    });
    setFocusedId((f) =>
      f && trackedData.some((t) => t.item_id === f) ? f : trackedData[0]?.item_id ?? null
    );
  }, [trackedData.length]); // Only run on length change to avoid loop

  // Initialize range from settings
  useEffect(() => {
    if (settings && RANGES.includes(settings.default_chart_range as ChartRange)) {
      setRange(settings.default_chart_range as ChartRange);
    }
  }, [settings?.default_chart_range]);

  const dark = (settings?.theme ?? "dark") === "dark";
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  const chartIds = useMemo(() => {
    if (viewedUntracked && focusedId === viewedUntracked.item_id) {
      return [viewedUntracked.item_id];
    }
    return trackedData.filter((t) => selectedIds.has(t.item_id)).map((t) => t.item_id);
  }, [trackedData, selectedIds, focusedId, viewedUntracked]);

  const { data: series = [], error: seriesError } = usePrices(chartIds, range, maKeys);
  const { data: stats = null } = useStats(focusedId);
  const { data: trend = null } = useTrend(focusedId);

  const trackMutation = useTrackItem();
  const untrackMutation = useUntrackItem();
  const favoriteMutation = useFavoriteItem();
  const setGroupMutation = useSetGroup();
  const collectMutation = useCollectNow();

  const handleTrack = async (item: { item_id: number }) => {
    trackMutation.mutate(item.item_id, {
      onSuccess: () => {
        setSelectedIds((s) => new Set(s).add(item.item_id));
        setFocusedId(item.item_id);
        if (viewedUntracked?.item_id === item.item_id) setViewedUntracked(null);
      }
    });
  };

  const handleRemove = async (id: number) => {
    untrackMutation.mutate(id, {
      onSuccess: () => {
        setSelectedIds((s) => { const n = new Set(s); n.delete(id); return n; });
      }
    });
  };

  const handleFavorite = async (id: number, fav: boolean) => {
    favoriteMutation.mutate({ id, fav });
  };

  const handleSetGroup = async (id: number, group: string) => {
    setGroupMutation.mutate({ id, group });
  };

  const handleMoverSelect = async (itemId: number, name: string) => {
    if (!trackedData.some((t) => t.item_id === itemId)) {
      handleTrack({ item_id: itemId });
    } else {
      setFocusedId(itemId);
      setSelectedIds((s) => new Set(s).add(itemId));
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleCollectNow = async () => {
    collectMutation.mutate();
  };

  const focusedName =
    trackedData.find((t) => t.item_id === focusedId)?.name 
    ?? (focusedId === viewedUntracked?.item_id ? viewedUntracked.name : null);
  
  const single = chartIds.length === 1;

  let banner = null;
  if (statusError) banner = "Backend unreachable — is the server running?";
  else if (status && !status.api_online) banner = "API temporarily unavailable — displaying cached data.";
  else if (seriesError) banner = `Failed to load chart data: ${seriesError.message}`;
  else if (trackMutation.isError) banner = `Could not track item: ${trackMutation.error?.message}`;

  return (
    <div className="app">
      <Header
        status={status || null}
        onOpenSettings={() => setSettingsOpen(true)}
        onCollectNow={handleCollectNow}
      />
      {banner && <div className="banner">{banner}</div>}

      <SearchBar
        trackedIds={new Set(trackedData.map((t) => t.item_id))}
        onTrack={handleTrack}
        onSelect={(item) => {
          setViewedUntracked({ item_id: item.item_id, name: item.name });
          setFocusedId(item.item_id);
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
      />

      <div className="main-grid">
        <div className="main-col">
          <section className="card chart-card">
            <div className="chart-controls">
              <div className="seg">
                {RANGES.map((r) => (
                  <button key={r}
                    className={"seg-btn" + (range === r ? " active" : "")}
                    onClick={() => setRange(r)}>
                    {r.toUpperCase()}
                  </button>
                ))}
              </div>
              <div className="seg">
                <button className={"seg-btn" + (mode === "price" ? " active" : "")}
                        onClick={() => setMode("price")}
                        title="Absolute GP prices">Actual Price</button>
                <button className={"seg-btn" + (mode === "percent" ? " active" : "")}
                        onClick={() => setMode("percent")}
                        title="Normalized to 0% at window start — compare items of any price">
                  % Change
                </button>
              </div>
              <div className="chart-toggles">
                <label className={single ? "" : "disabled"} title="Volume bars (single item)">
                  <input type="checkbox" checked={showVolume} disabled={!single}
                         onChange={(e) => setShowVolume(e.target.checked)} /> Volume
                </label>
                <label className={single && mode === "price" ? "" : "disabled"}
                       title="Instant buy/sell bands (single item, actual price)">
                  <input type="checkbox" checked={showHighLow}
                         disabled={!single || mode !== "price"}
                         onChange={(e) => setShowHighLow(e.target.checked)} /> High/Low
                </label>
                {MA_OPTIONS.map((k) => (
                  <label key={k} className={single ? "" : "disabled"}
                         title={`${k} moving average (single item)`}>
                    <input type="checkbox" checked={maKeys.includes(k)} disabled={!single}
                           onChange={(e) =>
                             setMaKeys((keys) => e.target.checked
                               ? [...keys, k] : keys.filter((x) => x !== k))} />
                    MA&nbsp;{k}
                  </label>
                ))}
                {focusedId && (
                  <span className="export-links">
                    <a href={api.exportUrl(focusedId, "csv", range)} download>CSV ⭳</a>
                    <a href={api.exportUrl(focusedId, "json", range)} download>JSON ⭳</a>
                  </span>
                )}
              </div>
            </div>
            <PriceChart
              series={series}
              mode={mode}
              showVolume={showVolume && single}
              showHighLow={showHighLow && single}
              maKeys={single ? maKeys : []}
              dark={dark}
            />
          </section>

          <TrackedList
            items={trackedData}
            selectedIds={selectedIds}
            focusedId={focusedId}
            onToggleChart={(id) =>
              setSelectedIds((s) => {
                const n = new Set(s);
                n.has(id) ? n.delete(id) : n.add(id);
                return n;
              })}
            onFocus={setFocusedId}
            onFavorite={handleFavorite}
            onRemove={handleRemove}
            onSetGroup={handleSetGroup}
          />
        </div>

        <div className="side-col">
          <StatsPanel name={focusedName || null} stats={stats} trend={trend} />
          <TopMovers onSelect={handleMoverSelect} />
        </div>
      </div>

      <SettingsPanel
        open={settingsOpen}
        status={status || null}
        onClose={() => setSettingsOpen(false)}
        onSaved={() => {}}
      />
      <footer className="footer muted">
        Price data © RuneScape Wiki real-time prices · Made by <a href="https://github.com/Davedebugs" target="_blank" rel="noopener noreferrer" style={{color: "inherit", textDecoration: "underline"}}>Davedebugs</a> ·
        not affiliated with Jagex
      </footer>
    </div>
  );
}
