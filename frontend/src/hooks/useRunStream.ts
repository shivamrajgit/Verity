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
  | { kind: "load-mock-start" }
  | { kind: "load-mock-progress"; statusLine: string; logItem: LogItem }
  | { kind: "load-mock-done"; summary: Summary; reports: PlannerReport[]; reportMarkdown: string; logItems: LogItem[] }
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
    case "load-mock-start":
      return {
        ...initialState,
        phase: "running",
        target: "https://demo.verity.qa",
        headless: true,
        statusLine: "Initializing planner node with screenshot...",
        startedAt: Date.now(),
        logs: [
          { id: 1, source: "system", type: "status", content: "Starting Verity pipeline runner...", ts: new Date().toISOString() },
        ],
      };
    case "load-mock-progress":
      return {
        ...state,
        statusLine: action.statusLine,
        logs: [...state.logs, action.logItem],
      };
    case "load-mock-done":
      return {
        ...state,
        phase: "done",
        statusLine: "Demo run completed successfully.",
        finishedAt: Date.now(),
        summary: action.summary,
        logs: [...state.logs, ...action.logItems],
        reports: action.reports,
        reportMarkdown: action.reportMarkdown,
      };
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
    async (url: string, instructions: string) => {
      closeStream();
      dispatch({ kind: "start", target: url });

      try {
        await api.authenticate();
      } catch (error) {
        dispatch({
          kind: "stream-error",
          message: error instanceof Error ? error.message : "API authentication failed.",
        });
        return;
      }

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

  const loadMockData = useCallback(() => {
    dispatch({ kind: "load-mock-start" });

    setTimeout(() => {
      dispatch({
        kind: "load-mock-progress",
        statusLine: "Planning: scanned 2 pages; generated 5 browser test actions...",
        logItem: { id: 2, source: "planner", type: "status", content: "Scanned pages: / and /dashboard", ts: new Date().toISOString() },
      });
    }, 2000);

    setTimeout(() => {
      dispatch({
        kind: "load-mock-progress",
        statusLine: "Executor: running browser assertions on /dashboard...",
        logItem: { id: 3, source: "executor", type: "status", content: "Executing test assertion: authenticate valid credentials", ts: new Date().toISOString() },
      });
    }, 4500);

    setTimeout(() => {
      const summary = {
        total: 5,
        pass: 3,
        fail: 1,
        error: 1,
        skip: 0,
        cost: 0.082,
      };
      const reports = [
        {
          depth: 1,
          url: "https://demo.verity.qa",
          page_summary: "Main landing page containing user auth, call-to-actions, and main menu navigation.",
          results: [
            {
              test_name: "Verify landing page title contains 'Verity'",
              status: "pass" as const,
              duration_seconds: 3.4,
              cost_usd: 0.008,
              evidence: "Title check returned 'Verity | Simplistic QA Runner'",
              error_detail: "",
              steps_executed: ["Launch browser and navigate to homepage", "Extract document.title", "Assert title contains 'Verity'"],
            },
            {
              test_name: "Verify responsiveness of main navigation bar",
              status: "pass" as const,
              duration_seconds: 4.1,
              cost_usd: 0.012,
              evidence: "Elements flex properly; hamburger menu visible at < 768px viewport",
              error_detail: "",
              steps_executed: ["Set window size to 375x812", "Locate selector `#nav-hamburger`", "Assert visible"],
            },
            {
              test_name: "Attempt checkout with invalid credit card",
              status: "fail" as const,
              duration_seconds: 9.8,
              cost_usd: 0.024,
              evidence: "Validation error alert element was not displayed in DOM",
              error_detail: "AssertionError: Expected error message to be visible",
              steps_executed: ["Navigate to /checkout", "Fill fake credit card fields", "Click submit button", "Wait 3000ms for error element"],
            },
          ],
        },
        {
          depth: 2,
          url: "https://demo.verity.qa/dashboard",
          page_summary: "Dynamic authenticated user dashboard and metrics workspace.",
          results: [
            {
              test_name: "Authenticate with valid demo user credentials",
              status: "pass" as const,
              duration_seconds: 6.2,
              cost_usd: 0.015,
              evidence: "Successfully logged in, user token set in localStorage",
              error_detail: "",
              steps_executed: ["Navigate to /login", "Input email 'demo@verity.qa'", "Input password '******'", "Click submit", "Assert URL is /dashboard"],
            },
            {
              test_name: "Load dynamic product detail modal dialog",
              status: "error" as const,
              duration_seconds: 8.5,
              cost_usd: 0.023,
              evidence: "Element `#product-dialog` missing from dynamic DOM updates",
              error_detail: "TimeoutError: waiting for selector `#product-dialog` failed: timeout 5000ms exceeded",
              steps_executed: ["Click on first product grid item", "Wait for dynamic modal selector"],
            },
          ],
        },
      ];
      const reportMarkdown = "# Verity QA Test Report - Demo\n\n**Target Website:** https://demo.verity.qa  \n**Status:** Done  \n**Cost:** $0.082 USD  \n\n## Summary of Findings\nDuring this automated QA run, we scanned **2 pages** at depths up to **2**. We executed **5 unique test plan assertions**:\n\n* **Passes:** 3/5  \n* **Failures:** 1/5  \n* **Errors:** 1/5  \n\n### Critical Failures & Errors\n1. **Attempt checkout with invalid credit card (Failed)**\n   * The application allows form submission with invalid cards and fails to display a validation alert.\n2. **Load dynamic product detail modal dialog (Error)**\n   * Clicking on a product grid item throws a timeout error waiting for the modal element, suggesting a JavaScript render regression.\n\n## Recommendations\n- Implement validation on frontend forms for credit card fields prior to API submit.\n- Investigate JavaScript console errors inside `/dashboard` preventing the modal from mounting.";
      const logItems = [
        { id: 4, source: "executor" as const, type: "status", content: "Dispatched 5 browser test assertions", ts: new Date().toISOString() },
        { id: 5, source: "system" as const, type: "status", content: "Compiling summaries and report...", ts: new Date().toISOString() },
      ];
      dispatch({
        kind: "load-mock-done",
        summary,
        reports,
        reportMarkdown,
        logItems,
      });
    }, 7000);
  }, []);

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
      loadMockData,
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
      loadMockData,
    ],
  );

  const isBusy = state.phase === "connecting" || state.phase === "running" ||
    state.phase === "awaiting_input";

  return { state, actions, isBusy };
}
