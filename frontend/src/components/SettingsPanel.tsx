import { useEffect, useState } from "react";
import { api } from "../api";
import type { Settings, StatusInfo, UpdateCheckResult } from "../types";
import { formatTime } from "../lib/format";

interface Props {
  open: boolean;
  status: StatusInfo | null;
  onClose: () => void;
  onSaved: (s: Settings) => void;
}

export default function SettingsPanel({ open, status, onClose, onSaved }: Props) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [applyingUpdate, setApplyingUpdate] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<UpdateCheckResult | null>(null);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setUpdateMessage(null);
      api.settings().then(setSettings).catch((e) => setError(String(e)));
    }
  }, [open]);

  if (!open) return null;

  const update = (patch: Partial<Settings>) =>
    setSettings((s) => (s ? { ...s, ...patch } : s));

  const handleCheckUpdates = async () => {
    setCheckingUpdate(true);
    setUpdateMessage(null);
    setError(null);
    try {
      const info = await api.checkUpdates();
      setUpdateInfo(info);
      if (info.error && !info.update_available) {
        setUpdateMessage(`You are on v${info.current_version}. (${info.error})`);
      } else if (!info.update_available) {
        setUpdateMessage(`You are running the latest version (v${info.current_version}).`);
      } else {
        setUpdateMessage(`Update available: v${info.latest_version} (Current: v${info.current_version})`);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setCheckingUpdate(false);
    }
  };

  const handleApplyUpdate = async () => {
    if (!updateInfo?.download_url) {
      if (updateInfo?.release_url) {
        window.open(updateInfo.release_url, "_blank", "noopener,noreferrer");
      }
      return;
    }
    setApplyingUpdate(true);
    setError(null);
    try {
      const res = await api.applyUpdate({
        download_url: updateInfo.download_url,
        checksum_url: updateInfo.checksum_url,
        asset_name: updateInfo.asset_name,
      });
      setUpdateMessage(res.message);
    } catch (e) {
      setError(String(e));
    } finally {
      setApplyingUpdate(false);
    }
  };

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await api.updateSettings({
        update_interval_minutes: settings.update_interval_minutes,
        theme: settings.theme,
        default_chart_range: settings.default_chart_range,
        show_item_tooltips: settings.show_item_tooltips || "true",
        user_agent: settings.user_agent,
        collector_autostart: settings.collector_autostart,
      });
      onSaved(saved);
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="card-head">
          <h2>Settings</h2>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        {error && <p className="error-text">{error}</p>}
        {!settings ? <p className="muted">Loading…</p> : (
          <div className="settings-form">
            <label>
              <span>Update interval</span>
              <select
                value={settings.update_interval_minutes}
                onChange={(e) => update({ update_interval_minutes: e.target.value })}
              >
                {["5", "10", "15", "30", "60"].map((m) => (
                  <option key={m} value={m}>{m} minutes</option>
                ))}
              </select>
            </label>
            <label>
              <span>Theme</span>
              <select value={settings.theme} onChange={(e) => update({ theme: e.target.value })}>
                <option value="dark">Dark</option>
                <option value="light">Light</option>
              </select>
            </label>
            <label>
              <span>Default chart range</span>
              <select
                value={settings.default_chart_range}
                onChange={(e) => update({ default_chart_range: e.target.value })}
              >
                {["1h", "6h", "24h", "7d", "14d", "30d"].map((r) => (
                  <option key={r} value={r}>{r.toUpperCase()}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Show item info &amp; Wiki hover tooltips</span>
              <select
                value={settings.show_item_tooltips ?? "true"}
                onChange={(e) => update({ show_item_tooltips: e.target.value })}
              >
                <option value="true">Enabled (Hover on ingredients)</option>
                <option value="false">Disabled</option>
              </select>
            </label>
            <label>
              <span>Start collector automatically</span>
              <select
                value={settings.collector_autostart}
                onChange={(e) => update({ collector_autostart: e.target.value })}
              >
                <option value="true">Yes (recommended)</option>
                <option value="false">No — manual only</option>
              </select>
            </label>
            <label className="full">
              <span>API User-Agent <em>(must stay descriptive — the wiki blocks generic agents)</em></span>
              <input
                value={settings.user_agent}
                onChange={(e) => update({ user_agent: e.target.value })}
              />
            </label>
            <label className="full">
              <span>Database location</span>
              <input value={settings.database_path} readOnly className="readonly" />
            </label>
            <div className="full" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", padding: "8px 0" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: "13px" }}>Application Version: v1.2.0</div>
                {updateMessage && (
                  <div className="muted" style={{ fontSize: "12px", marginTop: "4px" }}>
                    {updateMessage}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={handleCheckUpdates}
                  disabled={checkingUpdate || applyingUpdate}
                >
                  {checkingUpdate ? "Checking…" : "Check for Updates"}
                </button>
                {updateInfo?.update_available && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handleApplyUpdate}
                    disabled={applyingUpdate}
                  >
                    {applyingUpdate ? "Downloading…" : `Update to v${updateInfo.latest_version}`}
                  </button>
                )}
              </div>
            </div>
            <div className="settings-meta muted">
              <span>Items in database: {status?.item_count?.toLocaleString() ?? "—"}</span>
              <span>Price records: {status?.database_records?.toLocaleString() ?? "—"}</span>
              <span>Data coverage: {status?.data_coverage_days ?? 0} days</span>
              <span>Last sync: {status?.last_run_ok ? "OK" : status?.last_run_error ?? "—"} ({formatTime(status?.last_update)})</span>
            </div>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn btn-primary" onClick={save} disabled={saving}>
                {saving ? "Saving…" : "Save settings"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
