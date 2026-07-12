import { motion } from "framer-motion";
import { Controls } from "./Controls";
import { ClarificationPrompt } from "./ClarificationPrompt";
import { LogPanel } from "./LogPanel";
import { Results } from "./Results";
import { ReportView } from "./ReportView";
import { SummaryTiles } from "./SummaryTiles";
import { useElapsed } from "../hooks/useElapsed";
import type { useRunStream } from "../hooks/useRunStream";

type Stream = ReturnType<typeof useRunStream>;

interface RunViewProps {
  stream: Stream;
  onNewRun: () => void;
}

export function RunView({ stream, onNewRun }: RunViewProps) {
  const { state, actions, isBusy } = stream;
  const elapsed = useElapsed(state.startedAt, state.finishedAt, isBusy);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="grid grid-cols-1 wide:grid-cols-12 gap-6 items-start"
    >
      {/* Left Sidebar Column: Metadata, Controls, Summary & Logs */}
      <div className="wide:col-span-5 space-y-4 wide:sticky wide:top-6 flex flex-col wide:h-[calc(100vh-110px)]">
        {/* Run header */}
        <div className="rounded-2xl border border-stone-200 bg-white p-4 dark:border-border-dark dark:bg-card-dark shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-stone-400">
                <span className="truncate font-semibold text-slate-900 dark:text-stone-100">
                  {state.target}
                </span>
              </div>
              {state.runId && (
                <div className="mt-1 text-xs text-stone-400 font-mono">
                  run {state.runId.slice(0, 8)}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              {!isBusy && (
                <button
                  type="button"
                  onClick={onNewRun}
                  className="rounded-full bg-[#3e3a37] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-stone-850 dark:bg-stone-100 dark:text-stone-950 dark:hover:bg-stone-200"
                >
                  New run
                </button>
              )}
            </div>
          </div>

          <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-600 dark:border-border-dark dark:text-stone-300">
            {state.statusLine}
          </p>

          {isBusy && (
            <div className="mt-3">
              <Controls onStop={actions.stopRun} />
            </div>
          )}
        </div>

        <SummaryTiles cost={state.summary?.cost ?? 0} elapsedMs={elapsed} />

        <LogPanel logs={state.logs} defaultOpen={true} onClear={actions.clearLogs} className="flex-1 min-h-0" />
      </div>

      {/* Right Column: Execution results & Reports */}
      <div className="wide:col-span-7 space-y-4">
        {state.errorMessage && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
            {state.errorMessage}
          </div>
        )}

        <ClarificationPrompt interrupt={state.pendingInterrupt} onSubmit={actions.submitClarification} />

        {state.reports.length === 0 && isBusy && (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-stone-200 bg-white p-12 text-center dark:border-border-dark dark:bg-card-dark shadow-sm wide:h-[calc(100vh-110px)] min-h-[300px]">
            <div className="relative flex h-12 w-12 items-center justify-center">
              <div className="absolute h-10 w-10 animate-ping rounded-full bg-slate-200 dark:bg-stone-800 opacity-75" />
              <div className="h-4 w-4 rounded-full bg-[#3e3a37] dark:bg-stone-100" />
            </div>
            <p className="mt-6 text-xs text-slate-400 dark:text-stone-500 font-mono animate-pulse max-w-md break-words">
              {state.statusLine || "Waiting for pipeline..."}
            </p>
          </div>
        )}

        <Results reports={state.reports} />

        <ReportView markdown={state.reportMarkdown} runId={state.runId} />
      </div>
    </motion.div>
  );
}
