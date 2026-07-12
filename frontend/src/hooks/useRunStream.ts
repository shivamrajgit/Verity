import { useCallback, useMemo, useReducer, useRef } from "react";
import { api, buildRunUrl } from "../lib/api";
import { classifySource } from "../lib/classify";
import { normalizeText } from "../lib/format";
import type {
  LogItem,
  PendingInterrupt,
  PlannerReport,
  RunPhase,
  SseEvent,
  Summary,
} from "../lib/types";

interface RunState {
  phase: RunPhase;
  runId: string | null;
  target: string;
  headless: boolean | null;
  statusLine: string;
  logs: LogItem[];
  reports: PlannerReport[];
  summary: Summary | null;
  reportMarkdown: string;
  pendingInterrupt: PendingInterrupt | null;
  errorMessage: string | null;
  startedAt: number | null;
  finishedAt: number | null;
}

const initialState: RunState = {
  phase: "idle",
  runId: null,
  target: "",
  headless: null,
  statusLine: "Ready.",
  logs: [],
  reports: [],
  summary: null,
  reportMarkdown: "",
  pendingInterrupt: null,
  errorMessage: null,
  startedAt: null,
  finishedAt: null,
};

let logSeq = 0;

type Action =
  | { kind: "start"; target: string }
  | { kind: "connected" }
  | { kind: "event"; event: SseEvent }
  | { kind: "stream-error"; message: string }
  | { kind: "clear-logs" }
  | { kind: "answered" }
  | { kind: "headless"; value: boolean }
  | { kind: "reset" };

function summarize(reports: PlannerReport[]): Summary {
  const summary: Summary = { pass: 0, fail: 0, error: 0, skip: 0, cost: 0, total: 0 };
  for (const report of reports) {
    for (const r of report.results ?? []) {
      summary.total += 1;
      summary.cost += Number(r.cost_usd) || 0;
      if (r.status === "pass") summary.pass += 1;
      else if (r.status === "fail") summary.fail += 1;
      else if (r.status === "error") summary.error += 1;
      else if (r.status === "skip") summary.skip += 1;
    }
  }
  return summary;
}

function appendLog(state: RunState, event: SseEvent): LogItem[] {
  const content = normalizeText(event.content);
  if (!content.trim()) return state.logs;
  const item: LogItem = {
    id: ++logSeq,
    source: classifySource(event.type, content),
    type: event.type,
    content,
    ts: event.timestamp,
  };
  // Keep memory bounded on long runs.
  const next = [...state.logs, item];
  return next.length > 2000 ? next.slice(next.length - 2000) : next;
}

function reduceEvent(state: RunState, event: SseEvent): RunState {
  let next: RunState = state;

  // Any event may carry an updated headless flag.
  if (typeof event.headless === "boolean") {
    next = { ...next, headless: event.headless };
  }

  switch (event.type) {
    case "heartbeat":
      return next;

    case "run":
      return { ...next, runId: event.run_id ?? next.runId, phase: "running" };

    case "status":
      return { ...next, statusLine: event.content, logs: appendLog(next, event) };

    case "interrupt":
      return {
        ...next,
        phase: "awaiting_input",
        pendingInterrupt: {
          question: event.question ?? event.content,
          url: event.url ?? "",
        },
        statusLine: "Planner is waiting for your input.",
        logs: appendLog(next, event),
      };

    case "error":
      return {
        ...next,
        errorMessage: event.content,
        logs: appendLog(next, event),
      };

    case "results": {
      const reports = event.reports ?? [];
      return { ...next, reports, summary: summarize(reports), logs: appendLog(next, event) };
    }

    case "report":
      return { ...next, reportMarkdown: event.content };

    case "summary":
      // Prefer summary computed from full reports; only use this if none yet.
      if (next.summary) return { ...next, logs: appendLog(next, event) };
      return {
        ...next,
        summary: {
          pass: event.pass_count ?? 0,
          fail: event.fail_count ?? 0,
          error: event.error_count ?? 0,
          skip: 0,
          cost: 0,
          total: (event.pass_count ?? 0) + (event.fail_count ?? 0) + (event.error_count ?? 0),
        },
        logs: appendLog(next, event),
      };

    case "done":
      return {
        ...next,
        phase: "done",
        statusLine: "Run complete.",
        pendingInterrupt: null,
        finishedAt: Date.now(),
      };

    default:
      return { ...next, logs: appendLog(next, event) };
  }
}

function reducer(state: RunState, action: Action): RunState {
  switch (action.kind) {
    case "start":
      return {
        ...initialState,
        phase: "connecting",
        target: action.target,
        statusLine: "Connecting…",
        startedAt: Date.now(),
      };
    case "connected":
      return state.phase === "connecting"
        ? { ...state, phase: "running", statusLine: "Connected. Running pipeline…" }
        : state;
    case "event":
      return reduceEvent(state, action.event);
    case "stream-error":
      return {
        ...state,
        phase: "error",
        errorMessage: action.message,
        statusLine: "Disconnected.",
        finishedAt: state.finishedAt ?? Date.now(),
      };
    case "clear-logs":
      return { ...state, logs: [] };
    case "answered":
      return { ...state, pendingInterrupt: null, phase: "running" };
    case "headless":
      return { ...state, headless: action.value };
    case "reset":
      return initialState;
    default:
      return state;
  }
}

export function useRunStream() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const sourceRef = useRef<EventSource | null>(null);
  const runIdRef = useRef<string | null>(null);
  runIdRef.current = state.runId;

  const closeStream = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  const startRun = useCallback(
    (url: string, instructions: string) => {
      closeStream();
      dispatch({ kind: "start", target: url });

      const source = new EventSource(buildRunUrl(url, instructions));
      sourceRef.current = source;

      source.onopen = () => dispatch({ kind: "connected" });

      source.onmessage = (ev) => {
        try {
          const event = JSON.parse(ev.data) as SseEvent;
          dispatch({ kind: "event", event });
          if (event.type === "done") closeStream();
        } catch {
          /* ignore malformed frames */
        }
      };

      source.onerror = () => {
        // The browser auto-reconnects while CONNECTING; only treat a closed
        // stream as fatal.
        if (!sourceRef.current) return;
        if (source.readyState === EventSource.CONNECTING) return;
        dispatch({ kind: "stream-error", message: "SSE stream closed unexpectedly." });
        closeStream();
      };
    },
    [closeStream],
  );

  // Real cancel: closes the stream AND tells the backend to abort the run.
  const stopRun = useCallback(async () => {
    const runId = runIdRef.current;
    closeStream();
    if (runId) {
      try {
        await api.cancel(runId);
      } catch {
        /* backend may have already finished */
      }
    }
    dispatch({ kind: "stream-error", message: "" });
  }, [closeStream]);

  const submitClarification = useCallback(async (answer: string) => {
    const runId = runIdRef.current;
    if (!runId) throw new Error("No active run.");
    await api.respond(runId, answer);
    dispatch({ kind: "answered" });
  }, []);

  const setHeadless = useCallback(async (headless: boolean) => {
    const runId = runIdRef.current;
    if (!runId) throw new Error("No active run.");
    const res = await api.setHeadless(runId, headless);
    dispatch({ kind: "headless", value: res.headless_after });
  }, []);

  const captchaStart = useCallback(async () => {
    const runId = runIdRef.current;
    if (!runId) throw new Error("No active run.");
    const res = await api.captchaStart(runId);
    dispatch({ kind: "headless", value: res.headless_after });
  }, []);

  const captchaSolved = useCallback(async () => {
    const runId = runIdRef.current;
    if (!runId) throw new Error("No active run.");
    const res = await api.captchaSolved(runId);
    dispatch({ kind: "headless", value: res.headless_after });
  }, []);

  const clearLogs = useCallback(() => dispatch({ kind: "clear-logs" }), []);
  const reset = useCallback(() => {
    closeStream();
    dispatch({ kind: "reset" });
  }, [closeStream]);

  const actions = useMemo(
    () => ({
      startRun,
      stopRun,
      submitClarification,
      setHeadless,
      captchaStart,
      captchaSolved,
      clearLogs,
      reset,
    }),
    [
      startRun,
      stopRun,
      submitClarification,
      setHeadless,
      captchaStart,
      captchaSolved,
      clearLogs,
      reset,
    ],
  );

  const isBusy = state.phase === "connecting" || state.phase === "running" ||
    state.phase === "awaiting_input";

  return { state, actions, isBusy };
}
