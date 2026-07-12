import { STATUS_META } from "../lib/status";
import type { TestStatus } from "../lib/types";

export function StatusBadge({ status }: { status: TestStatus }) {
  const meta = STATUS_META[status] ?? STATUS_META.skip;
  const isError = status === "error";
  return (
    <span
      className={`inline-flex items-center rounded-full py-0.5 font-semibold ring-1 ring-inset ${
        isError ? "text-[11px] px-2 gap-1" : "text-xs px-2.5 gap-1.5"
      } ${meta.badge}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${meta.dot}`} />
      {meta.label}
    </span>
  );
}
