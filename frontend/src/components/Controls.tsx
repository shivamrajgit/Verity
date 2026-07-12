import { useState } from "react";

interface ControlsProps {
  headless: boolean | null;
  canControl: boolean;
  onStop: () => void;
  onToggleHeadless: () => Promise<void>;
  onCaptchaStart: () => Promise<void>;
  onCaptchaSolved: () => Promise<void>;
}

const secondaryBtn =
  "rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800";

export function Controls({
  headless,
  canControl,
  onStop,
  onToggleHeadless,
  onCaptchaStart,
  onCaptchaSolved,
}: ControlsProps) {
  const [pending, setPending] = useState<string | null>(null);

  async function run(key: string, fn: () => Promise<void>) {
    setPending(key);
    try {
      await fn();
    } catch {
      /* surfaced via the error banner upstream if needed */
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={onStop}
        className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
      >
        Stop run
      </button>

      <button
        type="button"
        disabled={!canControl || pending !== null}
        onClick={() => run("headless", onToggleHeadless)}
        className={secondaryBtn}
      >
        {headless === null ? "Headless: —" : headless ? "Headless: on" : "Headless: off"}
      </button>

      <button
        type="button"
        disabled={!canControl || pending !== null}
        onClick={() => run("captcha-start", onCaptchaStart)}
        className={secondaryBtn}
        title="Show the browser so you can solve a captcha"
      >
        Show browser
      </button>

      <button
        type="button"
        disabled={!canControl || pending !== null}
        onClick={() => run("captcha-solved", onCaptchaSolved)}
        className={secondaryBtn}
        title="Restore the previous headless mode after solving"
      >
        Captcha solved
      </button>
    </div>
  );
}
