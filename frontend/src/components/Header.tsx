import type { RunPhase } from "../lib/types";

const PHASE_LABEL: Record<RunPhase, string> = {
  idle: "Idle",
  connecting: "Connecting",
  running: "Running",
  awaiting_input: "Waiting",
  done: "Complete",
  error: "Error",
};

const PHASE_DOT: Record<RunPhase, string> = {
  idle: "bg-slate-400",
  connecting: "bg-amber-500 animate-pulse",
  running: "bg-emerald-500 animate-pulse",
  awaiting_input: "bg-amber-500 animate-pulse",
  done: "bg-emerald-500",
  error: "bg-rose-500",
};

interface HeaderProps {
  phase: RunPhase;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

export function Header({ phase, theme, onToggleTheme }: HeaderProps) {
  return (
    <header className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-600 text-white shadow-sm">
          <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden>
            <path
              d="M8 11l6 12 10-16"
              fill="none"
              stroke="currentColor"
              strokeWidth="3.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-50">
            Verity
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">Autonomous Web QA</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/60 px-3 py-1 text-xs font-medium text-slate-600 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300">
          <span className={`h-2 w-2 rounded-full ${PHASE_DOT[phase]}`} />
          {PHASE_LABEL[phase]}
        </span>

        <button
          type="button"
          onClick={onToggleTheme}
          aria-label="Toggle color theme"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          {theme === "dark" ? (
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
              <path d="M12 3a1 1 0 011 1v1a1 1 0 11-2 0V4a1 1 0 011-1zm0 15a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM4 12a1 1 0 01-1 1H2a1 1 0 110-2h1a1 1 0 011 1zm18 0a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM6.3 6.3a1 1 0 011.4 0l.7.7A1 1 0 117 8.4l-.7-.7a1 1 0 010-1.4zm10 10a1 1 0 011.4 0l.7.7a1 1 0 01-1.4 1.4l-.7-.7a1 1 0 010-1.4zM17.7 6.3a1 1 0 010 1.4l-.7.7A1 1 0 0115.6 7l.7-.7a1 1 0 011.4 0zM7.7 16.3a1 1 0 010 1.4l-.7.7a1 1 0 01-1.4-1.4l.7-.7a1 1 0 011.4 0zM12 8a4 4 0 100 8 4 4 0 000-8z" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
              <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
            </svg>
          )}
        </button>
      </div>
    </header>
  );
}
