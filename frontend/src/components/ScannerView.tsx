import { useState, useMemo } from "react";
import {
  useFlipScanner,
  useAlchScanner,
  useRecipeScanner,
  useTrackItem,
  useCreateRecipe,
  useGeSlots,
  useUpsertGeSlot,
} from "../hooks";
import { formatGP, formatGPExact, formatPct, parseGPInput } from "../lib/format";
import ItemTooltip from "./ItemTooltip";
import { useToast } from "../context/ToastContext";
import type { FlipScannerItem, AlchScannerItem, ArbitrageRecipeItem } from "../types";

interface Props {
  trackedIds: Set<number>;
  onInspectItem: (itemId: number, name: string) => void;
  showTooltips?: boolean;
}

const BUDGET_PRESETS: { label: string; value: number | null }[] = [
  { label: "Any Budget", value: null },
  { label: "≤ 100K gp", value: 100_000 },
  { label: "≤ 1M gp", value: 1_000_000 },
  { label: "≤ 10M gp", value: 10_000_000 },
  { label: "≤ 100M gp", value: 100_000_000 },
  { label: "≤ 500M gp", value: 500_000_000 },
];

export default function ScannerView({ trackedIds, onInspectItem, showTooltips = true }: Props) {
  const { addToast } = useToast();
  const [subTab, setSubTab] = useState<"flips" | "alch" | "recipes">("flips");
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [minVolume, setMinVolume] = useState<number>(50);
  const [membersFilter, setMembersFilter] = useState<boolean | null>(null);
  const [sortBy, setSortBy] = useState<string>("limit_profit");
  const [searchFilter, setSearchFilter] = useState<string>("");

  const [alchMode, setAlchMode] = useState<"manual" | "machine">("manual");
  const [recipeExecMode, setRecipeExecMode] = useState<"patient" | "instant">("patient");

  const [calcName, setCalcName] = useState<string>("Custom Flip");
  const [calcBuyRaw, setCalcBuyRaw] = useState<string>("1,000,000");
  const [calcSellRaw, setCalcSellRaw] = useState<string>("1,060,000");
  const [calcQtyRaw, setCalcQtyRaw] = useState<string>("10");

  const { data: geSlots = [] } = useGeSlots();
  const upsertSlotMut = useUpsertGeSlot();
  const createRecipeMut = useCreateRecipe();
  const trackMut = useTrackItem();

  const flipQuery = useFlipScanner({
    minPrice: 100,
    maxPrice,
    minVolume,
    members: membersFilter,
    sortBy,
    enabled: subTab === "flips",
  });

  const alchQuery = useAlchScanner({
    minVolume,
    members: membersFilter,
    sortBy,
    mode: alchMode,
    enabled: subTab === "alch",
  });

  const recipeQuery = useRecipeScanner({
    executionMode: recipeExecMode,
    minVolume,
    sortBy,
    enabled: subTab === "recipes",
  });

  const handleTrack = (itemId: number, name: string) => {
    trackMut.mutate(itemId, {
      onSuccess: () => addToast(`Added ${name} to watchlist`, "success"),
      onError: () => addToast(`Could not track ${name}`, "error"),
    });
  };

  const handleSendToGeSlot = (itemId: number, name: string, buyOffer: number, limit: number | null) => {
    const emptySlot = geSlots.find((s) => s.empty);
    const targetSlot = emptySlot ? emptySlot.slot_index : 1;
    upsertSlotMut.mutate(
      {
        slot_index: targetSlot,
        item_id: itemId,
        offer_type: "buy",
        target_price: buyOffer,
        quantity: limit && limit > 0 ? limit : 1,
        reset_timer: true,
      },
      {
        onSuccess: () => addToast(`Assigned ${name} to GE Slot #${targetSlot} (4h timer started)`, "success"),
        onError: () => addToast(`Failed to assign ${name} to GE Slot`, "error"),
      }
    );
  };

  const handleSaveArbitrageRecipe = (item: ArbitrageRecipeItem) => {
    createRecipeMut.mutate(
      {
        name: item.name,
        output_item_id: item.output_item_id,
        output_qty: 1,
        ingredients: item.ingredients.map((i) => ({ item_id: i.item_id, qty: i.qty })),
      },
      {
        onSuccess: () => addToast(`Saved "${item.name}" to your Recipes tab!`, "success"),
        onError: () => addToast(`Could not save recipe "${item.name}"`, "error"),
      }
    );
  };

  const loadIntoCalc = (name: string, buyOffer: number, sellTarget: number, limit: number | null) => {
    setCalcName(name);
    setCalcBuyRaw(String(buyOffer));
    setCalcSellRaw(String(sellTarget));
    setCalcQtyRaw(String(limit && limit > 0 ? limit : 1));
    addToast(`Loaded ${name} into Flip Calculator`, "info");
  };

  const calcMetrics = useMemo(() => {
    const buy = Math.max(0, parseGPInput(calcBuyRaw) || 0);
    const sell = Math.max(0, parseGPInput(calcSellRaw) || 0);
    const qty = Math.max(1, parseGPInput(calcQtyRaw) || 1);
    const taxPerItem = sell >= 50 ? Math.min(Math.floor(sell * 0.02), 50_000_000) : 0;
    const netPerItem = sell - taxPerItem - buy;
    const breakEvenSell = buy >= 50 ? Math.ceil(buy / 0.98) : buy;
    const roiPct = buy > 0 ? (netPerItem / buy) * 100 : 0;
    const totalCapital = buy * qty;
    const totalNet = netPerItem * qty;
    const totalTax = taxPerItem * qty;
    return {
      buy,
      sell,
      qty,
      taxPerItem,
      netPerItem,
      breakEvenSell,
      roiPct,
      totalCapital,
      totalNet,
      totalTax,
    };
  }, [calcBuyRaw, calcSellRaw, calcQtyRaw]);

  const filteredFlips = useMemo(() => {
    const list = flipQuery.data || [];
    if (!searchFilter.trim()) return list;
    const q = searchFilter.toLowerCase();
    return list.filter((i) => i.name.toLowerCase().includes(q));
  }, [flipQuery.data, searchFilter]);

  const filteredAlchs = useMemo(() => {
    const list = alchQuery.data?.items || [];
    if (!searchFilter.trim()) return list;
    const q = searchFilter.toLowerCase();
    return list.filter((i) => i.name.toLowerCase().includes(q));
  }, [alchQuery.data, searchFilter]);

  const filteredRecipes = useMemo(() => {
    const list = recipeQuery.data || [];
    if (!searchFilter.trim()) return list;
    const q = searchFilter.toLowerCase();
    return list.filter(
      (i) =>
        i.name.toLowerCase().includes(q) ||
        i.ingredients.some((ing) => ing.name.toLowerCase().includes(q))
    );
  }, [recipeQuery.data, searchFilter]);

  const natPrice = alchQuery.data?.nature_rune_price ?? 350;
  const castCost = alchQuery.data?.cast_cost ?? natPrice;

  return (
    <div className="scanner-layout">
      <div className="scanner-main">
        <section className="card scanner-panel">
          <div className="scanner-header">
            <div className="scanner-mode-tabs">
              <button
                type="button"
                className={`scanner-mode-btn ${subTab === "flips" ? "active" : ""}`}
                onClick={() => setSubTab("flips")}
              >
                <span className="scanner-mode-title">Smart Flip Finder</span>
                <span className="scanner-mode-sub">2% GE Tax &amp; 4h Buy Limit Matrix</span>
              </button>
              <button
                type="button"
                className={`scanner-mode-btn ${subTab === "alch" ? "active" : ""}`}
                onClick={() => setSubTab("alch")}
              >
                <span className="scanner-mode-title">High Level Alchemy</span>
                <span className="scanner-mode-sub">
                  {alchMode === "machine" ? "Auto-Alcher Mk. II" : "Manual Cast"}:{" "}
                  <strong>{castCost.toLocaleString()} gp/alch</strong>
                </span>
              </button>
              <button
                type="button"
                className={`scanner-mode-btn ${subTab === "recipes" ? "active" : ""}`}
                onClick={() => setSubTab("recipes")}
              >
                <span className="scanner-mode-title">Crafting &amp; Arbitrage</span>
                <span className="scanner-mode-sub">Potions, Smithing &amp; Combinations</span>
              </button>
            </div>

            <div className="scanner-filters">
              <input
                type="text"
                className="scanner-search-input"
                placeholder="Filter item or ingredient…"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
              />

              {subTab === "flips" && (
                <div className="filter-group">
                  <label>Max Offer</label>
                  <select
                    value={maxPrice ?? ""}
                    onChange={(e) => setMaxPrice(e.target.value ? Number(e.target.value) : null)}
                  >
                    {BUDGET_PRESETS.map((b) => (
                      <option key={b.label} value={b.value ?? ""}>
                        {b.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {subTab === "alch" && (
                <div className="filter-group">
                  <label>Alch Mode</label>
                  <select
                    value={alchMode}
                    onChange={(e) => setAlchMode(e.target.value as "manual" | "machine")}
                  >
                    <option value="manual">Manual Cast (Nature Rune)</option>
                    <option value="machine">Auto-Alcher Mk. II (+Fire/Charge)</option>
                  </select>
                </div>
              )}

              {subTab === "recipes" && (
                <div className="filter-group">
                  <label>Execution</label>
                  <select
                    value={recipeExecMode}
                    onChange={(e) => setRecipeExecMode(e.target.value as "patient" | "instant")}
                  >
                    <option value="patient">Patient (Slow Buy/Sell)</option>
                    <option value="instant">Instant (Insta Buy/Sell)</option>
                  </select>
                </div>
              )}

              <div className="filter-group">
                <label>Min 24h Vol</label>
                <select
                  value={minVolume}
                  onChange={(e) => setMinVolume(Number(e.target.value))}
                >
                  <option value={0}>Any Volume</option>
                  <option value={50}>50+ / day</option>
                  <option value={500}>500+ / day</option>
                  <option value={5000}>5,000+ / day</option>
                  <option value={25000}>25,000+ / day</option>
                </select>
              </div>

              {subTab !== "recipes" && (
                <div className="filter-group">
                  <label>Access</label>
                  <select
                    value={membersFilter === null ? "all" : membersFilter ? "members" : "f2p"}
                    onChange={(e) => {
                      const v = e.target.value;
                      setMembersFilter(v === "all" ? null : v === "members");
                    }}
                  >
                    <option value="all">All Items</option>
                    <option value="members">Members Only</option>
                    <option value="f2p">Free-to-Play</option>
                  </select>
                </div>
              )}

              <div className="filter-group">
                <label>Rank By</label>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                  <option value="limit_profit">4h Limit Profit</option>
                  <option value="net_profit">Profit per Item</option>
                  <option value="roi">ROI %</option>
                  <option value="volume">24h Volume</option>
                  <option value="liquidity">Liquidity &amp; Fill Speed</option>
                </select>
              </div>
            </div>
          </div>

          {subTab === "flips" && (
            <div className="table-scroll">
              <table className="table scanner-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th className="num" title="Slow Buy Offer (Instant Sell / Low)">Buy Offer</th>
                    <th className="num" title="Slow Sell Target (Instant Buy / High)">Sell Target</th>
                    <th className="num" title="2% GE Tax deducted on sale">2% Tax</th>
                    <th className="num" title="Net profit per item after 2% tax">Net / Item</th>
                    <th className="num" title="Return on Investment %">ROI %</th>
                    <th className="num" title="24-Hour Trade Volume & Estimated 4h Limit Fill Time">Vol / Est. Fill</th>
                    <th className="num" title="4-Hour GE Buy Limit">4h Limit</th>
                    <th className="num" title="Net Profit × 4-Hour Buy Limit">4h Max Profit</th>
                    <th className="num">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {flipQuery.isLoading ? (
                    <tr>
                      <td colSpan={10} className="empty-cell">
                        Scanning Grand Exchange spreads...
                      </td>
                    </tr>
                  ) : filteredFlips.length === 0 ? (
                    <tr>
                      <td colSpan={10} className="empty-cell">
                        No flips match the current filters. Try relaxing the budget or volume filter.
                      </td>
                    </tr>
                  ) : (
                    filteredFlips.map((item: FlipScannerItem) => {
                      const isTracked = trackedIds.has(item.item_id);
                      return (
                        <tr key={item.item_id} onClick={() => onInspectItem(item.item_id, item.name)}>
                          <td className="item-cell">
                            <ItemTooltip
                              enabled={showTooltips}
                              itemId={item.item_id}
                              name={item.name}
                              iconUrl={item.icon_url}
                              description={item.description}
                              members={item.members}
                              buyLimit={item.buy_limit}
                              highAlch={item.highalch}
                              buyPrice={item.buy_price}
                              sellPrice={item.sell_price}
                              wikiUrl={item.wiki_url}
                            >
                              <div className="scanner-item-wrap">
                                {item.icon_url ? (
                                  <img src={item.icon_url} alt="" className="item-icon" loading="lazy" />
                                ) : (
                                  <span className="item-icon placeholder" />
                                )}
                                <span className="item-name">{item.name}</span>
                                {item.members && (
                                  <span className="badge members" title="Members">M</span>
                                )}
                              </div>
                            </ItemTooltip>
                          </td>
                          <td className="num" title={formatGPExact(item.sell_price)}>{formatGP(item.sell_price)}</td>
                          <td className="num" title={formatGPExact(item.buy_price)}>{formatGP(item.buy_price)}</td>
                          <td className="num muted">-{formatGP(item.tax)}</td>
                          <td className="num up">+{formatGP(item.net_profit)}</td>
                          <td className="num up">{formatPct(item.roi_pct)}</td>
                          <td className="num">
                            <div>{formatGP(item.volume_24h)}</div>
                            {item.liquidity_rating && (
                              <div
                                style={{
                                  fontSize: "10px",
                                  color:
                                    item.liquidity_rating === "High"
                                      ? "var(--up)"
                                      : item.liquidity_rating === "Medium"
                                      ? "var(--warn)"
                                      : "var(--fg-dim)",
                                }}
                                title={`Liquidity Score: ${item.liquidity_score ?? 0}/100 (Est. ${item.est_fill_hours ?? "?"}h to fill 4h limit at 25% market capture)`}
                              >
                                {item.liquidity_rating}
                                {item.est_fill_hours != null ? ` · ~${item.est_fill_hours}h` : ""}
                              </div>
                            )}
                          </td>
                          <td className="num">
                            {item.buy_limit ? item.buy_limit.toLocaleString() : "—"}
                          </td>
                          <td className="num profit-highlight">
                            +{formatGP(item.limit_profit_4h)}
                          </td>
                          <td className="num actions-cell" onClick={(e) => e.stopPropagation()}>
                            <button
                              type="button"
                              className="btn-mini"
                              title="Load into Flip Calculator"
                              onClick={() =>
                                loadIntoCalc(item.name, item.sell_price, item.buy_price, item.buy_limit)
                              }
                            >
                              Calc
                            </button>
                            <button
                              type="button"
                              className="btn-mini"
                              title="Assign to an open GE Slot & start 4-hour buy limit timer"
                              onClick={() =>
                                handleSendToGeSlot(item.item_id, item.name, item.sell_price, item.buy_limit)
                              }
                            >
                              → Slot
                            </button>
                            <button
                              type="button"
                              className={`btn-mini ${isTracked ? "tracked-pill" : "btn-track-pill"}`}
                              disabled={isTracked}
                              onClick={() => handleTrack(item.item_id, item.name)}
                            >
                              {isTracked ? "Tracked" : "+ Track"}
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}

          {subTab === "alch" && (
            <div className="table-scroll">
              <table className="table scanner-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th className="num" title="GE Buy Price">Buy Cost</th>
                    <th className="num" title="Rune + Charge Cost per Alch">
                      {alchMode === "machine" ? "Machine Cost" : "Nature Rune"}
                    </th>
                    <th className="num" title="Coins produced by High Level Alchemy">High Alch</th>
                    <th className="num" title="High Alch - (Buy Cost + Cast Cost)">Profit / Alch</th>
                    <th className="num">ROI %</th>
                    <th className="num">24h Vol</th>
                    <th className="num">4h Limit</th>
                    <th className="num" title="Profit per Alch × 4h Buy Limit">
                      {alchMode === "machine" ? "24h Machine (600x)" : "4h Alch Profit"}
                    </th>
                    <th className="num">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {alchQuery.isLoading ? (
                    <tr>
                      <td colSpan={10} className="empty-cell">
                        Scanning High Level Alchemy values...
                      </td>
                    </tr>
                  ) : filteredAlchs.length === 0 ? (
                    <tr>
                      <td colSpan={10} className="empty-cell">
                        No alchemy items match the current filters.
                      </td>
                    </tr>
                  ) : (
                    filteredAlchs.map((item: AlchScannerItem) => {
                      const isTracked = trackedIds.has(item.item_id);
                      const isPos = item.net_profit >= 0;
                      const capProfit =
                        alchMode === "machine"
                          ? (item.machine_profit_24h ?? item.net_profit * 600)
                          : item.limit_profit_4h;
                      return (
                        <tr key={item.item_id} onClick={() => onInspectItem(item.item_id, item.name)}>
                          <td className="item-cell">
                            <ItemTooltip
                              enabled={showTooltips}
                              itemId={item.item_id}
                              name={item.name}
                              iconUrl={item.icon_url}
                              description={item.description}
                              members={item.members}
                              buyLimit={item.buy_limit}
                              highAlch={item.highalch}
                              buyPrice={item.buy_price}
                              sellPrice={item.sell_price}
                              wikiUrl={item.wiki_url}
                            >
                              <div className="scanner-item-wrap">
                                {item.icon_url ? (
                                  <img src={item.icon_url} alt="" className="item-icon" loading="lazy" />
                                ) : (
                                  <span className="item-icon placeholder" />
                                )}
                                <span className="item-name">{item.name}</span>
                                {item.members && (
                                  <span className="badge members" title="Members">M</span>
                                )}
                              </div>
                            </ItemTooltip>
                          </td>
                          <td className="num">{formatGP(item.sell_price)}</td>
                          <td className="num muted">
                            {(item.cast_cost ?? item.nature_rune_price).toLocaleString()} gp
                          </td>
                          <td className="num">{formatGP(item.highalch)}</td>
                          <td className={`num ${isPos ? "up" : "down"}`}>
                            {isPos ? "+" : ""}
                            {formatGP(item.net_profit)}
                          </td>
                          <td className={`num ${isPos ? "up" : "down"}`}>
                            {formatPct(item.roi_pct)}
                          </td>
                          <td className="num">{formatGP(item.volume_24h)}</td>
                          <td className="num">
                            {item.buy_limit ? item.buy_limit.toLocaleString() : "—"}
                          </td>
                          <td className={`num ${isPos ? "profit-highlight" : "down"}`}>
                            {isPos ? "+" : ""}
                            {formatGP(capProfit)}
                          </td>
                          <td className="num actions-cell" onClick={(e) => e.stopPropagation()}>
                            <button
                              type="button"
                              className="btn-mini"
                              title="Assign to GE Slot"
                              onClick={() =>
                                handleSendToGeSlot(item.item_id, item.name, item.sell_price, item.buy_limit)
                              }
                            >
                              → Slot
                            </button>
                            <button
                              type="button"
                              className={`btn-mini ${isTracked ? "tracked-pill" : "btn-track-pill"}`}
                              disabled={isTracked}
                              onClick={() => handleTrack(item.item_id, item.name)}
                            >
                              {isTracked ? "Tracked" : "+ Track"}
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}

          {subTab === "recipes" && (
            <div className="table-scroll">
              <table className="table scanner-table">
                <thead>
                  <tr>
                    <th>Output Item &amp; Ingredients</th>
                    <th className="num" title="Total Ingredient Cost">Input Cost</th>
                    <th className="num" title="Output Sell Price">Output Price</th>
                    <th className="num" title="2% GE Tax on Output">2% Tax</th>
                    <th className="num" title="Net Profit per Craft after 2% Tax">Net / Craft</th>
                    <th className="num">ROI %</th>
                    <th className="num">24h Vol</th>
                    <th className="num" title="Bottleneck 4h Craft Limit">4h Crafts</th>
                    <th className="num" title="Net Profit × 4h Craft Limit">4h Max Profit</th>
                    <th className="num">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {recipeQuery.isLoading ? (
                    <tr>
                      <td colSpan={10} className="empty-cell">
                        Scanning crafting, potion &amp; combination arbitrage margins…
                      </td>
                    </tr>
                  ) : filteredRecipes.length === 0 ? (
                    <tr>
                      <td colSpan={10} className="empty-cell">
                        No profitable recipes match the current filters. Try lowering Min 24h Vol.
                      </td>
                    </tr>
                  ) : (
                    filteredRecipes.map((r: ArbitrageRecipeItem) => {
                      const isTracked = trackedIds.has(r.output_item_id);
                      return (
                        <tr
                          key={r.output_item_id}
                          onClick={() => onInspectItem(r.output_item_id, r.name)}
                        >
                          <td className="item-cell">
                            <div className="scanner-item-wrap">
                              {r.icon_url ? (
                                <img src={r.icon_url} alt="" className="item-icon" loading="lazy" />
                              ) : (
                                <span className="item-icon placeholder" />
                              )}
                              <div>
                                <span className="item-name">{r.name}</span>
                                <div className="muted" style={{ fontSize: "11px" }}>
                                  {r.ingredients
                                    .map((ing) => `${ing.qty}x ${ing.name} (${formatGP(ing.unit_cost)})`)
                                    .join(" + ")}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="num">{formatGP(r.total_cost)}</td>
                          <td className="num">{formatGP(r.output_price)}</td>
                          <td className="num muted">-{formatGP(r.tax)}</td>
                          <td className="num up">+{formatGP(r.net_profit)}</td>
                          <td className="num up">{formatPct(r.roi_pct)}</td>
                          <td className="num">{formatGP(r.volume_24h)}
                            {r.liquidity_rating && (
                              <div
                                style={{
                                  fontSize: "10px",
                                  color:
                                    r.liquidity_rating === "High"
                                      ? "var(--up)"
                                      : r.liquidity_rating === "Medium"
                                      ? "var(--warn)"
                                      : "var(--fg-dim)",
                                }}
                              >
                                {r.liquidity_rating}
                                {r.est_fill_hours != null ? ` · ~${r.est_fill_hours}h` : ""}
                              </div>
                            )}
                          </td>
                          <td className="num">{r.max_crafts_4h.toLocaleString()}</td>
                          <td className="num profit-highlight">+{formatGP(r.limit_profit_4h)}</td>
                          <td className="num actions-cell" onClick={(e) => e.stopPropagation()}>
                            <button
                              type="button"
                              className="btn-mini"
                              title="Load into Flip Calculator"
                              onClick={() =>
                                loadIntoCalc(r.name, r.total_cost, r.output_price, r.max_crafts_4h)
                              }
                            >
                              Calc
                            </button>
                            <button
                              type="button"
                              className="btn-mini btn-track-pill"
                              title="Save to your Recipes & Crafting tab"
                              onClick={() => handleSaveArbitrageRecipe(r)}
                            >
                              + Recipe
                            </button>
                            <button
                              type="button"
                              className={`btn-mini ${isTracked ? "tracked-pill" : "btn-track-pill"}`}
                              disabled={isTracked}
                              onClick={() => handleTrack(r.output_item_id, r.name)}
                            >
                              {isTracked ? "Tracked" : "+ Track"}
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <aside className="scanner-sidebar">
        <section className="card calc-panel">
          <div className="card-head">
            <h2 style={{ margin: 0 }}>GE Tax &amp; Flip Calculator</h2>
            <span className="calc-badge">2% Tax</span>
          </div>
          <p className="calc-subtitle">
            Calculates Grand Exchange net profit after the 2% seller tax (capped at 50M gp per item).
            Supports RS3 shorthand like <code>250k</code>, <code>12.5m</code>, or <code>1.2b</code>.
          </p>

          <div className="calc-item-tag">{calcName}</div>

          <div className="calc-form">
            <label className="calc-field">
              <span>Buy Offer Price (gp or 2.5m)</span>
              <input
                type="text"
                value={calcBuyRaw}
                onChange={(e) => setCalcBuyRaw(e.target.value)}
                placeholder="e.g. 1.5m"
              />
            </label>
            <label className="calc-field">
              <span>Sell Target Price (gp or 2.6m)</span>
              <input
                type="text"
                value={calcSellRaw}
                onChange={(e) => setCalcSellRaw(e.target.value)}
                placeholder="e.g. 1.6m"
              />
            </label>
            <label className="calc-field">
              <span>Quantity / 4h Buy Limit</span>
              <input
                type="text"
                value={calcQtyRaw}
                onChange={(e) => setCalcQtyRaw(e.target.value)}
                placeholder="e.g. 100 or 10k"
              />
            </label>
          </div>

          <div className="calc-results">
            <div className="calc-row">
              <span>Break-Even Sell Price</span>
              <strong>{calcMetrics.breakEvenSell.toLocaleString()} gp</strong>
            </div>
            <div className="calc-row">
              <span>2% GE Tax / Item</span>
              <strong className="down">-{calcMetrics.taxPerItem.toLocaleString()} gp</strong>
            </div>
            <div className="calc-row">
              <span>Net Profit / Item</span>
              <strong className={calcMetrics.netPerItem >= 0 ? "up" : "down"}>
                {calcMetrics.netPerItem >= 0 ? "+" : ""}
                {calcMetrics.netPerItem.toLocaleString()} gp ({formatPct(calcMetrics.roiPct)})
              </strong>
            </div>
            <div className="calc-divider" />
            <div className="calc-row">
              <span>Total Capital Needed</span>
              <strong>{formatGP(calcMetrics.totalCapital)} gp</strong>
            </div>
            <div className="calc-row">
              <span>Total GE Tax Paid</span>
              <strong className="muted">-{formatGP(calcMetrics.totalTax)} gp</strong>
            </div>
            <div className="calc-row total">
              <span>Total Flip Profit</span>
              <strong className={calcMetrics.totalNet >= 0 ? "up" : "down"}>
                {calcMetrics.totalNet >= 0 ? "+" : ""}
                {formatGP(calcMetrics.totalNet)} gp
              </strong>
            </div>
          </div>
        </section>
      </aside>
    </div>
  );
}
