import { useEffect, useMemo, useRef, useState } from "react";
import { formatClock } from "../lib/format";
import type { LogItem, LogSource } from "../lib/types";

type Filter = "all" | LogSource | "errors";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "planner", label: "Planner" },
  { key: "executor", label: "Executor" },
  { key: "system", label: "System" },
  { key: "errors", label: "Errors" },
];

const SOURCE_TAG: Record<LogSource, string> = {
  planner: "text-sky-600 dark:text-sky-400",
  executor: "text-emerald-600 dark:text-emerald-400",
  system: "text-slate-400 dark:text-slate-500",
};

function matches(item: LogItem, filter: Filter): boolean {
  if (filter === "all") return true;
  if (filter === "errors") return item.type === "error" || item.type === "stderr";
  return item.source === filter;
}

interface LogPanelProps {
  logs: LogItem[];
  defaultOpen?: boolean;
  onClear: () => void;
}

export function LogPanel({ logs, defaultOpen = false, onClear }: LogPanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [filter, setFilter] = useState<Filter>("all");
  const bodyRef = useRef<HTMLDivElement>(null);
  const pinnedToBottom = useRef(true);

  const filtered = useMemo(() => logs.filter((l) => matches(l, filter)), [logs, filter]);

  // Keep the view pinned to the newest line unless the user scrolls up.
  useEffect(() => {
    const el = bodyRef.current;
    if (!el || !open) return;
    if (pinnedToBottom.current) el.scrollTop = el.scrollHeight;
  }, [filtered, open]);

  function onScroll() {
    const el = bodyRef.current;
    if (!el) return;
    pinnedToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2 px-4 py-3">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200"
        >
          <svg
            viewBox="0 0 20 20"
            className={`h-4 w-4 text-slate-400 transition-transform ${open ? "rotate-90" : ""}`}
            fill="currentColor"
          >
            <path d="M7 5l6 5-6 5V5z" />
          </svg>
          Live logs
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            {logs.length}
          </span>
        </button>

        {open && (
          <button
            type="button"
            onClick={onClear}
            className="text-xs font-medium text-slate-400 transition hover:text-slate-600 dark:hover:text-slate-300"
          >
            Clear
          </button>
        )}
      </div>

      {open && (
        <div className="border-t border-slate-100 dark:border-slate-800">
          <div className="flex flex-wrap gap-1.5 px-4 py-2.5">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilter(f.key)}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition ${
                  filter === f.key
                    ? "bg-teal-600 text-white"
                    : "bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div
            ref={bodyRef}
            onScroll={onScroll}
            className="max-h-96 overflow-y-auto px-4 pb-4 font-mono text-xs leading-relaxed"
          >
            {filtered.length === 0 ? (
              <p className="py-6 text-center text-slate-400">No log lines yet.</p>
            ) : (
              filtered.map((item) => (
                <div
                  key={item.id}
                  className={`whitespace-pre-wrap break-words border-b border-slate-50 py-1 dark:border-slate-800/50 ${
                    item.type === "error" ? "text-rose-600 dark:text-rose-400" : "text-slate-700 dark:text-slate-300"
                  }`}
                >
                  <span className="mr-2 text-slate-400 dark:text-slate-600">
                    {formatClock(item.ts)}
                  </span>
                  <span className={`mr-2 font-semibold uppercase ${SOURCE_TAG[item.source]}`}>
                    {item.source.slice(0, 4)}
                  </span>
                  {item.content}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </section>
  );
}
