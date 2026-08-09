import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import Header from "./components/Header";
import PriceChart from "./components/PriceChart";
import SearchBar from "./components/SearchBar";
import SettingsPanel from "./components/SettingsPanel";
import StatsPanel from "./components/StatsPanel";
import TopMovers from "./components/TopMovers";
import TrackedList from "./components/TrackedList";
import type {
  ChartMode, ChartRange, ItemStats, PriceSeries, Settings, StatusInfo,
  TrackedItem, TrendInfo,
} from "./types";

const RANGES: ChartRange[] = ["1h", "6h", "24h", "7d", "14d"];
const MA_OPTIONS = ["1h", "6h", "24h", "7d"];

export default function App() {
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [tracked, setTracked] = useState<TrackedItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const [viewedUntracked, setViewedUntracked] = useState<{item_id: number, name: string} | null>(null);
  const [range, setRange] = useState<ChartRange>("24h");
  const [mode, setMode] = useState<ChartMode>("price");
  const [maKeys, setMaKeys] = useState<string[]>([]);
  const [showVolume, setShowVolume] = useState(false);
  const [showHighLow, setShowHighLow] = useState(false);
  const [series, setSeries] = useState<PriceSeries[]>([]);
  const [stats, setStats] = useState<ItemStats | null>(null);
  const [trend, setTrend] = useState<TrendInfo | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const dark = (settings?.theme ?? "dark") === "dark";

  // ---- initial load: settings + status + tracked
  useEffect(() => {
    api.settings().then((s) => {
      setSettings(s);
      if (RANGES.includes(s.default_chart_range as ChartRange)) {
        setRange(s.default_chart_range as ChartRange);
      }
    }).catch(() => setBanner("Backend unreachable — is the server running?"));
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      const s = await api.status();
      setStatus(s);
      setBanner(s.api_online ? null
        : "API temporarily unavailable — displaying cached data.");
    } catch {
      setBanner("Backend unreachable — is the server running?");
    }
  }, []);

  const loadTracked = useCallback(async () => {
    try {
      const { tracked } = await api.tracked();
      setTracked(tracked);
      setSelectedIds((prev) => {
        const ids = new Set(tracked.map((t) => t.item_id));
        const kept = new Set([...prev].filter((id) => ids.has(id)));
        // newly tracked items go on the chart automatically
        for (const t of tracked) if (!prev.size || !prev.has(t.item_id)) {
          if (!kept.size || !prev.has(t.item_id)) kept.add(t.item_id);
        }
        return kept.size ? kept : ids;
      });
      setFocusedId((f) =>
        f && tracked.some((t) => t.item_id === f) ? f : tracked[0]?.item_id ?? null);
    } catch {
      /* banner already handled by status */
    }
  }, []);

  useEffect(() => {
    loadStatus();
    loadTracked();
    const id = window.setInterval(() => {
      loadStatus();
      loadTracked();
      setRefreshKey((k) => k + 1);
    }, 60_000);
    return () => window.clearInterval(id);
  }, [loadStatus, loadTracked]);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  // ---- chart data
  const chartIds = useMemo(
    () => {
      if (viewedUntracked && focusedId === viewedUntracked.item_id) {
        return [viewedUntracked.item_id];
      }
      return tracked.filter((t) => selectedIds.has(t.item_id)).map((t) => t.item_id);
    },
    [tracked, selectedIds, focusedId, viewedUntracked]
  );

  useEffect(() => {
    let cancelled = false;
    if (!chartIds.length) { setSeries([]); return; }
    const ma = chartIds.length === 1 ? maKeys : [];
    Promise.all(chartIds.map((id) => api.prices(id, range, ma)))
      .then((all) => { if (!cancelled) setSeries(all); })
      .catch((e) => { if (!cancelled) setBanner(`Failed to load chart data: ${e}`); });
    return () => { cancelled = true; };
  }, [chartIds, range, maKeys, refreshKey]);

  // ---- stats for focused item
  useEffect(() => {
    let cancelled = false;
    if (!focusedId) { setStats(null); setTrend(null); return; }
    Promise.all([api.stats(focusedId), api.trend(focusedId)])
      .then(([s, t]) => { if (!cancelled) { setStats(s); setTrend(t); } })
      .catch(() => { if (!cancelled) { setStats(null); setTrend(null); } });
    return () => { cancelled = true; };
  }, [focusedId, refreshKey]);

  // ---- actions
  const handleTrack = async (item: { item_id: number }) => {
    try {
      await api.track(item.item_id);
      setSelectedIds((s) => new Set(s).add(item.item_id));
      setFocusedId(item.item_id);
      if (viewedUntracked?.item_id === item.item_id) setViewedUntracked(null);
      await loadTracked();
    } catch (e) {
      setBanner(`Could not track item: ${e}`);
    }
  };

  const handleRemove = async (id: number) => {
    await api.untrack(id).catch(() => undefined);
    setSelectedIds((s) => { const n = new Set(s); n.delete(id); return n; });
    await loadTracked();
  };

  const handleFavorite = async (id: number, fav: boolean) => {
    await api.favorite(id, fav).catch(() => undefined);
    await loadTracked();
  };

  const handleSetGroup = async (id: number, group: string) => {
    await api.setGroup(id, group).catch(() => undefined);
    await loadTracked();
  };

  const handleMoverSelect = async (itemId: number) => {
    if (!tracked.some((t) => t.item_id === itemId)) await handleTrack({ item_id: itemId });
    else { setFocusedId(itemId); setSelectedIds((s) => new Set(s).add(itemId)); }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleCollectNow = async () => {
    await api.collectNow().catch(() => undefined);
    setTimeout(() => { loadStatus(); loadTracked(); setRefreshKey((k) => k + 1); }, 4000);
  };

  const focusedName =
    tracked.find((t) => t.item_id === focusedId)?.name 
    ?? (focusedId === viewedUntracked?.item_id ? viewedUntracked.name : null);
  const single = chartIds.length === 1;

  return (
    <div className="app">
      <Header
        status={status}
        onOpenSettings={() => setSettingsOpen(true)}
        onCollectNow={handleCollectNow}
      />
      {banner && <div className="banner">{banner}</div>}

      <SearchBar
        trackedIds={new Set(tracked.map((t) => t.item_id))}
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
            items={tracked}
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
          <StatsPanel name={focusedName} stats={stats} trend={trend} />
          <TopMovers onSelect={handleMoverSelect} refreshKey={refreshKey} />
        </div>
      </div>

      <SettingsPanel
        open={settingsOpen}
        status={status}
        onClose={() => setSettingsOpen(false)}
        onSaved={(s) => { setSettings(s); loadStatus(); }}
      />
      <footer className="footer muted">
        Price data © RuneScape Wiki real-time prices · Made by <a href="https://github.com/Davedebugs" target="_blank" rel="noopener noreferrer" style={{color: "inherit", textDecoration: "underline"}}>Davedebugs</a> ·
        not affiliated with Jagex
      </footer>
    </div>
  );
}
