import type { StatusInfo } from "../types";
import { relativeTime } from "../lib/format";

interface Props {
  status: StatusInfo | null;
  alertsCount?: number;
  onOpenSettings: () => void;
  onOpenAlerts: () => void;
  onCollectNow: () => void;
}

export default function Header({ status, alertsCount = 0, onOpenSettings, onOpenAlerts, onCollectNow }: Props) {
  const online = status?.api_online ?? false;
  return (
    <header className="header">
      <div className="header-title">
        <div>
          <h1>RS3 Grand Exchange Tracker</h1>
          <span className="header-sub">
            1-year rolling market intelligence · Flipping, Alchemy &amp; Arbitrage terminal · Press{" "}
            <kbd className="kbd-hint">/</kbd> to search
          </span>
        </div>
      </div>
      <div className="header-status">
        <span className={`pill ${online ? "pill-online" : "pill-offline"}`}>
          <span className="dot" /> API {online ? "ONLINE" : "OFFLINE"}
        </span>
        <span className="status-item" title="Last successful collection">
          Last update: <b>{relativeTime(status?.last_update)}</b>
        </span>
        <span className="status-item" title="Next scheduled collection">
          Next: <b>{relativeTime(status?.next_update)}</b>
        </span>
        <button className="btn btn-ghost" onClick={onOpenAlerts} title="Manage price alerts">
          🔔 Alerts {alertsCount > 0 && <span className="count-badge" style={{ marginLeft: "4px" }}>{alertsCount}</span>}
        </button>
        <button className="btn btn-ghost" onClick={onCollectNow} title="Collect prices now">
          ↻ Refresh
        </button>
        <button className="btn btn-ghost" onClick={onOpenSettings} title="Settings">
          ⚙ Settings
        </button>
      </div>
    </header>
  );
}
