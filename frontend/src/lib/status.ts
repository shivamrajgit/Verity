import type { TestStatus } from "./types";

// Central place for per-status colors so tiles, badges, and rows stay in sync.
interface StatusMeta {
  label: string;
  dot: string;
  badge: string;
  accent: string;
}

export const STATUS_META: Record<TestStatus, StatusMeta> = {
  pass: {
    label: "Pass",
    dot: "bg-emerald-500",
    badge:
      "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-400/20",
    accent: "text-emerald-600 dark:text-emerald-400",
  },
  fail: {
    label: "Fail",
    dot: "bg-rose-500",
    badge:
      "bg-rose-50 text-rose-700 ring-rose-600/20 dark:bg-rose-500/10 dark:text-rose-400 dark:ring-rose-400/20",
    accent: "text-rose-600 dark:text-rose-400",
  },
  error: {
    label: "Error",
    dot: "bg-amber-500",
    badge:
      "bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-400 dark:ring-amber-400/20",
    accent: "text-amber-600 dark:text-amber-400",
  },
  skip: {
    label: "Skip",
    dot: "bg-slate-400",
    badge:
      "bg-slate-100 text-slate-600 ring-slate-500/20 dark:bg-slate-500/10 dark:text-slate-400 dark:ring-slate-400/20",
    accent: "text-slate-500 dark:text-slate-400",
  },
};
