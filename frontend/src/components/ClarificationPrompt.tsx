import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { PendingInterrupt } from "../lib/types";

interface ClarificationPromptProps {
  interrupt: PendingInterrupt | null;
  onSubmit: (answer: string) => Promise<void>;
}

export function ClarificationPrompt({ interrupt, onSubmit }: ClarificationPromptProps) {
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function send() {
    setSubmitting(true);
    try {
      await onSubmit(answer);
      setAnswer("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AnimatePresence>
      {interrupt && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="overflow-hidden"
        >
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-500/30 dark:bg-amber-500/10">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
              Planner needs input
            </p>
            <p className="mt-1 text-sm text-amber-900 dark:text-amber-200">
              {interrupt.question || "The planner is asking for more detail."}
              {interrupt.url && (
                <span className="text-amber-700/70 dark:text-amber-300/60"> · {interrupt.url}</span>
              )}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <input
                type="text"
                value={answer}
                autoFocus
                placeholder="Answer for the planner…"
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !submitting && send()}
                className="min-w-0 flex-1 rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500 dark:border-amber-500/30 dark:bg-bg-dark dark:text-stone-100"
              />
              <button
                type="button"
                disabled={submitting}
                onClick={send}
                className="rounded-lg bg-[#3e3a37] px-4 py-2 text-sm font-semibold text-white transition hover:bg-stone-850 dark:bg-stone-100 dark:text-stone-950 dark:hover:bg-stone-200 disabled:opacity-60"
              >
                {submitting ? "Sending…" : "Send answer"}
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
