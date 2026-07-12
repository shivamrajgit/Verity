import { useMemo, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { StatusBadge } from "./StatusBadge";
import { STATUS_META } from "../lib/status";
import { formatCost, formatDuration } from "../lib/format";
import type { ExecutorResult, PlannerReport, TestStatus } from "../lib/types";

type Filter = "all" | TestStatus;

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "pass", label: "Pass" },
  { key: "fail", label: "Fail" },
  { key: "error", label: "Error" },
  { key: "skip", label: "Skip" },
];

function ResultRow({ result }: { result: ExecutorResult }) {
  const [open, setOpen] = useState(false);
  const hasDetail =
    result.evidence || result.error_detail || (result.steps_executed?.length ?? 0) > 0;

  return (
    <div className="border-b border-slate-100 last:border-0 dark:border-slate-800">
      <button
        type="button"
        onClick={() => hasDetail && setOpen((o) => !o)}
        className={`flex w-full items-center gap-3 px-4 py-3 text-left ${hasDetail ? "cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40" : "cursor-default"}`}
      >
        {hasDetail ? (
          <svg
            viewBox="0 0 20 20"
            className={`h-4 w-4 shrink-0 text-slate-300 transition-transform dark:text-slate-600 ${open ? "rotate-90" : ""}`}
            fill="currentColor"
          >
            <path d="M7 5l6 5-6 5V5z" />
          </svg>
        ) : (
          <span className="w-4 shrink-0" />
        )}

        <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800 dark:text-slate-200">
          {result.test_name}
        </span>

        <span className="hidden shrink-0 text-xs tabular-nums text-slate-400 sm:inline">
          {formatDuration(result.duration_seconds)}
        </span>
        {result.cost_usd > 0 && (
          <span className="hidden shrink-0 text-xs tabular-nums text-slate-400 sm:inline">
            {formatCost(result.cost_usd)}
          </span>
        )}
        <StatusBadge status={result.status} />
      </button>

      <AnimatePresence initial={false}>
        {open && hasDetail && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="space-y-3 bg-slate-50 px-4 py-3 pl-11 text-sm dark:bg-slate-950/40">
              {result.evidence && (
                <Detail label="Evidence">{result.evidence}</Detail>
              )}
              {result.error_detail && (
                <Detail label="Error">
                  <span className="text-rose-600 dark:text-rose-400">{result.error_detail}</span>
                </Detail>
              )}
              {result.steps_executed?.length > 0 && (
                <Detail label="Steps executed">
                  <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-slate-600 dark:text-slate-400">
                    {result.steps_executed.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ol>
                </Detail>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-0.5 whitespace-pre-wrap break-words text-slate-700 dark:text-slate-300">
        {children}
      </div>
    </div>
  );
}

function PageCard({ report, filter }: { report: PlannerReport; filter: Filter }) {
  const results = report.results.filter((r) => filter === "all" || r.status === filter);
  if (results.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            depth {report.depth}
          </span>
          <a
            href={report.url}
            target="_blank"
            rel="noreferrer"
            className="min-w-0 truncate text-sm font-medium text-teal-700 hover:underline dark:text-teal-400"
          >
            {report.url}
          </a>
        </div>
        {report.page_summary && (
          <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">{report.page_summary}</p>
        )}
      </div>
      <div>
        {results.map((r, i) => (
          <ResultRow key={`${r.test_name}-${i}`} result={r} />
        ))}
      </div>
    </div>
  );
}

export function Results({ reports }: { reports: PlannerReport[] }) {
  const [filter, setFilter] = useState<Filter>("all");

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: 0, pass: 0, fail: 0, error: 0, skip: 0 };
    for (const report of reports) {
      for (const r of report.results) {
        c.all += 1;
        c[r.status] = (c[r.status] ?? 0) + 1;
      }
    }
    return c;
  }, [reports]);

  if (reports.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Results</h2>
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className={`rounded-full px-2.5 py-1 text-xs font-medium transition ${
                filter === f.key
                  ? f.key === "all"
                    ? "bg-teal-600 text-white"
                    : `${STATUS_META[f.key as TestStatus].badge} ring-1 ring-inset`
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700"
              }`}
            >
              {f.label} {counts[f.key] ?? 0}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        {reports.map((report, i) => (
          <PageCard key={`${report.url}-${i}`} report={report} filter={filter} />
        ))}
      </div>
    </section>
  );
}
