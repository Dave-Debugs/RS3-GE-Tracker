import type { ItemStats, TrendInfo } from "../types";
import { changeClass, formatGP, formatGPExact, formatPct, formatVolume } from "../lib/format";

interface Props {
  name: string | null;
  stats: ItemStats | null;
  trend: TrendInfo | null;
}

export default function StatsPanel({ name, stats, trend }: Props) {
  if (!name || !stats) {
    return (
      <section className="card stats-card">
        <h2>Price Statistics</h2>
        <p className="muted empty-hint">Select a tracked item to see its stats.</p>
      </section>
    );
  }
  const rows: [string, string, string?][] = [
    ["Current price", formatGPExact(stats.current_price)],
    ["24H change", formatPct(stats.change_24h), changeClass(stats.change_24h)],
    ["7D change", formatPct(stats.change_7d), changeClass(stats.change_7d)],
    ["7D high", formatGP(stats.high_7d)],
    ["7D low", formatGP(stats.low_7d)],
    ["7D average", formatGP(stats.average_7d)],
    ["7D median", formatGP(stats.median_7d)],
    ["7D volatility", stats.volatility_7d != null ? `${stats.volatility_7d}%` : "—"],
    ["Volume (7D)", formatVolume(stats.total_volume)],
  ];
  const trendCls = trend?.classification.includes("Rising") ? "up"
    : trend?.classification.includes("Falling") ? "down" : "neutral";
  return (
    <section className="card stats-card">
      <h2>{name}</h2>
      {trend && (
        <div className={`trend-banner ${trendCls}`}>
          <span className="trend-label">{trend.classification}</span>
        </div>
      )}
      <dl className="stats-grid">
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
