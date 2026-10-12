import { useState, useMemo } from "react";
import { useFlipScanner, useAlchScanner, useTrackItem } from "../hooks";
import { formatGP, formatGPExact, formatPct } from "../lib/format";
import ItemTooltip from "./ItemTooltip";
import { useToast } from "../context/ToastContext";
import type { FlipScannerItem, AlchScannerItem } from "../types";

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
  const [subTab, setSubTab] = useState<"flips" | "alch">("flips");
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [minVolume, setMinVolume] = useState<number>(50);
  const [membersFilter, setMembersFilter] = useState<boolean | null>(null);
  const [sortBy, setSortBy] = useState<string>("limit_profit");
  const [searchFilter, setSearchFilter] = useState<string>("");

  const [calcName, setCalcName] = useState<string>("Custom Flip");
  const [calcBuy, setCalcBuy] = useState<number>(1_000_000);
  const [calcSell, setCalcSell] = useState<number>(1_060_000);
  const [calcQty, setCalcQty] = useState<number>(10);

  const flipQuery = useFlipScanner({
    minPrice: 100,
    maxPrice,
    minVolume,
    members: membersFilter,
    sortBy,
  });

  const alchQuery = useAlchScanner({
    minVolume,
    members: membersFilter,
    sortBy,
  });

  const trackMut = useTrackItem();

  const handleTrack = (itemId: number, name: string) => {
    trackMut.mutate(itemId, {
      onSuccess: () => addToast(`Added ${name} to watchlist`, "success"),
      onError: () => addToast(`Could not track ${name}`, "error"),
    });
  };

  const loadIntoCalc = (name: string, buyOffer: number, sellTarget: number, limit: number | null) => {
    setCalcName(name);
    setCalcBuy(buyOffer);
    setCalcSell(sellTarget);
    setCalcQty(limit && limit > 0 ? limit : 1);
    addToast(`Loaded ${name} into Flip Calculator`, "info");
  };

  const calcMetrics = useMemo(() => {
    const buy = Math.max(0, calcBuy || 0);
    const sell = Math.max(0, calcSell || 0);
    const qty = Math.max(1, calcQty || 1);
    const taxPerItem = sell >= 50 ? Math.min(Math.floor(sell * 0.02), 50_000_000) : 0;
    const netPerItem = sell - taxPerItem - buy;
    const breakEvenSell = buy >= 50 ? Math.ceil(buy / 0.98) : buy;
    const roiPct = buy > 0 ? (netPerItem / buy) * 100 : 0;
    const totalCapital = buy * qty;
    const totalNet = netPerItem * qty;
    const totalTax = taxPerItem * qty;
    return {
      taxPerItem,
      netPerItem,
      breakEvenSell,
      roiPct,
      totalCapital,
      totalNet,
      totalTax,
    };
  }, [calcBuy, calcSell, calcQty]);

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

  const natPrice = alchQuery.data?.nature_rune_price ?? 350;

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
                  Nature Rune: <strong>{natPrice.toLocaleString()} gp</strong>
                </span>
              </button>
            </div>

            <div className="scanner-filters">
              <input
                type="text"
                className="scanner-search-input"
                placeholder="Filter item name..."
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

              <div className="filter-group">
                <label>Rank By</label>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                  <option value="limit_profit">4h Limit Profit</option>
                  <option value="net_profit">Profit per Item</option>
                  <option value="roi">ROI %</option>
                  <option value="volume">24h Volume</option>
                </select>
              </div>
            </div>
          </div>

          {subTab === "flips" ? (
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
                    <th className="num" title="24-Hour Trade Volume">24h Vol</th>
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
                          <td className="num">{formatGP(item.volume_24h)}</td>
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
          ) : (
            <div className="table-scroll">
              <table className="table scanner-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th className="num" title="GE Buy Price">Buy Cost</th>
                    <th className="num" title="Live Nature Rune Price">Nature Rune</th>
                    <th className="num" title="Coins produced by High Level Alchemy">High Alch</th>
                    <th className="num" title="High Alch - (Buy Cost + Nature Rune)">Profit / Alch</th>
                    <th className="num">ROI %</th>
                    <th className="num">24h Vol</th>
                    <th className="num">4h Limit</th>
                    <th className="num" title="Profit per Alch × 4h Buy Limit">4h Alch Profit</th>
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
                          <td className="num muted">{item.nature_rune_price.toLocaleString()} gp</td>
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
                            {formatGP(item.limit_profit_4h)}
                          </td>
                          <td className="num actions-cell" onClick={(e) => e.stopPropagation()}>
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
            Click <strong>Calc</strong> on any flip row to load its prices.
          </p>

          <div className="calc-item-tag">{calcName}</div>

          <div className="calc-form">
            <label className="calc-field">
              <span>Buy Offer Price (gp)</span>
              <input
                type="number"
                min={1}
                value={calcBuy}
                onChange={(e) => setCalcBuy(Number(e.target.value))}
              />
            </label>
            <label className="calc-field">
              <span>Sell Target Price (gp)</span>
              <input
                type="number"
                min={1}
                value={calcSell}
                onChange={(e) => setCalcSell(Number(e.target.value))}
              />
            </label>
            <label className="calc-field">
              <span>Quantity / 4h Buy Limit</span>
              <input
                type="number"
                min={1}
                value={calcQty}
                onChange={(e) => setCalcQty(Number(e.target.value))}
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
