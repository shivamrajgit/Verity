// Domain + transport types shared across the app.
//
// These mirror the backend contracts:
//   - SSE events emitted by server.py `_sse_msg(...)`
//   - src/models/executor_result.py  -> ExecutorResult
//   - src/models/report.py           -> PlannerReport

export type TestStatus = "pass" | "fail" | "error" | "skip";

export interface ExecutorResult {
  test_name: string;
  status: TestStatus;
  evidence: string;
  error_detail: string | null;
  steps_executed: string[];
  duration_seconds: number;
  cost_usd: number;
}

export interface PlannerReport {
  url: string;
  depth: number;
  page_summary: string;
  results: ExecutorResult[];
}

/** Every SSE payload from the backend has at least these fields. */
export interface SseEvent {
  type:
    | "run"
    | "status"
    | "log"
    | "interrupt"
    | "error"
    | "results"
    | "report"
    | "summary"
    | "done"
    | "heartbeat";
  timestamp: string;
  content: string;
  // Optional extras attached to specific event types.
  run_id?: string;
  headless?: boolean;
  interrupt_type?: string;
  question?: string;
  url?: string;
  reports?: PlannerReport[];
  pass_count?: number;
  fail_count?: number;
  error_count?: number;
}

/** Which live-activity column a log line belongs to. */
export type LogSource = "planner" | "executor" | "system";

export interface LogItem {
  id: number;
  source: LogSource;
  type: string;
  content: string;
  ts: string;
}

export interface Summary {
  pass: number;
  fail: number;
  error: number;
  skip: number;
  cost: number;
  total: number;
}

export type RunPhase =
  | "idle"
  | "connecting"
  | "running"
  | "awaiting_input"
  | "done"
  | "error";

export interface PendingInterrupt {
  question: string;
  url: string;
}
