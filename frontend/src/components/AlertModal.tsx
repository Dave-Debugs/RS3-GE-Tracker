import { useState, useEffect } from "react";
import { formatGP, formatGPExact, parseGPInput } from "../lib/format";
import { useCreateAlert } from "../hooks";
import { useToast } from "../context/ToastContext";
import type { AlertMetric } from "../types";

interface ItemAlertTarget {
  item_id: number;
  name: string;
  icon_url?: string | null;
  current_price?: number | null;
  buy_price?: number | null;
  sell_price?: number | null;
}

interface Props {
  target: ItemAlertTarget | null;
  onClose: () => void;
}

const METRIC_LABELS: Record<AlertMetric, string> = {
  either: "Live Price (High or Low)",
  high: "Instant Buy Price (High)",
  low: "Instant Sell Price (Low)",
  net_margin: "Net Flip Profit (After 2% Tax)",
  volume_24h: "24-Hour Trade Volume",
};

export default function AlertModal({ target, onClose }: Props) {
  const { toast } = useToast();
  const createAlertMutation = useCreateAlert();

  const [metric, setMetric] = useState<AlertMetric>("either");
  const [condition, setCondition] = useState<">" | "<" | ">=" | "<=">(">");
  const [threshold, setThreshold] = useState<string>("");
  const [cooldownMinutes, setCooldownMinutes] = useState<number>(0);

  useEffect(() => {
    if (target) {
      const base = target.buy_price || target.current_price || 0;
      setMetric("either");
      setCondition(">");
      setThreshold(base ? String(Math.ceil(base * 1.05)) : "");
      setCooldownMinutes(0);
    }
  }, [target]);

  if (!target) return null;

  const numThreshold = parseGPInput(threshold) ?? NaN;
  const isValid = !isNaN(numThreshold) && numThreshold > 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) {
      toast.error("Please enter a valid threshold (e.g. 5m, 250k, or 5000000).");
      return;
    }

    createAlertMutation.mutate(
      {
        item_id: target.item_id,
        condition,
        threshold_price: numThreshold,
        metric,
        cooldown_minutes: cooldownMinutes,
      },
      {
        onSuccess: () => {
          toast.success(
            `Alert created: ${target.name} (${METRIC_LABELS[metric]}) ${condition} ${formatGP(numThreshold)}`
          );
          onClose();
        },
        onError: (err) => {
          toast.error(`Failed to create alert: ${err.message}`);
        },
      }
    );
  };

  const netMarginRef =
    target.buy_price && target.sell_price
      ? target.buy_price -
        target.sell_price -
        (target.buy_price >= 50 ? Math.min(Math.floor(target.buy_price * 0.02), 50_000_000) : 0)
      : null;

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: "490px" }}>
        <div className="card-head">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {target.icon_url ? (
              <img src={target.icon_url} alt="" className="item-icon" />
            ) : (
              <span className="item-icon placeholder" />
            )}
            <div>
              <h2 style={{ margin: 0 }}>Set Smart Price Alert</h2>
              <span className="muted" style={{ fontSize: "12px" }}>{target.name} (ID: {target.item_id})</span>
            </div>
          </div>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>

        <div className="alert-market-ref" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", background: "var(--bg-soft)", padding: "10px", borderRadius: "8px", margin: "12px 0 16px", textAlign: "center" }}>
          <div>
            <div className="muted" style={{ fontSize: "11px", textTransform: "uppercase" }}>Instant Buy</div>
            <div style={{ fontWeight: 700, color: "var(--up)" }}>{target.buy_price ? formatGP(target.buy_price) : "—"}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: "11px", textTransform: "uppercase" }}>Instant Sell</div>
            <div style={{ fontWeight: 700, color: "var(--down)" }}>{target.sell_price ? formatGP(target.sell_price) : "—"}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: "11px", textTransform: "uppercase" }}>Net Margin</div>
            <div style={{ fontWeight: 700, color: "var(--accent)" }}>
              {netMarginRef != null ? `${netMarginRef > 0 ? "+" : ""}${formatGP(netMarginRef)}` : "—"}
            </div>
          </div>
        </div>

        <div style={{ marginBottom: "14px" }}>
          <span className="muted" style={{ fontSize: "11.5px", display: "block", marginBottom: "6px" }}>Quick presets:</span>
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {target.buy_price && (
              <button
                type="button"
                className="btn btn-ghost"
                style={{ fontSize: "11px", padding: "4px 8px" }}
                onClick={() => {
                  setMetric("high");
                  setCondition(">");
                  setThreshold(String(Math.ceil(target.buy_price! * 1.05)));
                }}
              >
                +5% above Buy ({formatGP(Math.ceil(target.buy_price * 1.05))})
              </button>
            )}
            {target.sell_price && (
              <button
                type="button"
                className="btn btn-ghost"
                style={{ fontSize: "11px", padding: "4px 8px" }}
                onClick={() => {
                  setMetric("low");
                  setCondition("<");
                  setThreshold(String(Math.floor(target.sell_price! * 0.95)));
                }}
              >
                -5% below Sell ({formatGP(Math.floor(target.sell_price * 0.95))})
              </button>
            )}
            {netMarginRef != null && netMarginRef > 0 && (
              <button
                type="button"
                className="btn btn-ghost"
                style={{ fontSize: "11px", padding: "4px 8px" }}
                onClick={() => {
                  setMetric("net_margin");
                  setCondition(">=");
                  setThreshold(String(Math.ceil(netMarginRef * 1.25)));
                }}
              >
                Net Margin &ge; {formatGP(Math.ceil(netMarginRef * 1.25))}
              </button>
            )}
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
            <span className="muted">Target Metric</span>
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value as AlertMetric)}
              style={{ height: "38px", background: "var(--input-bg)", border: "1px solid var(--card-border)", color: "var(--fg)", borderRadius: "7px", padding: "0 8px" }}
            >
              {Object.entries(METRIC_LABELS).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <div style={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: "10px" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
              <span className="muted">Condition</span>
              <select
                value={condition}
                onChange={(e) => setCondition(e.target.value as any)}
                style={{ height: "38px", background: "var(--input-bg)", border: "1px solid var(--card-border)", color: "var(--fg)", borderRadius: "7px", padding: "0 8px" }}
              >
                <option value=">">&gt; Higher than</option>
                <option value="<">&lt; Lower than</option>
                <option value=">=">&gt;= At or above</option>
                <option value="<=">&lt;= At or below</option>
              </select>
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
              <span className="muted">Threshold (Supports 250k / 5m / 1.2b)</span>
              <input
                type="text"
                placeholder="e.g. 5m or 250k"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                autoFocus
                style={{ height: "38px", background: "var(--input-bg)", border: "1px solid var(--card-border)", color: "var(--fg)", borderRadius: "7px", padding: "0 10px", fontSize: "14px", fontWeight: 600 }}
              />
            </label>
          </div>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
            <span className="muted">Trigger Mode / Cooldown</span>
            <select
              value={cooldownMinutes}
              onChange={(e) => setCooldownMinutes(Number(e.target.value))}
              style={{ height: "38px", background: "var(--input-bg)", border: "1px solid var(--card-border)", color: "var(--fg)", borderRadius: "7px", padding: "0 8px" }}
            >
              <option value={0}>One-Shot (Pause after triggering once)</option>
              <option value={15}>Recurring (15m cooldown between alerts)</option>
              <option value={60}>Recurring (1h cooldown between alerts)</option>
              <option value={240}>Recurring (4h buy-limit cooldown)</option>
            </select>
          </label>

          {isValid && (
            <div className="muted" style={{ fontSize: "12px", background: "var(--hover)", padding: "8px 12px", borderRadius: "6px" }}>
              Notify when <b>{METRIC_LABELS[metric]}</b> is{" "}
              <b>
                {condition} {metric === "volume_24h" ? numThreshold.toLocaleString() : formatGPExact(numThreshold)}
              </b>
            </div>
          )}

          <div className="modal-actions" style={{ marginTop: "6px" }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!isValid || createAlertMutation.isPending}
            >
              {createAlertMutation.isPending ? "Creating…" : "Create Alert"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
