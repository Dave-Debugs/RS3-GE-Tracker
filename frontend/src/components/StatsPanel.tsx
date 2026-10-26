import type { ItemStats, TrendInfo } from "../types";
import { changeClass, formatGP, formatGPExact, formatPct, formatVolume } from "../lib/format";

interface Props {
  name: string | null;
  itemId?: number | null;
  isTracked?: boolean;
  stats: ItemStats | null;
  trend: TrendInfo | null;
  onTrack?: (item: { item_id: number; name?: string }) => void;
}

export default function StatsPanel({ name, itemId, isTracked = true, stats, trend, onTrack }: Props) {
  if (!name || !stats) {
    return (
      <section className="card stats-card">
        <h2>Price Statistics</h2>
        <p className="muted empty-hint">Select a tracked item or click any Top Mover to preview stats.</p>
      </section>
    );
  }
  const zPrice = stats.price_zscore ?? 0;
  const zVol = stats.volume_zscore ?? 0;
  const rows: [string, string, string?][] = [
    ["Current price", formatGPExact(stats.current_price)],
    ["24H change", formatPct(stats.change_24h), changeClass(stats.change_24h)],
    ["7D change", formatPct(stats.change_7d), changeClass(stats.change_7d)],
    ["7D VWAP", formatGP(stats.vwap_7d ?? stats.average_7d)],
    ["7D high / low", `${formatGP(stats.high_7d)} / ${formatGP(stats.low_7d)}`],
    ["7D average", formatGP(stats.average_7d)],
    ["7D median", formatGP(stats.median_7d)],
    ["7D volatility", stats.volatility_7d != null ? `${stats.volatility_7d}%` : "—"],
    ["Price Z-score", `${zPrice > 0 ? "+" : ""}${zPrice.toFixed(2)}σ`, Math.abs(zPrice) >= 2 ? (zPrice > 0 ? "up" : "down") : ""],
    ["Volume (7D)", formatVolume(stats.total_volume)],
  ];
  const trendCls = trend?.classification.includes("Rising") ? "up"
    : trend?.classification.includes("Falling") ? "down" : "neutral";
  return (
    <section className="card stats-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px", marginBottom: "8px" }}>
        <div style={{ minWidth: 0 }}>
          <h2 style={{ margin: 0 }}>{name}</h2>
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "4px" }}>
            {!isTracked && (
              <span className="pill" style={{ background: "var(--accent-soft)", color: "var(--accent)", fontSize: "10px", padding: "1px 6px" }}>
                Preview Mode
              </span>
            )}
            {stats.anomaly_label && (
              <span
                className="pill"
                style={{
                  background: stats.anomaly_label.includes("Dump") || stats.anomaly_label.includes("Dip") ? "var(--down-soft)" : "var(--warn-soft)",
                  color: stats.anomaly_label.includes("Dump") || stats.anomaly_label.includes("Dip") ? "var(--down)" : "var(--warn)",
                  fontSize: "10px",
                  padding: "1px 8px",
                }}
                title={`Price Z=${zPrice}σ, Volume Z=${zVol}σ`}
              >
                ⚡ {stats.anomaly_label}
              </span>
            )}
          </div>
        </div>
        {!isTracked && itemId && onTrack && (
          <button
            type="button"
            className="btn btn-primary"
            style={{ fontSize: "11px", padding: "4px 8px", flexShrink: 0, whiteSpace: "nowrap" }}
            onClick={() => onTrack({ item_id: itemId, name })}
          >
            + Track Item
          </button>
        )}
      </div>
      {trend && (
        <div className={`trend-banner ${trendCls}`}>
          <span className="trend-label">{trend.classification}</span>
          {trend.r_squared > 0 && (
            <span className="muted" style={{ fontSize: "11px", marginLeft: "8px" }}>
              R² = {trend.r_squared}
            </span>
          )}
        </div>
      )}
      <dl className="stats-grid tabular-nums">
        {rows.map(([label, value, cls]) => (
          <div key={label} className="stat">
            <dt>{label}</dt>
            <dd className={cls ?? ""}>{value}</dd>
          </div>
        ))}
      </dl>
      {trend && (
        <p className="muted trend-note">
          Descriptive statistics over {trend.points_used} recorded points — not a
          prediction. Short MA {formatGP(trend.short_ma)} vs long MA {formatGP(trend.long_ma)};
          volatility {trend.volatility_pct}% per point.
        </p>
      )}
    </section>
  );
}
