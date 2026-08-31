import { useState, useMemo } from "react";
import type { TrackedItem } from "../types";
import { changeClass, formatGP, formatGPExact, formatPct, formatVolume, relativeTime } from "../lib/format";
import AlertModal from "./AlertModal";
import GroupModal from "./GroupModal";

interface Props {
  items: TrackedItem[];
  allGroups?: string[];
  activeCategory?: string;
  selectedIds: Set<number>;
  focusedId: number | null;
  onToggleChart: (id: number) => void;
  onFocus: (id: number) => void;
  onFavorite: (id: number, fav: boolean) => void;
  onRemove: (id: number) => void;
  onSetGroup: (id: number, group: string) => void;
  onTrack?: (item: { item_id: number }) => void;
  onCreateCategory?: () => void;
}

type SortField = "name" | "buy_price" | "sell_price" | "margin" | "net_profit" | "volume_24h" | "change_24h" | "change_7d" | "trend";

const TREND_ICON: Record<string, string> = {
  "Strongly Rising": "▲▲",
  Rising: "▲",
  Neutral: "◆",
  Falling: "▼",
  "Strongly Falling": "▼▼",
};

const STARTER_ITEMS = [
  { item_id: 4151, name: "Abyssal whip" },
  { item_id: 2, name: "Cannonball" },
  { item_id: 451, name: "Runite ore" },
  { item_id: 29556, name: "Elder logs" },
  { item_id: 536, name: "Dragon bones" },
  { item_id: 6685, name: "Saradomin brew (4)" },
  { item_id: 207, name: "Grimy ranarr weed" },
  { item_id: 11694, name: "Armadyl godsword" },
];

export default function TrackedList({
  items,
  allGroups = ["Default"],
  activeCategory = "__ALL__",
  selectedIds,
  focusedId,
  onToggleChart,
  onFocus,
  onFavorite,
  onRemove,
  onSetGroup,
  onTrack,
  onCreateCategory,
}: Props) {
  const [filter, setFilter] = useState("");
  const [viewMode, setViewMode] = useState<"cards" | "grid">("cards");
  const [sortField, setSortField] = useState<SortField>("name");
  const [sortAsc, setSortAsc] = useState<boolean>(true);

  // Modals state
  const [alertTarget, setAlertTarget] = useState<TrackedItem | null>(null);
  const [groupTarget, setGroupTarget] = useState<{ id: number; name: string } | null>(null);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === "name");
    }
  };

  const sortedAndFiltered = useMemo(() => {
    let list = items.filter((i) =>
      i.name.toLowerCase().includes(filter.toLowerCase())
    );

    list.sort((a, b) => {
      let valA: any = a[sortField];
      let valB: any = b[sortField];

      if (valA == null) valA = sortField === "name" ? "" : -Infinity;
      if (valB == null) valB = sortField === "name" ? "" : -Infinity;

      if (typeof valA === "string") {
        return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return sortAsc ? valA - valB : valB - valA;
    });

    return list;
  }, [items, filter, sortField, sortAsc]);

  const grouped = useMemo(() => {
    const map = new Map<string, TrackedItem[]>();
    for (const item of sortedAndFiltered) {
      const gName = item.group_name || "Default";
      if (!map.has(gName)) map.set(gName, []);
      map.get(gName)!.push(item);
    }
    const sortedGroups = Array.from(map.keys()).sort((a, b) => {
      if (a === "Default") return -1;
      if (b === "Default") return 1;
      return a.localeCompare(b);
    });
    return sortedGroups.map((name) => ({ name, items: map.get(name)! }));
  }, [sortedAndFiltered]);

  const renderSortIndicator = (field: SortField) => {
    if (sortField !== field) return null;
    return <span style={{ marginLeft: "4px", fontSize: "10px" }}>{sortAsc ? "▲" : "▼"}</span>;
  };

  const categoryTitle =
    activeCategory === "__ALL__" ? "All Watchlists" : `Category: ${activeCategory}`;

  return (
    <section className="card tracked-card">
      <div className="card-head">
        <div>
          <h2 style={{ margin: 0, display: "inline-block" }}>
            Tracked Items <span className="count-badge">{items.length}</span>
          </h2>
          <span className="muted" style={{ fontSize: "12px", marginLeft: "10px" }}>
            {categoryTitle}
          </span>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          {items.length > 2 && (
            <input
              className="mini-filter"
              placeholder="Filter watchlist…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          )}
          <button
            className="icon-btn"
            onClick={() => setViewMode(viewMode === "cards" ? "grid" : "cards")}
            title={viewMode === "cards" ? "Switch to Table View" : "Switch to Cards View"}
            style={{ fontSize: "12px", border: "1px solid var(--card-border)", padding: "4px 8px" }}
          >
            {viewMode === "cards" ? "⊞ Grid" : "☰ Cards"}
          </button>
        </div>
      </div>

      {!items.length && (
        <div className="empty-hint" style={{ textAlign: "center", padding: "32px 16px" }}>
          <p style={{ fontSize: "15px", fontWeight: 600, margin: "0 0 6px" }}>
            {activeCategory !== "__ALL__"
              ? `No items in category "${activeCategory}" yet`
              : "Nothing tracked yet"}
          </p>
          <p className="muted" style={{ margin: "0 0 16px", fontSize: "13px" }}>
            Search an item above or click a popular item below to start tracking:
          </p>
          <div style={{ display: "flex", gap: "8px", justifyContent: "center", flexWrap: "wrap", maxWidth: "600px", margin: "0 auto" }}>
            {STARTER_ITEMS.map((item) => (
              <button
                key={item.item_id}
                type="button"
                className="btn btn-track"
                style={{ fontSize: "12px", padding: "6px 12px", borderRadius: "999px" }}
                onClick={() => onTrack && onTrack({ item_id: item.item_id })}
              >
                + {item.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="tracked-groups">
        {grouped.map((group) => {
          const totalVol = group.items.reduce((acc, i) => acc + (i.volume_24h || 0), 0);
          const avgChange =
            group.items.reduce((acc, i) => acc + (i.change_24h || 0), 0) / (group.items.length || 1);

          return (
            <div key={group.name} className="tracked-group">
              {activeCategory === "__ALL__" && (
                <div className="group-header">
                  <h3>{group.name}</h3>
                  <span className="group-stats muted">
                    Vol: {formatVolume(totalVol)} · 24H:{" "}
                    <span className={changeClass(avgChange)}>{formatPct(avgChange)}</span>
                  </span>
                </div>
              )}

              {viewMode === "grid" ? (
                <div style={{ overflowX: "auto" }}>
                  <table className="table" style={{ width: "100%", textAlign: "left", borderCollapse: "collapse", fontSize: "0.9em" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border)" }}>
                        <th style={{ width: "36px" }}>Chart</th>
                        <th style={{ cursor: "pointer" }} onClick={() => handleSort("name")}>
                          Item {renderSortIndicator("name")}
                        </th>
                        <th style={{ cursor: "pointer", textAlign: "right" }} onClick={() => handleSort("buy_price")}>
                          Buy {renderSortIndicator("buy_price")}
                        </th>
                        <th style={{ cursor: "pointer", textAlign: "right" }} onClick={() => handleSort("sell_price")}>
                          Sell {renderSortIndicator("sell_price")}
                        </th>
                        <th style={{ cursor: "pointer", textAlign: "right" }} onClick={() => handleSort("margin")}>
                          Margin {renderSortIndicator("margin")}
                        </th>
                        <th style={{ cursor: "pointer", textAlign: "right" }} onClick={() => handleSort("net_profit")}>
                          Net Profit {renderSortIndicator("net_profit")}
                        </th>
                        <th style={{ cursor: "pointer", textAlign: "right" }} onClick={() => handleSort("volume_24h")}>
                          24H Vol {renderSortIndicator("volume_24h")}
                        </th>
                        <th style={{ cursor: "pointer", textAlign: "right" }} onClick={() => handleSort("change_24h")}>
                          24H {renderSortIndicator("change_24h")}
                        </th>
                        <th style={{ cursor: "pointer", textAlign: "center" }} onClick={() => handleSort("trend")}>
                          Trend {renderSortIndicator("trend")}
                        </th>
                        <th style={{ textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.items.map((item) => {
                        const marginRatio =
                          item.margin && item.sell_price ? Math.min(100, Math.max(0, (item.margin / item.sell_price) * 100)) : 0;
                        return (
                          <tr
                            key={item.item_id}
                            style={{
                              borderBottom: "1px solid var(--border)",
                              background: focusedId === item.item_id ? "var(--accent-soft)" : "transparent",
                              cursor: "pointer",
                            }}
                            onClick={() => onFocus(item.item_id)}
                          >
                            <td>
                              <input
                                type="checkbox"
                                checked={selectedIds.has(item.item_id)}
                                onClick={(e) => e.stopPropagation()}
                                onChange={() => onToggleChart(item.item_id)}
                              />
                            </td>
                            <td style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.6rem 0" }}>
                              {item.icon_url ? (
                                <img src={item.icon_url} alt="" width="22" height="22" style={{ objectFit: "contain" }} />
                              ) : (
                                <span className="item-icon sm placeholder" />
                              )}
                              <span style={{ fontWeight: 600 }}>{item.name}</span>
                            </td>
                            <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                              {item.buy_price ? formatGP(item.buy_price) : "—"}
                            </td>
                            <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                              {item.sell_price ? formatGP(item.sell_price) : "—"}
                            </td>
                            <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                              <div>{item.margin ? formatGP(item.margin) : "—"}</div>
                              {marginRatio > 0 && (
                                <div style={{ height: "3px", width: "40px", background: "var(--card-border)", borderRadius: "2px", marginLeft: "auto", marginTop: "2px" }}>
                                  <div style={{ height: "100%", width: `${Math.min(100, marginRatio * 10)}%`, background: "var(--accent)", borderRadius: "2px" }} />
                                </div>
                              )}
                            </td>
                            <td
                              style={{
                                textAlign: "right",
                                fontVariantNumeric: "tabular-nums",
                                fontWeight: 700,
                                color:
                                  item.net_profit && item.net_profit > 0
                                    ? "var(--up)"
                                    : item.net_profit && item.net_profit < 0
                                    ? "var(--down)"
                                    : "inherit",
                              }}
                            >
                              {item.net_profit ? formatGP(item.net_profit) : "—"}
                            </td>
                            <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                              {formatVolume(item.volume_24h)}
                            </td>
                            <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                              <span className={changeClass(item.change_24h)}>{formatPct(item.change_24h)}</span>
                            </td>
                            <td style={{ textAlign: "center" }}>
                              <span className={`trend-tag ${item.trend.includes("Rising") ? "up" : item.trend.includes("Falling") ? "down" : "neutral"}`} style={{ fontSize: "10px", padding: "2px 6px" }}>
                                {TREND_ICON[item.trend] ?? "◆"} {item.trend}
                              </span>
                            </td>
                            <td style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                              <div style={{ display: "flex", gap: "4px", justifyContent: "flex-end", alignItems: "center" }}>
                                <select
                                  className="group-select"
                                  title="Category"
                                  style={{ fontSize: "11px", padding: "2px 4px", maxWidth: "85px" }}
                                  value={item.group_name || "Default"}
                                  onChange={(e) => {
                                    if (e.target.value === "__NEW__") {
                                      setGroupTarget({ id: item.item_id, name: item.name });
                                    } else {
                                      onSetGroup(item.item_id, e.target.value);
                                    }
                                  }}
                                >
                                  {allGroups.map((g) => (
                                    <option key={g} value={g}>{g}</option>
                                  ))}
                                  <option value="__NEW__">+ New…</option>
                                </select>
                                <button className="icon-btn" title="Set Price Alert" onClick={() => setAlertTarget(item)}>🔔</button>
                                <button
                                  className={"icon-btn" + (item.favorite ? " fav" : "")}
                                  title={item.favorite ? "Unfavorite" : "Favorite"}
                                  onClick={() => onFavorite(item.item_id, !item.favorite)}
                                >
                                  ★
                                </button>
                                <button className="icon-btn danger" title="Stop tracking" onClick={() => onRemove(item.item_id)}>✕</button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="tracked-rows">
                  {group.items.map((item) => {
                    const trendCls = item.trend.includes("Rising")
                      ? "up"
                      : item.trend.includes("Falling")
                      ? "down"
                      : "neutral";
                    return (
                      <div
                        key={item.item_id}
                        className={
                          "tracked-row" +
                          (focusedId === item.item_id ? " focused" : "") +
                          (selectedIds.has(item.item_id) ? "" : " dimmed")
                        }
                        onClick={() => onFocus(item.item_id)}
                      >
                        <input
                          type="checkbox"
                          className="row-check"
                          title="Show on chart"
                          checked={selectedIds.has(item.item_id)}
                          onClick={(e) => e.stopPropagation()}
                          onChange={() => onToggleChart(item.item_id)}
                        />
                        {item.icon_url ? (
                          <img
                            src={item.icon_url}
                            alt=""
                            className="item-icon"
                            loading="lazy"
                            onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
                          />
                        ) : (
                          <span className="item-icon placeholder" />
                        )}
                        <div className="tracked-name">
                          <span className="name">{item.name}</span>
                          <span className="sub">
                            {item.backfilled ? relativeTime(item.last_updated) : "backfilling…"}
                            {" · vol "}
                            {formatVolume(item.volume_24h)}
                          </span>
                        </div>
                        <div className="tracked-price" title={formatGPExact(item.current_price)}>
                          <div className="main-val">{formatGP(item.current_price)}</div>
                          <div className="sub">
                            B: {item.buy_price ? formatGP(item.buy_price) : "—"} <br />
                            S: {item.sell_price ? formatGP(item.sell_price) : "—"}
                          </div>
                        </div>

                        <div className="tracked-price">
                          <div
                            className="main-val"
                            style={{
                              color:
                                item.net_profit && item.net_profit > 0
                                  ? "var(--up)"
                                  : item.net_profit && item.net_profit < 0
                                  ? "var(--down)"
                                  : "inherit",
                            }}
                          >
                            {item.net_profit ? formatGP(item.net_profit) : "—"}
                          </div>
                          <div className="sub" title="Net profit per flip after GE tax">Margin</div>
                        </div>

                        <div className="tracked-changes">
                          <span className={changeClass(item.change_24h)} title="24-hour change">
                            {formatPct(item.change_24h)}
                          </span>
                          <span className={changeClass(item.change_7d)} title="7-day change">
                            {formatPct(item.change_7d)}
                          </span>
                        </div>
                        <span className={`trend-tag ${trendCls}`} title={item.trend}>
                          {TREND_ICON[item.trend] ?? "◆"} {item.trend}
                        </span>
                        <div className="row-actions" onClick={(e) => e.stopPropagation()}>
                          <button className="icon-btn" title="Set Price Alert" onClick={() => setAlertTarget(item)}>
                            🔔
                          </button>
                          <select
                            className="group-select"
                            title="Move to item group"
                            value={item.group_name || "Default"}
                            onChange={(e) => {
                              if (e.target.value === "__NEW__") {
                                setGroupTarget({ id: item.item_id, name: item.name });
                              } else {
                                onSetGroup(item.item_id, e.target.value);
                              }
                            }}
                          >
                            {allGroups.map((g) => (
                              <option key={g} value={g}>{g}</option>
                            ))}
                            <option value="__NEW__">+ New Item Group…</option>
                          </select>
                          <button
                            className={"icon-btn" + (item.favorite ? " fav" : "")}
                            title={item.favorite ? "Unfavorite" : "Favorite"}
                            onClick={() => onFavorite(item.item_id, !item.favorite)}
                          >
                            ★
                          </button>
                          <button
                            className="icon-btn danger"
                            title="Stop tracking"
                            onClick={() => onRemove(item.item_id)}
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="muted legend-hint">
        24H / 7D changes · checkbox = show on chart · click a row to view statistical details
      </p>

      <AlertModal target={alertTarget} onClose={() => setAlertTarget(null)} />
      <GroupModal
        open={groupTarget !== null}
        itemId={groupTarget?.id ?? null}
        itemName={groupTarget?.name ?? ""}
        onClose={() => setGroupTarget(null)}
        onSave={(id, group) => {
          if (id) {
            onSetGroup(id, group);
          }
        }}
      />
    </section>
  );
}
