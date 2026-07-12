import { formatCost, formatElapsed } from "../lib/format";

interface SummaryTilesProps {
  cost: number;
  elapsedMs: number;
}

export function SummaryTiles({ cost, elapsedMs }: SummaryTilesProps) {
  return (
    <div className="grid grid-cols-2 divide-x divide-stone-100 rounded-2xl border border-stone-200 bg-white py-3 shadow-sm dark:divide-border-dark dark:border-border-dark dark:bg-card-dark">
      <div className="flex flex-col items-center justify-center text-center">
        <span className="text-xs font-medium uppercase tracking-wider text-stone-400">Run Cost</span>
        <span className="mt-1 text-lg font-bold tabular-nums text-stone-900 dark:text-stone-100">
          {formatCost(cost)}
        </span>
      </div>
      <div className="flex flex-col items-center justify-center text-center">
        <span className="text-xs font-medium uppercase tracking-wider text-stone-400">Duration</span>
        <span className="mt-1 text-lg font-bold tabular-nums text-stone-900 dark:text-stone-100">
          {formatElapsed(elapsedMs)}
        </span>
      </div>
    </div>
  );
}
