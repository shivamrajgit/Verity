import { motion } from "framer-motion";
import { Controls } from "./Controls";
import { ClarificationPrompt } from "./ClarificationPrompt";
import { LogPanel } from "./LogPanel";
import { Results } from "./Results";
import { ReportView } from "./ReportView";
import { SummaryTiles } from "./SummaryTiles";
import { useElapsed } from "../hooks/useElapsed";
import { formatElapsed } from "../lib/format";
import type { useRunStream } from "../hooks/useRunStream";

type Stream = ReturnType<typeof useRunStream>;

interface RunViewProps {
  stream: Stream;
  onNewRun: () => void;
}

export function RunView({ stream, onNewRun }: RunViewProps) {
  const { state, actions, isBusy } = stream;
  const elapsed = useElapsed(state.startedAt, state.finishedAt, isBusy);
  const canControl = Boolean(state.runId && isBusy);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-4"
    >
      {/* Run header */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <span className="truncate font-medium text-slate-900 dark:text-slate-100">
                {state.target}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
              {state.runId && <span className="font-mono">run {state.runId.slice(0, 8)}</span>}
              <span className="tabular-nums">{formatElapsed(elapsed)}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!isBusy && (
              <button
                type="button"
                onClick={onNewRun}
                className="rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-teal-700"
              >
                New run
              </button>
            )}
          </div>
        </div>

        <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-600 dark:border-slate-800 dark:text-slate-300">
          {state.statusLine}
        </p>

        {isBusy && (
          <div className="mt-3">
            <Controls
              headless={state.headless}
              canControl={canControl}
              onStop={actions.stopRun}
              onToggleHeadless={() => actions.setHeadless(!state.headless)}
              onCaptchaStart={actions.captchaStart}
              onCaptchaSolved={actions.captchaSolved}
            />
          </div>
        )}
      </div>

      {state.errorMessage && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
          {state.errorMessage}
        </div>
      )}

      <ClarificationPrompt interrupt={state.pendingInterrupt} onSubmit={actions.submitClarification} />

      {state.summary && <SummaryTiles summary={state.summary} />}

      <LogPanel logs={state.logs} defaultOpen={false} onClear={actions.clearLogs} />

      <Results reports={state.reports} />

      <ReportView markdown={state.reportMarkdown} runId={state.runId} />
    </motion.div>
  );
}
