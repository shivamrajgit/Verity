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
    <div className="flex flex-col min-h-screen bg-slate-50 text-slate-900 dark:bg-bg-dark dark:text-stone-100">
      <div className={`mx-auto flex flex-1 w-full flex-col px-4 py-6 sm:px-6 sm:py-8 transition-all duration-300 ${isIdle ? "max-w-3xl" : "max-w-[1400px]"}`}>
        <Header phase={stream.state.phase} theme={theme} onToggleTheme={toggle} />

        <main className={`flex-1 ${isIdle ? "flex items-center justify-center py-10" : "mt-6"}`}>
          {isIdle ? (
            <RunForm busy={stream.isBusy} onRun={stream.actions.startRun} onLoadMockData={stream.actions.loadMockData} />
          ) : (
            <RunView stream={stream} onNewRun={stream.actions.reset} />
          )}
        </main>

        <footer className="mt-8 border-t border-stone-100 pt-6 text-center text-xs text-stone-400 dark:border-border-dark flex items-center justify-center gap-1 select-none">
          <span><strong className="font-bold text-stone-500 dark:text-stone-300">verity</strong> · made with love</span>
          <svg
            viewBox="0 0 24 24"
            fill="currentColor"
            className="h-3.5 w-3.5 text-rose-500 animate-pulse"
            aria-hidden="true"
          >
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
          </svg>
        </footer>
      </div>
    </div>
  );
}
