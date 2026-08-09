import { useState, useMemo } from "react";
import type { TrackedItem } from "../types";
import {
  changeClass, formatGP, formatGPExact, formatPct, formatVolume, relativeTime,
} from "../lib/format";

interface Props {
  items: TrackedItem[];
  selectedIds: Set<number>;
  focusedId: number | null;
  onToggleChart: (id: number) => void;
  onFocus: (id: number) => void;
  onFavorite: (id: number, fav: boolean) => void;
  onRemove: (id: number) => void;
  onSetGroup: (id: number, group: string) => void;
}

const TREND_ICON: Record<string, string> = {
  "Strongly Rising": "▲▲",
  Rising: "▲",
  Neutral: "◆",
  Falling: "▼",
  "Strongly Falling": "▼▼",
};

export default function TrackedList({
  items, selectedIds, focusedId, onToggleChart, onFocus, onFavorite, onRemove, onSetGroup
}: Props) {
  const [filter, setFilter] = useState("");
  const shown = items.filter((i) =>
    i.name.toLowerCase().includes(filter.toLowerCase())
  );

  const existingGroups = Array.from(new Set(items.map((i) => i.group_name))).sort();

  const grouped = useMemo(() => {
    const map = new Map<string, TrackedItem[]>();
    for (const item of shown) {
      if (!map.has(item.group_name)) map.set(item.group_name, []);
      map.get(item.group_name)!.push(item);
    }
    // sort groups: Default first, then alphabetical
    const sortedGroups = Array.from(map.keys()).sort((a, b) => {
      if (a === "Default") return -1;
      if (b === "Default") return 1;
      return a.localeCompare(b);
    });
    return sortedGroups.map(name => ({ name, items: map.get(name)! }));
  }, [shown]);

  return (
    <section className="card tracked-card">
      <div className="card-head">
        <h2>Tracked Items <span className="count-badge">{items.length}</span></h2>
        {items.length > 3 && (
          <input
            className="mini-filter"
            placeholder="Filter…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        )}
      </div>
      {!items.length && (
        <p className="muted empty-hint">
          Nothing tracked yet — search an item above and hit <b>+ Track</b>.
        </p>
      )}
      <div className="tracked-groups">
        {grouped.map((group) => {
          const totalVol = group.items.reduce((acc, i) => acc + (i.volume_24h || 0), 0);
          const avgChange = group.items.reduce((acc, i) => acc + (i.change_24h || 0), 0) / group.items.length;
          
          return (
            <div key={group.name} className="tracked-group">
              <div className="group-header">
                <h3>{group.name}</h3>
                <span className="group-stats muted">
                  Vol: {formatVolume(totalVol)} · 24H: <span className={changeClass(avgChange)}>{formatPct(avgChange)}</span>
                </span>
              </div>
              <div className="tracked-rows">
                {group.items.map((item) => {
                  const trendCls =
                    item.trend.includes("Rising") ? "up"
                    : item.trend.includes("Falling") ? "down" : "neutral";
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
                        <img src={item.icon_url} alt="" className="item-icon" loading="lazy"
                             onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")} />
                      ) : <span className="item-icon placeholder" />}
                      <div className="tracked-name">
                        <span className="name">{item.name}</span>
                        <span className="sub">
                          {item.backfilled ? relativeTime(item.last_updated) : "backfilling…"}
                          {" · vol "}{formatVolume(item.volume_24h)}
                        </span>
                      </div>
                      <div className="tracked-price" title={formatGPExact(item.current_price)}>
                        <div>{formatGP(item.current_price)}</div>
                        <div className="sub">
                          Buy: {item.buy_price ? formatGP(item.buy_price) : "-"} <br/>
                          Sell: {item.sell_price ? formatGP(item.sell_price) : "-"}
                        </div>
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
                        <select
                          className="group-select"
                          title="Move to group"
                          value={item.group_name}
                          onChange={(e) => {
                            if (e.target.value === "__NEW__") {
                              const name = prompt("Enter new group name:");
                              if (name) onSetGroup(item.item_id, name);
                            } else {
                              onSetGroup(item.item_id, e.target.value);
                            }
                          }}
                        >
                          {existingGroups.map(g => <option key={g} value={g}>{g}</option>)}
                          {existingGroups.includes("Default") ? null : <option value="Default">Default</option>}
                          <option value="__NEW__">+ New Group...</option>
                        </select>
                        <button
                          className={"icon-btn" + (item.favorite ? " fav" : "")}
                          title={item.favorite ? "Unfavorite" : "Favorite"}
                          onClick={() => onFavorite(item.item_id, !item.favorite)}
                        >★</button>
                        <button
                          className="icon-btn danger"
                          title="Stop tracking"
                          onClick={() => onRemove(item.item_id)}
                        >✕</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      <p className="muted legend-hint">24H / 7D changes · checkbox = show on chart · click a row for stats</p>
    </section>
  );
}
