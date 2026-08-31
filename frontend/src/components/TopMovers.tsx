import { useState } from "react";
import type { Mover } from "../types";
import { changeClass, formatGP, formatPct, formatVolume } from "../lib/format";
import { useMovers } from "../hooks";

interface Props {
  onSelect: (itemId: number, name: string) => void;
}

export default function TopMovers({ onSelect }: Props) {
  const [period, setPeriod] = useState<"24h" | "7d">("24h");
  const { data, error } = useMovers(period);

  const renderList = (title: string, movers: Mover[], showChange: boolean) => (
    <div className="movers-col">
      <h3>{title}</h3>
      {!movers.length && <p className="muted">Not enough data yet</p>}
      {movers.map((m) => (
        <button
          key={m.item_id}
          className="mover-row"
          onClick={() => onSelect(m.item_id, m.name)}
          title="Preview chart"
        >
          {m.icon_url ? (
            <img src={m.icon_url} alt="" className="item-icon sm" loading="lazy"
                 onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")} />
          ) : <span className="item-icon sm placeholder" />}
          <span className="mover-name">{m.name}</span>
          <span className="mover-price">{formatGP(m.current_price)}</span>
          {showChange ? (
            <span className={`mover-pct ${changeClass(m.change_pct)}`}>
              {formatPct(m.change_pct)}
            </span>
          ) : (
            <span className="mover-pct neutral">{formatVolume(m.volume_24h)}</span>
          )}
        </button>
      ))}
    </div>
  );

  return (
    <section className="card movers-card">
      <div className="card-head">
        <h2>Top Movers</h2>
        <div className="seg">
          {(["24h", "7d"] as const).map((p) => (
            <button
              key={p}
              className={"seg-btn" + (period === p ? " active" : "")}
              onClick={() => setPeriod(p)}
            >{p.toUpperCase()}</button>
          ))}
        </div>
      </div>
      {error && <p className="muted">Top movers unavailable: {error.message}</p>}
      {data && (
        <div className="movers-grid">
          {renderList("Biggest Gainers", data.gainers, true)}
          {renderList("Biggest Losers", data.losers, true)}
          {renderList("Highest Volume (24H)", data.highest_volume, false)}
        </div>
      )}
      <p className="muted legend-hint">
        Whole-market view from hourly data (items ≥100 gp with real trade volume).
        Click any item to open its chart.
      </p>
    </section>
  );
}
