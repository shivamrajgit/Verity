import { STATUS_META } from "../lib/status";
import type { TestStatus } from "../lib/types";

export function StatusBadge({ status }: { status: TestStatus }) {
  const meta = STATUS_META[status] ?? STATUS_META.skip;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${meta.badge}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}
