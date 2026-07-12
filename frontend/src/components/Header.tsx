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
      <div className="flex items-center pl-1.5">
        <h1 className="font-mono text-2xl font-bold tracking-wider text-slate-900 dark:text-stone-100">verity_</h1>
      </div>

      <div className="flex items-center gap-4">
        <span className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-stone-400">
          <span className={`h-2 w-2 rounded-full ${PHASE_DOT[phase]}`} />
          {PHASE_LABEL[phase]}
        </span>

        <button
          type="button"
          onClick={onToggleTheme}
          aria-label="Toggle color theme"
          className="flex h-8 w-8 items-center justify-center text-slate-400 transition hover:text-slate-600 dark:text-stone-400 dark:hover:text-stone-200"
        >
          {theme === "dark" ? (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
            >
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2" />
              <path d="M12 20v2" />
              <path d="m4.93 4.93 1.41 1.41" />
              <path d="m17.66 17.66 1.41 1.41" />
              <path d="M2 12h2" />
              <path d="M20 12h2" />
              <path d="m6.34 17.66-1.41 1.41" />
              <path d="m19.07 4.93-1.41 1.41" />
            </svg>
          ) : (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
            >
              <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
            </svg>
          )}
        </button>
      </div>
    </header>
  );
}
