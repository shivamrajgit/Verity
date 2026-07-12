import { formatCost } from "../lib/format";
import type { Summary } from "../lib/types";

interface TileProps {
  label: string;
  value: string | number;
  accent?: string;
}

function Tile({ label, value, accent }: TileProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-800 dark:bg-slate-900">
      <div className={`text-xl font-semibold tabular-nums ${accent ?? "text-slate-900 dark:text-slate-100"}`}>
        {value}
      </div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
    </div>
  );
}

export function SummaryTiles({ summary }: { summary: Summary }) {
  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
      <Tile label="Total" value={summary.total} />
      <Tile label="Pass" value={summary.pass} accent="text-emerald-600 dark:text-emerald-400" />
      <Tile label="Fail" value={summary.fail} accent="text-rose-600 dark:text-rose-400" />
      <Tile label="Error" value={summary.error} accent="text-amber-600 dark:text-amber-400" />
      <Tile label="Skip" value={summary.skip} accent="text-slate-500 dark:text-slate-400" />
      <Tile label="Cost" value={formatCost(summary.cost)} />
    </div>
  );
}
