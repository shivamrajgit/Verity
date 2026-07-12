import { Header } from "./components/Header";
import { RunForm } from "./components/RunForm";
import { RunView } from "./components/RunView";
import { useRunStream } from "./hooks/useRunStream";
import { useTheme } from "./hooks/useTheme";

export default function App() {
  const { theme, toggle } = useTheme();
  const stream = useRunStream();
  const isIdle = stream.state.phase === "idle";

  return (
    <div className="min-h-full bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col px-4 py-6 sm:px-6 sm:py-8">
        <Header phase={stream.state.phase} theme={theme} onToggleTheme={toggle} />

        <main className={isIdle ? "flex flex-1 items-center justify-center py-10" : "mt-6"}>
          {isIdle ? (
            <RunForm busy={stream.isBusy} onRun={stream.actions.startRun} />
          ) : (
            <RunView stream={stream} onNewRun={stream.actions.reset} />
          )}
        </main>

        <footer className="mt-8 border-t border-slate-100 pt-4 text-center text-xs text-slate-400 dark:border-slate-800">
          Verity · autonomous website QA
        </footer>
      </div>
    </div>
  );
}
