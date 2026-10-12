import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import {
  useStatus,
  useSettings,
  useTracked,
  usePrices,
  useStats,
  useTrend,
  useTrackItem,
  useUntrackItem,
  useFavoriteItem,
  useSetGroup,
  useDeleteGroup,
  useCollectNow,
  useAlerts,
  usePortfolio,
} from "./hooks";
import { formatGP, formatPct } from "./lib/format";
import Header from "./components/Header";
import PriceChart from "./components/PriceChart";
import SearchBar from "./components/SearchBar";
import SettingsPanel from "./components/SettingsPanel";
import AlertsManagerModal from "./components/AlertsManagerModal";
import GroupModal from "./components/GroupModal";
import StatsPanel from "./components/StatsPanel";
import TopMovers from "./components/TopMovers";
import TrackedList from "./components/TrackedList";
import PortfolioView from "./components/PortfolioView";
import RecipesView from "./components/RecipesView";
import ScannerView from "./components/ScannerView";
import ToastContainer from "./components/ToastContainer";
import { ToastProvider, useToast } from "./context/ToastContext";
import type { ChartMode, ChartRange } from "./types";

const RANGES: ChartRange[] = ["1h", "6h", "24h", "7d", "14d", "30d"];
const MA_OPTIONS = ["1h", "6h", "24h", "7d"];

function AppInner() {
  const qc = useQueryClient();
  const { data: status, error: statusError } = useStatus();
  const { data: settings } = useSettings();
  const { data: trackedData = [] } = useTracked();
  const { data: alertsData = [] } = useAlerts();
  const { data: portfolioData } = usePortfolio();
  const { toast } = useToast();

  const [selectedCategory, setSelectedCategory] = useState<string>("__ALL__");
  const [customCategories, setCustomCategories] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const [viewedUntracked, setViewedUntracked] = useState<{ item_id: number; name: string } | null>(null);

  const [range, setRange] = useState<ChartRange>("24h");
  const [mode, setMode] = useState<ChartMode>("price");
  const [maKeys, setMaKeys] = useState<string[]>([]);
  const [showVolume, setShowVolume] = useState(false);
  const [showHighLow, setShowHighLow] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [createCategoryOpen, setCreateCategoryOpen] = useState(false);

  const [activeTab, setActiveTab] = useState<"dashboard" | "scanner" | "portfolio" | "recipes">("dashboard");

  const allCategories = useMemo(() => {
    const fromData = Array.from(new Set(trackedData.map((t) => t.group_name || "Default")));
    const merged = Array.from(new Set(["Default", ...fromData, ...customCategories])).sort((a, b) => {
      if (a === "Default") return -1;
      if (b === "Default") return 1;
      return a.localeCompare(b);
    });
    return merged;
  }, [trackedData, customCategories]);

  const activeCategoryItems = useMemo(() => {
    if (selectedCategory === "__ALL__") return trackedData;
    return trackedData.filter((t) => (t.group_name || "Default") === selectedCategory);
  }, [trackedData, selectedCategory]);

  useEffect(() => {
    if (!activeCategoryItems.length) {
      if (viewedUntracked) {
        setFocusedId(viewedUntracked.item_id);
      }
      return;
    }
    setSelectedIds((prev) => {
      const ids = new Set(activeCategoryItems.map((t) => t.item_id));
      const kept = new Set([...prev].filter((id) => ids.has(id)));
      if (kept.size > 0) return kept;
      const initial = new Set<number>();
      for (const item of activeCategoryItems.slice(0, 4)) {
        initial.add(item.item_id);
      }
      return initial;
    });

    setFocusedId((f) => {
      if (viewedUntracked && viewedUntracked.item_id === f) return f;
      if (f && activeCategoryItems.some((t) => t.item_id === f)) return f;
      return activeCategoryItems[0]?.item_id ?? null;
    });
  }, [activeCategoryItems, viewedUntracked]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        !["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement)?.tagName)
      ) {
        e.preventDefault();
        const searchInput = document.getElementById("global-search-input") as HTMLInputElement;
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
      if (e.key === "Escape") {
        setSettingsOpen(false);
        setAlertsOpen(false);
        setCreateCategoryOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

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
    return activeCategoryItems.filter((t) => selectedIds.has(t.item_id)).map((t) => t.item_id);
  }, [activeCategoryItems, selectedIds, focusedId, viewedUntracked]);

  const { data: series = [], error: seriesError } = usePrices(chartIds, range, maKeys);
  const { data: stats = null } = useStats(focusedId);
  const { data: trend = null } = useTrend(focusedId);

  const trackMutation = useTrackItem();
  const untrackMutation = useUntrackItem();
  const favoriteMutation = useFavoriteItem();
  const setGroupMutation = useSetGroup();
  const deleteGroupMutation = useDeleteGroup();
  const collectMutation = useCollectNow();

  const handleTrack = async (item: { item_id: number; name?: string }) => {
    trackMutation.mutate(item.item_id, {
      onSuccess: () => {
        const targetGroup = selectedCategory !== "__ALL__" ? selectedCategory : "Default";
        if (targetGroup !== "Default") {
          setGroupMutation.mutate({ id: item.item_id, group: targetGroup });
        }
        setSelectedIds((s) => new Set(s).add(item.item_id));
        setFocusedId(item.item_id);
        if (viewedUntracked?.item_id === item.item_id) setViewedUntracked(null);
        toast.success(`Tracking ${item.name || `Item ${item.item_id}`} in "${targetGroup}"`);
      },
      onError: (err) => {
        toast.error(`Could not track item: ${err.message}`);
      },
    });
  };

  const handleRemove = async (id: number) => {
    const item = trackedData.find((t) => t.item_id === id);
    const itemName = item?.name || `Item ${id}`;
    untrackMutation.mutate(id, {
      onSuccess: () => {
        setSelectedIds((s) => {
          const n = new Set(s);
          n.delete(id);
          return n;
        });
        if (focusedId === id) {
          const remaining = activeCategoryItems.filter((t) => t.item_id !== id);
          setFocusedId(remaining[0]?.item_id ?? null);
        }
        toast.info(`Removed ${itemName} from watchlist`);
      },
      onError: (err) => {
        toast.error(`Could not untrack item: ${err.message}`);
      },
    });
  };

  const handleFavorite = async (id: number, fav: boolean) => {
    favoriteMutation.mutate({ id, fav }, {
      onSuccess: () => {
        toast.success(fav ? "Added to favorites ★" : "Removed from favorites");
      },
    });
  };

  const handleSetGroup = async (id: number, group: string) => {
    setGroupMutation.mutate({ id, group }, {
      onSuccess: () => {
        if (!customCategories.includes(group)) {
          setCustomCategories((prev) => [...prev, group]);
        }
      },
    });
  };

  const handleDeleteCategory = (categoryName: string) => {
    if (categoryName === "Default" || categoryName === "__ALL__") return;
    deleteGroupMutation.mutate(categoryName, {
      onSuccess: () => {
        setCustomCategories((prev) => prev.filter((c) => c !== categoryName));
        if (selectedCategory === categoryName) {
          setSelectedCategory("__ALL__");
        }
        toast.info(`Deleted item group "${categoryName}". Items moved to Default.`);
      },
      onError: (err) => {
        toast.error(`Failed to delete item group: ${err.message}`);
      },
    });
  };

  const handleCreateCategory = (_: number | null, categoryName: string) => {
    const clean = categoryName.trim();
    if (clean) {
      if (!customCategories.includes(clean)) {
        setCustomCategories((prev) => [...prev, clean]);
      }
      setSelectedCategory(clean);
    }
  };

  const handleMoverSelect = (itemId: number, name: string) => {
    const isAlreadyTracked = trackedData.some((t) => t.item_id === itemId);
    if (!isAlreadyTracked) {
      setViewedUntracked({ item_id: itemId, name });
    } else {
      setViewedUntracked(null);
    }
    setFocusedId(itemId);
    toast.info(`Displaying ${name} on dashboard`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleCollectNow = async () => {
    collectMutation.mutate(undefined, {
      onSuccess: () => {
        toast.info("Triggered price collection cycle…");
      },
      onError: (err: any) => {
        toast.error(`Collection failed: ${err.message}`);
      },
    });
  };

  const focusedName =
    (focusedId === viewedUntracked?.item_id ? viewedUntracked.name : null) ||
    trackedData.find((t) => t.item_id === focusedId)?.name;

  const single = chartIds.length === 1;

  let banner = null;
  if (statusError) banner = "Backend unreachable — is the server running?";
  else if (status && !status.api_online) banner = "API temporarily unavailable — displaying cached data.";
  else if (seriesError) banner = `Failed to load chart data: ${seriesError.message}`;

  const activeAlertsCount = alertsData.filter((a) => a.active).length;
  const showTooltips = settings?.show_item_tooltips !== "false";

  const kpiStats = useMemo(() => {
    let bestFlip = activeCategoryItems[0] || null;
    let bestGainer = activeCategoryItems[0] || null;
    let total4hPotential = 0;

    for (const item of activeCategoryItems) {
      const lp = item.limit_profit_4h ?? (item.net_profit && item.buy_limit ? item.net_profit * item.buy_limit : 0);
      if (lp > 0) total4hPotential += lp;
      const curBestLp =
        bestFlip?.limit_profit_4h ??
        (bestFlip?.net_profit && bestFlip?.buy_limit ? bestFlip.net_profit * bestFlip.buy_limit : -Infinity);
      if (lp > curBestLp) bestFlip = item;

      if ((item.change_24h ?? -Infinity) > (bestGainer?.change_24h ?? -Infinity)) {
        bestGainer = item;
      }
    }
    return { bestFlip, bestGainer, total4hPotential };
  }, [activeCategoryItems]);

  return (
    <div className="app">
      <Header
        status={status || null}
        alertsCount={activeAlertsCount}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenAlerts={() => setAlertsOpen(true)}
        onCollectNow={handleCollectNow}
      />
      {banner && <div className="banner">{banner}</div>}

      <SearchBar
        trackedIds={new Set(trackedData.map((t) => t.item_id))}
        onTrack={handleTrack}
        onSelect={(item) => {
          const isAlreadyTracked = trackedData.some((t) => t.item_id === item.item_id);
          if (!isAlreadyTracked) {
            setViewedUntracked({ item_id: item.item_id, name: item.name });
          } else {
            setViewedUntracked(null);
          }
          setFocusedId(item.item_id);
          setActiveTab("dashboard");
          toast.info(`Displaying ${item.name} on dashboard`);
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
      />

      <div className="kpi-strip">
        <div
          className="kpi-card clickable"
          onClick={() => {
            if (kpiStats.bestFlip) {
              setActiveTab("dashboard");
              setFocusedId(kpiStats.bestFlip.item_id);
            } else {
              setActiveTab("scanner");
            }
          }}
          title="Click to inspect the highest 4-hour buy limit flip in your current view"
        >
          <span className="kpi-label">Best Watchlist Flip (4h)</span>
          <div className="kpi-value up">
            {kpiStats.bestFlip && (kpiStats.bestFlip.limit_profit_4h || kpiStats.bestFlip.net_profit)
              ? `+${formatGP(kpiStats.bestFlip.limit_profit_4h || kpiStats.bestFlip.net_profit)} gp`
              : "Scan Market →"}
          </div>
          <span className="kpi-sub">
            {kpiStats.bestFlip
              ? `${kpiStats.bestFlip.name} (${kpiStats.bestFlip.net_profit ? `+${formatGP(kpiStats.bestFlip.net_profit)}/ea` : "—"})`
              : "Open Flips & Alchemy scanner"}
          </span>
        </div>

        <div
          className="kpi-card clickable"
          onClick={() => setActiveTab("scanner")}
          title="Combined 4-hour limit profit across positive-margin items in this group"
        >
          <span className="kpi-label">Group 4h Profit Capacity</span>
          <div className="kpi-value gold">
            {kpiStats.total4hPotential > 0 ? `+${formatGP(kpiStats.total4hPotential)} gp` : "—"}
          </div>
          <span className="kpi-sub">
            Across {activeCategoryItems.filter((i) => (i.net_profit ?? 0) > 0).length} profitable items (after 2% tax)
          </span>
        </div>

        <div
          className="kpi-card clickable"
          onClick={() => {
            if (kpiStats.bestGainer) {
              setActiveTab("dashboard");
              setFocusedId(kpiStats.bestGainer.item_id);
            }
          }}
          title="Top 24-hour percentage mover in your active watchlist group"
        >
          <span className="kpi-label">24h Watchlist Leader</span>
          <div
            className={`kpi-value ${
              (kpiStats.bestGainer?.change_24h ?? 0) >= 0 ? "up" : "down"
            }`}
          >
            {kpiStats.bestGainer?.change_24h != null
              ? formatPct(kpiStats.bestGainer.change_24h)
              : "—"}
          </div>
          <span className="kpi-sub">
            {kpiStats.bestGainer ? kpiStats.bestGainer.name : "No tracked items"}
          </span>
        </div>

        <div
          className="kpi-card clickable"
          onClick={() => setActiveTab("portfolio")}
          title="Click to manage your held items and investments"
        >
          <span className="kpi-label">Portfolio Net Value</span>
          <div className="kpi-value">
            {portfolioData && portfolioData.current_value > 0
              ? `${formatGP(portfolioData.current_value)} gp`
              : "0 gp"}
          </div>
          <span
            className={`kpi-sub ${
              portfolioData && portfolioData.unrealized_profit > 0
                ? "up"
                : portfolioData && portfolioData.unrealized_profit < 0
                ? "down"
                : ""
            }`}
          >
            {portfolioData && portfolioData.items.length > 0
              ? `${portfolioData.unrealized_profit >= 0 ? "+" : ""}${formatGP(
                  portfolioData.unrealized_profit
                )} gp P/L (${portfolioData.items.length} lots)`
              : "Track held investments →"}
          </span>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="Main workspace navigation">
        <button
          type="button"
          className={`nav-tab ${activeTab === "dashboard" ? "active" : ""}`}
          onClick={() => setActiveTab("dashboard")}
        >
          <span className="nav-tab-label">Market Dashboard</span>
          <span className="nav-tab-badge">{trackedData.length}</span>
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === "scanner" ? "active" : ""}`}
          onClick={() => setActiveTab("scanner")}
        >
          <span className="nav-tab-label">Flips &amp; High Alch</span>
          <span className="nav-tab-pill">Scanner</span>
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === "portfolio" ? "active" : ""}`}
          onClick={() => setActiveTab("portfolio")}
        >
          <span className="nav-tab-label">Portfolio</span>
          {portfolioData && portfolioData.items.length > 0 && (
            <span className="nav-tab-badge">{portfolioData.items.length}</span>
          )}
        </button>
        <button
          type="button"
          className={`nav-tab ${activeTab === "recipes" ? "active" : ""}`}
          onClick={() => setActiveTab("recipes")}
        >
          <span className="nav-tab-label">Recipes &amp; Crafting</span>
        </button>
      </nav>

      {activeTab === "dashboard" && (
        <>
          <div className="category-bar">
            <div className="category-tabs">
              <button
                className={`category-tab ${selectedCategory === "__ALL__" ? "active" : ""}`}
                onClick={() => setSelectedCategory("__ALL__")}
              >
                All Items <span className="cat-count">{trackedData.length}</span>
              </button>
              {allCategories.map((cat) => {
                const count = trackedData.filter((t) => (t.group_name || "Default") === cat).length;
                return (
                  <button
                    key={cat}
                    className={`category-tab ${selectedCategory === cat ? "active" : ""}`}
                    onClick={() => setSelectedCategory(cat)}
                  >
                    {cat} <span className="cat-count">{count}</span>
                    {cat !== "Default" && (
                      <span
                        className="cat-delete-btn"
                        title={`Delete item group "${cat}" (moves items to Default)`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteCategory(cat);
                        }}
                      >
                        ✕
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              className="btn btn-ghost category-add-btn"
              onClick={() => setCreateCategoryOpen(true)}
              title="Create a new Item Group Dashboard"
            >
              + New Item Group
            </button>
          </div>

          <div className="main-grid">
            <div className="main-col">
              <section className="card chart-card">
                {viewedUntracked && (
                  <div className="chart-preview-banner">
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontSize: "16px" }}>👁️</span>
                      <span style={{ fontSize: "13px" }}>
                        Previewing <b>{viewedUntracked.name}</b> (Not on Watchlist)
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <button
                        type="button"
                        className="btn btn-primary"
                        style={{ fontSize: "11px", padding: "4px 10px" }}
                        onClick={() =>
                          handleTrack({ item_id: viewedUntracked.item_id, name: viewedUntracked.name })
                        }
                      >
                        + Track to Watchlist
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        style={{ fontSize: "11px", padding: "4px 8px" }}
                        onClick={() => {
                          setViewedUntracked(null);
                          setFocusedId(activeCategoryItems[0]?.item_id ?? null);
                        }}
                      >
                        Exit Preview ✕
                      </button>
                    </div>
                  </div>
                )}

                <div className="chart-controls">
                  <div className="seg">
                    {RANGES.map((r) => (
                      <button
                        key={r}
                        className={"seg-btn" + (range === r ? " active" : "")}
                        onClick={() => setRange(r)}
                      >
                        {r.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  <div className="seg">
                    <button
                      className={"seg-btn" + (mode === "price" ? " active" : "")}
                      onClick={() => setMode("price")}
                      title="Absolute GP prices"
                    >
                      Actual Price
                    </button>
                    <button
                      className={"seg-btn" + (mode === "percent" ? " active" : "")}
                      onClick={() => setMode("percent")}
                      title="Normalized to 0% at window start — compare items of any price"
                    >
                      % Change
                    </button>
                  </div>
                  <div className="chart-toggles">
                    <label className={single ? "" : "disabled"} title="Volume bars (single item)">
                      <input
                        type="checkbox"
                        checked={showVolume}
                        disabled={!single}
                        onChange={(e) => setShowVolume(e.target.checked)}
                      />{" "}
                      Volume
                    </label>
                    <label
                      className={single && mode === "price" ? "" : "disabled"}
                      title="Instant buy/sell bands (single item, actual price)"
                    >
                      <input
                        type="checkbox"
                        checked={showHighLow}
                        disabled={!single || mode !== "price"}
                        onChange={(e) => setShowHighLow(e.target.checked)}
                      />{" "}
                      High/Low
                    </label>
                    {MA_OPTIONS.map((k) => (
                      <label
                        key={k}
                        className={single ? "" : "disabled"}
                        title={`${k} moving average (single item)`}
                      >
                        <input
                          type="checkbox"
                          checked={maKeys.includes(k)}
                          disabled={!single}
                          onChange={(e) =>
                            setMaKeys((keys) =>
                              e.target.checked ? [...keys, k] : keys.filter((x) => x !== k)
                            )
                          }
                        />
                        MA&nbsp;{k}
                      </label>
                    ))}
                    {focusedId && (
                      <span className="export-links">
                        <a href={api.exportUrl(focusedId, "csv", range)} download>
                          CSV ⭳
                        </a>
                        <a href={api.exportUrl(focusedId, "json", range)} download>
                          JSON ⭳
                        </a>
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
                  onToggleItem={(id) =>
                    setSelectedIds((s) => {
                      const n = new Set(s);
                      n.delete(id);
                      return n;
                    })
                  }
                  onFocusItem={(id) => {
                    setViewedUntracked(null);
                    setFocusedId(id);
                  }}
                />
              </section>

              <TrackedList
                items={activeCategoryItems}
                allGroups={allCategories}
                activeCategory={selectedCategory}
                selectedIds={selectedIds}
                focusedId={focusedId}
                showTooltips={showTooltips}
                onToggleChart={(id) =>
                  setSelectedIds((s) => {
                    const n = new Set(s);
                    n.has(id) ? n.delete(id) : n.add(id);
                    return n;
                  })
                }
                onFocus={(id) => {
                  setViewedUntracked(null);
                  setFocusedId(id);
                }}
                onFavorite={handleFavorite}
                onRemove={handleRemove}
                onSetGroup={handleSetGroup}
                onTrack={handleTrack}
                onCreateCategory={() => setCreateCategoryOpen(true)}
              />
            </div>

            <div className="side-col">
              <StatsPanel
                name={focusedName || null}
                itemId={focusedId}
                isTracked={focusedId ? trackedData.some((t) => t.item_id === focusedId) : false}
                stats={stats}
                trend={trend}
                onTrack={handleTrack}
              />
              <TopMovers onSelect={handleMoverSelect} />
            </div>
          </div>
        </>
      )}

      {activeTab === "scanner" && (
        <ScannerView
          trackedIds={new Set(trackedData.map((t) => t.item_id))}
          showTooltips={showTooltips}
          onInspectItem={(itemId, name) => {
            setActiveTab("dashboard");
            handleMoverSelect(itemId, name);
          }}
        />
      )}
      {activeTab === "portfolio" && <PortfolioView />}
      {activeTab === "recipes" && <RecipesView />}

      <SettingsPanel
        open={settingsOpen}
        status={status || null}
        onClose={() => setSettingsOpen(false)}
        onSaved={() => {
          qc.invalidateQueries({ queryKey: ["settings"] });
          toast.success("Settings saved successfully!");
        }}
      />

      <AlertsManagerModal
        open={alertsOpen}
        onClose={() => setAlertsOpen(false)}
      />

      <GroupModal
        open={createCategoryOpen}
        onClose={() => setCreateCategoryOpen(false)}
        onSave={handleCreateCategory}
      />

      <ToastContainer />

      <footer className="footer muted">
        Price data © RuneScape Wiki real-time prices · Made by{" "}
        <a
          href="https://github.com/dave-debugs"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "inherit", textDecoration: "underline" }}
        >
          dave-debugs
        </a>{" "}
        · not affiliated with Jagex
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  );
}
