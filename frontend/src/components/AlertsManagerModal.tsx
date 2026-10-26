import { useAlerts, useUpdateAlert, useDeleteAlert } from "../hooks";
import { formatGP, relativeTime } from "../lib/format";
import { useToast } from "../context/ToastContext";

interface Props {
  open: boolean;
  onClose: () => void;
}

const METRIC_SHORT: Record<string, string> = {
  either: "Price",
  high: "Insta-Buy",
  low: "Insta-Sell",
  net_margin: "Net Margin",
  volume_24h: "24h Vol",
};

export default function AlertsManagerModal({ open, onClose }: Props) {
  const { data: alerts = [], isLoading } = useAlerts();
  const updateAlertMutation = useUpdateAlert();
  const deleteAlertMutation = useDeleteAlert();
  const { toast } = useToast();

  if (!open) return null;

  const handleToggle = (id: number, currentActive: boolean) => {
    updateAlertMutation.mutate(
      { id, active: !currentActive },
      {
        onSuccess: () => {
          toast.info(currentActive ? "Alert paused" : "Alert activated");
        },
      }
    );
  };

  const handleDelete = (id: number, itemName: string) => {
    deleteAlertMutation.mutate(id, {
      onSuccess: () => {
        toast.success(`Removed alert for ${itemName}`);
      },
      onError: (err) => {
        toast.error(`Failed to delete alert: ${err.message}`);
      },
    });
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ width: "640px" }}>
        <div className="card-head">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "18px" }}>🔔</span>
            <h2 style={{ margin: 0 }}>
              Price &amp; Margin Alerts <span className="count-badge">{alerts.length}</span>
            </h2>
          </div>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>

        {isLoading ? (
          <p className="muted" style={{ padding: "20px 0" }}>Loading alerts…</p>
        ) : alerts.length === 0 ? (
          <div className="empty-hint muted" style={{ textAlign: "center", padding: "32px 16px" }}>
            <p style={{ margin: "0 0 8px", fontSize: "15px", fontWeight: 600 }}>No price alerts configured</p>
            <p style={{ margin: 0, fontSize: "12.5px" }}>
              Click the 🔔 icon next to any tracked item to set Instant Buy, Instant Sell, Net Flip Margin, or Volume triggers.
            </p>
          </div>
        ) : (
          <div className="alerts-list" style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "12px", maxHeight: "60vh", overflowY: "auto" }}>
            {alerts.map((a) => {
              const itemName = a.name || `Item ${a.item_id}`;
              const isTriggered = !a.active && a.last_triggered;
              const metricKey = a.metric || "either";
              const metricTag = METRIC_SHORT[metricKey] || "Price";
              return (
                <div
                  key={a.id}
                  className="alert-item-card"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "12px",
                    padding: "10px 14px",
                    background: "var(--bg-soft)",
                    borderRadius: "8px",
                    border: "1px solid var(--card-border)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0, flex: 1 }}>
                    {a.icon_url ? (
                      <img src={a.icon_url} alt="" className="item-icon sm" />
                    ) : (
                      <span className="item-icon sm placeholder" />
                    )}
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: "13.5px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {itemName}
                      </div>
                      <div className="muted" style={{ fontSize: "11px" }}>
                        {a.current_price ? `Live: ${formatGP(a.current_price)}` : `ID: ${a.item_id}`}
                        {a.latest_net_margin != null ? ` · Margin: +${formatGP(a.latest_net_margin)}` : ""}
                        {a.cooldown_minutes && a.cooldown_minutes > 0 ? ` · Every ${a.cooldown_minutes}m` : " · One-shot"}
                        {a.last_triggered ? ` · Last: ${relativeTime(a.last_triggered)}` : ""}
                      </div>
                    </div>
                  </div>

                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: "var(--accent)" }}>
                      {metricTag} {a.condition} {formatGP(a.threshold_price)}
                    </div>
                    <div>
                      {a.active ? (
                        <span className="pill pill-online" style={{ fontSize: "10px", padding: "2px 8px" }}>Active</span>
                      ) : isTriggered ? (
                        <span className="pill" style={{ background: "rgba(232, 182, 76, 0.15)", color: "var(--accent)", fontSize: "10px", padding: "2px 8px" }}>Triggered</span>
                      ) : (
                        <span className="pill" style={{ background: "rgba(139, 147, 163, 0.15)", color: "var(--fg-dim)", fontSize: "10px", padding: "2px 8px" }}>Paused</span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: "11px", padding: "4px 8px" }}
                      onClick={() => handleToggle(a.id, a.active)}
                      title={a.active ? "Pause alert" : "Activate alert"}
                    >
                      {a.active ? "Pause" : "Resume"}
                    </button>
                    <button
                      className="icon-btn danger"
                      title="Delete alert"
                      onClick={() => handleDelete(a.id, itemName)}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="modal-actions" style={{ marginTop: "16px" }}>
          <button className="btn btn-primary" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}
