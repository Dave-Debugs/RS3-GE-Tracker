export function formatGP(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000)
    return trimZeros((value / 1_000_000_000).toFixed(2)) + "B";
  if (abs >= 10_000_000)
    return trimZeros((value / 1_000_000).toFixed(1)) + "M";
  if (abs >= 1_000_000)
    return trimZeros((value / 1_000_000).toFixed(2)) + "M";
  if (abs >= 100_000) return trimZeros((value / 1_000).toFixed(0)) + "K";
  return Math.round(value).toLocaleString("en-US");
}

function trimZeros(s: string): string {
  return s.replace(/\.0+$|(\.\d*?)0+$/, "$1");
}

/**
 * Parses RS3 shorthand GP or quantity strings like "250k", "12.5m", "1.2b", "5,000" into an integer.
 */
export function parseGPInput(raw: string | number | null | undefined): number | null {
  if (raw == null) return null;
  if (typeof raw === "number") return Number.isFinite(raw) ? Math.round(raw) : null;
  const cleaned = raw.trim().toLowerCase().replace(/[,_\s]/g, "").replace(/gp$/i, "");
  if (!cleaned) return null;
  const match = cleaned.match(/^(-?\d+(?:\.\d+)?)([kmb])?$/);
  if (!match) return null;
  const num = parseFloat(match[1]);
  if (Number.isNaN(num)) return null;
  const suffix = match[2];
  let mult = 1;
  if (suffix === "k") mult = 1_000;
  else if (suffix === "m") mult = 1_000_000;
  else if (suffix === "b") mult = 1_000_000_000;
  return Math.round(num * mult);
}

export function formatDurationSeconds(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return "Ready";
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hrs > 0) {
    return `${hrs}h ${String(mins).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
  }
  return `${mins}m ${String(secs).padStart(2, "0")}s`;
}

export function formatGPExact(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return Math.round(value).toLocaleString("en-US") + " gp";
}

export function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatVolume(value: number | null | undefined): string {
  if (value == null) return "—";
  return formatGP(value).replace(" gp", "");
}

export function formatTime(ts: number | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString();
}

export function formatDateTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(ts: number | null | undefined): string {
  if (!ts) return "—";
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 0) {
    const ahead = -diff;
    if (ahead < 90) return `in ${ahead}s`;
    if (ahead < 3600) return `in ${Math.round(ahead / 60)}m`;
    return `in ${Math.round(ahead / 3600)}h`;
  }
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

export function changeClass(value: number | null | undefined): string {
  if (value == null || Math.abs(value) < 0.005) return "neutral";
  return value > 0 ? "up" : "down";
}
