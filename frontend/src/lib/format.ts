// Small display helpers for log text and timestamps.

const ANSI_PATTERN = /\x1B\[[0-9;]*m/g;

export function stripAnsi(text: string): string {
  return String(text ?? "").replace(ANSI_PATTERN, "");
}

export function normalizeText(text: string): string {
  return stripAnsi(text).replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

/** Render an ISO timestamp as a short local clock like `14:03:12`. */
export function formatClock(iso?: string): string {
  if (!iso) return new Date().toLocaleTimeString([], { hour12: false });
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleTimeString([], { hour12: false });
}

/** Render an elapsed millisecond span as `m:ss` (or `h:mm:ss`). */
export function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  if (h > 0) return `${h}:${pad(m)}:${pad(s)}`;
  return `${m}:${pad(s)}`;
}

export function formatCost(usd: number): string {
  if (!usd || usd <= 0) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}
