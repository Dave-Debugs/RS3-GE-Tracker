import { useState, useEffect } from "react";
import { formatGP, formatGPExact } from "../lib/format";
import { useCreateAlert } from "../hooks";
import { useToast } from "../context/ToastContext";

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

export default function AlertModal({ target, onClose }: Props) {
  const { toast } = useToast();
  const createAlertMutation = useCreateAlert();

  const [condition, setCondition] = useState<">" | "<" | ">=" | "<=">(">");
  const [threshold, setThreshold] = useState<string>("");

  useEffect(() => {
    if (target) {
      // Default to slightly above high price or current price
      const base = target.buy_price || target.current_price || 0;
      setCondition(">");
      setThreshold(base ? String(Math.ceil(base * 1.05)) : "");
    }
  }, [target]);

  if (!target) return null;

  const numThreshold = parseInt(threshold.replace(/[^0-9]/g, ""), 10);
  const isValid = !isNaN(numThreshold) && numThreshold > 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) {
      toast.error("Please enter a valid positive GP threshold.");
      return;
    }

    createAlertMutation.mutate(
      {
        item_id: target.item_id,
        condition,
        threshold_price: numThreshold,
      },
      {
        onSuccess: () => {
          toast.success(`Alert created: ${target.name} ${condition} ${formatGP(numThreshold)}`);
          onClose();
        },
        onError: (err) => {
          toast.error(`Failed to create alert: ${err.message}`);
        },
      }
    );
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: "460px" }}>
        <div className="card-head">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {target.icon_url ? (
              <img src={target.icon_url} alt="" className="item-icon" />
            ) : (
              <span className="item-icon placeholder" />
            )}
            <div>
              <h2 style={{ margin: 0 }}>Set Price Alert</h2>
              <span className="muted" style={{ fontSize: "12px" }}>{target.name} (ID: {target.item_id})</span>
            </div>
          </div>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>

        <div className="alert-market-ref" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", background: "var(--bg-soft)", padding: "10px", borderRadius: "8px", margin: "12px 0 16px", textAlign: "center" }}>
          <div>
            <div className="muted" style={{ fontSize: "11px", textTransform: "uppercase" }}>Current</div>
            <div style={{ fontWeight: 700, color: "var(--accent)" }}>{target.current_price ? formatGP(target.current_price) : "—"}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: "11px", textTransform: "uppercase" }}>Instant Buy</div>
            <div style={{ fontWeight: 700, color: "var(--up)" }}>{target.buy_price ? formatGP(target.buy_price) : "—"}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: "11px", textTransform: "uppercase" }}>Instant Sell</div>
            <div style={{ fontWeight: 700, color: "var(--down)" }}>{target.sell_price ? formatGP(target.sell_price) : "—"}</div>
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
                onClick={() => { setCondition(">"); setThreshold(String(Math.ceil(target.buy_price! * 1.05))); }}
              >
                +5% above Buy ({formatGP(Math.ceil(target.buy_price * 1.05))})
              </button>
            )}
            {target.sell_price && (
              <button
                type="button"
                className="btn btn-ghost"
                style={{ fontSize: "11px", padding: "4px 8px" }}
                onClick={() => { setCondition("<"); setThreshold(String(Math.floor(target.sell_price! * 0.95))); }}
              >
                -5% below Sell ({formatGP(Math.floor(target.sell_price * 0.95))})
              </button>
            )}
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
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
              <span className="muted">Target Price (GP)</span>
              <input
                type="text"
                placeholder="e.g. 5000000"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                autoFocus
                style={{ height: "38px", background: "var(--input-bg)", border: "1px solid var(--card-border)", color: "var(--fg)", borderRadius: "7px", padding: "0 10px", fontSize: "14px", fontWeight: 600 }}
              />
            </label>
          </div>

          {isValid && (
            <div className="muted" style={{ fontSize: "12px", background: "var(--hover)", padding: "8px 12px", borderRadius: "6px" }}>
              Notify when price is <b>{condition} {formatGPExact(numThreshold)}</b>
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
