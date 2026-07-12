import { useEffect, useState } from "react";

/**
 * Elapsed milliseconds between `startedAt` and now (or `finishedAt` once set).
 * Ticks while `running` is true so the run header shows a live timer.
 */
export function useElapsed(
  startedAt: number | null,
  finishedAt: number | null,
  running: boolean,
): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, [running]);

  if (startedAt == null) return 0;
  const end = finishedAt ?? (running ? now : startedAt);
  return Math.max(0, end - startedAt);
}
