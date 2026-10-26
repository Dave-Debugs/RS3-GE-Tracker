import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { Settings, StatusInfo, UpdateCheckResult } from "../types";
import { formatTime } from "../lib/format";
import { useToast } from "../context/ToastContext";

interface Props {
  open: boolean;
  status: StatusInfo | null;
  onClose: () => void;
  onSaved: (s: Settings) => void;
}

export default function SettingsPanel({ open, status, onClose, onSaved }: Props) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [testingWebhook, setTestingWebhook] = useState(false);
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

  const handleTestWebhook = async () => {
    if (!settings?.discord_webhook_url) {
      toast.error("Please enter a Discord Webhook URL first.");
      return;
    }
    setTestingWebhook(true);
    setError(null);
    try {
      await api.testWebhook(settings.discord_webhook_url);
      toast.success("Sent test alert to Discord!");
    } catch (e: any) {
      setError(`Webhook test failed: ${e.message || e}`);
    } finally {
      setTestingWebhook(false);
    }
  };

  const handleExportWorkspace = async () => {
    try {
      const data = await api.exportWorkspace();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `rs3_ge_tracker_backup_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Exported workspace backup JSON!");
    } catch (e: any) {
      toast.error(`Export failed: ${e.message || e}`);
    }
  };

  const handleImportWorkspaceFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const res = await api.importWorkspace(payload);
      qc.invalidateQueries();
      toast.success(
        `Restored workspace (${res.restored.tracked_items || 0} tracked, ${res.restored.portfolio || 0} holdings, ${res.restored.recipes || 0} recipes)!`
      );
    } catch (err: any) {
      toast.error(`Failed to import backup: ${err.message || err}`);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
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
        discord_webhook_url: settings.discord_webhook_url ?? "",
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
      <div className="modal" style={{ maxWidth: "620px" }}>
        <div className="card-head">
          <h2>Settings &amp; Backup</h2>
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
                <option value="dark">Grand Exchange Gold (Dark)</option>
                <option value="nox">Noxious Abyss (Dark Green)</option>
                <option value="prif">Prifddinas Crystal (Dark Blue)</option>
                <option value="light">GE Parchment (Light)</option>
              </select>
            </label>
            <label>
              <span>Default chart range</span>
              <select
                value={settings.default_chart_range}
                onChange={(e) => update({ default_chart_range: e.target.value })}
              >
                {["1h", "6h", "24h", "7d", "14d", "30d", "90d", "6m", "1y"].map((r) => (
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
                <option value="true">Enabled (Hover on items)</option>
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
              <span>Discord Webhook URL <em>(optional — sends price alerts &amp; 4h GE limit resets to Discord)</em></span>
              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  style={{ flex: 1 }}
                  placeholder="https://discord.com/api/webhooks/..."
                  value={settings.discord_webhook_url ?? ""}
                  onChange={(e) => update({ discord_webhook_url: e.target.value })}
                />
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={handleTestWebhook}
                  disabled={testingWebhook || !settings.discord_webhook_url}
                >
                  {testingWebhook ? "Testing…" : "Test Webhook"}
                </button>
              </div>
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

            <div className="full" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", padding: "8px 0", borderTop: "1px solid var(--card-border)" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: "13px" }}>Workspace Backup &amp; Restore</div>
                <div className="muted" style={{ fontSize: "11.5px" }}>
                  Export or restore your watchlist, groups, portfolio, flip history, 8 GE slots, recipes &amp; alerts
                </div>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <button type="button" className="btn btn-ghost" onClick={handleExportWorkspace}>
                  Export Backup ⭳
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Import Backup ⭱
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json,application/json"
                  style={{ display: "none" }}
                  onChange={handleImportWorkspaceFile}
                />
              </div>
            </div>

            <div className="full" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", padding: "8px 0", borderTop: "1px solid var(--card-border)" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: "13px" }}>Application Version: v1.3.0</div>
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
